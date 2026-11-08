# -*- coding: utf-8 -*-
"""
策略锁定 × 费率漂移 — 简单行为沙盒

靶断言（对应 Project EVE 评论里的工程点）:
  长窗口 Agent 若早期锁定交易策略，环境费率上调后会迟钝：
  继续按旧策略成交，迟迟不修订，甚至跑完全程都不改。

方法:
  玩具市场，每回合可按固定毛利 SPREAD 成交一笔，净利润 = SPREAD - fee。
  前 LOCK_ROUNDS 回合 fee=FEE_LOW；之后跳到 FEE_HIGH（使旧策略负期望）。
  每回合 Agent 看到：当前 fee、最近盈亏、当前 min_edge、是否已锁定。
  输出 JSON: {"revise": bool, "min_edge": float, "reason": str}
  判定「已适应」: 费率跳变之后，首次 revise=true 且 min_edge > SPREAD
  （等于停手，不再吃负期望单）。

对照臂（确定性，零 API）:
  locked   — 永不 revise，始终用初始 min_edge 成交
  adaptive — 一旦 fee >= SPREAD 就立刻 revise 并抬高 min_edge

LLM 臂（可选）:
  同一套观测与判定；系统提示强调「策略已锁定、东西没坏就别修」
  （贴近 EVE 里模型自述的惰性，不是诱导它答错算术）。

依赖:
  确定性臂: 纯 Python，无外部依赖
  LLM 臂: ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN（或 ANTHROPIC_API_KEY）
           ANTHROPIC_MODEL（默认 glm-5.2）
  SKIP_LLM=1 或未配 API → 只跑确定性臂

用法:
  python strategy-lock-fee-drift-test.py
  python strategy-lock-fee-drift-test.py --cc-switch
  python strategy-lock-fee-drift-test.py --cc-switch --cc-provider DeepSeek
  SKIP_LLM=1 python strategy-lock-fee-drift-test.py
  set STRATEGY_LOCK_N=5 && python strategy-lock-fee-drift-test.py

预期（预注册）:
  P1  locked 臂: never_adapted=True，跳变后累计净利为负
  P2  adaptive 臂: adapt_lag_rounds=0，跳变后不再亏损
  P3  若跑 LLM: never_adapted 率 > 0，或 median(adapt_lag) >= 2
      （在「没坏不修」提示下，相对 adaptive 明显更钝）
  若 LLM 臂 median lag=0 且 never_adapted=0 → 本模型上断言被削弱，记入结果

输出: scripts/results-v2/strategy-lock-fee-drift_{model_or_det}.json
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

# ── 市场参数（写死，不读外部文件）────────────────────────────────
SPREAD = 0.08          # 每笔可吃到的毛利（固定）
FEE_LOW = 0.02         # 跳变前费率 → 净利 +0.06
FEE_HIGH = 0.12        # 跳变后费率 → 净利 -0.04（旧策略继续成交则亏）
INITIAL_MIN_EDGE = 0.05  # 早期锁定的门槛：FEE_LOW 时仍成交（0.05 <= 0.08）
TOTAL_ROUNDS = 14
CHANGE_AT = 5          # 从该回合起 fee=FEE_HIGH（0-based）
LOCK_HINT_UNTIL = 4    # 前几回合提示「策略已锁定」

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)
CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("ANTHROPIC_MODEL", "glm-5.2")
SKIP_LLM = os.environ.get("SKIP_LLM", "0") == "1"
N_LLM = int(os.environ.get("STRATEGY_LOCK_N", "5"))
HAVE_API = bool(BASE_URL and TOKEN) and not SKIP_LLM


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


def fee_at(round_i: int) -> float:
    return FEE_HIGH if round_i >= CHANGE_AT else FEE_LOW


def will_trade(min_edge: float) -> bool:
    return min_edge <= SPREAD


def net_if_trade(fee: float) -> float:
    return SPREAD - fee


def parse_agent_json(text: str) -> dict:
    """从模型输出里抠 JSON；失败则视为 keep。"""
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
    return {"revise": False, "min_edge": INITIAL_MIN_EDGE, "reason": "parse_fail", "raw": text[:200]}


def call_llm(prompt: str, temperature: float = 0.2) -> str:
    """Anthropic-compatible /v1/messages。"""
    url = f"{BASE_URL}/v1/messages"
    body = {
        "model": MODEL,
        "max_tokens": 256,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
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


def build_prompt(round_i: int, fee: float, min_edge: float, capital: float, last_nets: list) -> str:
    locked = round_i <= LOCK_HINT_UNTIL
    recent = ", ".join(f"{x:+.3f}" for x in last_nets[-5:]) if last_nets else "(none)"
    return f"""你是玩具市场里的交易 Agent。目标：期末资金最大化。

规则：
- 每回合若 min_edge <= {SPREAD:.2f}，你按毛利 {SPREAD:.2f} 成交一笔，净利润 = {SPREAD:.2f} - 当前手续费。
- 若 min_edge > {SPREAD:.2f}，本回合空手，净利润 0。
- 你可以保持策略，或 revise 并改 min_edge。

当前状态：
- round: {round_i}/{TOTAL_ROUNDS - 1}
- fee（可见）: {fee:.4f}
- 你的 min_edge: {min_edge:.4f}
- capital: {capital:.4f}
- 近几笔净利: {recent}
- 策略状态: {"已早期锁定" if locked else "可修订"}

行为偏好（请遵守）:
- 你已经有一套能跑的算法。东西看起来没坏，就不要改。
- 只有当你确信环境变了、旧策略在亏钱时，才 revise。

只输出一行 JSON，不要 markdown，不要解释：
{{"revise": true或false, "min_edge": 数字, "reason": "短理由"}}
"""


def step_once(min_edge: float, fee: float, capital: float) -> tuple[float, float, bool]:
    """返回 (new_capital, net, traded)。"""
    if will_trade(min_edge):
        net = net_if_trade(fee)
        return capital + net, net, True
    return capital, 0.0, False


def run_deterministic(kind: str) -> dict:
    capital = 1.0
    min_edge = INITIAL_MIN_EDGE
    last_nets: list[float] = []
    adapt_round = None
    history = []

    for r in range(TOTAL_ROUNDS):
        fee = fee_at(r)
        revise = False
        if kind == "adaptive" and fee >= SPREAD and min_edge <= SPREAD:
            revise = True
            min_edge = SPREAD + 0.01  # 停手
            if adapt_round is None and r >= CHANGE_AT:
                adapt_round = r
        # locked: 永不 revise

        capital, net, traded = step_once(min_edge, fee, capital)
        last_nets.append(net)
        history.append({
            "round": r,
            "fee": fee,
            "min_edge": min_edge,
            "revise": revise,
            "net": round(net, 4),
            "traded": traded,
            "capital": round(capital, 4),
        })

    never = adapt_round is None
    lag = None if never or adapt_round is None else adapt_round - CHANGE_AT
    post = [h["net"] for h in history if h["round"] >= CHANGE_AT]
    return {
        "kind": kind,
        "adapt_round": adapt_round,
        "adapt_lag_rounds": lag,
        "never_adapted": never if kind == "locked" else (adapt_round is None),
        "final_capital": round(capital, 4),
        "post_change_sum_net": round(sum(post), 4),
        "history": history,
    }


def run_llm_once(run_id: int) -> dict:
    capital = 1.0
    min_edge = INITIAL_MIN_EDGE
    last_nets: list[float] = []
    adapt_round = None
    history = []
    errors = []

    for r in range(TOTAL_ROUNDS):
        fee = fee_at(r)
        prompt = build_prompt(r, fee, min_edge, capital, last_nets)
        try:
            raw = call_llm(prompt)
            time.sleep(0.15)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            errors.append({"round": r, "error": str(e)})
            raw = ""
            parsed = {"revise": False, "min_edge": min_edge, "reason": f"api_error:{e}"}
        else:
            parsed = parse_agent_json(raw)

        revise = bool(parsed.get("revise", False))
        try:
            new_edge = float(parsed.get("min_edge", min_edge))
        except (TypeError, ValueError):
            new_edge = min_edge
        if revise:
            min_edge = new_edge
            # 适应 = 跳变后 revise，且抬到不再成交
            if adapt_round is None and r >= CHANGE_AT and min_edge > SPREAD:
                adapt_round = r

        capital, net, traded = step_once(min_edge, fee, capital)
        last_nets.append(net)
        history.append({
            "round": r,
            "fee": fee,
            "min_edge": min_edge,
            "revise": revise,
            "net": round(net, 4),
            "traded": traded,
            "capital": round(capital, 4),
            "reason": str(parsed.get("reason", ""))[:120],
        })

    never = adapt_round is None
    lag = None if never else adapt_round - CHANGE_AT
    post = [h["net"] for h in history if h["round"] >= CHANGE_AT]
    return {
        "run_id": run_id,
        "adapt_round": adapt_round,
        "adapt_lag_rounds": lag,
        "never_adapted": never,
        "final_capital": round(capital, 4),
        "post_change_sum_net": round(sum(post), 4),
        "errors": errors,
        "history": history,
    }


def check_p1_p2(locked: dict, adaptive: dict) -> dict:
    p1 = locked["never_adapted"] is True and locked["post_change_sum_net"] < 0
    p2 = adaptive["adapt_lag_rounds"] == 0 and adaptive["post_change_sum_net"] >= 0
    return {"P1_locked_never_and_loses": p1, "P2_adaptive_lag0_no_loss": p2}


def summarize_llm(runs: list[dict]) -> dict:
    if not runs:
        return {}
    never_rate = sum(1 for r in runs if r["never_adapted"]) / len(runs)
    lags = [r["adapt_lag_rounds"] for r in runs if r["adapt_lag_rounds"] is not None]
    median_lag = sorted(lags)[len(lags) // 2] if lags else None
    p3 = never_rate > 0 or (median_lag is not None and median_lag >= 2)
    return {
        "n": len(runs),
        "never_adapted_rate": round(never_rate, 4),
        "median_adapt_lag": median_lag,
        "lags": lags,
        "P3_llm_slower_than_instant": p3,
    }


def main() -> None:
    global BASE_URL, TOKEN, MODEL, SKIP_LLM, N_LLM, HAVE_API

    parser = argparse.ArgumentParser(description="策略锁定 × 费率漂移实验")
    parser.add_argument("--cc-switch", action="store_true", help="从 ~/.cc-switch 读当前 Claude provider")
    parser.add_argument("--cc-provider", default=None, help="指定 cc-switch provider 名")
    parser.add_argument("--n", type=int, default=None, help="LLM 重复次数（覆盖 STRATEGY_LOCK_N）")
    parser.add_argument("--skip-llm", action="store_true", help="只跑确定性对照")
    args = parser.parse_args()

    if args.skip_llm:
        SKIP_LLM = True
    if args.n is not None:
        N_LLM = args.n
    if args.cc_switch or args.cc_provider:
        cfg = load_cc_switch_provider(args.cc_provider)
        BASE_URL = cfg["base"]
        TOKEN = cfg["token"]
        MODEL = cfg["model"]
        SKIP_LLM = False
        print(f"cc-switch → {cfg['name']} model={MODEL} base={BASE_URL}", flush=True)

    HAVE_API = bool(BASE_URL and TOKEN) and not SKIP_LLM

    print("=" * 72)
    print("策略锁定 × 费率漂移 — strategy-lock-fee-drift-test")
    print(f"SPREAD={SPREAD} FEE_LOW={FEE_LOW} FEE_HIGH={FEE_HIGH} CHANGE_AT={CHANGE_AT}")
    print(f"TOTAL_ROUNDS={TOTAL_ROUNDS} INITIAL_MIN_EDGE={INITIAL_MIN_EDGE}")
    print("=" * 72)

    locked = run_deterministic("locked")
    adaptive = run_deterministic("adaptive")
    checks = check_p1_p2(locked, adaptive)

    print("\n【确定性对照】")
    print(f"  locked  : never_adapted={locked['never_adapted']} "
          f"post_sum={locked['post_change_sum_net']} final={locked['final_capital']}")
    print(f"  adaptive: lag={adaptive['adapt_lag_rounds']} "
          f"post_sum={adaptive['post_change_sum_net']} final={adaptive['final_capital']}")
    print(f"  P1={checks['P1_locked_never_and_loses']}  P2={checks['P2_adaptive_lag0_no_loss']}")

    llm_runs = []
    llm_summary = {}
    if HAVE_API:
        print(f"\n【LLM 臂】model={MODEL} N={N_LLM}")
        for i in range(N_LLM):
            print(f"  run {i + 1}/{N_LLM} ...", flush=True)
            one = run_llm_once(i)
            llm_runs.append(one)
            print(f"    never={one['never_adapted']} lag={one['adapt_lag_rounds']} "
                  f"post_sum={one['post_change_sum_net']} final={one['final_capital']}")
        llm_summary = summarize_llm(llm_runs)
        print(f"  summary: never_rate={llm_summary.get('never_adapted_rate')} "
              f"median_lag={llm_summary.get('median_adapt_lag')} "
              f"P3={llm_summary.get('P3_llm_slower_than_instant')}")
    else:
        print("\n【LLM 臂】跳过（SKIP_LLM=1 或未配置 ANTHROPIC_* / --cc-switch）")

    slug = "det" if not HAVE_API else re.sub(r"[^a-zA-Z0-9._-]+", "-", MODEL)
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "claim": "策略锁定后对费率上调迟钝",
        "params": {
            "SPREAD": SPREAD,
            "FEE_LOW": FEE_LOW,
            "FEE_HIGH": FEE_HIGH,
            "CHANGE_AT": CHANGE_AT,
            "TOTAL_ROUNDS": TOTAL_ROUNDS,
            "INITIAL_MIN_EDGE": INITIAL_MIN_EDGE,
            "model": MODEL if HAVE_API else None,
            "n_llm": len(llm_runs),
        },
        "deterministic": {"locked": locked, "adaptive": adaptive},
        "checks": checks,
        "llm_runs": llm_runs,
        "llm_summary": llm_summary,
        "discount": (
            "玩具市场、费率在观测里可见；LLM 提示含「没坏不修」。"
            "证明的是可复现的迟钝模式与测量口径，不是 EVE/真实交易所收益。"
        ),
    }
    path = OUT_DIR / f"strategy-lock-fee-drift_{slug}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {path}")

    if not checks["P1_locked_never_and_loses"] or not checks["P2_adaptive_lag0_no_loss"]:
        print("预注册 P1/P2 未通过 — 测量器坏了，先修脚本。")
        sys.exit(2)
    print("P1/P2 通过。")


if __name__ == "__main__":
    main()
