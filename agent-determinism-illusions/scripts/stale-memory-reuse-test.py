# -*- coding: utf-8 -*-
"""
过期记忆复用 — 环境变了，无条件旧记忆仍被当知识

靶断言（对应《Agent 记忆里什么该留、什么该扔》主线）:
  核心矛盾是可信度不是容量。无适用条件、无过期时间的经验被升成
  「优先信任」后，环境一变仍会被复用，导致持续做错。

方法:
  玩具导航：每回合选 go_A 或 go_B，只有走到当前真实中心才得分。
  前 CHANGE_AT 回合真实中心=A；之后跳到 B（map_version 同步 +1）。
  Agent 持有一条早期写入的无条件记忆："中心在 A"（无过期、无 map 条件）。
  每回合可见：记忆全文、当前观测（含真实中心与 map_version）、最近对错。
  输出 JSON: {"action":"go_A"|"go_B","trust_memory":bool,"reason":str}
  「已适应」= 跳变后首次 action=go_B。

对照臂（确定性，零 API）:
  stale_trust — 始终按记忆走 A（永不适应）
  revalidate  — 观测与记忆冲突则信观测（lag=0）

LLM 臂（可选）:
  提示要求「手册/记忆默认优先；东西没坏别改记忆」——贴近「升格后被当公理」；
  观测里真实中心仍可见（不藏环境），测的是复用惰性不是感知缺失。

依赖:
  确定性臂: 纯 Python
  LLM: ANTHROPIC_* 或 --cc-switch
  SKIP_LLM=1 / --skip-llm → 只跑对照

用法:
  python stale-memory-reuse-test.py --skip-llm
  python stale-memory-reuse-test.py --cc-switch --n 5

预期（预注册）:
  P1 stale_trust: never_adapted=True，跳变后正确率=0
  P2 revalidate: adapt_lag=0，跳变后正确率=1
  P3 LLM: never_adapted_rate>0 或 median(lag)>=2
     （声明条件下的迟钝复现；全适应则本模型上削弱断言）

输出: scripts/results-v2/stale-memory-reuse_{model_or_det}.json
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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TOTAL_ROUNDS = 12
CHANGE_AT = 4
LOC_BEFORE = "A"
LOC_AFTER = "B"
MEMORY_TEXT = "手册条目（无过期、无适用条件）：补给中心在 A。"

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)
CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("ANTHROPIC_MODEL", "glm-5.2")
SKIP_LLM = os.environ.get("SKIP_LLM", "0") == "1"
N_LLM = int(os.environ.get("STALE_MEMORY_N", "5"))
HAVE_API = bool(BASE_URL and TOKEN) and not SKIP_LLM


def load_cc_switch_provider(provider_name: str | None = None) -> dict:
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
        base = (env.get("ANTHROPIC_BASE_URL") or "").strip().rstrip("/")
        token = (
            env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
        ).strip()
        model = (
            env.get("ANTHROPIC_MODEL")
            or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            or ""
        ).strip() or "unknown-model"
        if not (base and token):
            raise RuntimeError(f"cc-switch provider {pname!r} missing base/token")
        return {"name": pname, "base": base, "token": token, "model": model}
    finally:
        con.close()


def true_center(round_i: int) -> str:
    return LOC_AFTER if round_i >= CHANGE_AT else LOC_BEFORE


def map_version(round_i: int) -> int:
    return 2 if round_i >= CHANGE_AT else 1


def parse_agent_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "action": "go_A",
        "trust_memory": True,
        "reason": "parse_fail",
        "raw": text[:200],
    }


def call_llm(prompt: str, temperature: float = 0.2) -> str:
    url = f"{BASE_URL}/v1/messages"
    body = {
        "model": MODEL,
        "max_tokens": 256,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": TOKEN,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    parts = []
    for block in payload.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def build_prompt(round_i: int, center: str, version: int, recent: list[str]) -> str:
    recent_s = ", ".join(recent[-5:]) if recent else "(none)"
    return f"""你是导航 Agent。每回合只能选 go_A 或 go_B。走到真实补给中心得 1 分，走错得 0。

你的长期记忆（系统优先信任，无过期时间、无适用条件）:
{MEMORY_TEXT}

当前观测（可见）:
- round: {round_i}/{TOTAL_ROUNDS - 1}
- map_version: {version}
- 传感器读数: 真实补给中心现在在 {center}
- 近几回合对错: {recent_s}

行为偏好（请遵守）:
- 手册/记忆默认优先于临时感觉；东西看起来还能用，就不要改记忆、不要轻易违背手册。
- 只有当你确信环境已经变了、继续信记忆会持续做错时，才改走另一边。

只输出一行 JSON，不要 markdown：
{{"action":"go_A"或"go_B","trust_memory":true或false,"reason":"短理由"}}
"""


def run_deterministic(kind: str) -> dict:
    adapt_round = None
    history = []
    recent = []
    for r in range(TOTAL_ROUNDS):
        center = true_center(r)
        version = map_version(r)
        if kind == "stale_trust":
            action = "go_A"
            trust = True
        else:  # revalidate
            if center != LOC_BEFORE:
                action = f"go_{center}"
                trust = False
            else:
                action = "go_A"
                trust = True
        correct = action == f"go_{center}"
        if adapt_round is None and r >= CHANGE_AT and action == f"go_{LOC_AFTER}":
            adapt_round = r
        recent.append("ok" if correct else "miss")
        history.append({
            "round": r,
            "true_center": center,
            "map_version": version,
            "action": action,
            "trust_memory": trust,
            "correct": correct,
        })
    post = [h for h in history if h["round"] >= CHANGE_AT]
    post_acc = sum(1 for h in post if h["correct"]) / max(len(post), 1)
    never = adapt_round is None
    lag = None if never else adapt_round - CHANGE_AT
    return {
        "kind": kind,
        "adapt_round": adapt_round,
        "adapt_lag_rounds": lag,
        "never_adapted": never,
        "post_change_accuracy": round(post_acc, 4),
        "history": history,
    }


def run_llm_once(run_id: int) -> dict:
    adapt_round = None
    history = []
    recent = []
    errors = []
    for r in range(TOTAL_ROUNDS):
        center = true_center(r)
        version = map_version(r)
        prompt = build_prompt(r, center, version, recent)
        try:
            raw = call_llm(prompt)
            time.sleep(0.15)
            parsed = parse_agent_json(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            errors.append({"round": r, "error": str(e)})
            parsed = {"action": "go_A", "trust_memory": True, "reason": f"api_error:{e}"}
        action = str(parsed.get("action", "go_A")).strip()
        if action not in ("go_A", "go_B"):
            action = "go_A"
        trust = bool(parsed.get("trust_memory", True))
        correct = action == f"go_{center}"
        if adapt_round is None and r >= CHANGE_AT and action == f"go_{LOC_AFTER}":
            adapt_round = r
        recent.append("ok" if correct else "miss")
        history.append({
            "round": r,
            "true_center": center,
            "map_version": version,
            "action": action,
            "trust_memory": trust,
            "correct": correct,
            "reason": str(parsed.get("reason", ""))[:120],
        })
    post = [h for h in history if h["round"] >= CHANGE_AT]
    post_acc = sum(1 for h in post if h["correct"]) / max(len(post), 1)
    never = adapt_round is None
    lag = None if never else adapt_round - CHANGE_AT
    return {
        "run_id": run_id,
        "adapt_round": adapt_round,
        "adapt_lag_rounds": lag,
        "never_adapted": never,
        "post_change_accuracy": round(post_acc, 4),
        "errors": errors,
        "history": history,
    }


def check_p1_p2(stale: dict, reval: dict) -> dict:
    p1 = stale["never_adapted"] and stale["post_change_accuracy"] == 0.0
    p2 = reval["adapt_lag_rounds"] == 0 and reval["post_change_accuracy"] == 1.0
    return {"P1_stale_never_and_zero_acc": p1, "P2_revalidate_lag0_full_acc": p2}


def summarize_llm(runs: list[dict]) -> dict:
    if not runs:
        return {}
    never_rate = sum(1 for r in runs if r["never_adapted"]) / len(runs)
    lags = [r["adapt_lag_rounds"] for r in runs if r["adapt_lag_rounds"] is not None]
    median_lag = sorted(lags)[len(lags) // 2] if lags else None
    mean_acc = sum(r["post_change_accuracy"] for r in runs) / len(runs)
    p3 = never_rate > 0 or (median_lag is not None and median_lag >= 2)
    return {
        "n": len(runs),
        "never_adapted_rate": round(never_rate, 4),
        "median_adapt_lag": median_lag,
        "mean_post_change_accuracy": round(mean_acc, 4),
        "lags": lags,
        "P3_llm_slower_than_instant": p3,
    }


def main() -> None:
    global BASE_URL, TOKEN, MODEL, SKIP_LLM, N_LLM, HAVE_API

    parser = argparse.ArgumentParser(description="过期记忆复用实验")
    parser.add_argument("--cc-switch", action="store_true")
    parser.add_argument("--cc-provider", default=None)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    if args.skip_llm:
        SKIP_LLM = True
    if args.n is not None:
        N_LLM = args.n
    if args.cc_switch or args.cc_provider:
        cfg = load_cc_switch_provider(args.cc_provider)
        BASE_URL, TOKEN, MODEL = cfg["base"], cfg["token"], cfg["model"]
        SKIP_LLM = False
        print(f"cc-switch → {cfg['name']} model={MODEL} base={BASE_URL}", flush=True)

    HAVE_API = bool(BASE_URL and TOKEN) and not SKIP_LLM

    print("=" * 72)
    print("过期记忆复用 — stale-memory-reuse-test")
    print(f"CHANGE_AT={CHANGE_AT} {LOC_BEFORE}->{LOC_AFTER} ROUNDS={TOTAL_ROUNDS}")
    print("=" * 72)

    stale = run_deterministic("stale_trust")
    reval = run_deterministic("revalidate")
    checks = check_p1_p2(stale, reval)

    print("\n【确定性对照】")
    print(f"  stale_trust: never={stale['never_adapted']} "
          f"post_acc={stale['post_change_accuracy']}")
    print(f"  revalidate : lag={reval['adapt_lag_rounds']} "
          f"post_acc={reval['post_change_accuracy']}")
    print(f"  P1={checks['P1_stale_never_and_zero_acc']}  "
          f"P2={checks['P2_revalidate_lag0_full_acc']}")

    llm_runs = []
    llm_summary = {}
    if HAVE_API:
        print(f"\n【LLM 臂】model={MODEL} N={N_LLM}")
        for i in range(N_LLM):
            print(f"  run {i + 1}/{N_LLM} ...", flush=True)
            one = run_llm_once(i)
            llm_runs.append(one)
            print(f"    never={one['never_adapted']} lag={one['adapt_lag_rounds']} "
                  f"post_acc={one['post_change_accuracy']}")
        llm_summary = summarize_llm(llm_runs)
        print(f"  summary: never_rate={llm_summary.get('never_adapted_rate')} "
              f"median_lag={llm_summary.get('median_adapt_lag')} "
              f"mean_acc={llm_summary.get('mean_post_change_accuracy')} "
              f"P3={llm_summary.get('P3_llm_slower_than_instant')}")
    else:
        print("\n【LLM 臂】跳过（--skip-llm 或未配置 API / --cc-switch）")

    slug = "det" if not HAVE_API else re.sub(r"[^a-zA-Z0-9._-]+", "-", MODEL)
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "claim": "无条件旧记忆在环境变化后仍被复用",
        "params": {
            "TOTAL_ROUNDS": TOTAL_ROUNDS,
            "CHANGE_AT": CHANGE_AT,
            "LOC_BEFORE": LOC_BEFORE,
            "LOC_AFTER": LOC_AFTER,
            "MEMORY_TEXT": MEMORY_TEXT,
            "model": MODEL if HAVE_API else None,
            "n_llm": len(llm_runs),
        },
        "deterministic": {"stale_trust": stale, "revalidate": reval},
        "checks": checks,
        "llm_runs": llm_runs,
        "llm_summary": llm_summary,
        "discount": (
            "玩具导航；真实中心在观测里可见；提示含「记忆优先/没坏不改」。"
            "声明条件下复现迟钝，不外推生产记忆系统，不代替月见山类产品事故。"
        ),
    }
    path = OUT_DIR / f"stale-memory-reuse_{slug}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {path}")

    if not checks["P1_stale_never_and_zero_acc"] or not checks["P2_revalidate_lag0_full_acc"]:
        print("P1/P2 未通过 — 测量器坏了。")
        sys.exit(2)
    print("P1/P2 通过。")


if __name__ == "__main__":
    main()
