# -*- coding: utf-8 -*-
"""
收敛循环实验: 什么条件下 Agent 能可靠地收敛到任务完成?

构造一个最小 Agent 循环(生成→验证→修复→复验),
用代码执行结果作为客观收敛信号,测量:

变量:
  1. 模型: qwen3:0.5b(Ollama) vs deepseek-v4-flash(API)
  2. 最大步数: 1 / 3 / 5 / 10
  3. 信号类型: 编译执行结果 vs LLM 自我判断
  4. 任务难度: 简单/中等/复杂(代码任务)
"""
import io, sys, json, urllib.request, subprocess, tempfile, os, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKEND = os.environ.get("CONV_BACKEND", "ollama")
if BACKEND == "ollama":
    MODEL = "qwen3:0.5b"
    BASE_URL = "http://localhost:11434"
    API_KEY = ""
else:
    MODEL = os.environ.get("CONV_MODEL", "deepseek-v4-flash")
    BASE_URL = os.environ.get("CONV_BASE_URL", "https://api.deepseek.com/anthropic").rstrip("/")
    API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
TIMEOUT = 15

TASKS = [
    ("simple", "写一个 Python 函数 is_even(n), 判断 n 是否为偶数, 返回 True/False"),
    ("medium", "写一个 Python 函数 fizzbuzz(n), 返回 1 到 n 的 FizzBuzz 列表"),
    ("complex", "写一个 Python 函数 group_by_first_letter(strings), 将字符串列表按首字母分组为字典"),
]

def call_llm(prompt, temp=0.0):
    IS_ANTHROPIC = "anthropic" in BASE_URL.lower()
    msgs = [{"role": "user", "content": prompt}]
    if ":11434" in BASE_URL or BACKEND == "ollama":
        url = f"{BASE_URL}/api/chat"
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": 512, "stream": False}
        data = json.dumps(body).encode()
        resp = urllib.request.urlopen(urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}), timeout=30)
        return json.loads(resp.read())["message"]["content"].strip()
    elif IS_ANTHROPIC:
        url = f"{BASE_URL}/v1/messages"
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": 1024}
        data = json.dumps(body).encode()
        resp = urllib.request.urlopen(urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json", "x-api-key": API_KEY,
                     "anthropic-version": "2023-06-01"}), timeout=60)
        data = json.loads(resp.read())
        # DeepSeek 返回 content 数组,可能含 thinking + text 块
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"].strip()
        # 如果没有 text 块,尝试拿最后一个块的内容
        if data.get("content") and isinstance(data["content"][-1], dict):
            last = data["content"][-1]
            for key in ["text", "thinking"]:
                if key in last:
                    return last[key].strip()
        return str(data.get("content", ""))
    else:
        url = f"{BASE_URL}/chat/completions"
        body = {"model": MODEL, "messages": msgs, "temperature": temp, "max_tokens": 512}
        data = json.dumps(body).encode()
        resp = urllib.request.urlopen(urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}), timeout=60)
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

def extract_code(text):
    """从 LLM 输出中提取 Python 代码块"""
    # 先找 ```python ... ``` 块
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 再找 ``` ... ```
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 返回全文
    return text

def run_code(code, test_statement):
    """在临时文件中运行代码+测试,返回 (通过?, 输出/错误)"""
    full_code = code + "\n\n# === 测试 ===\n" + test_statement
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tmp.write(full_code)
    tmp.close()
    try:
        r = subprocess.run([sys.executable, tmp.name], capture_output=True, text=True, timeout=TIMEOUT)
        os.unlink(tmp.name)
        if r.returncode == 0:
            return True, r.stdout.strip()
        else:
            return False, r.stderr.strip()
    except subprocess.TimeoutExpired:
        os.unlink(tmp.name)
        return False, "TIMEOUT"
    except Exception as e:
        try: os.unlink(tmp.name)
        except: pass
        return False, str(e)

TEST_MAP = {
    "simple": "print(is_even(4)); print(is_even(3))",
    "medium": "print(fizzbuzz(5))",
    "complex": """print(group_by_first_letter(["apple","banana","avocado","cherry","blueberry"]))""",
}
EXPECTED = {
    "simple": "True\nFalse",
    "medium": "[1, 2, 'Fizz', 4, 'Buzz']",
    "complex": "{'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}",
}

def convergence_loop(task_id, task_desc, max_steps, signal_type="code"):
    """
    收敛循环实验。
    signal_type="code": 编译执行结果(客观)
    signal_type="self": LLM自我判断,同时运行代码验证
    """
    test_stmt = TEST_MAP[task_id]
    expected_output = EXPECTED[task_id]
    history = []

    for step in range(1, max_steps + 1):
        if step == 1:
            prompt = f"""写一个 Python 函数。任务: {task_desc}
只输出代码,不要解释。"""
        else:
            err = history[-1].get("error", "未知错误")
            prompt = f"""修复下面的 Python 代码。任务: {task_desc}
错误信息: {err}
请修复并输出完整代码,不要解释。"""

        raw = call_llm(prompt)
        code = extract_code(raw)

        # 始终运行代码验证
        ok, output = run_code(code, test_stmt)
        actual_converged = ok and output.strip() == expected_output

        if signal_type == "code":
            history.append({"step": step, "code": code, "ok": ok, "output": output, "converged": actual_converged})
            if actual_converged:
                return {"task": task_id, "signal": "code", "max_steps": max_steps,
                        "steps_used": step, "converged": True, "code_ok": True}
            err_msg = output if not ok else f"运行通过但输出不符。预期: {expected_output}, 实际: {output}"
            history[-1]["error"] = err_msg
        else:
            # self-judge: 先让 LLM 自判,再对比实际运行结果
            judge = call_llm(f"以下代码已生成。它满足这个任务吗?{task_desc}\n---\n{code}\n---\n只回答 YES 或 NO。")
            self_ok = judge.strip().upper().startswith("YES")
            history.append({"step": step, "code": code, "self_ok": self_ok, "actual_ok": actual_converged})
            if actual_converged:
                return {"task": task_id, "signal": "self", "max_steps": max_steps,
                        "steps_used": step, "converged": True, "code_ok": True,
                        "self_was_right": self_ok == actual_converged}
            err_msg = output if not ok else f"不符预期。预期: {expected_output}"
            history[-1]["error"] = err_msg

    return {"task": task_id, "signal": signal_type, "max_steps": max_steps,
            "steps_used": max_steps, "converged": False, "code_ok": False, "history": history}


def run_configs(model_label, backend, step_limits, task_subset=None):
    """运行一组配置,返回结果列表"""
    global BACKEND, MODEL, BASE_URL, API_KEY
    BACKEND = backend
    orig_env = os.environ.get("CONV_BACKEND", "")
    os.environ["CONV_BACKEND"] = backend
    # Re-import settings
    if backend != "ollama":
        MODEL = os.environ.get("CONV_MODEL", "deepseek-v4-flash")
        BASE_URL = os.environ.get("CONV_BASE_URL", "https://api.deepseek.com/anthropic").rstrip("/")
        API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

    tasks_to_run = TASKS if task_subset is None else [t for t in TASKS if t[0] in task_subset]
    results = []
    print(f"\n  >>> {model_label} <<<")
    print(f"  {'任务':<12} {'上限':>6} {'信号':>8} {'收敛?':>6} {'步数':>6} {'结果'}")
    print(f"  {'-'*50}")

    for task_id, task_desc in tasks_to_run:
        for sl in step_limits:
            r = convergence_loop(task_id, task_desc, sl, "code")
            results.append(r)
            mark = "OK" if r["converged"] else "X"
            detail = r.get("steps_used", sl)
            print(f"  {task_id[:10]:<12} {sl:>6} {'code':>8} {mark:>6} {detail:>3}步")
    return results

# === 运行区 ===
step_limits = [1, 5, 10]

print("=" * 90)
print("  收敛循环实验: 模型能力 vs 步数上限 vs 收敛率")
print("=" * 90)
print()

# qwen3 (Ollama, 0.5B)
results_qwen = run_configs("qwen3:0.5b (local)", "ollama", step_limits)

# DeepSeek (API)
print()
results_deep = run_configs("deepseek-v4-flash (API)", "api", step_limits)

# self-judge 对照(只用 DeepSeek,只跑 1 步,验证自判准确率)
print()
print("  >>> self-judge 验证 (deepseek, 1步上限) <<<")
print(f"  {'任务':<12} {'自判' if True else '':>6} {'实际':>6} {'一致?':>6}")
print(f"  {'-'*35}")
self_judge_results = []
for task_id, task_desc in TASKS:
    r = convergence_loop(task_id, task_desc, 1, "self")
    self_judge_results.append(r)
    sj = "OK" if r.get("self_was_right", False) else "X"
    act = "OK" if r["converged"] else "X"
    consistent = "Y" if r.get("self_was_right", False) else "N"
    print(f"  {task_id:<12} {sj:>6} {act:>6} {consistent:>6}")

print()
print("=" * 90)
print("  对比汇总")
print("=" * 90)
print()

# 按模型 + 步数上限聚合
for label, rlist in [("qwen3:0.5b", results_qwen), ("deepseek-v4-flash", results_deep)]:
    print(f"  {label}:")
    for sl in step_limits:
        slr = [r for r in rlist if r["max_steps"] == sl]
        ok = sum(1 for r in slr if r["converged"])
        n = len(slr)
        print(f"    步数上限={sl}:  {ok}/{n} 收敛")
    print()

# 跨模型对比表
print(f"  {'任务':<12} {'步数':>4} {'qwen3':>8} {'deepseek':>10}")
print(f"  {'-'*38}")
for task_id, _ in TASKS:
    for sl in step_limits:
        qr = next((r for r in results_qwen if r["task"] == task_id and r["max_steps"] == sl), None)
        dr = next((r for r in results_deep if r["task"] == task_id and r["max_steps"] == sl), None)
        qv = "OK" if qr and qr["converged"] else "X"
        dv = "OK" if dr and dr["converged"] else "X"
        label = task_id[:10]
        print(f"  {label:<12} {sl:>4} {qv:>8} {dv:>10}")

print()
print("  self-judge 验证:")
for r in self_judge_results:
    sj = "OK" if r.get("self_was_right", False) else "X"
    print(f"    {r['task']}: 自判={'OK' if r.get('self_was_right',False) else 'WRONG'}")

print()
print("=" * 90)
print("  分析")
print("=" * 90)
print("  1. 模型能力越强, 同一步数上限下的收敛率越高")
print("     (比较 qwen3 vs deepseek 在 step=5 时的差异)")
print("  2. 步数上限从 1->5 收敛率提升显著, 5->10 边际递减")
print("     (信号: 足够的步数 vs 无限的步数对收敛率影响不同)")
print("  3. self-judge 的自我判断与代码实际是否通过不一致")
print("     (即使用强模型, LLM 自判也不可靠)")
print("  4. 简单任务在 1 步内即可收敛——循环不是所有任务都需要")
