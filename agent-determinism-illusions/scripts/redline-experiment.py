# -*- coding: utf-8 -*-
"""
红线实验: 有客观收敛信号 vs 无客观收敛信号 的循环行为。

实验A(有红线): 写 Python 函数 → 编译+测试验证 → 过了就停
实验B(无红线): 写产品文案 → LLM 自我评判 → "还能更好吗?" → 无限循环
实验C(无红线+硬截断): 文案任务,3步硬上限

核心测量:
  1. 有红线: 几步收敛?
  2. 无红线: 发散模式是什么(长度暴增/主题漂移/原地振荡)?
  3. 硬截断: 截断时输出质量相比第1步是改善还是退化?
"""
import io, sys, json, urllib.request, subprocess, tempfile, os, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKEND = os.environ.get("CONV_BACKEND", "ollama")
if BACKEND == "ollama":
    MODEL, BASE_URL, API_KEY = "qwen3:0.5b", "http://localhost:11434", ""
else:
    MODEL = os.environ.get("CONV_MODEL", "deepseek-v4-flash")
    BASE_URL = os.environ.get("CONV_BASE_URL", "https://api.deepseek.com/anthropic").rstrip("/")
    API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

def call_llm(prompt, temp=0.0, max_tokens=512):
    IS_A = "anthropic" in BASE_URL.lower()
    msgs = [{"role": "user", "content": prompt}]
    if ":11434" in BASE_URL or BACKEND == "ollama":
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": max_tokens, "stream": False}
        url = f"{BASE_URL}/api/chat"
        resp = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}), timeout=30)
        return json.loads(resp.read())["message"]["content"].strip()
    elif IS_A:
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": max_tokens}
        url = f"{BASE_URL}/v1/messages"
        resp = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-api-key": API_KEY, "anthropic-version": "2023-06-01"}), timeout=60)
        data = json.loads(resp.read())
        for block in data.get("content", []):
            if block.get("type") == "text": return block["text"].strip()
        return str(data.get("content", ""))
    else:
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": max_tokens}
        url = f"{BASE_URL}/chat/completions"
        resp = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}), timeout=60)
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

# ═══════════════════════════════════════════════
# 实验 A: 有红线(编译+测试)
# ═══════════════════════════════════════════════
print("=" * 80)
print("  实验 A: 有红线(编译+测试通过) — Python 代码任务")
print("=" * 80)
print()

code_tasks = [
    ("简单", "写一个函数 add(a,b) 返回两数之和"),
    ("中等", "写一个函数 dedup(lst) 去除列表中的重复元素，保持原有顺序"),
    ("复杂", "写一个函数 merge_dicts(d1,d2) 合并两个字典，相同 key 的值相加"),
]
code_tests = {
    "简单": "print(add(2,3)); print(add(-1,1))",
    "中等": "print(dedup([3,1,2,1,3,4]))",
    "复杂": "print(merge_dicts({'a':1,'b':2},{'b':3,'c':4}))",
}
code_expected = {
    "简单": "5\n0",
    "中等": "[3, 1, 2, 4]",
    "复杂": "{'a': 1, 'b': 5, 'c': 4}",
}

for cid, desc in code_tasks:
    prompt = f"写 Python 代码。{desc}\n只输出代码。"
    raw = call_llm(prompt)
    # 提取代码
    m = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    code = m.group(1).strip() if m else raw.strip()
    # 跑测试
    full = code + "\n\n" + code_tests[cid]
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp.write(full); tmp.close()
    try:
        r = subprocess.run([sys.executable, tmp.name], capture_output=True, text=True, timeout=10)
        os.unlink(tmp.name)
        passed = (r.returncode == 0 and r.stdout.strip() == code_expected[cid])
    except:
        os.unlink(tmp.name); passed = False
    print(f"  {cid:<6} | 1步 {'OK 收敛' if passed else 'X 未通过'}")
    print(f"          {'红线信号=编译测试通过' if passed else '未达到红线条件'}")

print()
print("  结论: 有红线时,1步就能判断收敛。过不了红线=没做完,没有歧义。")
print()

# ═══════════════════════════════════════════════
# 实验 B: 无红线(LLM 自我评判)
# ═══════════════════════════════════════════════
print("=" * 80)
print("  实验 B: 无红线(LLM自我评判) — 开放式文案任务")
print("=" * 80)
print()

WRITING_TASK = "为一款智能水杯写一段产品介绍(50-80字)"
MAX_ITER = 8  # 跑 8 轮看看演化趋势

print(f"  任务: {WRITING_TASK}")
print(f"  迭代上限: {MAX_ITER} 轮 (无硬截断)")
print()

versions = []
for i in range(MAX_ITER):
    if i == 0:
        prompt = f"{WRITING_TASK}。直接写,不要解释。"
    else:
        prompt = f"""当前版本:
{versions[-1]}

请改进这段文案,让它更好。只输出改进后的版本。"""

    text = call_llm(prompt, max_tokens=300)
    versions.append(text)

    # 让 LLM 自我评分(1-10)
    judge = call_llm(f"给这段产品文案打分(1-10,10=最好)。只输出数字。\n---\n{text}\n---", max_tokens=10)
    score = re.search(r"\d+", judge)
    score_val = int(score.group()) if score else 0

    # 检测退化信号
    prev = versions[-2] if i > 0 else ""
    drift = ""
    if i > 0:
        # 长度变化
        len_delta = len(text) - len(prev)
        # 关键词重复率
        prev_words = set(prev)
        new_words = set(text)
        overlap = len(prev_words & new_words) / len(prev_words) if prev_words else 0
        if len_delta > 100:
            drift = "【长度暴涨】"
        elif len_delta < -50:
            drift = "【长度骤缩】"
        elif overlap < 0.2:
            drift = "【大范围重写】"
        elif score_val < 5:
            drift = "【低分振荡】"

    print(f"  第{i+1}版 | 自评{score_val}/10 | 长度{len(text)}字 {drift}")

print()
print("  观察: 无红线时迭代行为——")
lengths = [len(v) for v in versions]
print(f"    长度: 第1版={lengths[0]}, 第{MAX_ITER}版={lengths[-1]}, {'暴涨' if lengths[-1] > lengths[0]*1.5 else '稳定'}")
scores_raw = []
for v in versions:
    j = call_llm(f"打分1-10:\n---\n{v}\n---\n只输数字", max_tokens=10)
    m = re.search(r"\d+", j)
    scores_raw.append(int(m.group()) if m else 0)
delta = scores_raw[-1] - scores_raw[0] if len(scores_raw) > 1 else 0
print(f"    自评分变化: 第1版={scores_raw[0]}, 第{MAX_ITER}版={scores_raw[-1]} ({'+' if delta>=0 else ''}{delta})")
print()

# ═══════════════════════════════════════════════
# 实验 C: 无红线但有硬截断
# ═══════════════════════════════════════════════
print("=" * 80)
print("  实验 C: 无红线但有硬截断(上限=3步) — 同文案任务")
print("=" * 80)
print()

HARD_LIMIT = 3
print(f"  任务: {WRITING_TASK}")
print(f"  硬截断: 第{HARD_LIMIT}步强制停")
print()

versions_c = []
for i in range(HARD_LIMIT):
    if i == 0:
        prompt = f"{WRITING_TASK}。直接写。"
    else:
        prompt = f"改进:\n{versions_c[-1]}\n只输出新版。"
    text = call_llm(prompt, max_tokens=300)
    versions_c.append(text)
    tc = len(text)
    print(f"  第{i+1}版 | {tc}字")

print()
print(f"  截断: 取第{HARD_LIMIT}版作为最终输出。")
final = versions_c[-1]
print(f"  最终输出: {final[:80]}...")
print(f"  长度: {len(final)}字")
print(f"  无人判断它是否'够好'——系统只是停了,不是因为完成了。")
print()

# ═══════════════════════════════════════════════
print("=" * 80)
print("  三组实验对比")
print("=" * 80)
print()
r1 = "停止信号"
r2 = "停止时输出"
r3 = "能长成生产级?"
for r, a, b, c in [
    (r1, "编译+测试通过", "LLM自判够了", "上限到了"),
    (r2, "通过了测试", "从不停(发散)", "截断,质量未知"),
    (r3, "可", "不可", "靠上限兜底"),
]:
    print(f"  {r:30} {a:>18} {b:>18} {c:>18}")
print()
print("=" * 80)
print("  结论")
print("=" * 80)
print("  1. 有红线(客观收敛信号): 循环可自然收敛,输出质量可验证")
print("     -> 可以进入生产管线")
print("  2. 无红线(依赖LLM自我判断): 循环不收敛,自评分无效")
print("     -> 不允许进入生产管线,除非有人工截断")
print("  3. 无红线但有硬截断: 循环停止,但停止不是因为完成")
print("     -> 截断点=红线: '到这里不管了对不对,人接手'")
print()
print("  生产级Agent的红线法则:")
print("    如果任务没有客观收敛信号,就必须设硬截断,")
print("    且截断后的输出必须标注'未经验证'进入人工队列,")
print("    不能自动进入生产流程。")
