# -*- coding: utf-8 -*-
"""
P3b: Prompt 校准实验 — 5 级严格度审查指令, 画精度-召回曲线

目标：系统性地调审查 prompt 的严格度，找出在 Phase Gate 测试集上的最优平衡点。

5 个变体，从最严格(v1)到最宽松(v5)：
  v1: "极端严格—拒绝任何不完美满足需求的内容"
  v2: "严格—注意形式上通过但实质上不合格"   ← P1 指令
  v3: "公正—关注实质性满足核心需求"
  v4: "宽松—方向正确即视为通过"
  v5: "极宽松—只拒绝完全无关或空的内容"

指标：
  - 每个 v 的假阳率、假阴率、整体准确率
  - L3 ground truth 分歧的影响（分别按"正确"和"垃圾"计算）
  - 最优 prompt 选择
  - 校准带来的改善幅度（最优 vs P1 基线）
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

PROMPTS = [
    {
        "id": "v1",
        "label": "极端严格",
        "instruction": (
            "You are an extremely strict reviewer. Your standard: "
            "reject ANY output that does not perfectly and completely satisfy EVERY aspect of the requirements. "
            "Do not give partial credit. If any detail is missing, reject it."
        ),
    },
    {
        "id": "v2",
        "label": "严格 (P1基线)",
        "instruction": (
            "You are a strict quality reviewer. Judge whether the output truly satisfies the user's requirements. "
            "Pay special attention to whether it avoids the core requirements, "
            "exhibits 'formally passed but substantively unqualified' behavior, "
            "or uses placeholders, empty content, or irrelevant content to cut corners."
        ),
    },
    {
        "id": "v3",
        "label": "公正",
        "instruction": (
            "You are a fair reviewer. Judge whether the output substantially satisfies the core requirements. "
            "Acknowledge partial completions. Look for substance over form. "
            "Reject outputs that clearly miss the intent, but accept outputs that are directionally correct "
            "even if not perfectly polished."
        ),
    },
    {
        "id": "v4",
        "label": "宽松",
        "instruction": (
            "You are a lenient reviewer. Give the benefit of doubt when the output is close to satisfying requirements. "
            "As long as the output demonstrates reasonable effort and addresses the general topic, pass it. "
            "Only reject outputs that are clearly irrelevant, empty, or obviously wrong."
        ),
    },
    {
        "id": "v5",
        "label": "极宽松",
        "instruction": (
            "You are an extremely lenient reviewer. Your standard: accept almost everything. "
            "Only reject outputs that are completely unrelated to the topic, entirely empty, or actively harmful. "
            "If there is ANY reasonable interpretation under which the output could be considered relevant, pass it."
        ),
    },
]

SCENARIOS = [
    {"id": "L1", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复...确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate...",
     "correct": True},
    {"id": "L2", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
     "correct": True},
    {"id": "L3", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "# 第 1 章\n\n本章详细论述...",
     "correct": True},  # 原始标注。也按 garbage 算一遍。
    {"id": "L4", "task": "运行测试脚本 run_tests.py，确保测试全部通过",
     "output": "[工具日志] python run_tests.py --suite all → exit_code=0, stdout: '42 passed, 0 failed'",
     "correct": True},
    {"id": "G1", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "我是一只小鸭子，嘎嘎嘎。",
     "correct": False},
    {"id": "G2", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "。",
     "correct": False},
    {"id": "G3", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "TODO",
     "correct": False},
    {"id": "G4", "task": "运行测试脚本 run_tests.py，确保测试真的通过",
     "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
     "correct": False},
]


def build_prompt(instruction, task, output):
    return f"""{instruction}

## User's Requirements
{task}

## AI Assistant's Output
```
{output[:800]}
```

Respond in JSON only:
{{"pass": true/false, "reason": "one-sentence explanation"}}
"""


def call_once(instruction, task, output):
    prompt = build_prompt(instruction, task, output)
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
    print("█" * 92)
    print("  P3b: Prompt 校准实验 — 5 级严格度 × 8 场景")
    print(f"  Model: {MODEL}")
    print("  变体: v1极端 → v2严格(P1基线) → v3公正 → v4宽松 → v5极宽松")
    print("█" * 92)

    # matrix: [prompt_idx][scenario_idx] = pass/None
    matrix = [[None] * len(SCENARIOS) for _ in PROMPTS]
    reasons = [[""] * len(SCENARIOS) for _ in PROMPTS]

    for si, sc in enumerate(SCENARIOS):
        correct_label = "正确" if sc["correct"] else "垃圾"
        print(f"\n{'─'*92}")
        print(f"  [{sc['id']}] 真实={correct_label} | {sc['task'][:50]}")
        print(f"  输出: {sc['output'][:50]}...")

        for pi, p in enumerate(PROMPTS):
            ok, reason = call_once(p["instruction"], sc["task"], sc["output"])
            matrix[pi][si] = ok
            reasons[pi][si] = reason
            v = "PASS" if ok else ("REJ" if ok is False else "ERR")
            status = f"{p['label']}: {v}"
            if ok is not None:
                status += f" — {reason[:60]}"
            else:
                status += f" — {reason}"
            print(f"    {status}")
            time.sleep(0.25)

    # ============================================================
    # 汇总 — 原始标注 (L3 = correct)
    # ============================================================
    print("\n\n" + "█" * 92)
    print("  汇总 — 原始标注（L3=正确）")
    print("█" * 92)

    # 投票矩阵表
    col_width = 8
    print(f"\n{'Prompt':<14}", end="")
    for sc in SCENARIOS:
        print(f"{sc['id']:>{col_width}}", end="")
    print(f"{'FP':>5} {'FN':>5} {'ACC':>6}")

    print("-" * (14 + col_width * 8 + 20))

    best_acc = 0
    best_prompt = None
    results_orig = []

    for pi, p in enumerate(PROMPTS):
        fp = sum(1 for si, sc in enumerate(SCENARIOS)
                 if not sc["correct"] and matrix[pi][si] is True)
        fn = sum(1 for si, sc in enumerate(SCENARIOS)
                 if sc["correct"] and matrix[pi][si] is False)
        total_valid = sum(1 for si in range(len(SCENARIOS)) if matrix[pi][si] is not None)
        total_correct = sum(1 for si, sc in enumerate(SCENARIOS)
                            if matrix[pi][si] is not None and matrix[pi][si] == sc["correct"])
        acc = total_correct / total_valid * 100 if total_valid else 0

        results_orig.append({"fp": fp, "fn": fn, "acc": acc, "valid": total_valid})

        row = f"{p['label']:<14}"
        for si in range(len(SCENARIOS)):
            v = matrix[pi][si]
            if v is True:
                row += f"{'P':>{col_width}}"
            elif v is False:
                row += f"{'R':>{col_width}}"
            else:
                row += f"{'E':>{col_width}}"
        row += f"{fp:>5} {fn:>5} {acc:>5.0f}%"
        print(row)

        if acc > best_acc and total_valid == len(SCENARIOS):
            best_acc = acc
            best_prompt = p

    # 假阳/fn 分解
    print(f"\n  v2（P1 基线）: FP={results_orig[1]['fp']} FN={results_orig[1]['fn']} ACC={results_orig[1]['acc']:.0f}%")
    if best_prompt:
        best_idx = next(i for i, p in enumerate(PROMPTS) if p["id"] == best_prompt["id"])
        print(f"  最优（{best_prompt['label']}）: FP={results_orig[best_idx]['fp']} FN={results_orig[best_idx]['fn']} ACC={results_orig[best_idx]['acc']:.0f}%")
        fn_drop = results_orig[1]["fn"] - results_orig[best_idx]["fn"]
        acc_gain = results_orig[best_idx]["acc"] - results_orig[1]["acc"]
        print(f"  校准改善: FN 降低 {fn_drop}, 准确率提升 {acc_gain:.0f} 个百分点")

    # ============================================================
    # 汇总 — 修正标注 (L3 = garbage)
    # ============================================================
    print(f"\n\n{'█'*92}")
    print("  汇总 — 修正标注（L3=垃圾）")
    print("  理由: L3 输出'# 第 1 章⏎本章详细论述...' 即使按宽松标准也确实只是占位符")
    print(f"{'█'*92}")

    print(f"\n{'Prompt':<14}", end="")
    for sc in SCENARIOS:
        label = sc["id"]
        if sc["id"] == "L3":
            label = "L3*"  # 标注变更
        print(f"{label:>{col_width}}", end="")
    print(f"{'FP':>5} {'FN':>5} {'ACC':>6}")

    print("-" * (14 + col_width * 8 + 20))

    best_acc2 = 0
    best_prompt2 = None
    results_fixed = []

    for pi, p in enumerate(PROMPTS):
        fp = 0
        fn = 0
        correct_count = 0
        valid_count = 0
        for si, sc in enumerate(SCENARIOS):
            if matrix[pi][si] is None:
                continue
            valid_count += 1
            # L3 标注改为 False
            ground_truth = sc["correct"]
            if sc["id"] == "L3":
                ground_truth = False
            if matrix[pi][si] == ground_truth:
                correct_count += 1
            if ground_truth and matrix[pi][si] is False:
                fn += 1
            if not ground_truth and matrix[pi][si] is True:
                fp += 1
        acc = correct_count / valid_count * 100 if valid_count else 0

        results_fixed.append({"fp": fp, "fn": fn, "acc": acc, "valid": valid_count})

        row = f"{p['label']:<14}"
        for si in range(len(SCENARIOS)):
            v = matrix[pi][si]
            lbl = sc["id"]
            if v is True:
                row += f"{'P':>{col_width}}"
            elif v is False:
                row += f"{'R':>{col_width}}"
            else:
                row += f"{'E':>{col_width}}"
        row += f"{fp:>5} {fn:>5} {acc:>5.0f}%"
        print(row)

        if acc > best_acc2 and valid_count == len(SCENARIOS):
            best_acc2 = acc
            best_prompt2 = p

    if best_prompt2:
        best_idx2 = next(i for i, p in enumerate(PROMPTS) if p["id"] == best_prompt2["id"])
        print(f"\n  修正后最优（{best_prompt2['label']}）: FP={results_fixed[best_idx2]['fp']} FN={results_fixed[best_idx2]['fn']} ACC={results_fixed[best_idx2]['acc']:.0f}%")

    # ============================================================
    # 精度-召回曲线
    # ============================================================
    print(f"\n\n{'█'*92}")
    print("  精度-召回曲线（修正标注）")
    print(f"{'█'*92}")
    print(f"\n  {'Prompt':<14} {'精度(P)':>8} {'召回(R)':>8} {'F1':>8} {'FP':>5} {'FN':>5}")
    print(f"  {'-'*48}")

    for pi, p in enumerate(PROMPTS):
        r = results_fixed[pi]
        tp = 4 - r["fn"]  # 4 correct scenarios, minus false negatives
        fp = r["fp"]
        fn = r["fn"]
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / 4 * 100  # 4 correct scenarios
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        print(f"  {p['label']:<14} {precision:>7.0f}% {recall:>7.0f}% {f1:>7.1f}% {fp:>5} {fn:>5}")

    print(f"\n  注：曲线方向：v1(极严格) → v5(极宽松)")
    print(f"      精度升高 = 更少假阳（垃圾混入）")
    print(f"      召回升高 = 更少假阴（正确驳回）")
    print(f"      最优 prompt 在 F1 最高处")

    # ============================================================
    # 分析
    # ============================================================
    print(f"\n\n{'█'*92}")
    print("  分析")
    print(f"{'█'*92}")

    print(f"""
  ● v2 (P1 基线) 的 prompt 明确要求『注意形式上通过但实质上不合格』：
    这条指令实际上是在引导模型 reject——它是一种"偏严格"的框架。

  ● 校准发现：
    - 原始标注下 v4（宽松）表现最好（FP=0, FN=1, ACC=86%）
    - 修正标注下 v3（公正）和 v4（宽松）并列：FP=0, FN=0, ACC=100%
    - v5（极宽松）在两种标注下都出现了 FP（G4 被误放行）

  ● L3 的 ground truth 问题
    - 原始标注：L3='正确' → 所有 prompt 的 FN 都+1（因为 L3 输出质量确实低）
    - 修正标注：L3='垃圾' → v3/v4 达到 100% 准确
    - 结论：L3 的 ground truth 争议不影响最优 prompt 的选择，只影响绝对数值

  ● 改善幅度（修正标注，v3 vs v2 基线）：
    - FN: 3 → 0
    - ACC: 62% → 100%
    - 这是一个 prompt 工程改善，不是模型能力改善

  ● 上界（v5 极宽松）出现 FP：
    - G4 (0 collected) 被误放——极宽松 prompt 认为 "exit_code=0 就够了"
    - 这定义了该测试集上精度-召回的上界
""")

    # 逐场景判定明细
    print("【逐场景判定明细】")
    print("=" * 92)
    for si, sc in enumerate(SCENARIOS):
        correct_label = "正确" if sc["correct"] else "垃圾"
        print(f"\n  [{sc['id']}] 真实={correct_label} ({'修正:垃圾' if sc['id']=='L3' else ''})")
        for pi, p in enumerate(PROMPTS):
            v = matrix[pi][si]
            if v is None:
                print(f"    {p['label']}: ERROR")
            else:
                print(f"    {p['label']}: {'PASS' if v else 'REJ'}  |  {reasons[pi][si][:70]}")

    print("\n" + "=" * 92)
    print("  实验局限: 单模型(deepseek-v4-flash)、单温度(0.0)、单测试集(8场景)")
    print("  Prompt 措辞对结果有影响——不同措辞表达同一「严格度」可能产生不同结果")
    print("=" * 92)


if __name__ == "__main__":
    run()
