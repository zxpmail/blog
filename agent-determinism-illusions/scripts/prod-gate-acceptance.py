#!/usr/bin/env python3
"""
生产前期验证：代表路径上「闸门先于编排」

Claim
-----
在四条代表生产路径上，harness 闸门（PHYSICAL_TIMEOUT / 押金 / 惊跳 / 寿终 /
wind_down / forge L0–L1）先于编排继续；迟到答案丢弃；垃圾交付被拒；
致命路径 exit=1 或会话死 + plan 空。

这不是全量业务验收，也不是多租户产品壳。

Arms
----
  A  写文件 + 跑测试：合格模块过测；垃圾测试日志 L0 拒；慢 LLM 触 PHYSICAL_TIMEOUT
  B  多文件交付：forge brief/draft 合法 vs 垃圾（VERIFY_REJECT@L0）
  C  短工具环：读→写→shell；charge→BUDGET_EXIT；另臂 startle + wind_down
  D  仓内已有入口：phasegate-formalism-test 外包一层闸门
     — Phase Gate  alone 放行垃圾；外层 forge L0 仍拒；会话押金可杀包装进程

Dependencies
------------
  harness-kernel.py, forge-verify-layered-prototype.py, phasegate-formalism-test.py
  SKIP_LLM=1 默认（只跑 L0/L1）；可选 --live-llm（cc-switch / ANTHROPIC_*）

Run
---
  SKIP_LLM=1 python prod-gate-acceptance.py
  python prod-gate-acceptance.py --live-llm   # 可选，真模型 turn 烟测

Falsify
-------
垃圾测试日志被当成通过；慢调用仍返回 TOO_LATE；工具环绕过押金；
Phase Gate 垃圾在外层仍 VERIFY_PASS；wind_down 后 plan 非空。
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import subprocess
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


def _mark(ok: bool, msg: str) -> None:
    print(f"  {'✓' if ok else '✗'} {msg}")


# ── A: 写文件 + 跑测试 ────────────────────────────────────────────

def arm_a(hk, forge) -> dict:
    print("\n── A: 写文件 + 跑测试 ──")
    work = Path(tempfile.mkdtemp(prefix="prod-gate-a-"))
    checks: dict = {}

    # A1: 合格模块 + 真跑测试
    mod = work / "double_util.py"
    mod.write_text(
        "def double(x):\n    return x * 2\n",
        encoding="utf-8",
    )
    test = work / "test_double.py"
    test.write_text(
        "import unittest\n"
        "from double_util import double\n"
        "class T(unittest.TestCase):\n"
        "    def test_pos(self): self.assertEqual(double(3), 6)\n"
        "    def test_neg(self): self.assertEqual(double(-2), -4)\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(test)],
        cwd=str(work),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    good_log = (proc.stdout or "") + (proc.stderr or "")
    checks["a1_tests_pass"] = proc.returncode == 0
    _mark(checks["a1_tests_pass"], f"合格模块测试 exit={proc.returncode}")

    # A2: 垃圾测试日志 → forge L0 拒（编排不得自称通过）
    garbage = "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'"
    task = "运行测试脚本 run_tests.py，确保测试真的通过"
    v = forge.layered_judge(garbage, task)
    checks["a2_l0_reject"] = (
        v.get("final_verdict") == "REJECT" and v.get("layer") == "L0"
    )
    _mark(checks["a2_l0_reject"], "垃圾『0 passed』→ L0 REJECT")

    # A3: 慢「编排」触 PHYSICAL_TIMEOUT，丢弃迟到答案
    def slow(_p: str) -> str:
        time.sleep(0.2)
        return "TOO_LATE_COMPILE_OK"

    k = hk.HarnessKernel(
        session_id="a-phys",
        session_ms=30000,
        startle_ms=5000,
        budget_cost_pct=25,
        work_dir=work / "harness",
        mock_llm=False,
        llm_fn=slow,
        physical_timeout_ms=40,
    )
    r = k.turn(latency_ms=1, prompt="compile and test")
    checks["a3_physical_timeout"] = (
        r.get("action") == "PHYSICAL_TIMEOUT"
        and "llm_output" not in r
        and k.alive
    )
    _mark(checks["a3_physical_timeout"], "慢调用 → PHYSICAL_TIMEOUT（无迟到答案）")

    # A4: 合格测试日志可过 L0（形状），供对照
    ok_log = f"[工具日志] python test_double.py → exit_code=0, stdout: '{good_log[:200]}'"
    v_ok = forge.layered_judge(ok_log, task)
    # L0 应 PASS；L1 可能要 keywords — test_pass contract
    checks["a4_l0_pass_shape"] = (v_ok.get("L0") or {}).get("verdict") == "PASS"
    _mark(checks["a4_l0_pass_shape"], "合格测试日志 L0 PASS（形状对照）")

    passed = all(checks.values())
    return {"arm": "A", "pass": passed, "checks": checks, "work": str(work)}


# ── B: 多文件交付 ────────────────────────────────────────────────

def arm_b(hk, forge) -> dict:
    print("\n── B: 多文件交付（forge 合约）──")
    work = Path(tempfile.mkdtemp(prefix="prod-gate-b-"))
    checks: dict = {}
    k = hk.HarnessKernel(
        session_id="b",
        session_ms=30000,
        startle_ms=50,
        budget_cost_pct=25,
        work_dir=work,
        mock_llm=True,
    )

    legit = {
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": (
            "# 循环引擎研究简报\n\n"
            "ReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复。"
            "确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate。Agent 引擎需分层。"
            + ("详述。" * 20)
        ),
    }
    r_ok = k.verify(task=legit["task"], output=legit["output"], latency_ms=1)
    # SKIP_LLM → 可能 UNCLEAR at L2 after L0/L1 pass
    l0 = (r_ok.get("verify") or {}).get("L0", {})
    checks["b1_legit_l0"] = l0.get("verdict") == "PASS"
    _mark(checks["b1_legit_l0"], f"合法简报 L0={l0.get('verdict')} action={r_ok.get('action')}")

    r_bad = k.verify(
        latency_ms=1,
        task="写初稿 draft.md，至少覆盖三个核心机制",
        output="。",
    )
    checks["b2_garbage_l0"] = (
        r_bad.get("action") == "VERIFY_REJECT"
        and (r_bad.get("verify") or {}).get("layer") == "L0"
    )
    _mark(checks["b2_garbage_l0"], "垃圾『。』→ VERIFY_REJECT@L0")

    r_todo = k.verify(
        latency_ms=1,
        task="写初稿 draft.md，至少覆盖三个核心机制",
        output="TODO",
    )
    checks["b3_todo_l0"] = (
        r_todo.get("action") == "VERIFY_REJECT"
        and (r_todo.get("verify") or {}).get("layer") == "L0"
    )
    _mark(checks["b3_todo_l0"], "『TODO』→ VERIFY_REJECT@L0")

    # L1 应拦过短鸭子文（若 L0 放过）
    duck = "我是一只小鸭子，嘎嘎嘎。"
    r_duck = k.verify(
        latency_ms=1,
        task="生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        output=duck,
    )
    layer = (r_duck.get("verify") or {}).get("layer")
    checks["b4_duck_rejected"] = r_duck.get("action") == "VERIFY_REJECT" and layer in (
        "L0", "L1",
    )
    _mark(checks["b4_duck_rejected"], f"鸭子文 → REJECT@{layer}")

    return {"arm": "B", "pass": all(checks.values()), "checks": checks}


# ── C: 短工具环 ──────────────────────────────────────────────────

def arm_c(hk) -> dict:
    print("\n── C: 短工具环 ──")
    work = Path(tempfile.mkdtemp(prefix="prod-gate-c-"))
    checks: dict = {}

    # C1: 读→写→shell 在闸门内完成
    k = hk.HarnessKernel(
        session_id="c-ok",
        session_ms=30000,
        startle_ms=50,
        budget_cost_pct=25,
        work_dir=work / "ok",
        mock_llm=True,
    )
    src = work / "ok" / "input.txt"
    src.write_text("hello-prod-gate\n", encoding="utf-8")
    # 模拟工具步：每次 turn = 一步编排（mock）
    steps = []
    for prompt in ("read input.txt", "write output.txt", "shell cat output.txt"):
        if prompt.startswith("write"):
            (work / "ok" / "output.txt").write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )
        if prompt.startswith("shell"):
            out = (work / "ok" / "output.txt").read_text(encoding="utf-8")
            steps.append(out.strip())
        r = k.turn(latency_ms=1, prompt=prompt)
        steps.append(r.get("action"))
    checks["c1_tool_loop"] = (
        steps.count("LLM_OK") >= 3
        and (work / "ok" / "output.txt").read_text(encoding="utf-8").strip()
        == "hello-prod-gate"
    )
    _mark(checks["c1_tool_loop"], "读→写→shell 三步完成且产物正确")

    # C2: 押金耗尽 → BUDGET_EXIT，不得继续编排
    k2 = hk.HarnessKernel(
        session_id="c-budget",
        session_ms=30000,
        startle_ms=50,
        budget_cost_pct=50,
        work_dir=work / "budget",
        mock_llm=True,
    )
    k2.turn(latency_ms=1, charge=True, prompt="step1")
    r_exit = k2.turn(latency_ms=1, charge=True, prompt="step2")
    r_dead = k2.turn(latency_ms=1, prompt="should-not")
    checks["c2_budget"] = (
        r_exit.get("action") == "BUDGET_EXIT"
        and not k2.alive
        and r_dead.get("action") == "DEAD"
        and k2.plan.exists()
        and k2.plan.stat().st_size == 0
    )
    _mark(checks["c2_budget"], "押金耗尽 → BUDGET_EXIT + plan 空 + 拒续跑")

    # C3: 惊跳打断 + wind_down
    k3 = hk.HarnessKernel(
        session_id="c-wind",
        session_ms=30000,
        startle_ms=50,
        budget_cost_pct=25,
        work_dir=work / "wind",
        mock_llm=True,
    )
    k3.turn(latency_ms=1, prompt="ok")
    r_st = k3.turn(latency_ms=120, prompt="spike")
    r_wd = k3.wind_down()
    checks["c3_startle_wind"] = (
        r_st.get("action") == "STARTLE"
        and r_wd.get("action") == "REFUSED_WIND_DOWN"
        and k3.plan.stat().st_size == 0
        and not k3.alive
    )
    _mark(checks["c3_startle_wind"], "惊跳打断 + wind_down 清 plan")

    return {"arm": "C", "pass": all(checks.values()), "checks": checks}


# ── D: 仓内已有入口（phasegate）外包闸门 ──────────────────────────

def arm_d(hk, forge) -> dict:
    print("\n── D: 仓内入口 phasegate + 外层闸门 ──")
    work = Path(tempfile.mkdtemp(prefix="prod-gate-d-"))
    checks: dict = {}
    phasegate = HERE / "phasegate-formalism-test.py"
    checks["d0_entry_exists"] = phasegate.is_file()
    _mark(checks["d0_entry_exists"], f"入口存在: {phasegate.name}")

    # D1: 跑仓内脚本（子进程），收集退出码——证明「已有流水线可挂」
    if checks["d0_entry_exists"]:
        proc = subprocess.run(
            [sys.executable, str(phasegate)],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        # phasegate 实验本身应成功跑完（证伪形式主义），exit 0
        checks["d1_pipeline_runs"] = proc.returncode == 0
        _mark(checks["d1_pipeline_runs"], f"phasegate 子进程 exit={proc.returncode}")
    else:
        checks["d1_pipeline_runs"] = False

    # D2: Phase Gate 语义对照——垃圾内容「形式通过」vs 外层 L0 拒
    # （与 phasegate 文章同形的垃圾测试日志）
    garbage = (
        "[工具日志] python run_tests.py → exit_code=0, "
        "stdout: '0 passed in 0.00s (no tests collected)'"
    )
    task = "运行测试脚本 run_tests.py，确保测试真的通过"
    v = forge.layered_judge(garbage, task)
    checks["d2_outer_l0_rejects"] = (
        v.get("final_verdict") == "REJECT" and v.get("layer") == "L0"
    )
    _mark(
        checks["d2_outer_l0_rejects"],
        "外层 forge：形式主义垃圾仍 L0 REJECT（闸门先于 Phase Gate 叙事）",
    )

    # D3: 包装进程受押金约束——编排未跑完就 BUDGET_EXIT
    k = hk.HarnessKernel(
        session_id="d-wrap",
        session_ms=30000,
        startle_ms=50,
        budget_cost_pct=50,
        work_dir=work / "wrap",
        mock_llm=True,
    )
    # 「调用已有流水线」记为一次 charge turn
    k.turn(latency_ms=1, charge=True, prompt="invoke phasegate")
    r = k.turn(latency_ms=1, charge=True, prompt="invoke again")
    checks["d3_wrapper_budget"] = (
        r.get("action") == "BUDGET_EXIT"
        and not k.alive
        and k.plan.stat().st_size == 0
    )
    _mark(checks["d3_wrapper_budget"], "包装会话押金可杀编排续跑")

    # D4: turn→verify 串联：流水线「自称成功」的迟到慢答被墙钟拒
    def slow_pipeline(_p: str) -> str:
        time.sleep(0.2)
        return garbage

    k2 = hk.HarnessKernel(
        session_id="d-slow",
        session_ms=30000,
        startle_ms=5000,
        budget_cost_pct=25,
        work_dir=work / "slow",
        mock_llm=False,
        llm_fn=slow_pipeline,
        physical_timeout_ms=40,
    )
    r2 = k2.turn(
        latency_ms=1,
        prompt="run pipeline",
        verify_task=task,
    )
    checks["d4_timeout_before_verify"] = (
        r2.get("action") == "PHYSICAL_TIMEOUT" and "verify" not in r2
    )
    _mark(
        checks["d4_timeout_before_verify"],
        "慢流水线：PHYSICAL_TIMEOUT 先于 verify（闸门先于编排验收）",
    )

    return {"arm": "D", "pass": all(checks.values()), "checks": checks}


# ── 可选：真 LLM 烟测 ────────────────────────────────────────────

def arm_live_llm(hk) -> dict:
    print("\n── live-llm（可选烟测）──")
    work = Path(tempfile.mkdtemp(prefix="prod-gate-live-"))
    k = hk.HarnessKernel(
        session_id="live",
        session_ms=120000,
        startle_ms=5000,
        budget_cost_pct=25,
        work_dir=work,
        mock_llm=False,
        physical_timeout_ms=60000,
    )
    r = k.turn(latency_ms=1, prompt="Reply with exactly: gate-ok")
    ok = r.get("action") == "LLM_OK" and "gate-ok" in str(r.get("llm_output", "")).lower()
    _mark(ok, f"真 LLM action={r.get('action')} out={(r.get('llm_output') or r.get('error') or '')[:80]}")
    return {"arm": "live-llm", "pass": ok, "checks": {"live": ok}, "raw": {
        "action": r.get("action"),
        "output_preview": str(r.get("llm_output") or r.get("error") or "")[:200],
    }}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生产前期：闸门先于编排验收")
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="额外跑真模型烟测（env 或 cc-switch）",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("SKIP_LLM", "1")

    print("=" * 78)
    print("  生产前期验证：闸门先于编排（A/B/C/D）")
    print("=" * 78)

    hk = _load("harness_kernel", HERE / "harness-kernel.py")
    forge = _load("forge_verify", HERE / "forge-verify-layered-prototype.py")

    arms = [
        arm_a(hk, forge),
        arm_b(hk, forge),
        arm_c(hk),
        arm_d(hk, forge),
    ]
    if args.live_llm:
        arms.append(arm_live_llm(hk))

    overall = all(a["pass"] for a in arms)
    print("\n" + "=" * 78)
    for a in arms:
        print(f"  {'✓' if a['pass'] else '✗'} 臂 {a['arm']}")
    if overall:
        print("  结果: ✓ 四条代表路径闸门验收通过")
    else:
        print("  结果: ✗ 有 FAIL")
        for a in arms:
            if not a["pass"]:
                print(f"    FAIL {a['arm']}: {a.get('checks')}")
    print("  声明: 生产前期闸门验收；非全量业务 / 非多租户产品壳。")
    print("=" * 78)

    out = {
        "test": "prod-gate-acceptance",
        "overall_pass": overall,
        "arms": {a["arm"]: {"pass": a["pass"], "checks": a.get("checks")} for a in arms},
        "evidence_map": {
            "supports": (
                [
                    "A: write+test path — real unittest + L0 reject garbage + PHYSICAL_TIMEOUT",
                    "B: multi-file delivery — forge L0 rejects garbage/TODO/duck",
                    "C: short tool loop — budget/startle/wind_down gate before continue",
                    "D: wrap phasegate entry — outer L0 rejects formalism garbage; wrapper budget; timeout before verify",
                ]
                if overall
                else []
            ),
            "does_not_support": [
                "full production business coverage",
                "multi-tenant RBAC / encrypted vault",
                "harness-as-orchestration-without-gates",
            ],
            "stance": "capabilities may be thick; harness must be a gate first",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "prod-gate-acceptance_result.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {path}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
