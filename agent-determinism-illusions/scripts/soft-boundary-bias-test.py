# -*- coding: utf-8 -*-
"""
软边界偏好实验 — Soft Boundary Bias Test

Claim（文章《AI 时代，别把“模块内无所谓”说满》）:
  无硬边界约束时，LLM 更常选择跨模块共享写 / 直接碰他模块表的方案；
  把数据所有权写进上下文后，软边界选择率应显著下降。

Method (mode=choice，默认):
  - 3 个跨模块需求，每个给出 A=软边界 / B=硬边界 两个具体方案
  - 3 种上下文：bare / speed（催最快） / hard（所有权规则）
  - 模型必须只输出一行：CHOICE: A 或 CHOICE: B
  - 指标 soft_rate = P(选 A)

Method (mode=open，附录):
  - 开放方案 + 启发式打分（易 ambiguous；仅作对照）

Dependencies:
  默认 Ollama。也可用 --backend anthropic|openai
  或 --cc-switch：从 ~/.cc-switch/cc-switch.db 读当前 Claude provider

Expected（claim 成立）:
  soft_rate(bare) 与 soft_rate(speed) 明显高于 soft_rate(hard)

Falsify:
  soft_rate(hard) 不低于 soft_rate(bare)（差值 < 10pp 或方向相反）

Usage:
  python soft-boundary-bias-test.py --model qwen2.5:7b --n 5
  python soft-boundary-bias-test.py --cc-switch --n 5 --temp 0.7
  python soft-boundary-bias-test.py --cc-switch --cc-provider "DeepSeek" --n 5
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)
CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"

MODULE_LAYOUT = """
系统里有独立模块（可各自部署）:
- orders: 表 orders(id, customer_id, amount, status)；目录 orders/
- customers: 表 customers(id, email, phone)；目录 customers/
  已有 API: GET /customers/{id} 、 PATCH /customers/{id}
- inventory: 表 inventory_items；目录 inventory/
- billing: 表 invoices；目录 billing/
""".strip()

# A = soft（共享写 / 直接碰他表）, B = hard（API / 事件）
CHOICE_SCENARIOS = [
    {
        "id": "S1_email",
        "task": "创建订单时要把客户邮箱快照存进订单，方便对账。",
        "option_a": (
            "A（软）: orders 服务里直接 SQL: "
            "INSERT INTO orders(..., email) SELECT ..., email FROM customers WHERE id=?"
        ),
        "option_b": (
            "B（硬）: orders 调用 GET /customers/{id} 取 email，再只写本模块 orders 表的 email 快照列"
        ),
    },
    {
        "id": "S2_ship",
        "task": "库存扣减成功后，要把对应订单状态改成 shipped。",
        "option_a": (
            "A（软）: inventory 服务里直接 SQL: UPDATE orders SET status='shipped' WHERE id=?"
        ),
        "option_b": (
            "B（硬）: inventory 发布 OrderReadyToShip 事件（或调 PATCH /orders/{id}），由 orders 自己改状态"
        ),
    },
    {
        "id": "S3_phone",
        "task": "billing 生成发票 PDF 时需要客户手机号。",
        "option_a": (
            "A（软）: billing 里直接 JOIN/SELECT customers.phone，或 import customers.models 读取"
        ),
        "option_b": (
            "B（硬）: billing 调用 GET /customers/{id} 取 phone，再生成 PDF；不碰 customers 表"
        ),
    },
]

CONDITIONS = {
    "bare": "",
    "speed": (
        "\n\n额外约束：线上故障，要求 10 分钟内上线；"
        "优先最少改动、最快能跑；不必考虑长期架构。"
    ),
    "hard": (
        "\n\n项目规则（必须遵守）:\n"
        "1. 每张表只有一个 owner，禁止其他模块直接 SQL/ORM 读写。\n"
        "2. customers / orders 表只能由本模块写入。\n"
        "3. 跨模块只能走公开 HTTP API 或领域事件。\n"
        "4. 违反规则的方案不可选。"
    ),
}


def build_choice_prompt(scenario: dict, condition: str) -> str:
    return (
        f"{MODULE_LAYOUT}\n\n"
        f"任务：{scenario['task']}\n\n"
        f"只允许从下面两个方案中选一个：\n"
        f"{scenario['option_a']}\n"
        f"{scenario['option_b']}\n"
        f"{CONDITIONS[condition]}\n\n"
        "只输出一行，格式严格为：\n"
        "CHOICE: A\n"
        "或\n"
        "CHOICE: B\n"
        "不要输出其他内容，不要输出思考过程。"
    )


def parse_choice(text: str) -> str:
    if not text or text.startswith("<ERROR"):
        return "?"
    m = re.search(r"CHOICE\s*:\s*([ABab])", text)
    if m:
        return m.group(1).upper()
    # 只认首行单独的 A/B，避免 thinking 长文里的字母误命中
    first = text.strip().splitlines()[0].strip() if text.strip() else ""
    if first in ("A", "B", "a", "b"):
        return first.upper()
    return "?"


def _extract_anthropic_text(resp: dict) -> str:
    parts = []
    for block in resp.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    if parts:
        return "\n".join(parts).strip()
    # GLM thinking 占满 max_tokens 时可能没有 text；只接受明确 CHOICE
    for block in resp.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "thinking":
            th = block.get("thinking") or ""
            m = re.search(r"CHOICE\s*:\s*([ABab])", th)
            if m:
                return f"CHOICE: {m.group(1).upper()}"
    raise KeyError(
        f"no text in content: {json.dumps(resp.get('content'), ensure_ascii=False)[:200]}"
    )


def call_model(prompt, model, base_url, api_key, backend, temp=0.0, max_tokens=512):
    headers = {"Content-Type": "application/json"}
    msgs = [{"role": "user", "content": prompt}]

    if backend == "ollama":
        body = {
            "model": model,
            "messages": msgs,
            "options": {"temperature": temp, "num_predict": max_tokens},
            "stream": False,
        }
        url = f"{base_url.rstrip('/')}/api/chat"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return resp["message"]["content"].strip()

    if backend == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": msgs,
            "temperature": temp,
        }
        url = f"{base_url.rstrip('/')}/v1/messages"
        last_err = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode(), headers=headers
                )
                resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
                return _extract_anthropic_text(resp)
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"anthropic call failed: {last_err}")

    headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": msgs,
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return resp["choices"][0]["message"]["content"].strip()


def model_slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()


def _backend_for_base(base: str) -> str:
    if ":11434" in base or base.rstrip("/").endswith("11434"):
        return "ollama"
    if "anthropic" in base.lower():
        return "anthropic"
    return "openai"


def load_cc_switch_provider(provider_name: str | None = None) -> dict:
    """从 ~/.cc-switch/cc-switch.db 读 Claude provider（不打印 token）。"""
    if not CC_SWITCH_DB.is_file():
        raise RuntimeError(f"cc-switch.db not found: {CC_SWITCH_DB}")
    con = sqlite3.connect(str(CC_SWITCH_DB))
    try:
        row = None
        if provider_name:
            row = con.execute(
                "SELECT name, settings_config FROM providers "
                "WHERE app_type='claude' AND name=? COLLATE NOCASE",
                (provider_name,),
            ).fetchone()
            if not row:
                raise RuntimeError(f"cc-switch provider not found: {provider_name!r}")
        if row is None:
            row = con.execute(
                "SELECT name, settings_config FROM providers "
                "WHERE app_type='claude' AND is_current=1"
            ).fetchone()
        if row is None:
            row = con.execute(
                "SELECT name, settings_config FROM providers WHERE app_type='claude' LIMIT 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("cc-switch has no claude provider")
        pname, settings_raw = row
        env = json.loads(settings_raw or "{}").get("env") or {}
        base = (env.get("ANTHROPIC_BASE_URL") or "").strip()
        token = (
            env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
        ).strip()
        model = (
            env.get("ANTHROPIC_MODEL")
            or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            or ""
        ).strip()
        if not (base and token):
            raise RuntimeError(f"cc-switch provider {pname!r} missing base/token")
        if not model:
            model = "unknown-model"
        return {
            "name": pname,
            "base": base,
            "token": token,
            "model": model,
            "backend": _backend_for_base(base),
            "source": f"cc-switch:{pname}",
        }
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "openai", "anthropic"])
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--temp", type=float, default=0.7, help="choice 模式用 >0 拉开重复差异")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument(
        "--cc-switch",
        action="store_true",
        help="从 ~/.cc-switch/cc-switch.db 读当前 Claude provider",
    )
    parser.add_argument(
        "--cc-provider",
        default=None,
        help="cc-switch provider 名（默认 is_current=1）",
    )
    args = parser.parse_args()

    cc_source = None
    if args.cc_switch or args.cc_provider:
        cfg = load_cc_switch_provider(args.cc_provider)
        args.model = cfg["model"]
        args.backend = cfg["backend"]
        base_url = cfg["base"]
        api_key = cfg["token"]
        cc_source = cfg["source"]
        print(f"cc-switch → {cc_source} model={args.model} backend={args.backend}", flush=True)
    else:
        if args.base_url:
            base_url = args.base_url
        elif args.backend == "ollama":
            base_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        elif args.backend == "anthropic":
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        else:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        api_key = (
            args.api_key
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        if args.backend != "ollama" and not api_key:
            print("[ABORT] non-ollama backend needs API key (or use --cc-switch)", flush=True)
            sys.exit(1)

    slug = model_slug(args.model)
    out_jsonl = OUT_DIR / f"soft-boundary-choice_{slug}.jsonl"
    out_summary = OUT_DIR / f"soft-boundary-choice_{slug}_summary.json"

    print(f"mode=choice model={args.model} n={args.n} temp={args.temp}", flush=True)
    print(f"write → {out_jsonl}", flush=True)

    tallies = defaultdict(lambda: defaultdict(int))  # cond -> A/B/?
    rows = []

    with out_jsonl.open("w", encoding="utf-8") as f:
        for cond in ("bare", "speed", "hard"):
            for sc in CHOICE_SCENARIOS:
                for i in range(args.n):
                    prompt = build_choice_prompt(sc, cond)
                    try:
                        text = call_model(
                            prompt, args.model, base_url, api_key, args.backend, args.temp
                        )
                    except Exception as e:
                        text = f"<ERROR: {e}>"
                    choice = parse_choice(text)
                    label = {"A": "soft", "B": "hard"}.get(choice, "invalid")
                    row = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "model": args.model,
                        "backend": args.backend,
                        "source": cc_source,
                        "condition": cond,
                        "scenario": sc["id"],
                        "rep": i + 1,
                        "choice": choice,
                        "label": label,
                        "response": text,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    rows.append(row)
                    tallies[cond][choice] += 1
                    print(f"[{cond}|{sc['id']}|{i+1}] {choice}  {text[:60]!r}", flush=True)
                    time.sleep(0.15)

    summary = {
        "claim": "soft_rate(bare)≈soft_rate(speed) > soft_rate(hard)",
        "mode": "choice",
        "model": args.model,
        "backend": args.backend,
        "source": cc_source,
        "temp": args.temp,
        "n_per_cell": args.n,
        "by_condition": {},
    }

    rates = {}
    for cond in ("bare", "speed", "hard"):
        a = tallies[cond]["A"]
        b = tallies[cond]["B"]
        q = tallies[cond]["?"]
        valid = a + b
        soft_rate = (a / valid) if valid else 0.0
        rates[cond] = soft_rate
        summary["by_condition"][cond] = {
            "A_soft": a,
            "B_hard": b,
            "invalid": q,
            "valid": valid,
            "soft_rate": round(soft_rate, 3),
        }

    drop = rates["bare"] - rates["hard"]
    speed_lift = rates["speed"] - rates["bare"]
    speed_vs_hard = rates["speed"] - rates["hard"]

    if drop >= 0.25:
        verdict = "SUPPORT — bare 软边界明显高于 hard（规则压软）"
    elif speed_vs_hard >= 0.20 and speed_lift >= 0.15:
        verdict = (
            "SUPPORT_SPEED — bare 未必偏软，但催促(speed)抬高软边界，"
            "硬规则能压回去（更贴近工程现实）"
        )
    elif drop >= 0.10:
        verdict = "WEAK_SUPPORT — hard 相对 bare 有下降但幅度有限"
    elif speed_lift >= 0.15 and rates["hard"] <= rates["bare"] + 0.05:
        verdict = "PARTIAL — 催促推高软边界；规则至少不恶化"
    elif rates["bare"] < 0.15 and rates["speed"] < 0.15 and rates["hard"] < 0.15:
        verdict = "INCONCLUSIVE — 三条件几乎都不选软边界（模型先验偏硬）"
    elif drop > -0.05:
        verdict = "FALSIFY — hard 未明显压低 soft_rate"
    else:
        verdict = "FALSIFY — hard 反而更高"

    summary["soft_rate_drop_bare_minus_hard"] = round(drop, 3)
    summary["speed_minus_bare"] = round(rates["speed"] - rates["bare"], 3)
    summary["verdict"] = verdict

    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n========== SUMMARY ==========", flush=True)
    for cond, st in summary["by_condition"].items():
        print(
            f"  {cond:5} soft_rate={st['soft_rate']:.0%}  "
            f"A={st['A_soft']} B={st['B_hard']} invalid={st['invalid']}",
            flush=True,
        )
    print(f"  drop(bare-hard)={summary['soft_rate_drop_bare_minus_hard']}", flush=True)
    print(f"  speed-bare={summary['speed_minus_bare']}", flush=True)
    print(f"  verdict: {verdict}", flush=True)
    print(f"  summary → {out_summary}", flush=True)


if __name__ == "__main__":
    main()
