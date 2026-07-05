# -*- coding: utf-8 -*-
"""
红线实验 V2: 同一任务,有红线 vs 无红线(仅自判) 直接对比收敛分布。

去掉混杂变量——同样都是代码任务,只改变停止信号类型。

条件 A(有红线): 编译+测试通过 = 停止
条件 B(无红线): LLM 自判"完成了" = 停止(同时后台跑代码验证)

测量:
  1. 收敛率(代码实际通过的比例)
  2. 步数分布
  3. 条件B的假阳性率(自判YES但代码失败)
  4. 条件B的假阴性率(代码通过但自判NO)
"""
import io, sys, json, urllib.request, subprocess, tempfile, os, re, time, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com/anthropic"
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

def call_llm(prompt, temp=0.0, max_tokens=1024):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": max_tokens}).encode()
    resp = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/messages",
        data=body, headers={"Content-Type": "application/json", "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01"}), timeout=60)
    data = json.loads(resp.read())
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"].strip()
    return str(data.get("content", ""))

def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()

def run_code(code, test_stmt, timeout=10):
    full = code + "\n\n" + test_stmt
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp.write(full); tmp.close()
    try:
        r = subprocess.run([sys.executable, tmp.name], capture_output=True, text=True, timeout=timeout)
        os.unlink(tmp.name)
        if r.returncode == 0:
            return ("pass", r.stdout.strip())
        else:
            return ("error", r.stderr.strip())
    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp.name)
        except:
            pass
        return ("timeout", "")
    except Exception as e:
        try:
            os.unlink(tmp.name)
        except:
            pass
        return ("error", str(e))

TASKS = [
    ("simple", "写一个 Python 函数 is_even(n), 判断偶数返回 True 否则 False",
     "print(is_even(4)); print(is_even(3))", "True\nFalse"),
    ("medium", "写一个 Python 函数 fizzbuzz(n), 返回 1~n 的 FizzBuzz 列表",
     "print(fizzbuzz(5))", "[1, 2, 'Fizz', 4, 'Buzz']"),
    ("complex", "写一个函数 group_by_first_letter(strings), 按首字母分组为字典",
     "print(group_by_first_letter(['apple','banana','avocado','cherry','blueberry']))",
     "{'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}"),
]

MAX_STEPS = 10
TRIALS = 5

def trial_redline(tid, desc, test_stmt, expected):
    """条件 A: 有红线(编译+测试通过=停)。返回 (收敛?, 步数)"""
    for step in range(1, MAX_STEPS + 1):
        if step == 1:
            prompt = f"写 Python 代码。{desc}\n只输出代码,不要解释。"
        else:
            prompt = f"修复错误。{desc}\n错误: {last_err}\n输出完整代码。"
        raw = call_llm(prompt)
        code = extract_code(raw)
        status, output = run_code(code, test_stmt)
        if status == "pass" and output.strip() == expected:
            return (True, step)
        last_err = output if status == "error" else f"输出不符。期望: {expected[:40]}"
    return (False, MAX_STEPS)

def trial_selfjudge(tid, desc, test_stmt, expected):
    """条件 B: 无红线(LLM自判=停)。同时后台跑代码记录实际是否正确。"""
    for step in range(1, MAX_STEPS + 1):
        if step == 1:
            prompt = f"写 Python 代码。{desc}\n只输出代码,不要解释。"
        else:
            prompt = f"改进代码。{desc}\n上次代码:\n{last_code}\n输出改进后的完整代码。"
        raw = call_llm(prompt)
        code = extract_code(raw)
        last_code = code

        # 后台验证
        status, output = run_code(code, test_stmt)
        actually_correct = (status == "pass" and output.strip() == expected)

        # LLM 自判
        judge = call_llm(f"以下代码满足任务要求吗?{desc}\n---\n{code}\n---\n只回答 YES 或 NO。", max_tokens=10)
        self_yes = judge.strip().upper().startswith("YES")

        if self_yes:
            # 自判收敛
            return (actually_correct, step, "correct" if actually_correct else "false_positive")

    return (actually_correct, MAX_STEPS, "false_negative" if actually_correct else "correctly_rejected")

print("=" * 90)
print("  红线实验 V2: 同一任务,有红线 vs 无红线 直接对比")
print("=" * 90)
print(f"  Model: {MODEL}  |  每条件{TRIALS}次  |  上限{MAX_STEPS}步")
print()

results = {"redline": [], "selfjudge": []}

for tid, desc, test_stmt, expected in TASKS:
    print(f"  [{tid}] {desc[:50]}...")
    print(f"  {'-'*70}")

    # 条件 A
    a_converged = 0; a_steps = []
    for t in range(TRIALS):
        ok, steps = trial_redline(tid, desc, test_stmt, expected)
        a_converged += 1 if ok else 0
        a_steps.append(steps)
        results["redline"].append((tid, ok, steps))
    a_avg = sum(a_steps) / len(a_steps)
    print(f"    有红线(编译): {a_converged}/{TRIALS} 收敛  步数={a_steps}  平均{a_avg:.1f}")

    # 条件 B
    b_converged = 0; b_steps = []; b_fp = 0; b_fn = 0
    for t in range(TRIALS):
        actually_ok, steps, mode = trial_selfjudge(tid, desc, test_stmt, expected)
        b_converged += 1 if actually_ok else 0
        b_steps.append(steps)
        b_fp += 1 if mode == "false_positive" else 0
        b_fn += 1 if mode == "false_negative" else 0
        results["selfjudge"].append((tid, actually_ok, steps, mode))
    b_avg = sum(b_steps) / len(b_steps)
    print(f"    无红线(自判): {b_converged}/{TRIALS} 实际收敛  步数={b_steps}  平均{b_avg:.1f}")
    if b_fp or b_fn:
        print(f"      自判假阳性(自判OK但代码错): {b_fp}/{TRIALS}")
        print(f"      自判假阴性(代码对但自判NO): {b_fn}/{TRIALS}")
    print()

print("=" * 90)
print("  汇总: 红线的边际贡献")
print("=" * 90)
print()
print(f"  {'任务':<12} {'有红线收敛率':>16} {'无红线收敛率':>16} {'假阳性率(自判':>16} {'边际贡献':>16}")
print(f"  {'-'*76}")

for tid, desc, test_stmt, expected in TASKS:
    ar = [r for r in results["redline"] if r[0] == tid]
    br = [r for r in results["selfjudge"] if r[0] == tid]
    a_rate = sum(1 for r in ar if r[1]) / len(ar)
    b_rate = sum(1 for r in br if r[1]) / len(br)
    fp = sum(1 for r in br if len(r) > 3 and r[3] == "false_positive") / len(br)
    margin = a_rate - b_rate
    print(f"  {tid:<12} {a_rate:.0%}               {b_rate:.0%}               {fp:.0%}               {'+' if margin>0 else ''}{margin:.0%}")

print()
print("=" * 90)
print("  解读")
print("=" * 90)
print()
print("  - 有红线的收敛率: 编译+测试通过即停, 不依赖模型自我认知。")
print("  - 无红线的收敛率: 即使代码写对了, 模型自判也可能说NO(假阴性);")
print("    而代码写错了, 模型自判也可能说YES(假阳性)。")
print("  - 红线的边际贡献 = 有红线收敛率 - 无红线收敛率。")
print("    这个差值就是红线作为一个客观停止信号带来的收敛增益。")
print()
print("  如果边际贡献 > 0: 红线对收敛有因果效应(不仅仅是'格式过滤')")
print("  如果边际贡献 ≈ 0: 红线只是确认, 模型自己也能判断")
print("  如果边际贡献 < 0: 红线反而阻碍了收敛(几乎不可能)")
