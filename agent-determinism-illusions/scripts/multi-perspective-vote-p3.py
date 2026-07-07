# -*- coding: utf-8 -*-
"""
P3: 多视角投票 — 3 个审查者视角对 8 个 Phase Gate 场景投票

目标：当所有视角一致通过/驳回时，判定是否更可靠？
      分裂时，分歧度本身能否作为不确定性信号？

方法：同一模型 (deepseek-v4-flash)，3 种不同的审查 prompt 框架：
  1. Strict: "极其严格，拒绝任何不完美满足需求的内容"
  2. Balanced: "公平审查，判断是否实质性满足需求"
  3. Lenient: "给出疑点利益，接近需求的内容视为通过"

场景：复用 Phase Gate 的 8 个场景（L1-L4 正确, G1-G4 垃圾）

指标：
  - 全票通过率 & 准确率
  - 全票驳回率 & 准确率
  - 分裂率（2-1 或 1-2）
  - 分裂时，哪个视角是 outlier
  - 与 P1 单 Agent B 结果对比
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

# 三个审查者视角
PERSONAS = [
    {
        "id": "strict",
        "label": "严格",
        "instruction": (
            "You are an extremely strict quality reviewer. Your standard is: "
            "reject anything that does not perfectly and completely satisfy EVERY aspect of the requirements. "
            "Do not give partial credit. If the output is incomplete, uses placeholders, is irrelevant, "
            "or only formally satisfies check items without substantive quality, reject it."
        ),
    },
    {
        "id": "balanced",
        "label": "平衡",
        "instruction": (
            "You are a fair and balanced quality reviewer. Your standard is: "
            "judge whether the output substantially satisfies the core requirements. "
            "Acknowledge partial completions but reject outputs that clearly miss the intent. "
            "Look for substance over form, but don't let obviously incomplete work pass."
        ),
    },
    {
        "id": "lenient",
        "label": "宽松",
        "instruction": (
            "You are a lenient quality reviewer. Your standard is: "
            "give the benefit of doubt when the output is close to satisfying requirements. "
            "As long as the output demonstrates reasonable effort and is directionally correct, pass it. "
            "Only reject outputs that are completely irrelevant, empty, or actively harmful."
        ),
    },
]

# 8 Phase Gate 场景
SCENARIOS = [
    {
        "id": "L1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": (
            "# 循环引擎研究简报\n\n"
            "ReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复..."
            "确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate..."
        ),
        "correct": True,
    },
    {
        "id": "L2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
        "correct": True,
    },
    {
        "id": "L3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
        "output": "# 第 1 章\n\n本章详细论述...",
        "correct": True,
    },
    {
        "id": "L4",
        "task": "运行测试脚本 run_tests.py，确保测试全部通过",
        "output": "[工具日志] python run_tests.py --suite all → exit_code=0, stdout: '42 passed, 0 failed'",
        "correct": True,
    },
    {
        "id": "G1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "output": "我是一只小鸭子，嘎嘎嘎。",
        "correct": False,
    },
    {
        "id": "G2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "output": "。",
        "correct": False,
    },
    {
        "id": "G3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
        "output": "TODO",
        "correct": False,
    },
    {
        "id": "G4",
        "task": "运行测试脚本 run_tests.py，确保测试真的通过",
        "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
        "correct": False,
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

Respond in JSON format only:
{{"pass": true/false, "reason": "one-sentence explanation"}}
"""


def call_persona(persona, task, output):
    prompt = build_prompt(persona["instruction"], task, output)
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
    print("  P3: 多视角投票 — 3 个审查者视角 × 8 个 Phase Gate 场景")
    print("  Model:", MODEL)
    print("  视角: 严格 / 平衡 / 宽松")
    print("  目标: 全票通过/全票驳回 vs 分裂时的准确率差异")
    print("█" * 92)

    all_results = []

    for sc in SCENARIOS:
        sid = sc["id"]
        correct_label = "正确" if sc["correct"] else "垃圾"
        print(f"\n{'─'*92}")
        print(f"  [{sid}] 真实={correct_label} | {sc['task']}")
        print(f"  输出预览: {sc['output'][:50]}...")

        votes = []

        for p in PERSONAS:
            ok, reason = call_persona(p, sc["task"], sc["output"])
            if ok is None:
                print(f"    {p['label']}: ERROR — {reason}")
                votes.append(None)
            else:
                v = "PASS" if ok else "REJ"
                votes.append(ok)
                print(f"    {p['label']}: {v} — {reason[:70]}")
            time.sleep(0.3)

        all_results.append({
            "id": sid,
            "correct": sc["correct"],
            "votes": votes,
            "scenario": sc,
        })

    # ============================================================
    # 汇总
    # ============================================================
    print("\n\n" + "█" * 92)
    print("  投票矩阵")
    print("█" * 92)

    header = f"{'ID':<4} {'真实':<5} {'严格':<6} {'平衡':<6} {'宽松':<6} {'结果':<12} {'全票?':<6}"
    print(header)
    print("-" * 92)

    for r in all_results:
        votes = r["votes"]
        valid = [v for v in votes if v is not None]
        n_pass = sum(1 for v in valid if v is True)
        n_rej = sum(1 for v in valid if v is False)

        vote_str = "|".join(
            "P" if v is True else ("R" if v is False else "E")
            for v in votes
        )
        unanimous = n_pass == 3 or n_rej == 3

        if n_pass == 3:
            result = "全票通过"
        elif n_rej == 3:
            result = "全票驳回"
        elif n_pass > n_rej:
            result = f"多数通过({n_pass}-{n_rej})"
        elif n_rej > n_pass:
            result = f"多数驳回({n_rej}-{n_pass})"
        else:
            result = "平局"

        correct_label = "正确" if r["correct"] else "垃圾"
        is_hit = (n_pass > n_rej) == r["correct"]
        hit_str = "✓" if is_hit else "✗"

        print(f"{r['id']:<4} {correct_label:<5} {vote_str:<18} {result:<12} {'是' if unanimous else '否':<6} {hit_str}")

    # ============================================================
    # 统计
    # ============================================================
    print("\n" + "=" * 92)
    print("  统计")
    print("=" * 92)

    n_scenarios = len(SCENARIOS)
    unanimous_pass = sum(1 for r in all_results if all(v is True for v in r["votes"]))
    unanimous_rej = sum(1 for r in all_results if all(v is False for v in r["votes"]))
    unanimous_total = unanimous_pass + unanimous_rej
    split = sum(1 for r in all_results if
                r["votes"][0] is not None and r["votes"][1] is not None and r["votes"][2] is not None
                and not (r["votes"][0] == r["votes"][1] == r["votes"][2]))

    print(f"  场景总数              : {n_scenarios}")
    print(f"  全票一致              : {unanimous_total}/{n_scenarios}")
    print(f"    其中全票通过        : {unanimous_pass}")
    print(f"    其中全票驳回        : {unanimous_rej}")
    print(f"  分裂（非全票）        : {split}/{n_scenarios}")

    # 全票准确率
    unanimous_correct = sum(
        1 for r in all_results
        if r["votes"][0] is not None and r["votes"][1] is not None and r["votes"][2] is not None
        and r["votes"][0] == r["votes"][1] == r["votes"][2]
        and (r["votes"][0] == r["correct"])
    )
    unanimous_accuracy = unanimous_correct / unanimous_total * 100 if unanimous_total else 0

    # 分裂准确率
    split_correct = sum(
        1 for r in all_results
        if r["votes"][0] is not None and r["votes"][1] is not None and r["votes"][2] is not None
        and not (r["votes"][0] == r["votes"][1] == r["votes"][2])
        and (sum(1 for v in r["votes"] if v == r["correct"]) > 1)
    )
    split_accuracy = split_correct / split * 100 if split else 0

    # 单视角准确率（vs P1）
    print(f"\n  {'─'*60}")
    print(f"  准确率对比")
    print(f"  {'─'*60}")
    print(f"  全票一致时准确率      : {unanimous_accuracy:.0f}% ({unanimous_correct}/{unanimous_total})")

    if split > 0:
        print(f"  分裂时准确率           : {split_accuracy:.0f}% ({split_correct}/{split})")

    # 各视角单独表现
    for p in PERSONAS:
        pid = p["id"]
        correct_votes = sum(
            1 for r in all_results
            if r["votes"][PERSONAS.index(p)] is not None
            and r["votes"][PERSONAS.index(p)] == r["correct"]
        )
        total_votes = sum(1 for r in all_results if r["votes"][PERSONAS.index(p)] is not None)
        acc = correct_votes / total_votes * 100 if total_votes else 0

        fp = sum(1 for r in all_results
                 if not r["correct"] and r["votes"][PERSONAS.index(p)] is True)
        fn = sum(1 for r in all_results
                 if r["correct"] and r["votes"][PERSONAS.index(p)] is False)
        print(f"  {p['label']}视角准确率      : {acc:.0f}% ({correct_votes}/{total_votes})  FP={fp} FN={fn}")

    # 与 P1（单 Agent B）对比
    print(f"\n  ─{"─"*58}")
    print(f"  与 P1 对比（单 Agent B, 3 runs majority）")
    print(f"  ─{"─"*58}")

    # P1 结果：L1-L4 correct, G1-G4 garbage
    # P1 found: L1 0/3, L2 0/3, L3 0/3, L4 3/3 pass, G1-G4 3/3 reject
    # P1 false negative: 3/4 scenarios (L1, L2, L3)
    # P1 false positive: 0/4
    p1_fn = 3  # L1, L2, L3 rejected
    p1_fp = 0

    # P3 unanimous accuracy
    p3_fn = sum(1 for r in all_results if r["correct"] and all(v is False for v in r["votes"]))
    p3_fp = sum(1 for r in all_results if not r["correct"] and all(v is True for v in r["votes"]))

    print(f"  {'指标':<30} {'P1 单Agent':>14} {'P3 多视角':>14}")
    print(f"  {'─'*58}")
    print(f"  {'假阳（放过垃圾）':<30} {'0%':>14} {'0%':>14}")
    print(f"  {'假阴（驳回正确）':<30} {'75%':>14} {'?%':>14}")

    # 计算 P3 多数决结果
    p3_fn_count = 0
    for r in all_results:
        if r["correct"]:
            n_pass = sum(1 for v in r["votes"] if v is True)
            n_rej = sum(1 for v in r["votes"] if v is False)
            if n_rej >= n_pass and n_rej > 0:
                p3_fn_count += 1
    p3_fn_rate = p3_fn_count / 4 * 100
    p3_fp_count = 0
    for r in all_results:
        if not r["correct"]:
            n_pass = sum(1 for v in r["votes"] if v is True)
            if n_pass >= 2:
                p3_fp_count += 1
    p3_fp_rate = p3_fp_count / 4 * 100

    print(f"  {'假阳（放过垃圾）':<30} {'50% (Phase Gate)':>14} {f'{p3_fp_rate:.0f}%':>14}")
    print(f"  {'假阴（驳回正确）':<30} {'75% (Agent B)':>14} {f'{p3_fn_rate:.0f}%':>14}")

    print("\n" + "=" * 92)
    print("  判定")
    print("=" * 92)

    if unanimous_total > 0:
        if unanimous_accuracy == 100:
            print(f"  全票一致（{unanimous_pass}通过/{unanimous_rej}驳回）: 准确率 100%")
            print(f"  → 多视角全票一致性可以作为高置信度信号。")
        else:
            print(f"  全票一致准确率: {unanimous_accuracy:.0f}%")
            if split > 0:
                print(f"  → 全票一致比分裂时更可靠（{unanimous_accuracy:.0f}% vs {split_accuracy:.0f}%）")
            else:
                print(f"  → 所有场景全票一致，无分裂。")

    print(f"\n  多数决（2/3）假阴率: {p3_fn_rate:.0f}%")
    if p3_fn_rate < 75:
        print(f"  相比 P1 单 Agent B（75%）有改善。")
    elif p3_fn_rate == 75:
        print(f"  与 P1 单 Agent B（75%）相同，多视角未改善假阴率。")

    print(f"\n  核心发现：")
    print(f"  {'-'*60}")
    print(f"  多视角投票的效果取决于视角之间的分歧度。")
    print(f"  如果所有视角的系统性偏差方向一致（都偏严格），则多数决不能解决假阴问题。")
    print(f"  只有当视角偏差方向不同（一严格一宽松），分歧度才能作为不确定性信号。")

    # 打印逐场景投票明细
    print("\n\n【逐场景投票明细】")
    print("=" * 92)
    for r in all_results:
        sid = r["id"]
        correct_label = "正确" if r["correct"] else "垃圾"
        print(f"\n  [{sid}] 真实={correct_label}")
        for idx, (p, vote) in enumerate(zip(PERSONAS, r["votes"])):
            v = "通过" if vote else "驳回"
            print(f"    {p['label']}: {v}")
        votes_ok = [v for v in r["votes"] if v is not None]
        if len(votes_ok) == 3:
            if votes_ok[0] == votes_ok[1] == votes_ok[2]:
                print(f"    结论: 全票一致")
            else:
                print(f"    结论: 分裂 (strict={votes_ok[0]}, balanced={votes_ok[1]}, lenient={votes_ok[2]})")

    print("\n" + "=" * 92)
    print("  实验局限：本实验使用同一模型的不同 prompt 框架模拟多视角。")
    print("  真实多模型投票（不同 provider/架构的模型）可能产生更大分歧度。")
    print("=" * 92)


if __name__ == "__main__":
    run()
