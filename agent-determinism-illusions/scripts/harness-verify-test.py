# -*- coding: utf-8 -*-
"""
实验 E（参数化版）：Harness 验证层 — 内容校验能否兜住 Phase Gate 假阳

8 场景（4 合法 + 4 垃圾），每场景：
  1. Phase Gate（纯代码，已知全过，假阳率 50%）
  2. 验证层 LLM 判产物是否符合任务定位
  3. 每场景重复 N 次取多数票（抗温度 0 的开放输出抽样噪声，见实验 A）

参数化（环境变量，便于横向对比 小模型 vs 强模型）：
  VERIFY_MODEL     模型名（默认 qwen3:0.5b）
  VERIFY_BASE_URL  API base（默认 http://localhost:11434 = Ollama）
  VERIFY_API_KEY   API key（Ollama 留空；API 模型必填）
  VERIFY_N         每场景重复次数（默认 3）

后端自动识别（三选一）：
  base_url 含 :11434        → Ollama      （/api/chat）
  base_url 含 anthropic     → Anthropic 兼容（/v1/messages，如智谱 GLM）
  其余                       → OpenAI 兼容 （/chat/completions）
API key fallback：VERIFY_API_KEY → OPENAI_API_KEY → ANTHROPIC_AUTH_TOKEN → ZHIPU_API_KEY

例：
  # 1) Ollama 小模型（默认）
  python harness-verify-test.py

  # 2) GLM-5.2 强模型（Anthropic 兼容端点，key 从 ANTHROPIC_AUTH_TOKEN 自动读）
  set VERIFY_MODEL=glm-5.2
  set VERIFY_BASE_URL=https://open.bigmodel.cn/api/anthropic
  python harness-verify-test.py
"""

import json, os, sys, io, urllib.request, time
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MODEL    = os.environ.get("VERIFY_MODEL", "qwen3:0.5b")
BASE_URL = os.environ.get("VERIFY_BASE_URL", "http://localhost:11434").rstrip("/")
API_KEY  = (os.environ.get("VERIFY_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ZHIPU_API_KEY", ""))
N_RUNS   = int(os.environ.get("VERIFY_N", "3"))
IS_OLLAMA    = ":11434" in BASE_URL
IS_ANTHROPIC = "anthropic" in BASE_URL.lower()

PROMPT = """You are a quality inspector. Determine if the FILE CONTENT below actually satisfies the TASK REQUIREMENT.

TASK: {task}
FILE CONTENT: {content}

Does the file content actually fulfill the task requirements?
Answer EXACTLY one line:
YES -- <brief reason>    OR    NO -- <what's missing/wrong>
Then a blank line, then a brief explanation."""

# 8 场景：4 合法 + 4 垃圾。垃圾就是 Phase Gate 放行、但内容不达标的假阳。
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


def call_model(prompt, temp=0.0):
    """统一调用：Ollama / Anthropic 兼容 / OpenAI 兼容，按 base_url 自动选。"""
    headers = {"Content-Type": "application/json"}
    msgs = [{"role": "user", "content": prompt}]

    try:
        if IS_OLLAMA:
            body = {"model": MODEL, "messages": msgs, "temperature": temp,
                    "max_tokens": 256, "stream": False}
            url = f"{BASE_URL}/api/chat"
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=60).read())["message"]["content"].strip()

        if not API_KEY:
            sys.exit("[abort] 非 Ollama 后端必须提供 API key（设 VERIFY_API_KEY 或 ANTHROPIC_AUTH_TOKEN）。")

        if IS_ANTHROPIC:
            headers["x-api-key"] = API_KEY
            headers["anthropic-version"] = "2023-06-01"
            body = {"model": MODEL, "max_tokens": 256, "messages": msgs, "temperature": temp}
            url = f"{BASE_URL}/v1/messages"
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=60).read())["content"][0]["text"].strip()

        # OpenAI 兼容
        headers["Authorization"] = f"Bearer {API_KEY}"
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": 256}
        url = f"{BASE_URL}/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers=headers)
        return json.loads(urllib.request.urlopen(req, timeout=60).read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"<ERROR: {e}>"


def classify(text):
    """解析首行 YES/NO。"""
    first = text.split("\n")[0].strip().upper()
    if first.startswith("NO") or first.startswith("N --"):
        return "REJECT"
    if first.startswith("YES") or first.startswith("Y --"):
        return "PASS"
    return "UNCLEAR"


def majority(verdicts):
    """多数票；平票（含 UNCLEAR 主导）记 UNCLEAR。"""
    c = Counter(verdicts)
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "UNCLEAR"
    return top[0][0]


# ─────────────────────────── 主流程 ───────────────────────────
print("=" * 72)
print("  实验 E: Harness 验证层 — 内容校验能兜住 Phase Gate 假阳吗？")
print(f"  Backend: {'Ollama' if IS_OLLAMA else 'Anthropic' if IS_ANTHROPIC else 'OpenAI-compat'}  |  Model: {MODEL}  |  N={N_RUNS}/场景")
print("=" * 72)

results = []
for sc_id, legit, task, content in SCENARIOS:
    prompt = PROMPT.format(task=task, content=content)
    verdicts = []
    for _ in range(N_RUNS):
        verdicts.append(classify(call_model(prompt)))
        time.sleep(0.15)
    maj = majority(verdicts)
    correct = (maj == "REJECT" and not legit) or (maj == "PASS" and legit)
    stable = len(set(verdicts)) == 1
    results.append({"id": sc_id, "legit": legit, "verdicts": verdicts,
                    "majority": maj, "correct": correct, "stable": stable})

    label = f"{sc_id}({'合法' if legit else '垃圾'})"
    mark = "ok" if correct else "WRONG"
    flag = "" if stable else "  [不稳!]"
    print(f"  {label:>10} | {str(verdicts):>30} -> {maj:>8} | {mark}{flag}")
    print(f"    Content: {content[:50].replace(chr(10),' | ')}")

# ─────────────────────────── 汇总 ───────────────────────────
legit_n   = sum(1 for r in results if r["legit"])
garbage_n = sum(1 for r in results if not r["legit"])
fp  = sum(1 for r in results if not r["legit"] and r["majority"] == "PASS")     # 垃圾被放行
tp  = sum(1 for r in results if not r["legit"] and r["majority"] == "REJECT")   # 垃圾被拦
fn  = sum(1 for r in results if r["legit"]   and r["majority"] == "REJECT")     # 合法被误杀
tn  = sum(1 for r in results if r["legit"]   and r["majority"] == "PASS")
unc = sum(1 for r in results if r["majority"] == "UNCLEAR")
unstable = sum(1 for r in results if not r["stable"])

print()
print("=" * 72)
print("  汇总")
print("=" * 72)
print(f"  Phase Gate 基线:        假阳率 50% ({garbage_n}/{garbage_n} 垃圾全放行)")
print(f"  + {MODEL} 验证层:")
print(f"      假阳率    : {fp}/{garbage_n} = {fp/garbage_n*100:.0f}%   (垃圾被放行)")
print(f"      垃圾拦截  : {tp}/{garbage_n}")
print(f"      误杀合法  : {fn}/{legit_n}")
print(f"      不确定    : {unc}/{len(results)}")
print(f"      不稳场景  : {unstable}/{len(results)}   (N 次投票出现分歧)")
print(f"  -> 成本: Phase Gate(零) + 验证({N_RUNS} 调用/场景) + 人工兜底(UNCLEAR)")
if fp == 0 and fn == 0 and unc == 0:
    print(f"  -> 完美兜住: 假阳清零、无误杀、无不确定。")
elif fp == 0:
    print(f"  -> 假阳清零,但存在误杀/不确定 — 需人工兜底。")
else:
    print(f"  -> 假阳未清零 — 该模型作为验证层不够强。")
print("=" * 72)
print(f"\n  复跑（换模型）: 设置 VERIFY_MODEL / VERIFY_BASE_URL / VERIFY_API_KEY 后重跑")
print(f"  当前命令行回显（供记录到博文）:")
print(f"    VERIFY_MODEL={MODEL} VERIFY_BASE_URL={BASE_URL} VERIFY_N={N_RUNS}")
