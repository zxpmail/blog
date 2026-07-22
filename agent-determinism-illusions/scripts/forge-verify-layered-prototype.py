#!/usr/bin/env python3
"""
实验 F: 分层审查原型 — Layer 0/1 确定性检查 + Layer 2 LLM 瘦审查

在 P1(8场景) + P4(30样本) 上验证社区提出的分层架构:

  Layer 0  形状/存在性 → 正则、长度、关键字黑名单  (零成本)
  Layer 1  期望匹配   → task pre-run contract      (零成本)
  Layer 2  语义充分性 → LLM 只处理残差             (有成本)
  Layer 3  分歧/残差 → 人工 (本实验不模拟)

目标:
  1) 多少垃圾场景在 Layer 0/1 就被拦截 — 不需要 LLM 参与?
  2) 瘦身后 LLM 只处理语义残差, 假阴率是否改善?
  3) Layer 0/1 的零成本拦截能节省多少 LLM 调用?

对照基线: P1 Agent B (8 场景, 3 次多数决) + P4 v3 公正 prompt

依赖: ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN (同系列其他实验)
      设 SKIP_LLM=1 可只跑 Layer 0/1, 不调 API

用法:
  python forge-verify-layered-prototype.py              # 完整实验
  SKIP_LLM=1 python forge-verify-layered-prototype.py   # 只跑确定性部分
"""

import json, os, sys, io, re, math, time
from collections import Counter

# stdout UTF-8 wrap 仅在 __main__；被 harness-kernel import 时不得改写 stdout（会破坏 NDJSON）

# ── 配置 ──────────────────────────────────────────────────────────
MODEL    = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-flash")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
TOKEN    = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
SKIP_LLM = os.environ.get("SKIP_LLM", "0") == "1"

HAVE_API = bool(BASE_URL and TOKEN) and not SKIP_LLM
N_RUNS   = 3  # Layer 2 投票重复次数

# ── Layer 0: 确定性形状检查 ────────────────────────────────────────
def layer0_check(content: str) -> dict:
    """返回 {'verdict': 'PASS'|'REJECT', 'reason': str, 'check': str}"""
    c = content.strip()

    # 0a. 空或极短
    if len(c) < 5:
        return {"verdict": "REJECT", "reason": f"内容极短({len(c)}字符), 无法构成有效输出", "check": "L0_min_length"}

    # 0b. 纯标点 / 纯无意义符号
    punct_ratio = sum(1 for ch in c if ch in "。，、！？；：.。，!?;:,，''""") / max(len(c), 1)
    if punct_ratio > 0.5:
        return {"verdict": "REJECT", "reason": f"标点占比 {punct_ratio:.0%}, 超过 50% 阈值", "check": "L0_punctuation_ratio"}

    # 0c. 占位符关键词
    placeholders = ["todo", "fixme", "tbd", "xxx", "待填写", "这里填写"]
    for ph in placeholders:
        if ph in c.lower():
            # 只有占位符没有正文才算
            if len(c) < 30:
                return {"verdict": "REJECT", "reason": f"内容包含占位符 '{ph}' 且长度极短({len(c)})", "check": "L0_placeholder"}

    # 0d. 0 passed / no tests collected
    if re.search(r'\b0\s+passed\b', c, re.IGNORECASE) and re.search(r'no tests?\s+collected', c, re.IGNORECASE):
        return {"verdict": "REJECT", "reason": "测试结果: 0 passed, no tests collected — 零用例通过", "check": "L0_zero_tests"}

    return {"verdict": "PASS", "reason": "Layer 0 通过", "check": "L0_pass"}


# ── Layer 1: Task 期望匹配 ─────────────────────────────────────────
# 与 task 关联的"预查合约": 期望的关键词、最小长度、结构特征
TASK_CONTRACTS = {
    "research_brief": {
        "min_len": 100,
        "keywords": ["循环", "引擎", "ReAct", "Agent", "Phase Gate", "LLM"],
        "expect_heading": True,
    },
    "draft": {
        "min_len": 200,
        "keywords": ["机制", "约束", "确定", "生产"],
        "expect_heading": True,
    },
    "chapter": {
        "min_len": 50,
        "keywords": ["章", "节", "第"],
        "expect_heading": True,
    },
    "test_pass": {
        "min_len": 10,
        "keywords": ["pass", "failed", "exit_code", "测试"],
        "expect_heading": False,
    },
    "code": {
        "min_len": 30,
        "keywords": ["def ", "function", "return"],
        "expect_heading": False,
    },
    "summary": {
        "min_len": 80,
        "keywords": ["终止", "中断", "错误", "恢复"],
        "expect_heading": True,
    },
    "email": {
        "min_len": 40,
        "keywords": ["主题", "你好", "大家", "谢谢", "team", "review", "meeting", "Friday"],
        "expect_heading": True,
    },
    "parse": {
        "min_len": 10,
        "keywords": ["deploy", "env", "branch"],
        "expect_heading": False,
    },
    "table": {
        "min_len": 30,
        "keywords": ["|", "LRU", "LFU", "FIFO", "缓存"],
        "expect_heading": False,
    },
    "translate": {
        "min_len": 10,
        "keywords": ["reliability", "design", "depends"],
        "expect_heading": False,
    },
}

def classify_task(task_text: str) -> str:
    """基于 task 文本分类到预查合约类型"""
    t = task_text.lower()
    if "循环引擎" in t or "研究简报" in t:
        return "research_brief"
    if "初稿" in t or "三个核心" in t:
        return "draft"
    if "章节" in t or "chapter" in t:
        return "chapter"
    if "测试" in t or "test" in t or "run_tests" in t:
        return "test_pass"
    if "斐波那契" in t or "fibonacci" in t or "函数" in t or "python" in t:
        return "code"
    if "总结" in t or "终止条件" in t:
        return "summary"
    if "邮件" in t or "代码评审" in t or "review" in t:
        return "email"
    if "解析" in t or "命令" in t or "deploy" in t:
        return "parse"
    if "表格" in t or "markdown" in t or "缓存" in t or "table" in t:
        return "table"
    if "翻译" in t or "translate" in t or "英文" in t:
        return "translate"
    return "research_brief"  # fallback


def layer1_check(content: str, task: str) -> dict:
    """按 task 期望检查。{'verdict': 'PASS'|'REJECT'|'UNCLEAR', ...}"""
    c = content.strip()
    task_type = classify_task(task)
    contract = TASK_CONTRACTS.get(task_type, TASK_CONTRACTS["research_brief"])

    failures = []

    # 1a. 最小长度
    if len(c) < contract["min_len"]:
        failures.append(f"长度不足: {len(c)} < {contract['min_len']}")

    # 1b. 关键词匹配
    matched_kw = [kw for kw in contract["keywords"] if kw.lower() in c.lower()]
    # 要求至少匹配预期关键词中的 1/3 (向上取整)
    required = max(1, math.ceil(len(contract["keywords"]) / 3))
    if len(matched_kw) < required:
        failures.append(f"关键词匹配不足: 命中 {len(matched_kw)}/{len(contract['keywords'])}, 需 ≥{required}")

    # 1c. Heading 期望
    heading_patterns = [r'^#', r'^#{2,3}\s', r'^主题:', r'^Subject:', r'^##']
    has_heading = any(re.search(p, c, re.MULTILINE) for p in heading_patterns)
    if contract["expect_heading"] and not has_heading:
        failures.append("缺少标题/主题行")

    if not failures:
        return {"verdict": "PASS", "reason": "Layer 1 合约匹配通过", "check": "L1_pass"}

    if len(failures) >= 2:
        return {"verdict": "REJECT", "reason": "; ".join(failures), "check": "L1_reject"}

    # 单项失败 = UNCLEAR (模糊, 交给 Layer 2)
    return {"verdict": "UNCLEAR", "reason": "; ".join(failures), "check": "L1_unclear"}


# ── Layer 2: 瘦 LLM 审查 ────────────────────────────────────────────
THIN_PROMPT = """You are a quality inspector.

The output below has already passed basic format checks:
- It is not empty, not pure punctuation, not a placeholder
- It meets minimum length requirements
- It contains some expected keywords

Your job is ONLY to judge the SEMANTIC dimension:
Does this output substantively satisfy the CORE requirements of the task?

DO NOT reject for missing keywords, short length, or formatting.
Only reject if the output fundamentally misses the INTENT of the task.

TASK: {task}

OUTPUT:
```
{content}
```

Respond in JSON only:
{{"pass": true/false, "reason": "one-sentence reason focusing on semantic sufficiency"}}
"""


def call_llm(prompt: str, temp: float = 0.0):
    """调用 LLM API (OpenAI-compatible / Anthropic)"""
    from anthropic import Anthropic

    client = Anthropic(base_url=BASE_URL, api_key=TOKEN)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=256,
            temperature=temp,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", "") == "text"
        )
        text = text.strip()
        # unwrap markdown
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0] if "```" in text else text
            text = text.strip()
        data = json.loads(text)
        return data.get("pass", None), data.get("reason", "")
    except Exception as e:
        return None, f"API ERROR: {e}"


def layer2_check(content: str, task: str) -> dict:
    """瘦 LLM: 只问语义充分性, N 次投票"""
    if not HAVE_API:
        return {"verdict": "SKIP", "reason": "API 未配置或 SKIP_LLM=1", "check": "L2_skip"}

    prompt = THIN_PROMPT.format(task=task, content=content[:1500])
    passes = []
    reasons = []

    for i in range(N_RUNS):
        ok, reason = call_llm(prompt)
        if ok is not None:
            passes.append(ok)
            reasons.append(reason)
        time.sleep(0.15)

    if not passes:
        return {"verdict": "UNCLEAR", "reason": "所有 LLM 调用失败", "check": "L2_error"}

    pass_cnt = sum(1 for p in passes if p)
    rej_cnt = sum(1 for p in passes if p is False)
    total = len(passes)

    # 分歧 > 0.8 阈值 → UNCLEAR (转 Layer 3)
    max_frac = max(pass_cnt, rej_cnt) / total
    if max_frac < 0.8:
        return {
            "verdict": "UNCLEAR",
            "reason": f"分歧: {pass_cnt}PASS/{rej_cnt}REJ (max_frac={max_frac:.0%})",
            "check": "L2_divergence",
        }

    verdict = "PASS" if pass_cnt > rej_cnt else "REJECT"
    return {"verdict": verdict, "reason": reasons[0], "check": "L2_verdict"}


# ── 完整分层管道 ────────────────────────────────────────────────────
def layered_judge(content: str, task: str) -> dict:
    """
    按 L0 → L1 → L2 → (L3 占位) 顺序检查。
    返回: {verdict, layer_stopped, details, ...}
    """
    result = {"content_preview": content[:60], "task_preview": task[:50]}

    # Layer 0
    l0 = layer0_check(content)
    result["L0"] = l0
    if l0["verdict"] == "REJECT":
        result["verdict"] = "REJECT"
        result["layer"] = "L0"
        result["final_verdict"] = "REJECT"
        return result

    # Layer 1
    l1 = layer1_check(content, task)
    result["L1"] = l1
    if l1["verdict"] == "REJECT":
        result["verdict"] = "REJECT"
        result["layer"] = "L1"
        result["final_verdict"] = "REJECT"
        return result

    # Layer 1 UNCLEAR → 继续到 Layer 2
    # Layer 1 PASS → 继续到 Layer 2 做语义确认

    # Layer 2
    l2 = layer2_check(content, task)
    result["L2"] = l2
    if l2["verdict"] in ("PASS", "REJECT", "UNCLEAR"):
        result["verdict"] = l2["verdict"]
        result["layer"] = "L2"
        result["final_verdict"] = l2["verdict"]
        return result

    # fallback
    result["verdict"] = "UNCLEAR"
    result["layer"] = "L2"
    result["final_verdict"] = "UNCLEAR"
    return result


# ── P1 的 8 场景 ────────────────────────────────────────────────────
P1_SCENARIOS = [
    {"id": "L1", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复...确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate...",
     "correct": True},
    {"id": "L2", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
     "correct": True},
    {"id": "L3", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "# 第 1 章\n\n本章详细论述...",
     "correct": True},
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

# ── P4 的 30 样本 ───────────────────────────────────────────────────
P4_SCENARIOS = [
    # 正确 C01-C10
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

    # 垃圾 G01-G10
    {"id": "G01", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "我是一只小鸭子，嘎嘎嘎。", "label": "garbage"},
    {"id": "G02", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "。", "label": "garbage"},
    {"id": "G03", "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "output": "TODO", "label": "garbage"},
    {"id": "G04", "task": "运行测试脚本 run_tests.py，确保测试真的通过",
     "output": "[工具日志] python run_tests.py → exit_code=0, stdout: '0 passed in 0.00s (no tests collected)'",
     "label": "garbage"},
    {"id": "G05", "task": "写一段 Python 函数，计算斐波那契数列的第 n 项",
     "output": "print('hello world')", "label": "garbage"},
    {"id": "G06", "task": "总结 Agent 循环的终止条件、中断处理、错误恢复",
     "output": "这是一个关于 Agent 的话题。Agent 很有趣。循环很重要。",
     "label": "garbage"},
    {"id": "G07", "task": "写一封邮件邀请团队参加周五的代码评审会",
     "output": "你好。周五有会。来。", "label": "garbage"},
    {"id": "G08", "task": "解析用户输入命令 'deploy --env staging --branch feature/logging'",
     "output": "对不起，我无法解析命令。", "label": "garbage"},
    {"id": "G09", "task": "生成 Markdown 表格对比三种缓存策略",
     "output": "表格如下：略", "label": "garbage"},
    {"id": "G10", "task": "将句子翻译成英文：'Agent 系统的可靠性取决于其错误处理机制的设计'",
     "output": "The reliability of an Agent system depends on... 我还没想好怎么翻译。",
     "label": "garbage"},

    # 边缘 E01-E10
    {"id": "E01", "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "output": "# 循环引擎\n\n研究简报",
     "label": "edge", "correctish": False,
     "note": "有标题但内容极简"},
    {"id": "E02", "task": "写初稿 draft.md，至少覆盖三个核心机制",
     "output": "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）",
     "label": "edge", "correctish": True,
     "note": "类似 L2"},
    {"id": "E03", "task": "写一段 Python 函数，计算斐波那契数列的第 n 项",
     "output": "def fib(n):\n    if n <= 2:\n        return 1\n    return fib(n-1) + fib(n-2)",
     "label": "edge", "correctish": True,
     "note": "功能正确但递归效率低"},
    {"id": "E04", "task": "运行测试脚本 run_tests.py，确保测试全部通过",
     "output": "[工具日志] python run_tests.py → exit_code=1, stdout: '3 passed, 1 failed'",
     "label": "edge", "correctish": False,
     "note": "测试有失败"},
    {"id": "E05", "task": "总结 Agent 循环的终止条件、中断处理、错误恢复",
     "output": "Agent 循环的终止条件是指... 中断处理是指... 错误恢复是指... 这些都很重要。",
     "label": "edge", "correctish": False,
     "note": "有框架无实质"},
    {"id": "E06", "task": "写一封邮件邀请团队参加周五的代码评审会",
     "output": "Hi team, let's review code on Friday. Bring your laptops.",
     "label": "edge", "correctish": True,
     "note": "英文回复中文需求"},
    {"id": "E07", "task": "解析用户输入命令 'deploy --env staging --branch feature/logging'",
     "output": "解析结果：命令=deploy，参数=[--env=staging, --branch=feature/logging, --dry-run]",
     "label": "edge", "correctish": False,
     "note": "幻觉：添加不存在的 --dry-run"},
    {"id": "E08", "task": "生成 Markdown 表格对比三种缓存策略",
     "output": "| LRU | LFU | FIFO |\n| 读快 | 写快 | 简单 |\n| 热点 | 频率 | 队列 |",
     "label": "edge", "correctish": False,
     "note": "格式对但内容含糊"},
    {"id": "E09", "task": "将句子翻译成英文：'Agent 系统的可靠性取决于其错误处理机制的设计'",
     "output": "# English Translation\n\nThe reliability of an Agent system depends on the design of its error handling mechanisms.\n\n# 中文对照\n\nAgent 系统的可靠性取决于其错误处理机制的设计。",
     "label": "edge", "correctish": True,
     "note": "翻译正确但附加多余格式"},
    {"id": "E10", "task": "生成 3 个章节文件 chapter-1/2/3.md",
     "output": "第1章：概述\n第2章：方法\n第3章：结论",
     "label": "edge", "correctish": True,
     "note": "三个章节都列了但极简"},
]


# ── 报告 ────────────────────────────────────────────────────────────
def wilson_ci(n, N, z=1.96):
    if N == 0:
        return 0, 0, 0
    p = n / N
    d = 1 + z**2 / N
    c = (p + z**2 / (2 * N)) / d
    m = z * math.sqrt((p * (1 - p) + z**2 / (4 * N)) / N) / d
    return p, c - m, c + m


def run_headline(which, scenarios, llm_enabled):
    """跑一批场景, 返回统计"""
    print(f"\n{'█'*78}")
    print(f"  {which}")
    print(f"  Layer 2: {'LLM (' + MODEL + ')' if llm_enabled else 'SKIP（只跑确定性部分）'}")
    print(f"{'█'*78}")

    results = []
    for sc in scenarios:
        content = sc["output"]
        task = sc["task"]
        correct = sc.get("correct", sc.get("label") == "correct" or (sc.get("label") == "edge" and sc.get("correctish", False)))

        r = layered_judge(content, task)
        r["id"] = sc["id"]
        r["correct"] = correct
        r["label"] = sc.get("label", "unknown")
        r["note"] = sc.get("note", "")
        results.append(r)

        # 单行输出
        final = r.get("final_verdict", "?")
        layer = r.get("layer", "?")
        is_right = (final == "PASS") == correct if final in ("PASS", "REJECT") else None
        mark = "✓" if is_right is True else ("✗" if is_right is False else "?")

        print(f"  {sc['id']:<5} {final:<8} @ {layer:<3} {mark}  {task[:45]}")

        if final != "PASS" and final != "REJECT":
            reason = r.get("L2", {}).get("reason", r.get("L1", {}).get("reason", ""))
            if reason:
                print(f"         → {reason[:55]}")

    # ── 统计 ──
    n = len(results)

    by_layer = Counter(r.get("layer", "?") for r in results)
    by_verdict = Counter(r.get("final_verdict", "?") for r in results)

    # 各 layer 停止数
    l0_stop = by_layer.get("L0", 0)
    l1_stop = by_layer.get("L1", 0)
    l2_reach = by_layer.get("L2", 0)

    # 正确性 (对有明显正确标签的场景)
    valid = [r for r in results if r.get("final_verdict") in ("PASS", "REJECT")]
    correct_count = sum(1 for r in valid
                        if (r["final_verdict"] == "PASS") == r["correct"])
    correct_pct = correct_count / len(valid) * 100 if valid else 0
    _, ci_lo, ci_hi = wilson_ci(correct_count, len(valid))

    # FP / FN
    fp = sum(1 for r in valid if not r["correct"] and r["final_verdict"] == "PASS")
    fn = sum(1 for r in valid if r["correct"] and r["final_verdict"] == "REJECT")

    print(f"\n  {'─'*60}")
    print(f"  停止层: L0={l0_stop}  L1={l1_stop}  L2={l2_reach}")
    print(f"  LLM 调用节省: {l0_stop + l1_stop}/{n} ({(l0_stop + l1_stop)/n*100:.0f}%)")
    print(f"  FP(放过垃圾): {fp}  FN(误杀正确): {fn}")
    print(f"  准确率: {correct_count}/{len(valid)} = {correct_pct:.1f}%  CI=[{ci_lo*100:.0f}%, {ci_hi*100:.0f}%]")
    print(f"  {'─'*60}")

    return {
        "n": n,
        "l0_stop": l0_stop,
        "l1_stop": l1_stop,
        "l2_reach": l2_reach,
        "llm_save": (l0_stop + l1_stop) / n,
        "fp": fp,
        "fn": fn,
        "correct": correct_count,
        "valid": len(valid),
        "accuracy": correct_pct,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "results": results,
    }


def compare_to_baseline(p1_result, p4_result):
    """与 P1 和 P4 原始结果对比"""
    print(f"\n\n{'█'*78}")
    print("  与原始实验对比")
    print(f"{'█'*78}")

    # P1 基线: Layer 0/1 节省, FP/FN 变化
    print(f"""
  ┌─────────────────────────────────────────────────────────────┐
  │  P1 (8 场景) 对比                                           │
  ├──────────────────────┬──────────┬──────────┬────────────────┤
  │  指标                 │ P1 原始   │ 分层(本实验) │ 变化           │
  ├──────────────────────┼──────────┼──────────┼────────────────┤""")

    p1_save = p1_result["llm_save"] * 100
    print(f"  │  LLM 调用减少        │ 0%       │ {p1_save:>6.0f}%   │ {'+' if p1_save > 0 else ''}{p1_save:.0f}%           │")

    p1_fp_orig = 0  # P1 Agent B 假阳
    p1_fn_orig = 3  # P1 Agent B 假阴 (L1, L2, L3)
    fp_change = p1_result["fp"] - p1_fp_orig
    fn_change = p1_result["fn"] - p1_fn_orig
    print(f"  │  FP (放过垃圾)        │ {p1_fp_orig}         │ {p1_result['fp']}          │ {'↓' if fp_change < 0 else '↑' if fp_change > 0 else '='} {abs(fp_change) if fp_change else '0'}             │")
    print(f"  │  FN (误杀正确)        │ {p1_fn_orig}         │ {p1_result['fn']}          │ {'↓' if fn_change < 0 else '↑' if fn_change > 0 else '='} {abs(fn_change) if fn_change else '0'}             │")

    print(f"  ├──────────────────────┴──────────┴──────────┴────────────────┤")

    # P4 基线
    print(f"""
  │  P4 (30 样本) 对比                                          │
  ├──────────────────────┬──────────┬──────────┬────────────────┤""")

    p4_save = p4_result["llm_save"] * 100
    print(f"  │  LLM 调用减少        │ 0%       │ {p4_save:>6.0f}%   │ {'+' if p4_save > 0 else ''}{p4_save:.0f}%           │")

    # P4 v3 公正: 排除边缘时 88.2%, FP/FN 各? 从原始数据看
    # P4 原文: 排除边缘, 两者都是 88.2%, v2/v3 FP/FN 一样
    print(f"  │  准确率(排除边缘)    │ 88.2%    │ {p4_result['accuracy']:>5.1f}%   │ {p4_result['accuracy'] - 88.2:+.1f}%        │")

    print(f"""  │  LLM 调用次数         │ {p4_result['n']:>4d}     │ {p4_result['l2_reach']:>4d}     │ -{p4_result['l0_stop'] + p4_result['l1_stop']}              │
  └──────────────────────┴──────────┴──────────┴────────────────┘""")


# ════════════════════════ 主流程 ═══════════════════════════════
def main():
    llm_avail = HAVE_API

    if not llm_avail:
        print("=" * 78)
        print("  ! SKIP_LLM=1 或 API 未配置 — 只跑 Layer 0/1 确定性部分")
        print("  ! 设 ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN 启用 Layer 2 LLM")
        print("=" * 78)

    # P1 8 场景
    p1r = run_headline("P1 测试集 (8 场景)", P1_SCENARIOS, llm_avail)

    # P4 30 样本
    p4r = run_headline("P4 测试集 (30 样本)", P4_SCENARIOS, llm_avail)

    # 对比
    compare_to_baseline(p1r, p4r)

    # 补充: P4 按类别分解
    print(f"\n\n{'█'*78}")
    print("  P4 分类分解")
    print(f"{'█'*78}")

    for cat_name in ("correct", "garbage", "edge"):
        cat_scenarios = [sc for sc in P4_SCENARIOS if sc["label"] == cat_name]
        cat_results = [
            r for r in p4r["results"]
            if any(sc["id"] == r["id"] for sc in cat_scenarios)
        ]

        l0_s = sum(1 for r in cat_results if r.get("layer") == "L0")
        l1_s = sum(1 for r in cat_results if r.get("layer") == "L1")
        l2_s = sum(1 for r in cat_results if r.get("layer") == "L2")

        correct_ct = sum(1 for r in cat_results
                         if r.get("final_verdict") in ("PASS", "REJECT")
                         and (r["final_verdict"] == "PASS") == r["correct"])
        valid_ct = sum(1 for r in cat_results
                       if r.get("final_verdict") in ("PASS", "REJECT"))
        acc = correct_ct / valid_ct * 100 if valid_ct else 0

        print(f"\n  {cat_name} ({len(cat_scenarios)} 样本):")
        print(f"    L0={l0_s} L1={l1_s} L2={l2_s}")
        print(f"    准确率: {correct_ct}/{valid_ct} = {acc:.1f}%")

    print(f"\n{'='*78}")
    print(f"  实验 F 结束")
    print(f"{'='*78}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass
    main()
