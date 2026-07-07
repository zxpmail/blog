# -*- coding: utf-8 -*-
"""
P1: 对抗性验证 — 单 Agent B 审查 8 个 Phase Gate 场景

目标：Phase Gate 假阳率 50% — Agent B (deepseek-v4-flash) 能否降到 ≤25%？

方法：
  1. 复用 Phase Gate 实验的 8 场景 (L1-L4 内容正确, G1-G4 内容垃圾)
  2. 对每个场景：把任务描述 + 产物喂给 Agent B, 问"输出是否满足需求"
  3. 每个场景跑 N=3 次 (原因是 temp=0 实验已证实 deepseek 不保证一致)
  4. 结果与 Phase Gate 的 100% 无差别通过对比

判定：
  - Agent B 的假阳率 < Phase Gate 的 50% → 对抗验证有效
  - Agent B 假阳率 ≤ 25% → P1 目标达成
  - Agent B 也放过垃圾 → 单 Agent 同样不够, 需要 P3 多模型投票
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
    print("缺少 ANTHROPIC_BASE_URL 或 token, 无法测试")
    sys.exit(1)

client = Anthropic(base_url=BASE_URL, api_key=TOKEN)

N_RUNS = 3  # 每个场景重复次数, 覆盖 LLM 自身的不一致

# ============================================================
# 8 个场景 (与 Phase Gate 实验一致)
# ============================================================
SCENARIOS = [
    {
        "id": "L1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": (
            "# 循环引擎研究简报\n\n"
            "ReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复..."
            "确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate..."
        ),
        "actually_correct": True,
    },
    {
        "id": "L2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
        "actually_correct": True,
    },
    {
        "id": "L3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
        "output": "# 第 1 章\n\n本章详细论述...",
        "actually_correct": True,
    },
    {
        "id": "L4",
        "task": "运行测试脚本 run_tests.py，确保测试全部通过",
        "output": "[工具日志] python run_tests.py --suite all → exit_code=0, stdout: '42 passed, 0 failed'",
        "actually_correct": True,
    },
    {
        "id": "G1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": "我是一只小鸭子，嘎嘎嘎。",
        "actually_correct": False,
        "why": "文件内容是鸭子话，与循环引擎完全无关",
    },
    {
        "id": "G2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "output": "。",
        "actually_correct": False,
        "why": "文件内容只有一个句号，没有任何正文",
    },
    {
        "id": "G3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
        "output": "TODO",
        "actually_correct": False,
        "why": "3 个文件内容全是 TODO 占位符",
    },
    {
        "id": "G4",
        "task": "运行测试脚本 run_tests.py，确保测试真的通过",
        "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
        "actually_correct": False,
        "why": "exit_code=0 但 0 个用例被执行",
    },
]


def build_judge_prompt(task, output):
    """构造对抗性审查 prompt, 要求 Agent B 严格判断内容是否真正满足需求。"""
    return f"""你是一个严格的质量审查员 (Agent B)。你的任务是判断一个 AI 助手的输出是否真正满足用户的需求。

## 用户需求
{task}

## AI 助手的输出
```
{output[:800]}
```

## 审查要求
请判断这个输出是否真正满足了用户需求。特别注意：
- 是否回避了核心要求（如内容质量、覆盖范围、实质性结果）
- 是否存在"形式上通过但实质上不合格"的情况
- 是否用占位符、空内容、无关内容糊弄

请用 JSON 格式输出你的判定，不要加其他文字：
{{"pass": true/false, "reason": "一句话解释"}}

其中 pass=true 表示你认定输出满足需求，pass=false 表示你认为输出不合格。
"""


def judge_once(task, output, run_idx):
    """单次调用 Agent B 审查, 返回 pass (bool) 和 reason (str)。"""
    prompt = build_judge_prompt(task, output)
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
        # 解析 JSON
        text = text.strip()
        # 去掉可能的 markdown 代码块包裹
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0] if "```" in text else text
            text = text.strip()
        data = json.loads(text)
        return data.get("pass", False), data.get("reason", "无法解析原因")
    except (json.JSONDecodeError, Exception) as e:
        return None, f"调用失败: {e}"


def run():
    print("█" * 92)
    print("  P1: 对抗性验证 — 单 Agent B 审查 8 个 Phase Gate 场景")
    print(f"  审查模型: {MODEL}  |  每场景 N={N_RUNS} 次  |  temperature=0.0")
    print("  目标：Phase Gate 假阳率 50% → Agent B 能否降到 ≤25%？")
    print("█" * 92)

    all_results = []
    for sc in SCENARIOS:
        sid = sc["id"]
        print(f"\n{'─'*92}")
        print(f"  场景 {sid}: {sc['task']}")
        print(f"  输出: {sc['output'][:60]}...")
        print(f"  真实标注: {'正确' if sc['actually_correct'] else '垃圾'}")

        passes = []
        reasons = []
        for i in range(N_RUNS):
            ok, reason = judge_once(sc["task"], sc["output"], i)
            if ok is None:
                print(f"    [{i+1}] 调用异常: {reason}")
                continue
            passes.append(ok)
            reasons.append(reason)
            verdict = "通过" if ok else "驳回"
            print(f"    [{i+1}] {verdict} — {reason}")
            time.sleep(0.3)

        all_results.append({
            "id": sid,
            "task": sc["task"],
            "actually_correct": sc["actually_correct"],
            "passes": passes,
            "reasons": reasons,
            "why": sc.get("why", ""),
        })

    # ============================================================
    # 汇总
    # ============================================================
    print("\n\n" + "█" * 92)
    print("  汇总")
    print("█" * 92)

    header = f"{'ID':<4} {'真实':<5} {'Agent B判定':<22} {'多数意见':<8} {'Phase Gate':<10}"
    print(header)
    print("-" * 92)

    gate_fp = 0  # Phase Gate 假阳 (放过垃圾)
    gate_total = 0
    agent_fp = 0  # Agent B 假阳 (放过垃圾)
    agent_fn = 0  # Agent B 假阴 (驳回正确内容)
    agent_discarded = 0  # 无法判定
    total = len(SCENARIOS)

    for r in all_results:
        n_pass = sum(1 for p in r["passes"] if p is True)
        n_fail = sum(1 for p in r["passes"] if p is False)
        n_err = sum(1 for p in r["passes"] if p is None)
        majority_pass = n_pass > n_fail
        gate_pass = True  # Phase Gate 对所有场景无差别通过

        if r["actually_correct"]:
            truth = "正确"
        else:
            truth = "垃圾"

        if majority_pass:
            agent_verdict = "通过"
        elif n_pass == n_fail:
            agent_verdict = "平局"
        else:
            agent_verdict = "驳回"

        print(f"{r['id']:<4} {truth:<5} {agent_verdict:<22} {n_pass}/{N_RUNS}通过{'':>4} {'通过' if gate_pass else '×':<10}")

        # 统计
        gate_total += 1
        if gate_pass and not r["actually_correct"]:
            gate_fp += 1

        if r["actually_correct"] and not majority_pass and n_pass <= n_fail:
            agent_fn += 1
        if not r["actually_correct"] and majority_pass:
            agent_fp += 1
        if n_err >= n_pass and n_err > 0:
            agent_discarded += 1

    # 打印详细对比
    print("\n" + "─" * 46 + " 对比 " + "─" * 46)
    print(f"{'指标':<30} {'Phase Gate':>14} {'Agent B':>14}")
    print("─" * 92)
    print(f"{'通过率 (全部场景)':<30} {'100%':>14} {'?':>14}")
    print(f"{'假阳率 (放过垃圾)':<30} {'50%':>14} {'?':>14}")
    print(f"{'假阴率 (驳回正确)':<30} {'0%':>14} {'?':>14}")

    # 精确计算
    correct_scenarios = [r for r in all_results if r["actually_correct"]]
    garbage_scenarios = [r for r in all_results if not r["actually_correct"]]

    # Agent B 假阳：垃圾场景中被判通过的比例
    agent_false_pass = sum(
        1 for r in garbage_scenarios
        if sum(1 for p in r["passes"] if p is True) > sum(1 for p in r["passes"] if p is False)
    )
    # Agent B 假阴：正确场景中被判驳回的比例
    agent_false_fail = sum(
        1 for r in correct_scenarios
        if sum(1 for p in r["passes"] if p is False) > sum(1 for p in r["passes"] if p is True)
    )
    # 平局
    agent_tie = sum(
        1 for r in all_results
        if sum(1 for p in r["passes"] if p is True) == sum(1 for p in r["passes"] if p is False)
        and sum(1 for p in r["passes"] if p is not None) > 0
    )

    total_garbage = len(garbage_scenarios)
    total_correct = len(correct_scenarios)

    print("\n" + "=" * 92)
    print(" 【Agent B 审查结果】")
    print("=" * 92)
    print(f"  场景总数          : {total}")
    print(f"  其中正确内容      : {total_correct}")
    print(f"  其中垃圾内容      : {total_garbage}")
    print(f"  Agent B 平局(无法多数决): {agent_tie}")
    print(f"  Agent B 假阳(放过垃圾) : {agent_false_pass}/{total_garbage}  ({agent_false_pass/total_garbage*100:.0f}%)")
    print(f"  Agent B 假阴(驳回正确) : {agent_false_fail}/{total_correct}  ({agent_false_fail/total_correct*100:.0f}%)")

    print(f"\n  Phase Gate 假阳率     : 50%")
    print(f"  Agent B 假阳率       : {agent_false_pass/total_garbage*100:.0f}%")
    if agent_false_pass / total_garbage <= 0.25:
        print(f"\n  ★ 目标达成: Agent B 假阳率 ≤ 25%, 对抗验证有效降低 Phase Gate 假阳。")
    else:
        print(f"\n  △ 目标未完全达成: Agent B 假阳率仍 > 25%。")
        print(f"     单 Agent 审查同样不够。需要 P3 (多模型投票) 或人机协同。")

    # 输出每场景的逐次判定, 便于分析
    print("\n\n【逐场景逐次判定明细】")
    print("=" * 92)
    for r in all_results:
        print(f"\n  {r['id']} | 真实={'正确' if r['actually_correct'] else '垃圾'}")
        for i, (p, reason) in enumerate(zip(r["passes"], r["reasons"])):
            v = "通过" if p else "驳回"
            print(f"    Run {i+1}: {v}  |  {reason}")
        if not r["actually_correct"]:
            print(f"    问题: {r['why']}")

    print("\n" + "=" * 92)
    print('  判定: 单 Agent 对抗验证的结果取决于它能否在"语义鸿沟"上跨过去。')
    print("  Phase Gate 的问题是只检查动作, Agent B 被要求检查意图+内容质量。")
    print("  如果 Agent B 同样放过垃圾 → 说明 LLM-as-Judge 本身也有盲区。")
    print("=" * 92)


if __name__ == "__main__":
    run()
