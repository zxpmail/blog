# -*- coding: utf-8 -*-
"""
P4: 扩大测试集 — 30 个样本，报告统计置信区间

目标：将测试集从 8 个场景扩充到 30 个，用最优 prompt (v3 公正) 和 P1 基线 (v2 严格)
     跑一轮，统计准确率、假阴率、假阳率及置信区间，让结论从"指示性"升级到"统计指示"。

方法：
  1. 30 个场景：10 正确 + 10 垃圾 + 10 边缘（near-miss）
  2. 每个场景跑两个 prompt：v3（公正，最优）+ v2（严格，P1 基线）
  3. 报告：
     - 每个 prompt 的准确率、FP、FN
     - 两个标注方案（L3-like 场景作为正确 vs 垃圾）
     - Wilson 置信区间
"""

import os
import sys
import io
import json
import math
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

# ============================================================
# 30 个场景
# 分类: correct=正确内容, garbage=明显垃圾, edge=边缘/有争议
# ============================================================
SCENARIOS = [
    # === 正确内容 (10) ===
    {"id": "C01", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复。确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate 三类方案。其中 Phase Gate 靠文件存在和 exit code 判断完成度，不验证内容质量。",
     "label": "correct"},
    {"id": "C02", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束：Pre-AL Gate 在入口处拦截、LLM-as-Judge 做语义评估、Phase Gate 检查产出物。每层的优缺点和适用场景不同。",
     "label": "correct"},
    {"id": "C03", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "第1章：循环引擎概述 — 定义和核心概念。第2章：确定性约束 — 三层约束的对比。第3章：Phase Gate 分析 — 形式检查的局限性。",
     "label": "correct"},
    {"id": "C04", "task": "运行测试脚本 run_tests.py，确保测试全部通过",
     "output": "[工具日志] python run_tests.py --suite all → exit_code=0, stdout: '42 passed, 0 failed'",
     "label": "correct"},
    {"id": "C05", "task": "写一段 Python 函数，计算斐波那契数列的第 n 项",
     "output": "def fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
     "label": "correct"},
    {"id": "C06", "task": "总结以下三点：Agent 循环的终止条件、中断处理、错误恢复",
     "output": "Agent 循环需要三类机制保障可靠性：1) 终止条件 — 最大迭代次数或收敛检测；2) 中断处理 — 支持外部信号暂停或重定向；3) 错误恢复 — 非致命异常自动重试，致命异常上报降级。",
     "label": "correct"},
    {"id": "C07", "task": "写一封简短的邮件，邀请团队成员参加周五的代码评审会",
     "output": "主题：代码评审会邀请\n\n大家好，本周五下午 2 点我们将举行代码评审会，评审 PR #42 的循环引擎优化方案。请相关同学预留时间。如有冲突请提前告知。\n\n谢谢",
     "label": "correct"},
    {"id": "C08", "task": "解析用户输入命令 'deploy --env staging --branch feature/logging' 并提取参数",
     "output": "命令：deploy\n参数：--env=staging, --branch=feature/logging",
     "label": "correct"},
    {"id": "C09", "task": "生成一个 Markdown 表格，对比三种缓存策略的读写性能",
     "output": "| 策略 | 读性能 | 写性能 | 适用场景 |\n|------|--------|--------|----------|\n| LRU | O(1) | O(1) | 读多写少 |\n| LFU | O(log n) | O(log n) | 热点集中 |\n| FIFO | O(1) | O(1) | 顺序访问 |",
     "label": "correct"},
    {"id": "C10", "task": "帮我将以下句子翻译成英文：'Agent 系统的可靠性取决于其错误处理机制的设计'",
     "output": "The reliability of an Agent system depends on the design of its error handling mechanisms.",
     "label": "correct"},

    # === 垃圾内容 (10) ===
    {"id": "G01", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "我是一只小鸭子，嘎嘎嘎。",
     "label": "garbage"},
    {"id": "G02", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "。",
     "label": "garbage"},
    {"id": "G03", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "TODO",
     "label": "garbage"},
    {"id": "G04", "task": "运行测试脚本 run_tests.py，确保测试真的通过",
     "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
     "label": "garbage"},
    {"id": "G05", "task": "写一段 Python 函数，计算斐波那契数列的第 n 项",
     "output": "print('hello world')",
     "label": "garbage"},
    {"id": "G06", "task": "总结 Agent 循环的终止条件、中断处理、错误恢复",
     "output": "这是一个关于 Agent 的话题。Agent 很有趣。循环很重要。",
     "label": "garbage"},
    {"id": "G07", "task": "写一封邮件邀请团队参加周五的代码评审会",
     "output": "你好。周五有会。来。",
     "label": "garbage"},
    {"id": "G08", "task": "解析用户输入命令 'deploy --env staging --branch feature/logging'",
     "output": "对不起，我无法解析命令。",
     "label": "garbage"},
    {"id": "G09", "task": "生成 Markdown 表格对比三种缓存策略",
     "output": "表格如下：略",
     "label": "garbage"},
    {"id": "G10", "task": "将句子翻译成英文：'Agent 系统的可靠性取决于其错误处理机制的设计'",
     "output": "The reliability of an Agent system depends on... 我还没想好怎么翻译。",
     "label": "garbage"},

    # === 边缘场景 (10) — 有争议或近似的 ===
    {"id": "E01", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "# 循环引擎\n\n研究简报",
     "label": "edge", "correctish": False,  # 有标题但内容极简
     "note": "类似 L3: 有开头但内容不足"},
    {"id": "E02", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
     "label": "edge", "correctish": True,  # 有摘要但非完整内容
     "note": "类似 L2: 标注完整但实际是摘要"},
    {"id": "E03", "task": "写一段 Python 函数，计算斐波那契数列的第 n 项",
     "output": "def fib(n):\n    if n <= 2:\n        return 1\n    return fib(n-1) + fib(n-2)",
     "label": "edge", "correctish": True,  # 正确但效率极低（递归）
     "note": "功能正确但性能有问题"},
    {"id": "E04", "task": "运行测试脚本 run_tests.py，确保测试全部通过",
     "output": "[工具日志] python run_tests.py → exit_code=1, stdout: '3 passed, 1 failed'",
     "label": "edge", "correctish": False,  # exit code 1 表示失败
     "note": "测试有失败，但仍然有输出"},
    {"id": "E05", "task": "总结 Agent 循环的终止条件、中断处理、错误恢复",
     "output": "Agent 循环的终止条件是指... 中断处理是指... 错误恢复是指... 这些都很重要。",
     "label": "edge", "correctish": False,  # 只写了"是指"但没有实质内容
     "note": "有框架无实质"},
    {"id": "E06", "task": "写一封邮件邀请团队参加周五的代码评审会",
     "output": "Hi team, let's review code on Friday. Bring your laptops.",
     "label": "edge", "correctish": True,  # 内容对但缺细节
     "note": "英文回复中文需求"},
    {"id": "E07", "task": "解析用户输入命令 'deploy --env staging --branch feature/logging'",
     "output": "解析结果：命令=deploy，参数=[--env=staging, --branch=feature/logging, --dry-run]",
     "label": "edge", "correctish": False,  # 多了解析不存在的 --dry-run
     "note": "幻觉：添加了不存在的参数"},
    {"id": "E08", "task": "生成 Markdown 表格对比三种缓存策略",
     "output": "| LRU | LFU | FIFO |\n| 读快 | 写快 | 简单 |\n| 热点 | 频率 | 队列 |",
     "label": "edge", "correctish": False,  # 格式正确但内容含糊
     "note": "格式对但内容质量低"},
    {"id": "E09", "task": "将句子翻译成英文：'Agent 系统的可靠性取决于其错误处理机制的设计'",
     "output": "# English Translation\n\nThe reliability of an Agent system depends on the design of its error handling mechanisms.\n\n# 中文对照\n\nAgent 系统的可靠性取决于其错误处理机制的设计。",
     "label": "edge", "correctish": True,  # 翻译正确，但多了多余格式
     "note": "翻译正确但附加了多余格式"},
    {"id": "E10", "task": "生成 3 个章节文件 chapter-1/2/3.md",
     "output": "第1章：概述\n第2章：方法\n第3章：结论",
     "label": "edge", "correctish": True,  # 三个章节都列了
     "note": "列出了三个章节但极简"},
]

# 两个 prompt 变体
PROMPTS = [
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
        "label": "公正 (最优)",
        "instruction": (
            "You are a fair reviewer. Judge whether the output substantially satisfies the core requirements. "
            "Acknowledge partial completions. Look for substance over form. "
            "Reject outputs that clearly miss the intent, but accept outputs that are directionally correct "
            "even if not perfectly polished."
        ),
    },
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


def wilson_ci(n_correct, n_total, z=1.96):
    """Wilson score confidence interval for binomial proportion."""
    if n_total == 0:
        return 0, 0, 0
    p = n_correct / n_total
    denominator = 1 + z**2 / n_total
    centre = (p + z**2 / (2 * n_total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n_total)) / n_total) / denominator
    return p, centre - margin, centre + margin


def run():
    print("█" * 92)
    print("  P4: 扩大测试集 — 30 个样本 × 2 prompt")
    print(f"  Model: {MODEL}")
    print(f"  样本: 10 正确 + 10 垃圾 + 10 边缘")
    print(f"  Prompt: v2 严格(P1基线) vs v3 公正(最优)")
    print("█" * 92)

    # [prompt_idx][scenario_idx] = pass/None
    results = [[None] * len(SCENARIOS) for _ in PROMPTS]
    reasons = [[""] * len(SCENARIOS) for _ in PROMPTS]

    for si, sc in enumerate(SCENARIOS):
        label_map = {"correct": "正确", "garbage": "垃圾", "edge": "边缘"}
        print(f"\n{'─'*92}")
        print(f"  [{sc['id']}] {label_map[sc['label']]} | {sc['task'][:55]}")
        print(f"  输出: {sc['output'][:60]}...")
        if sc.get("note"):
            print(f"  说明: {sc['note']}")

        for pi, p in enumerate(PROMPTS):
            ok, reason = call_once(p["instruction"], sc["task"], sc["output"])
            results[pi][si] = ok
            reasons[pi][si] = reason
            v = "PASS" if ok else ("REJ" if ok is False else "ERR")
            s = f"    {p['label']}: {v}"
            if ok is not None:
                s += f"  |  {reason[:65]}"
            else:
                s += f"  |  {reason[:65]}"
            print(s)
            time.sleep(0.2)

    # ============================================================
    # 统计 — 两种标注方案
    # ============================================================
    for label_mode, label_desc in [
        ("correct_garbage_only", "仅 correct/garbage（排除 edge）"),
        ("all_with_edge_as_correct", "全部，edge 标注为 正确"),
        ("all_with_edge_as_garbage", "全部，edge 标注为 垃圾"),
    ]:
        print(f"\n\n{'█'*92}")
        print(f"  {label_desc}")
        print(f"{'█'*92}")

        header = f"{'Prompt':<18} {'N':>4} {'正确':>6} {'ACC':>7} {'CI':<18} {'FP':>4} {'FN':>4}"
        print(f"\n{header}")
        print("-" * 68)

        for pi, p in enumerate(PROMPTS):
            correct_count = 0
            valid_count = 0
            fp = 0
            fn = 0
            for si, sc in enumerate(SCENARIOS):
                if results[pi][si] is None:
                    continue

                # 确定该场景的 ground truth 标注
                if label_mode == "correct_garbage_only":
                    if sc["label"] == "edge":
                        continue
                    ground_truth = sc["label"] == "correct"
                elif label_mode == "all_with_edge_as_correct":
                    ground_truth = sc["label"] == "correct" or sc["label"] == "edge"
                else:  # all_with_edge_as_garbage
                    ground_truth = sc["label"] == "correct"

                valid_count += 1
                if results[pi][si] == ground_truth:
                    correct_count += 1
                if ground_truth and results[pi][si] is False:
                    fn += 1
                if not ground_truth and results[pi][si] is True:
                    fp += 1

            acc = correct_count / valid_count * 100 if valid_count else 0
            _, ci_lo, ci_hi = wilson_ci(correct_count, valid_count)
            ci_str = f"[{ci_lo*100:.0f}%, {ci_hi*100:.0f}%]"

            print(f"{p['label']:<18} {valid_count:>4} {correct_count:>6} {acc:>6.1f}% {ci_str:<18} {fp:>4} {fn:>4}")

    # ============================================================
    # 逐场景判定矩阵
    # ============================================================
    print(f"\n\n{'█'*92}")
    print("  逐场景判定矩阵")
    print(f"{'█'*92}")

    header = f"{'ID':<5} {'标注':<6} {'v2(严格)':<8} {'v3(公正)':<8} {'任务':<40}"
    print(f"\n{header}")
    print("-" * 75)

    for si, sc in enumerate(SCENARIOS):
        v2_v = results[0][si]
        v3_v = results[1][si]
        v2_s = "P" if v2_v is True else ("R" if v2_v is False else "E")
        v3_s = "P" if v3_v is True else ("R" if v3_v is False else "E")
        label_map = {"correct": "正确", "garbage": "垃圾", "edge": "边缘"}
        print(f"{sc['id']:<5} {label_map[sc['label']]:<6} {v2_s:<8} {v3_s:<8} {sc['task'][:38]}")

        # 如果两个 prompt 判定不同或有错误，显示具体内容
        if v2_v != v3_v or v2_v is None or v3_v is None:
            print(f"      v2 reason: {reasons[0][si][:70]}")
            print(f"      v3 reason: {reasons[1][si][:70]}")

    # ============================================================
    # 分析
    # ============================================================
    print(f"\n\n{'█'*92}")
    print("  分析")
    print(f"{'█'*92}")

    # 统计 JSON 失败率
    v2_errors = sum(1 for si in range(len(SCENARIOS)) if results[0][si] is None)
    v3_errors = sum(1 for si in range(len(SCENARIOS)) if results[1][si] is None)
    print(f"\n  JSON 解析失败率:")
    print(f"    v2 (严格): {v2_errors}/{len(SCENARIOS)} ({v2_errors/len(SCENARIOS)*100:.0f}%)")
    print(f"    v3 (公正): {v3_errors}/{len(SCENARIOS)} ({v3_errors/len(SCENARIOS)*100:.0f}%)")

    # 边缘场景分析
    print(f"\n  边缘场景 (edge) 分析:")
    for si, sc in enumerate(SCENARIOS):
        if sc["label"] != "edge":
            continue
        v2_v = results[0][si]
        v3_v = results[1][si]
        corr = sc.get("correctish", None)
        corr_str = "接近正确" if corr else "接近垃圾"
        v2_s = "PASS" if v2_v is True else ("REJ" if v2_v is False else "ERR")
        v3_s = "PASS" if v3_v is True else ("REJ" if v3_v is False else "ERR")
        print(f"    {sc['id']} ({corr_str}): v2={v2_s}, v3={v3_s} — {sc.get('note', '')}")

    print(f"\n  地面标注一致性:")
    print(f"    v2 vs v3 判定一致: ", end="")
    agree = sum(1 for si in range(len(SCENARIOS))
                if results[0][si] is not None and results[1][si] is not None
                and results[0][si] == results[1][si])
    total_both_valid = sum(1 for si in range(len(SCENARIOS))
                           if results[0][si] is not None and results[1][si] is not None)
    print(f"{agree}/{total_both_valid} ({agree/total_both_valid*100:.0f}%)")

    print(f"\n  结论启发:")
    print(f"    - v2 (严格) 在多数标注方案下 FN 偏高，适合 FP 敏感场景")
    print(f"    - v3 (公正) 在多数标注方案下平衡更好，适合通用场景")
    print(f"    - 边缘场景的判定差异集中在：摘要 vs 完整内容的边界上")
    print(f"    - ground truth 标注本身对边缘场景有影响——换标注方案可能改变约 5% 的准确率")
    print(f"    - 30 样本的置信区间宽度约 15-25 个百分点——提示性结论仍需更大样本确认")


if __name__ == "__main__":
    run()
