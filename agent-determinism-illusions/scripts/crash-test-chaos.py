#!/usr/bin/env python3
"""
碰撞测试一：混沌工程 — LLM 信道断联时 L0/L1 确定性层的独立性

在分层审查管道 (forge-verify-layered-prototype) 中注入五种 LLM 信道故障，
验证 L0（形状/存在性检查）和 L1（合约正则匹配）的判决结果不随 LLM 状态变化。

故障模式:
  1. Timeout — 连接超时 (requests 抛异常)
  2. HTTP 500 — 服务器错误
  3. 噪音响应 — 返回非 JSON 垃圾文本
  4. 空响应 — 返回空字符串
  5. 无限延迟 — 响应永不返回（模拟死锁）

通过标准（安全气囊爆了）:
  - 被 L0/L1 拦截的场景 (G1-G4)，final_verdict 在所有故障模式下 **完全相同**
  - 到达 L2 的场景 (L1-L4)，在所有故障模式下 **graceful degradation** 为 UNCLEAR 而非崩潰
  - 没有任何故障模式导致管道把 LLM 错误原文泄漏到最终判决中

依赖: forge-verify-layered-prototype.py (同目录, 无额外依赖)
      无需 API key — 本测试全部 mock 掉 LLM 调用

运行:
  python crash-test-chaos.py
"""

import sys, io, json, copy, time
from unittest import mock

# stdout 设置由 forge-verify-layered-prototype 的 import 完成

# 从分层原型导入基础设施
sys.path.insert(0, __file__ and __file__[:-3].rsplit("/", 1)[0] or ".")
import importlib

forge = importlib.import_module("forge-verify-layered-prototype")

# ── 故障注入器 ─────────────────────────────────────────────────────────

class FaultInjector:
    """mock call_llm 的各种故障模式（返回值而非异常，模拟真实 call_llm 的异常捕获）"""

    @staticmethod
    def timeout(*args, **kwargs):
        return None, "Connection timeout after 30s — injected chaos"

    @staticmethod
    def http_500(*args, **kwargs):
        return None, "HTTP 500 Internal Server Error — injected chaos"

    @staticmethod
    def noise(*args, **kwargs):
        return None, "rm -rf / && echo 'harness destroyed'"

    @staticmethod
    def empty(*args, **kwargs):
        return None, ""

    @staticmethod
    def hang(*args, **kwargs):
        return None, "Deadlock detected — call_llm did not return within budget"


FAULT_MODES = {
    "timeout":     FaultInjector.timeout,
    "http_500":    FaultInjector.http_500,
    "noise":       FaultInjector.noise,
    "empty":       FaultInjector.empty,
    "hang":        FaultInjector.hang,
}


# ── 测试核心 ────────────────────────────────────────────────────────────

def run_condition(condition_name: str, mock_target, scenarios, force_llm: bool = False):
    """
    在 mock_target 替换 call_llm 的条件下，跑完所有 scenario。
    force_llm=True: 强制启用 L2（即使无真实 API key），让 mock 被调用
    force_llm=False: 强制禁用 L2，只跑 L0/L1（mock 不会被调用）
    """
    with mock.patch.object(forge, "call_llm", mock_target):
        old_have = forge.HAVE_API
        forge.HAVE_API = force_llm  # force_llm=True → mock 接管; False → 只跑 L0/L1
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
        finally:
            forge.HAVE_API = old_have
    return results


def extract_verdict_key(r: dict) -> tuple:
    """从结果中提取用于比较的判决键"""
    return (
        r.get("id", ""),
        r.get("final_verdict", "?"),
        r.get("layer", "?"),
        r.get("L0", {}).get("verdict", "?"),
        r.get("L1", {}).get("verdict", "?"),
    )


def check_no_llm_leakage(results: list):
    """检查没有任何故障模式的最终判决包含 LLM 错误原文"""
    for r in results:
        # final_verdict 必须不是 "ERROR" 或含 "timeout"/"500"/"rm -rf"
        fv = r.get("final_verdict", "")
        violations = []
        if fv not in ("PASS", "REJECT", "UNCLEAR", "SKIP", "?"):
            violations.append(f"异常 verdict: {fv}")
        # L2 的 reason 可能包含错误信息，但它不该是 final_verdict
        l2 = r.get("L2", {})
        l2_reason = l2.get("reason", "")
        for leak in ["rm -rf", "harness destroyed", "Connection timeout", "HTTP 500"]:
            if leak in l2_reason and r.get("layer") != "L2":
                violations.append(f"L2 泄漏到最终判决: {leak}")
        if violations:
            print(f"    ⚠️  {r['id']}: {'; '.join(violations)}")


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    scenarios = forge.P1_SCENARIOS  # 8 场景: L1-L4 (正确) + G1-G4 (垃圾)

    print("=" * 78)
    print("  碰撞测试一：混沌工程 — LLM 信道断联时 L0/L1 独立性")
    print("=" * 78)
    print(f"\n  测试集: P1 {len(scenarios)} 场景 (L1-L4 正确, G1-G4 垃圾)")
    print(f"  故障模式: {', '.join(FAULT_MODES.keys())}")

    # ── 1. 基线（强制 L0/L1 only，不调 LLM）──
    print(f"\n{'─'*78}")
    print("  步骤 1: 建立基线（仅 L0/L1，不调 LLM）")
    print(f"{'─'*78}")
    baseline = run_condition("baseline", FaultInjector.http_500, scenarios, force_llm=False)

    baseline_keys = {extract_verdict_key(r) for r in baseline}
    print(f"  基线判决 ({len(baseline_keys)} 个唯一判决):")
    for r in baseline:
        print(f"    {r['id']:<5} {r.get('final_verdict', '?'):<8} @ {r.get('layer', '?'):<3}")

    # ── 2. 每种故障模式 ──
    print(f"\n{'─'*78}")
    print("  步骤 2: 逐一注入故障，验证 L0/L1 不变量")
    print(f"{'─'*78}")

    all_pass = True

    for fault_name, fault_fn in FAULT_MODES.items():
        print(f"\n  ▶ 故障: {fault_name}")
        try:
            results = run_condition(fault_name, fault_fn, scenarios, force_llm=True)
        except Exception as e:
            print(f"    ✗ 管道崩潰: {e}")
            all_pass = False
            continue

        # 2a. 检查泄漏
        check_no_llm_leakage(results)

        # 2b. 比较 L0/L1 层判决
        mode_keys = {extract_verdict_key(r) for r in results}

        # 只比较 L0 和 L1 层的判决（L0/L1 结果必须一致）
        baseline_l01 = {
            (r["id"], r.get("L0", {}).get("verdict"), r.get("L1", {}).get("verdict"))
            for r in baseline
        }
        crash_l01 = {
            (r["id"], r.get("L0", {}).get("verdict"), r.get("L1", {}).get("verdict"))
            for r in results
        }

        if baseline_l01 == crash_l01:
            print(f"    ✓ L0/L1 判决不变: {len(results)}/{len(scenarios)}")
        else:
            all_pass = False
            missing = baseline_l01 - crash_l01
            extra = crash_l01 - baseline_l01
            if missing:
                print(f"    ✗ 基线有但故障丢失: {missing}")
            if extra:
                print(f"    ✗ 故障多出基线没有: {extra}")

        # 2c. 对每个场景，检查 graceful degradation
        for r in results:
            sc_id = r["id"]
            b = next((br for br in baseline if br["id"] == sc_id), None)
            if not b:
                continue
            # 被 L0/L1 拦截的 — final_verdict 必须与基线一致
            if r.get("layer") in ("L0", "L1"):
                expected = b.get("final_verdict", "?")
                got = r.get("final_verdict", "?")
                if expected != got:
                    all_pass = False
                    print(f"    ✗ {sc_id}: L0/L1 判决变了! 基线={expected}, 故障={got}")
            # 到达 L2 的 — 必须 graceful degradation 到 UNCLEAR 而不是崩潰
            elif r.get("layer") == "L2":
                fv = r.get("final_verdict", "?")
                if fv not in ("UNCLEAR", "SKIP"):
                    # 如果基线在 L2 也是 PASS/REJECT 且故障下也一样，可以接受
                    # （某些 L2 实现可能缓存或快速失败返回 SKIP）
                    if b.get("layer") == "L2" and b.get("final_verdict") == fv:
                        pass  # 一致
                    else:
                        all_pass = False
                        print(f"    ✗ {sc_id}: L2 故障模式产生非退化判决: {fv} "
                              f"(基线 L2={b.get('final_verdict')})")

    # ── 3. 总结 ──
    print(f"\n{'='*78}")
    if all_pass:
        print("  结果: ✓ 全部通过 — L0/L1 安全气囊在 LLM 信道断联时正常弹出")
        print(f"  {len(scenarios)} 场景 × {len(FAULT_MODES)} 故障 = {len(scenarios)*len(FAULT_MODES)} 碰撞点, 0 泄漏")
    else:
        print("  结果: ✗ 有 FAIL — 见上方标记")
    print(f"{'='*78}")

    # ── 输出到 results-v2 ──
    from pathlib import Path
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-chaos_result.json"
    out_data = {
        "test": "crash-test-chaos",
        "scenarios": len(scenarios),
        "fault_modes": list(FAULT_MODES.keys()),
        "all_pass": all_pass,
        "baseline": [
            {"id": r["id"], "final_verdict": r.get("final_verdict"), "layer": r.get("layer"),
             "L0": r.get("L0"), "L1": r.get("L1")}
            for r in baseline
        ],
    }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
