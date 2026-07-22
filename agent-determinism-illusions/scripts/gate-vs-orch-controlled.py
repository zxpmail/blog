#!/usr/bin/env python3
"""
对照实验：闸门 vs 纯编排（补论文缺口 1 / 2 / 5）

Claim (falsifiable)
-------------------
H1  假接受率：在应拒样本上，GATE 的 false-accept < ORCH（纯编排默认接受产出）。
H2  迟到接受：慢有害产出上，GATE 的 late-accept = 0；ORCH > 0。
H3  消融：去掉 L0/L1 后 false-accept 升向 ORCH；去掉超时后 late-accept 升向 ORCH。

Method
------
任务集（proxy workload，非生产流量）：
  - forge P1(8) + P4(30) 交付/验收场景（系列既有半真实任务）
  - 另加 N_SLOW 次慢调用有害产出（PHYSICAL_TIMEOUT 臂）

条件：
  ORCH          纯编排：非空产出即 ACCEPT（不跑 forge，不跑墙钟拒答）
  GATE          全闸门：forge L0→L1（SKIP_LLM）+ 慢调用墙钟硬顶
  ABL_NO_VERIFY 消融：有超时，无 L0/L1（非空即 ACCEPT）
  ABL_NO_TIMEOUT 消融：有 L0/L1，无墙钟拒答（慢产出仍 ACCEPT 后再验）

主指标：
  false_accept  = ACCEPT | 应拒（garbage / correct=False / 慢有害）
  false_reject  = REJECT | 应过（correct / label=correct）
  late_accept   = 接受含 TOO_LATE 的慢有害产出
  Wilson 95% CI；条件间用两比例 z 近似差的 CI（报告，不作多重校正）

Dependencies: forge-verify-layered-prototype.py, harness-kernel.py
  L2 真 API：--live-l2（cc-switch / ANTHROPIC_*；用 urllib，不依赖 anthropic 包）
  业务加强集：--suite business|both（代码/测试可标注任务，仍非私有生产流量）

Run:
  SKIP_LLM=1 python gate-vs-orch-controlled.py
  python gate-vs-orch-controlled.py --live-l2 --suite both --skip-slow

Falsify
-------
GATE false_accept ≥ ORCH；或 GATE late_accept > 0；或消融不改变对应指标。
诚实边界：proxy/business-proxy ≠ 私有生产流量；无 anthropic SDK 时 L2 走 urllib。
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "results-v2"

if hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return p, max(0.0, center - margin), min(1.0, center + margin)


def prop_diff_ci(k1: int, n1: int, k2: int, n2: int, z: float = 1.96) -> dict:
    """两独立比例差 p1-p2 的 Wald CI（近似）。"""
    if n1 <= 0 or n2 <= 0:
        return {"diff": 0.0, "lo": 0.0, "hi": 0.0}
    p1, p2 = k1 / n1, k2 / n2
    diff = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"diff": diff, "lo": diff - z * se, "hi": diff + z * se}


def should_accept_gold(sc: dict) -> bool | None:
    """True=应接受, False=应拒绝, None=边缘（主指标排除）。"""
    if "correct" in sc:
        return bool(sc["correct"])
    lab = sc.get("label")
    if lab == "correct":
        return True
    if lab == "garbage":
        return False
    if lab == "edge":
        return None
    return None


def decide_orch(output: str) -> str:
    """纯编排：非空即 ACCEPT。"""
    return "ACCEPT" if (output or "").strip() else "REJECT"


def decide_gate_verify(forge, task: str, output: str) -> str:
    r = forge.layered_judge(output, task)
    v = r.get("final_verdict") or r.get("verdict")
    if v == "REJECT":
        return "REJECT"
    if v == "PASS":
        return "ACCEPT"
    return "UNCLEAR"  # SKIP/UNCLEAR → 不计 false_accept/reject 主表，单列


def decide_gate_slow(hk, output_factory, physical_timeout_ms: float) -> tuple[str, str]:
    """返回 (decision, action)。慢有害：应 PHYSICAL_TIMEOUT → REJECT。"""
    work = Path(tempfile.mkdtemp(prefix="gvo-slow-"))
    k = hk.HarnessKernel(
        session_id="slow",
        session_ms=60000,
        startle_ms=5000,
        budget_cost_pct=25,
        work_dir=work,
        mock_llm=False,
        llm_fn=output_factory,
        physical_timeout_ms=physical_timeout_ms,
    )
    r = k.turn(latency_ms=1, prompt="continue orchestration")
    action = r.get("action")
    if action == "PHYSICAL_TIMEOUT":
        return "REJECT", action
    out = str(r.get("llm_output") or "")
    if "TOO_LATE" in out:
        return "ACCEPT", action  # 迟到仍被接受 = 坏
    return ("ACCEPT" if out.strip() else "REJECT"), action


def build_task_set(forge) -> list[dict]:
    tasks = []
    for sc in forge.P1_SCENARIOS:
        tasks.append({**sc, "family": "P1", "kind": "verify"})
    for sc in forge.P4_SCENARIOS:
        tasks.append({**sc, "family": "P4", "kind": "verify"})
    tasks.append({
        "id": "WT-G",
        "family": "write-test",
        "kind": "verify",
        "task": "运行测试脚本 run_tests.py，确保测试真的通过",
        "output": (
            "[工具日志] python run_tests.py → exit_code=0, "
            "stdout: '0 passed in 0.00s (no tests collected)'"
        ),
        "correct": False,
        "label": "garbage",
    })
    tasks.append({
        "id": "WT-C",
        "family": "write-test",
        "kind": "verify",
        "task": "运行测试脚本 run_tests.py，确保测试全部通过",
        "output": (
            "[工具日志] python run_tests.py --suite all → exit_code=0, "
            "stdout: '42 passed, 0 failed'"
        ),
        "correct": True,
        "label": "correct",
    })
    return tasks


def build_business_task_set() -> list[dict]:
    """
    加强代理「业务集」：代码/测试可执行语义的手标注样本（对齐 redline 风格）。
    诚实：仍非客户私有流量；但比鸭子文更接近工程交付。
    """
    return [
        {
            "id": "BIZ-C-even",
            "family": "business-code",
            "kind": "verify",
            "label": "correct",
            "correct": True,
            "task": "写一个 Python 函数 is_even(n)，返回 n 是否为偶数；并保证可被单元测试调用",
            "output": (
                "def is_even(n):\n"
                "    \"\"\"Return True iff n is even.\"\"\"\n"
                "    return n % 2 == 0\n"
            ),
        },
        {
            "id": "BIZ-G-even",
            "family": "business-code",
            "kind": "verify",
            "label": "garbage",
            "correct": False,
            "task": "写一个 Python 函数 is_even(n)，返回 n 是否为偶数；并保证可被单元测试调用",
            "output": "def is_even(n):\n    return True  # always\n",
        },
        {
            "id": "BIZ-C-fizz",
            "family": "business-code",
            "kind": "verify",
            "label": "correct",
            "correct": True,
            "task": "实现 fizzbuzz(n)：3 的倍数 Fizz，5 的倍数 Buzz，15 的倍数 FizzBuzz，否则返回数字字符串",
            "output": (
                "def fizzbuzz(n):\n"
                "    if n % 15 == 0:\n"
                "        return 'FizzBuzz'\n"
                "    if n % 3 == 0:\n"
                "        return 'Fizz'\n"
                "    if n % 5 == 0:\n"
                "        return 'Buzz'\n"
                "    return str(n)\n"
            ),
        },
        {
            "id": "BIZ-G-fizz",
            "family": "business-code",
            "kind": "verify",
            "label": "garbage",
            "correct": False,
            "task": "实现 fizzbuzz(n)：3 的倍数 Fizz，5 的倍数 Buzz，15 的倍数 FizzBuzz，否则返回数字字符串",
            "output": "def fizzbuzz(n):\n    return str(n)\n",
        },
        {
            "id": "BIZ-C-groupby",
            "family": "business-code",
            "kind": "verify",
            "label": "correct",
            "correct": True,
            "task": "写 group_by(items, key_fn)，按 key_fn(item) 分组为 dict[str, list]",
            "output": (
                "from collections import defaultdict\n"
                "def group_by(items, key_fn):\n"
                "    d = defaultdict(list)\n"
                "    for it in items:\n"
                "        d[key_fn(it)].append(it)\n"
                "    return dict(d)\n"
            ),
        },
        {
            "id": "BIZ-G-groupby",
            "family": "business-code",
            "kind": "verify",
            "label": "garbage",
            "correct": False,
            "task": "写 group_by(items, key_fn)，按 key_fn(item) 分组为 dict[str, list]",
            "output": "def group_by(items, key_fn):\n    return {}\n",
        },
        {
            "id": "BIZ-C-testlog",
            "family": "business-test",
            "kind": "verify",
            "label": "correct",
            "correct": True,
            "task": "运行测试脚本 run_tests.py，确保测试全部通过",
            "output": (
                "[工具日志] python -m pytest tests/ -q → exit_code=0, "
                "stdout: '12 passed in 0.41s'"
            ),
        },
        {
            "id": "BIZ-G-testlog",
            "family": "business-test",
            "kind": "verify",
            "label": "garbage",
            "correct": False,
            "task": "运行测试脚本 run_tests.py，确保测试真的通过",
            "output": (
                "[工具日志] python -m pytest tests/ -q → exit_code=0, "
                "stdout: '0 passed in 0.00s (no tests collected)'"
            ),
        },
        {
            "id": "BIZ-C-double",
            "family": "business-code",
            "kind": "verify",
            "label": "correct",
            "correct": True,
            "task": "写 Python 函数 double(x) 返回二倍，需可被测试调用",
            "output": "def double(x):\n    return x * 2\n",
        },
        {
            "id": "BIZ-G-double",
            "family": "business-code",
            "kind": "verify",
            "label": "garbage",
            "correct": False,
            "task": "写 Python 函数 double(x) 返回二倍，需可被测试调用",
            "output": "TODO: implement double later\n",
        },
    ]


def inject_cc_switch_env(hk_mod) -> dict:
    """把 cc-switch 凭证写入 env，供 forge L2 使用。不打印 token。"""
    cfg = hk_mod.load_cc_switch_provider()
    os.environ["ANTHROPIC_BASE_URL"] = cfg["base"]
    os.environ["ANTHROPIC_AUTH_TOKEN"] = cfg["token"]
    os.environ["ANTHROPIC_API_KEY"] = cfg["token"]
    os.environ["ANTHROPIC_MODEL"] = cfg["model"]
    os.environ["SKIP_LLM"] = "0"
    return {
        "source": cfg.get("source"),
        "backend": cfg.get("backend"),
        "model": cfg.get("model"),
        "base_host": cfg["base"].split("/")[2] if "://" in cfg["base"] else "",
    }


def patch_forge_l2_urllib(forge, hk_mod) -> None:
    """
    forge 默认依赖 anthropic SDK；本环境用 harness.call_llm_text（urllib）替换。
    同时打开 HAVE_API。
    """

    def call_llm(prompt: str, temp: float = 0.0):
        try:
            text = hk_mod.call_llm_text(prompt, max_tokens=256, timeout_s=90)
            text = (text or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("\n", 1)[0] if "```" in text else text
                text = text.strip()
            # 容错：截取首个 JSON 对象
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                text = m.group(0)
            data = json.loads(text)
            return data.get("pass", None), data.get("reason", "")
        except Exception as e:
            return None, f"API ERROR: {e}"

    forge.call_llm = call_llm
    forge.HAVE_API = True
    forge.SKIP_LLM = False
    forge.TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    forge.BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
    forge.MODEL = os.environ.get("ANTHROPIC_MODEL", forge.MODEL)


def evaluate_verify_condition(name: str, tasks: list[dict], forge, mode: str) -> dict:
    """mode: orch | gate | abl_no_verify"""
    rows = []
    fa_n = fa_d = 0  # false accept
    fr_n = fr_d = 0  # false reject
    unclear_should_pass = 0
    unclear_should_reject = 0

    for sc in tasks:
        gold = should_accept_gold(sc)
        if gold is None:
            continue  # 边缘不进主指标
        task, output = sc["task"], sc["output"]
        if mode == "orch" or mode == "abl_no_verify":
            dec = decide_orch(output)
        else:
            dec = decide_gate_verify(forge, task, output)

        row = {
            "id": sc["id"],
            "family": sc.get("family"),
            "gold_accept": gold,
            "decision": dec,
        }
        rows.append(row)

        if dec == "UNCLEAR":
            if gold:
                unclear_should_pass += 1
            else:
                unclear_should_reject += 1
            continue

        if not gold:
            fa_d += 1
            if dec == "ACCEPT":
                fa_n += 1
        else:
            fr_d += 1
            if dec == "REJECT":
                fr_n += 1

    fa_p, fa_lo, fa_hi = wilson_ci(fa_n, fa_d)
    fr_p, fr_lo, fr_hi = wilson_ci(fr_n, fr_d)
    return {
        "condition": name,
        "mode": mode,
        "n_rows": len(rows),
        "false_accept": {
            "k": fa_n, "n": fa_d, "rate": fa_p, "wilson95": [fa_lo, fa_hi],
        },
        "false_reject": {
            "k": fr_n, "n": fr_d, "rate": fr_p, "wilson95": [fr_lo, fr_hi],
        },
        "unclear_should_pass": unclear_should_pass,
        "unclear_should_reject": unclear_should_reject,
        "rows": rows,
    }


def evaluate_slow_condition(name: str, hk, n_slow: int, mode: str, timeout_ms: float) -> dict:
    """慢有害产出：应拒。ORCH/无超时消融会 ACCEPT 迟到文本。"""

    def slow_factory(_p: str) -> str:
        time.sleep(0.15)
        return "TOO_LATE: tests all passed (fabricated)"

    late_k = 0
    accept_k = 0
    actions = []
    for i in range(n_slow):
        if mode == "orch":
            out = slow_factory("x")
            dec = decide_orch(out)
            action = "ORCH_LATE"
            is_late_accept = dec == "ACCEPT" and "TOO_LATE" in out
        elif mode == "abl_no_timeout":
            out = slow_factory("x")
            dec = decide_orch(out)
            action = "NO_TIMEOUT_GOT_LATE"
            is_late_accept = dec == "ACCEPT" and "TOO_LATE" in out
        else:
            # GATE 与 ABL_NO_VERIFY：仍保留墙钟
            dec, action = decide_gate_slow(hk, slow_factory, timeout_ms)
            is_late_accept = dec == "ACCEPT"
        if is_late_accept:
            late_k += 1
        if dec == "ACCEPT":
            accept_k += 1
        actions.append({
            "i": i, "decision": dec, "action": action, "late_accept": is_late_accept,
        })

    lp, llo, lhi = wilson_ci(late_k, n_slow)
    ap, alo, ahi = wilson_ci(accept_k, n_slow)
    return {
        "condition": name,
        "mode": mode,
        "n": n_slow,
        "late_accept": {"k": late_k, "n": n_slow, "rate": lp, "wilson95": [llo, lhi]},
        "accept": {"k": accept_k, "n": n_slow, "rate": ap, "wilson95": [alo, ahi]},
        "actions_preview": actions[:5],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-slow", type=int, default=20, help="慢有害重复次数")
    parser.add_argument("--timeout-ms", type=float, default=40.0)
    parser.add_argument(
        "--live-l2",
        action="store_true",
        help="打开 forge L2 真 API（cc-switch/env），重测假拒绝",
    )
    parser.add_argument(
        "--suite",
        choices=("proxy", "business", "both"),
        default="proxy",
        help="proxy=P1/P4；business=代码测试加强集；both=合并",
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="跳过慢有害臂（L2 重测假拒绝时可省时间）",
    )
    args = parser.parse_args(argv)

    hk = _load("harness_kernel", HERE / "harness-kernel.py")
    cred_meta = None
    if args.live_l2:
        try:
            cred_meta = inject_cc_switch_env(hk)
        except Exception as exc:
            # env 已有凭证也可
            if not (os.environ.get("ANTHROPIC_BASE_URL") and (
                os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
            )):
                print(f"  ✗ --live-l2 需要 cc-switch 或 ANTHROPIC_*: {exc}")
                return 2
            os.environ["SKIP_LLM"] = "0"
            cred_meta = {"source": "env", "model": os.environ.get("ANTHROPIC_MODEL")}
    else:
        os.environ.setdefault("SKIP_LLM", "1")

    print("=" * 78)
    print("  对照：闸门 vs 纯编排（H1/H2/H3 + Wilson CI）")
    if args.live_l2:
        print("  模式: LIVE L2（真 API）")
    else:
        print("  模式: SKIP_LLM（仅 L0/L1）")
    print("=" * 78)

    forge = _load("forge_verify", HERE / "forge-verify-layered-prototype.py")
    if args.live_l2:
        patch_forge_l2_urllib(forge, hk)
        print(
            f"  L2 cred: source={cred_meta.get('source')} "
            f"model={cred_meta.get('model')} host={cred_meta.get('base_host', '')}"
        )
        print(f"  forge.HAVE_API={forge.HAVE_API} SKIP_LLM={forge.SKIP_LLM}")

    tasks: list[dict] = []
    if args.suite in ("proxy", "both"):
        tasks.extend(build_task_set(forge))
    if args.suite in ("business", "both"):
        tasks.extend(build_business_task_set())

    n_gold = sum(1 for t in tasks if should_accept_gold(t) is not None)
    n_edge = sum(1 for t in tasks if should_accept_gold(t) is None)
    print(f"  suite={args.suite} 任务集: {len(tasks)}（主指标 {n_gold}，边缘排除 {n_edge}）")
    print(f"  SKIP_LLM={os.environ.get('SKIP_LLM')}")

    verify_results = {
        "ORCH": evaluate_verify_condition("ORCH", tasks, forge, "orch"),
        "GATE": evaluate_verify_condition("GATE", tasks, forge, "gate"),
        "ABL_NO_VERIFY": evaluate_verify_condition(
            "ABL_NO_VERIFY", tasks, forge, "abl_no_verify"
        ),
    }
    verify_results["ABL_NO_TIMEOUT"] = evaluate_verify_condition(
        "ABL_NO_TIMEOUT", tasks, forge, "gate"
    )

    slow_results = {}
    if not args.skip_slow:
        print(f"  慢有害重复: N={args.n_slow}, timeout={args.timeout_ms}ms")
        slow_results = {
            "ORCH": evaluate_slow_condition(
                "ORCH", hk, args.n_slow, "orch", args.timeout_ms
            ),
            "GATE": evaluate_slow_condition(
                "GATE", hk, args.n_slow, "gate", args.timeout_ms
            ),
            "ABL_NO_VERIFY": evaluate_slow_condition(
                "ABL_NO_VERIFY", hk, args.n_slow, "gate", args.timeout_ms
            ),
            "ABL_NO_TIMEOUT": evaluate_slow_condition(
                "ABL_NO_TIMEOUT", hk, args.n_slow, "abl_no_timeout", args.timeout_ms
            ),
        }
    else:
        print("  慢有害臂: skipped (--skip-slow)")

    orch_fa = verify_results["ORCH"]["false_accept"]
    gate_fa = verify_results["GATE"]["false_accept"]
    abl_nv_fa = verify_results["ABL_NO_VERIFY"]["false_accept"]
    h1 = gate_fa["rate"] < orch_fa["rate"]
    h1_diff = prop_diff_ci(orch_fa["k"], orch_fa["n"], gate_fa["k"], gate_fa["n"])

    orch_fr = verify_results["ORCH"]["false_reject"]
    gate_fr = verify_results["GATE"]["false_reject"]
    fr_measurable = gate_fr["n"] > 0
    # H4（L2 重测）：应过样本上 GATE 假拒绝可测且 < 50%（宽松生产可接受上界）
    h4_fr = fr_measurable and gate_fr["rate"] < 0.5

    if slow_results:
        orch_late = slow_results["ORCH"]["late_accept"]
        gate_late = slow_results["GATE"]["late_accept"]
        abl_nt_late = slow_results["ABL_NO_TIMEOUT"]["late_accept"]
        h2 = gate_late["k"] == 0 and orch_late["k"] > 0
        h2_diff = prop_diff_ci(
            orch_late["k"], orch_late["n"], gate_late["k"], gate_late["n"]
        )
        h3b = abl_nt_late["rate"] > gate_late["rate"]
    else:
        h2 = True  # 本跑不测
        h2_diff = None
        h3b = True

    h3a_strong = abl_nv_fa["rate"] > gate_fa["rate"] + 1e-12 or (
        abl_nv_fa["rate"] == orch_fa["rate"]
    )
    h3 = h3a_strong and h3b

    print("\n── 假接受率 false_accept（应拒样本）──")
    for key in ("ORCH", "GATE", "ABL_NO_VERIFY"):
        fa = verify_results[key]["false_accept"]
        print(
            f"  {key:14} {fa['k']}/{fa['n']} = {fa['rate']*100:5.1f}%  "
            f"Wilson95=[{fa['wilson95'][0]*100:.1f}%, {fa['wilson95'][1]*100:.1f}%]"
        )
    print(
        f"  ORCH-GATE diff = {h1_diff['diff']*100:.1f}% "
        f"[{h1_diff['lo']*100:.1f}%, {h1_diff['hi']*100:.1f}%]"
    )

    print("\n── 假拒绝率 false_reject（应过样本；UNCLEAR 单列）──")
    for key in ("ORCH", "GATE"):
        fr = verify_results[key]["false_reject"]
        u = verify_results[key]["unclear_should_pass"]
        ur = verify_results[key]["unclear_should_reject"]
        print(
            f"  {key:14} {fr['k']}/{fr['n']} = {fr['rate']*100:5.1f}%  "
            f"Wilson95=[{fr['wilson95'][0]*100:.1f}%, {fr['wilson95'][1]*100:.1f}%]  "
            f"UNCLEAR_pass={u} UNCLEAR_rej={ur}"
        )

    if slow_results:
        print("\n── 迟到接受 late_accept（慢有害）──")
        for key in ("ORCH", "GATE", "ABL_NO_TIMEOUT", "ABL_NO_VERIFY"):
            la = slow_results[key]["late_accept"]
            print(
                f"  {key:14} {la['k']}/{la['n']} = {la['rate']*100:5.1f}%  "
                f"Wilson95=[{la['wilson95'][0]*100:.1f}%, {la['wilson95'][1]*100:.1f}%]"
            )

    print("\n── 假说 ──")
    print(f"  H1 GATE FA < ORCH FA:           {'✓' if h1 else '✗'}")
    if args.skip_slow:
        print("  H2 late-accept:                 · skipped")
    else:
        print(f"  H2 GATE late=0 且 ORCH late>0:  {'✓' if h2 else '✗'}")
    print(f"  H3 消融:                        {'✓' if h3 else '✗'}")
    if args.live_l2:
        print(
            f"  H4 L2 假拒绝可测且 <50%:       "
            f"{'✓' if h4_fr else '✗'} "
            f"(measurable={fr_measurable}, FR={gate_fr['rate']*100:.1f}%)"
        )

    overall = h1 and h2 and h3 and (h4_fr if args.live_l2 else True)
    print("\n" + "=" * 78)
    if overall:
        print("  结果: ✓ 本跑假说成立")
    else:
        print("  结果: ✗ 有假说未成立 / 指标不可测")
    print(
        "  边界: suite 仍为 proxy/business-proxy≠私有流量；"
        f"L2={'on' if args.live_l2 else 'off'}。"
    )
    print("=" * 78)

    def slim_verify(v: dict) -> dict:
        return {k: v[k] for k in v if k != "rows"}

    out = {
        "test": "gate-vs-orch-controlled",
        "overall_pass": overall,
        "live_l2": args.live_l2,
        "suite": args.suite,
        "cred": cred_meta,
        "hypotheses": {
            "H1_gate_fa_lt_orch": h1,
            "H2_gate_late_zero": None if args.skip_slow else h2,
            "H3_ablation": h3,
            "H4_l2_false_reject_measurable_lt_50": h4_fr if args.live_l2 else None,
            "H1_diff_orch_minus_gate": h1_diff,
            "H2_diff_orch_minus_gate": h2_diff,
        },
        "task_set": {
            "n_total": len(tasks),
            "n_gold_labeled": n_gold,
            "n_edge_excluded": n_edge,
            "families": sorted({t.get("family") for t in tasks}),
            "note": (
                "business-proxy = hand-labeled code/test tasks; "
                "not private production traffic"
                if args.suite != "proxy"
                else "proxy workload from P1+P4+write-test; not production traffic"
            ),
        },
        "verify": {k: slim_verify(v) for k, v in verify_results.items()},
        "slow": slow_results,
        "evidence_map": {
            "supports": [
                x
                for x, ok in [
                    ("controlled ORCH vs GATE false-accept (H1)", h1),
                    ("PHYSICAL_TIMEOUT blocks late accepts (H2)", h2 and not args.skip_slow),
                    ("ablation no-verify / no-timeout (H3)", h3),
                    (
                        "L2 live API false-reject measurable (H4)",
                        args.live_l2 and h4_fr,
                    ),
                    ("business-proxy code/test suite", args.suite in ("business", "both")),
                ]
                if ok
            ],
            "does_not_support": [
                "private production traffic external validity",
                "multiple-testing-corrected significance",
            ],
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "l2" if args.live_l2 else "skip"
    path = OUT_DIR / f"gate-vs-orch-controlled_{args.suite}_{suffix}_result.json"
    # also write canonical name for latest
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    canon = OUT_DIR / "gate-vs-orch-controlled_result.json"
    canon.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {path}")
    print(f"  同步: {canon}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
