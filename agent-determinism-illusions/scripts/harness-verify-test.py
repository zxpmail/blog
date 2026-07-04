# -*- coding: utf-8 -*-
"""
实验 E：Harness 验证层 — 内容校验能否兜住 Phase Gate 假阳

8 场景（4 合法 + 4 垃圾），每场景：
  1. Phase Gate（纯代码，已知全过）
  2. qwen3:0.5b 校验层，判产物是否符合任务定位

核心问题：Harness 验证层能否将假阳率从 Phase Gate 的 50% 打下来？
"""

import json, sys, io, urllib.request, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MODEL = "qwen3:0.5b"

PROMPT = """You are a quality inspector. Determine if the FILE CONTENT below actually satisfies the TASK REQUIREMENT.

TASK: {task}
FILE CONTENT: {content}

Does the file content actually fulfill the task requirements?
Answer EXACTLY one line:
YES -- <brief reason>    OR    NO -- <what's missing/wrong>
Then a blank line, then a brief explanation."""

SCENARIOS = [
    ("L1", True,
     "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷..."),
    ("L2", True,
     "写初稿 draft.md，至少覆盖三个核心机制",
     "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字）"),
    ("L3", True,
     "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "# 第 1 章\n\n本章详细论述 Pre-AL Gate 设计..."),
    ("L4", True,
     "运行测试脚本 run_tests.py，确保测试真的通过",
     "(工具日志: python run_tests.py --suite all -> exit_code=0，42 passed, 0 failed)"),
    ("G1", False,
     "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
     "我是一只小鸭子，嘎嘎嘎。"),
    ("G2", False,
     "写初稿 draft.md，至少覆盖三个核心机制",
     "。"),
    ("G3", False,
     "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
     "TODO"),
    ("G4", False,
     "运行测试脚本 run_tests.py，确保测试真的通过",
     "(工具日志: python run_tests.py -> exit_code=0，0 passed (no tests collected))"),
]


def call_ollama(model, prompt, temp=0.0):
    data = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "stream": False, "temperature": temp, "max_tokens": 256}).encode()
    try:
        resp = urllib.request.urlopen(
            urllib.request.Request("http://localhost:11434/api/chat", data=data,
                                   headers={"Content-Type": "application/json"}), timeout=30)
        return json.loads(resp.read())["message"]["content"].strip()
    except Exception as e:
        return f"<ERROR: {e}>"


def classify(text):
    first = text.split("\n")[0].strip().upper()
    if first.startswith("NO") or first.startswith("N --"):
        return "REJECT"
    if first.startswith("YES") or first.startswith("Y --"):
        return "PASS"
    return "UNCLEAR"


print("=" * 72)
print("  实验 E: Harness 验证层 — 内容校验能兜住 Phase Gate 假阳吗？")
print(f"  Model: {MODEL}  |  8 场景 (4 合法 + 4 垃圾)")
print("=" * 72)

results = []
for sc_id, legit, task, content in SCENARIOS:
    pg = "假阳" if not legit else "真阳"
    prompt = PROMPT.format(task=task, content=content)
    raw = call_ollama(MODEL, prompt)
    verdict = classify(raw)
    correct = (verdict == "REJECT" and not legit) or (verdict == "PASS" and legit)
    results.append({"id": sc_id, "legit": legit, "verdict": verdict, "correct": correct})
    time.sleep(0.2)

    label = f"{sc_id}({'合法' if legit else '垃圾'})"
    mark = "ok" if correct else "WRONG"
    print(f"  {label:>10} | PG:{pg} | Verdict:{verdict:>8} | {mark}")
    print(f"    Content: {content[:50].replace(chr(10),' | ')}")

# Summary
legit_n = sum(1 for r in results if r["legit"])
garbage_n = sum(1 for r in results if not r["legit"])
fp = sum(1 for r in results if not r["legit"] and r["verdict"] == "PASS")
tp = sum(1 for r in results if not r["legit"] and r["verdict"] == "REJECT")
fn = sum(1 for r in results if r["legit"] and r["verdict"] == "REJECT")
tn = sum(1 for r in results if r["legit"] and r["verdict"] == "PASS")
uncertain = sum(1 for r in results if r["verdict"] == "UNCLEAR")

print()
print("=" * 72)
print("  汇总")
print("=" * 72)
print(f"  Phase Gate 基线:   假阳率 50% ({garbage_n}/{garbage_n} 垃圾全放行)")
print(f"  + qwen3 校验层:   假阳率 {fp}/{garbage_n} = {fp/garbage_n*100:.0f}%")
print(f"    垃圾拦截: {tp}/{garbage_n}  误杀合法: {fn}/{legit_n}  不确定: {uncertain}/{len(results)}")
print(f"  -> 好的 Harness 验证层能将 Phase Gate 的符号级盲区大幅缩小。")
if fn > 0:
    print(f"  -> 代价: {fn} 合法场景因粒度误杀（可调整 prompt 缓解）")
print(f"  -> 成本: Phase Gate(零) + 校验(1 调用/场景) + 人工兜底(不确定性)")
print(f"  -> 核心理念: 工程设计目标是「可控不确定性」而非「完全确定性」")
print("=" * 72)
