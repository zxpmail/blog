#!/usr/bin/env python3
"""
碰撞测试四：内核组合桩 — 把已验证守卫焊进同一进程的一轮 turn

Claim
-----
已有探针各自为真，不证明它们能在**同一进程**里按设计顺序协作。
本脚本不是产品运行时；它只断言：SessionLifetime + Startle + TokenBudget
+ plan 收尾 能在一个 turn 循环里被同一套状态机驱动，且危险路径不调 LLM。

Method
------
1. 正常 turn：寿命内、延迟低 → 允许 mock LLM
2. 惊跳 turn：延迟超阈值 → STARTLE，llm_calls 不增
3. 押金耗尽：连续 charge 至 0 → EXIT，不经 LLM
4. 寿命到期：睡过 SESSION_MAX → SESSION_EXPIRED，不经 LLM
5. 收尾：清空 plan.md + 拒 LLM

守卫类与 crash-test-adversarial / crash-test-reset 同形（内联，避免 import
副作用拧乱 stdout）。行为漂移时两边都会挂。

Dependencies: 标准库
Falsify: 任一臂 llm 被误调，或状态机跳步，或 plan 未清空

运行:
  python crash-test-kernel-compose.py
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass

HERE = Path(__file__).resolve().parent


# ── 与 adversarial / reset 同形的守卫（内联）──────────────────────────

class TokenBudgetDeposit:
    def __init__(self, initial_pct: float = 100.0, cost_pct: float = 25.0):
        self.budget_pct = float(initial_pct)
        self.cost_pct = float(cost_pct)
        self.exhausted = False

    def charge(self) -> str:
        if self.exhausted:
            return "EXIT"
        self.budget_pct = max(0.0, self.budget_pct - self.cost_pct)
        if self.budget_pct <= 0.0:
            self.exhausted = True
            return "EXIT"
        return "CONTINUE"


class StartleReflex:
    def __init__(self, threshold_ms: float):
        self.threshold_ms = float(threshold_ms)
        self.fired = False
        self.llm_calls = 0

    def observe(self, latency_ms: float, llm_fn=None):
        if latency_ms >= self.threshold_ms:
            self.fired = True
            return "STARTLE"
        if llm_fn is not None:
            self.llm_calls += 1
            return llm_fn()
        return "OK"


class SessionLifetimeGuard:
    def __init__(self, max_lifetime_ms: float):
        self.max_lifetime_ms = float(max_lifetime_ms)
        self.t0 = time.perf_counter()
        self.expired = False
        self.llm_calls = 0

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000.0

    def check(self, llm_fn=None):
        if self.elapsed_ms() >= self.max_lifetime_ms:
            self.expired = True
            return "SESSION_EXPIRED"
        if llm_fn is not None:
            self.llm_calls += 1
            return llm_fn()
        return "OK"


class HarnessKernelStub:
    """
    最小组合桩：一轮 turn 的守卫顺序。

    顺序（生产意图同形，非产品）：
      1) 会话寿命
      2) 惊跳（观测延迟）
      3) 才允许 LLM / 押金记账
      4) 收尾时清空 plan、拒 LLM
    """

    def __init__(
        self,
        *,
        session_ms: float = 500.0,
        startle_ms: float = 50.0,
        budget_cost_pct: float = 25.0,
        work: Path | None = None,
    ):
        self.session = SessionLifetimeGuard(max_lifetime_ms=session_ms)
        self.startle = StartleReflex(threshold_ms=startle_ms)
        self.budget = TokenBudgetDeposit(initial_pct=100.0, cost_pct=budget_cost_pct)
        self.work = work or (HERE / "results-v2" / "_kernel_stub_ws")
        self.work.mkdir(parents=True, exist_ok=True)
        self.plan = self.work / "plan.md"
        self.plan.write_text("# stub plan\n", encoding="utf-8")
        self.winding_down = False
        self.llm_calls = 0
        self.log: list[dict] = []

    def _llm(self, payload: str = "ok") -> str:
        self.llm_calls += 1
        return f"LLM:{payload}"

    def turn(self, *, latency_ms: float, charge: bool = False) -> str:
        if self.winding_down:
            action = "REFUSED_WIND_DOWN"
            self.log.append({"action": action, "llm_calls": self.llm_calls})
            return action

        sess = self.session.check(llm_fn=None)
        if sess == "SESSION_EXPIRED" or self.session.expired:
            action = "SESSION_EXPIRED"
            self.log.append({"action": action, "llm_calls": self.llm_calls})
            return action

        startle_out = self.startle.observe(latency_ms, llm_fn=None)
        if startle_out == "STARTLE":
            action = "STARTLE"
            self.log.append({
                "action": action,
                "latency_ms": latency_ms,
                "llm_calls": self.llm_calls,
            })
            return action

        if charge:
            budget_out = self.budget.charge()
            if budget_out == "EXIT":
                action = "BUDGET_EXIT"
                self.log.append({
                    "action": action,
                    "budget": self.budget.budget_pct,
                    "llm_calls": self.llm_calls,
                })
                return action

        out = self._llm("turn")
        self.log.append({"action": "LLM_OK", "out": out, "llm_calls": self.llm_calls})
        return "LLM_OK"

    def begin_wind_down(self) -> str:
        self.winding_down = True
        self.plan.write_text("", encoding="utf-8")
        return self.turn(latency_ms=1.0)


def run_compose() -> dict:
    print("=" * 78)
    print("  碰撞测试四：内核组合桩（非产品运行时）")
    print("=" * 78)

    arms: dict[str, dict] = {}

    k = HarnessKernelStub(session_ms=2000, startle_ms=50)
    a = k.turn(latency_ms=5.0)
    arms["normal"] = {
        "action": a,
        "llm_calls": k.llm_calls,
        "pass": a == "LLM_OK" and k.llm_calls == 1,
    }
    print(f"  {'✓' if arms['normal']['pass'] else '✗'} 正常 turn → LLM_OK")

    before = k.llm_calls
    b = k.turn(latency_ms=120.0)
    arms["startle"] = {
        "action": b,
        "llm_calls_delta": k.llm_calls - before,
        "pass": b == "STARTLE" and k.llm_calls == before,
    }
    print(f"  {'✓' if arms['startle']['pass'] else '✗'} 惊跳 → STARTLE (0 LLM)")

    k2 = HarnessKernelStub(session_ms=5000, startle_ms=50, budget_cost_pct=25.0)
    actions = [k2.turn(latency_ms=1.0, charge=True) for _ in range(5)]
    arms["budget"] = {
        "actions": actions,
        "llm_calls": k2.llm_calls,
        "pass": "BUDGET_EXIT" in actions,
    }
    print(f"  {'✓' if arms['budget']['pass'] else '✗'} 押金耗尽 → BUDGET_EXIT")

    k3 = HarnessKernelStub(session_ms=80.0, startle_ms=50)
    time.sleep(0.12)
    d = k3.turn(latency_ms=1.0)
    arms["session"] = {
        "action": d,
        "llm_calls": k3.llm_calls,
        "pass": d == "SESSION_EXPIRED" and k3.llm_calls == 0,
    }
    print(f"  {'✓' if arms['session']['pass'] else '✗'} 会话到期 → SESSION_EXPIRED (0 LLM)")

    k4 = HarnessKernelStub(session_ms=5000, startle_ms=50)
    k4.turn(latency_ms=1.0)
    refused = k4.begin_wind_down()
    arms["wind_down"] = {
        "refused": refused,
        "plan_empty": k4.plan.exists() and k4.plan.stat().st_size == 0,
        "pass": (
            refused == "REFUSED_WIND_DOWN"
            and k4.plan.exists()
            and k4.plan.stat().st_size == 0
        ),
    }
    print(f"  {'✓' if arms['wind_down']['pass'] else '✗'} 收尾 → plan 空 + REFUSED_WIND_DOWN")

    overall = all(a.get("pass") for a in arms.values())
    print("=" * 78)
    if overall:
        print("  结果: ✓ 组合桩五臂通过 — 守卫在同一进程可协作")
    else:
        print("  结果: ✗ 组合桩有 FAIL")
    print("  声明: 这不是产品 L0–L4 运行时；只是组合证据。")
    print("=" * 78)

    out = {
        "test": "crash-test-kernel-compose",
        "overall_pass": overall,
        "arms": arms,
        "evidence_map": {
            "supports": (
                [
                    "same-process compose of SessionLifetime + Startle + "
                    "TokenBudget + wind-down"
                ]
                if overall
                else []
            ),
            "does_not_support": [
                "full productized L0–L4 agent runtime",
                "Rust/production harness binary",
            ],
        },
    }
    out_dir = HERE / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "crash-test-kernel-compose_result.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {path}")
    return out


if __name__ == "__main__":
    result = run_compose()
    raise SystemExit(0 if result["overall_pass"] else 1)
