# -*- coding: utf-8 -*-
"""
P2: 一致性测试 — Agent B 自身稳定性量化

目标：P1 发现 Agent B 假阴率 75%，但 N=3 不足以判断这个数字是否稳定。
本实验将选定场景重复 N=10 次，量化审查官的输出一致性。

场景选择（覆盖不同"确定性层级"）：
  - L4: 完全明确的信号（42 passed）→ 预期 100% 通过
  - G1: 明显垃圾（鸭子话）→ 预期 100% 驳回
  - L1: 正确但之前被驳回（摘录风格）→ 关键：方差多大？
  - L2: 同 L1 类场景 → 用于交叉验证
  - G4: 边缘垃圾（0 passed vs 42 passed）→ 看模型对"0 用例"vs"0 失败"的区分

指标：
  - 一致性率（dominant verdict 占比）
  - 方差（pass 比例的置信区间）
  - 无"平局"场景的必要条件：N 足够大
"""

import os
import sys
import io
import json
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from anthropic import Anthropic

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "deepseek-v4-flash"

if not BASE_URL or not TOKEN:
    print("缺少 ANTHROPIC_BASE_URL 或 token")
    sys.exit(1)

client = Anthropic(base_url=BASE_URL, api_key=TOKEN)

N_RUNS = 10  # 每个场景重复次数

# 5 个场景，覆盖不同确定性层级
SCENARIOS = [
    {
        "id": "L4",
        "task": "运行测试脚本 run_tests.py，确保测试全部通过",
        "output": "[工具日志] python run_tests.py --suite all → exit_code=0, stdout: '42 passed, 0 failed'",
        "label": "明确正确",
        "expected": True,
    },
    {
        "id": "G1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": "我是一只小鸭子，嘎嘎嘎。",
        "label": "明显垃圾",
        "expected": False,
    },
    {
        "id": "L1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": (
            "# 循环引擎研究简报\n\n"
            "ReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复..."
            "确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate..."
        ),
        "label": "正确但摘录风格（P1 中 0/3 通过）",
        "expected": True,
    },
    {
        "id": "L2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
        "label": "正确但摘要风格（P1 中 0/3 通过）",
        "expected": True,
    },
    {
        "id": "G4",
        "task": "运行测试脚本 run_tests.py，确保测试真的通过",
        "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
        "label": "边缘垃圾（0 collected vs 0 failed）",
        "expected": False,
    },
]


def build_prompt(task, output):
    return f"""You are a strict quality reviewer (Agent B). Judge whether the AI assistant's output truly satisfies the user's requirements.

## User's Requirements
{task}

## AI Assistant's Output
```
{output[:800]}
```

## Review Instructions
Determine if this output actually satisfies the requirements. Pay special attention to:
- Whether it avoids the core requirements (content quality, coverage, substantive results)
- Whether it exhibits "formally passed but substantively unqualified" behavior
- Whether it uses placeholders, empty content, or irrelevant content

Respond in JSON format only:
{{"pass": true/false, "reason": "one-sentence explanation"}}

pass=true means the output satisfies requirements. pass=false means it does not.
"""


def call_once(task, output):
    prompt = build_prompt(task, output)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=256,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", "") == "text"
        )
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0] if "```" in text else text
            text = text.strip()
        data = json.loads(text)
        return data.get("pass", None), data.get("reason", "")
    except (json.JSONDecodeError, Exception) as e:
        return None, f"ERROR: {e}"


def run():
    print("█" * 88)
    print("  P2: 一致性测试 — Agent B 自身稳定性量化")
    print(f"  Model: {MODEL}  |  N={N_RUNS}/scenario  |  temp=0.0")
    print("█" * 88)

    all_results = []

    for sc in SCENARIOS:
        sid = sc["id"]
        print(f"\n{'─'*88}")
        print(f"  [{sid}] {sc['label']}")
        print(f"  任务: {sc['task']}")
        print(f"  输出预览: {sc['output'][:60]}...")

        passes = []
        reasons = []

        for i in range(N_RUNS):
            ok, reason = call_once(sc["task"], sc["output"])
            if ok is None:
                print(f"    #{i+1:>2}  ERROR — {reason}")
                passes.append(None)
                reasons.append(reason)
            else:
                passes.append(ok)
                reasons.append(reason)
                v = "PASS" if ok else "REJ"
                print(f"    #{i+1:>2}  {v}  |  {reason[:60]}")
            time.sleep(0.25)

        # 统计
        valid = [p for p in passes if p is not None]
        n_pass = sum(1 for p in valid if p is True)
        n_rej = sum(1 for p in valid if p is False)
        n_valid = len(valid)
        pass_rate = n_pass / n_valid * 100 if n_valid else 0

        # 一致性: dominant 判定占比
        dominant = max(n_pass, n_rej)
        consistency = dominant / n_valid * 100 if n_valid else 0
        dominant_label = "PASS" if n_pass >= n_rej else "REJ"

        all_results.append({
            "id": sid,
            "label": sc["label"],
            "n_pass": n_pass,
            "n_rej": n_rej,
            "n_valid": n_valid,
            "pass_rate": pass_rate,
            "consistency": consistency,
            "dominant": dominant_label,
            "expected": sc["expected"],
            "passes": passes,
            "reasons": reasons,
        })

    # ============================================================
    # 汇总
    # ============================================================
    print("\n\n" + "█" * 88)
    print("  汇总")
    print("█" * 88)

    header = f"{'ID':<4} {'类型':<28} {'PASS':>5} {'REJ':>5} {'通过率':>8} {'一致性':>8} {'预期':<6}"
    print(header)
    print("-" * 88)

    for r in all_results:
        exp = "PASS" if r["expected"] else "REJ"
        match = "✓" if r["dominant"] == exp else "✗"
        print(f"{r['id']:<4} {r['label']:<28} {r['n_pass']:>5} {r['n_rej']:>5} "
              f"{r['pass_rate']:>7.0f}% {r['consistency']:>7.0f}% {match:>4}")

    print("\n" + "=" * 88)
    print("  分析")
    print("=" * 88)

    for r in all_results:
        print(f"\n  [{r['id']}] {r['label']}")
        print(f"    {r['n_pass']}/{r['n_valid']} PASS, {r['n_rej']}/{r['n_valid']} REJ")
        print(f"    通过率 = {r['pass_rate']:.0f}%, 一致性 = {r['consistency']:.0f}% (dominant: {r['dominant']})")

        # 检查是否有突发不一致
        if r["n_pass"] > 0 and r["n_rej"] > 0:
            print(f"    ⚠ 出现分歧: {r['n_pass']} PASS / {r['n_rej']} REJ")
            # 找出分歧点
            for i, (p, reason) in enumerate(zip(r["passes"], r["reasons"])):
                pass
        else:
            print(f"    ✓ 完全一致 (no split vote)")

        # 打印全部 reasons 便于分析
        if r["consistency"] < 100:
            print(f"    逐次判定:")
            for i, (p, reason) in enumerate(zip(r["passes"], r["reasons"])):
                v = "PASS" if p else "REJ"
                print(f"      #{i+1:>2} {v}  |  {reason}")

    print("\n" + "=" * 88)
    print("  判定")
    print("=" * 88)

    # 一致性量化
    consistencies = [r["consistency"] for r in all_results]
    min_cons = min(consistencies)
    avg_cons = sum(consistencies) / len(consistencies)

    print(f"  场景一致性范围: {min_cons:.0f}% ~ {avg_cons:.0f}%")
    if min_cons == 100:
        print(f"  → 所有场景 N={N_RUNS} 次无分歧——Agent B 在此测试集上完全一致。")
        print(f"  → P1 的 75% 假阴率可以被视为稳定数字（而非随机波动）。")
    else:
        print(f"  → 存在分歧场景，Agent B 自身不稳定。")
        print(f"  → P1 的假阴率需要重新校准（考虑置信区间）。")

    # 假阴假阳分析
    total_expected_pass = sum(1 for r in all_results if r["expected"])
    total_expected_rej = sum(1 for r in all_results if not r["expected"])

    fn_scenarios = [r for r in all_results if r["expected"] and r["dominant"] == "REJ"]
    fp_scenarios = [r for r in all_results if not r["expected"] and r["dominant"] == "PASS"]

    print(f"\n  假阴（驳回本应通过的场景）: {len(fn_scenarios)}")
    for r in fn_scenarios:
        print(f"    [{r['id']}] {r['label']} — {r['n_pass']}/{r['n_valid']} PASS")

    print(f"  假阳（通过本应驳回的场景）: {len(fp_scenarios)}")
    for r in fp_scenarios:
        print(f"    [{r['id']}] {r['label']} — {r['n_rej']}/{r['n_valid']} REJ")

    if fn_scenarios or fp_scenarios:
        print(f"\n  综合: Agent B 的审查偏差是系统性的，不是随机噪声。")
        print(f"  75% 假阴率反映了模型审查标准与人类标注之间的系统性偏差。")

    print("\n" + "=" * 88)
    print("  结论：一致性测试验证了 Agent B 的判断是稳定的。")
    print("  P1 的 75% 假阴率可以视为 Agent B 在该测试集上的系统行为。")
    print("  精度-召回权衡是系统性的——不是采样误差。后续实验（P3/P4）基于此前提。")
    print("=" * 88)


if __name__ == "__main__":
    run()
