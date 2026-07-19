# -*- coding: utf-8 -*-
"""
Stuck-loop budget 实验:Reid Marlow 的坑——同一红线失败 N 次就停 vs 步数硬截断。

被测主张(来自 redline 文章回复二十七 @Reid Marlow):
  "a cheap stuck-loop budget: same failing red line N times means stop and
   surface the evidence, not keep sampling."

redline 文章 Part §"The boundary of loops" 把"循环边界"标为 untested hypothesis;
Part 6 Cost Asymmetry 承认 false negative 会触发 "possible infinite loops",
但没给刹车。本实验就是那个刹车。

方法:
  两类任务 × 两模型,只跑红线条件(编译+测试=停)。
  - repairable 类: 现有 3 个(is_even / fizzbuzz / group_by)——语法/边界错误,迭代可修。
  - conceptual 类: 4 个需求陷阱——测试期望违背描述字面意思,迭代修不动。
    红线持续 fail 且签名相似(同一类错误反复)。
  每任务落盘逐步轨迹: (step, code, status, output, error_signature)。
  MAX_STEPS=8。

离线分析(analysis 在脚本末尾):
  对每条轨迹,对比三种停止策略的"停止步数"与"判定正确性":
    - step-cap:        step 8 硬停(现有方案)
    - sig-budget(N):   同一 error_signature 连续重复 N 次即停
    - oracle:          实际首次通过步数(若有)
  关键指标:
    - 早停收益:    conceptual 任务上 sig-budget 比 step-cap 早停几步
    - 误停代价:    repairable 任务上 sig-budget 是否过早停掉最终会修好的任务
    - 判别力:      sig-budget 的停止步数是否在两类任务间显著分离

两模型对比:
  - DeepSeek (deepseek-v4-flash, api.deepseek.com):  与 redline 文章 9/9 vs 2/9 同模型, 可直接对比。
  - Zhipu GLM (glm-5.2, open.bigmodel.cn):           当前会话模型, 新增对照。
  凭证从 cc-switch.db 动态读取(app_type='claude', name='DeepSeek' / 'Zhipu GLM'),
  不硬编码、不落盘、不打印 token。

依赖: cc-switch.db (默认路径 ~/.cc-switch/cc-switch.db); 无第三方包。
预期: conceptual 任务上 sig-budget 显著早于 step-cap; repairable 任务上两者接近
      (误停率低)。若 sig-budget 在 repairable 上也早早停掉, 说明签名阈值过严——
      这是 N 的调参信号, 实验需报告。

输出:
  - stdout: 每条轨迹的逐步签名 + 三策略对比表
  - scripts/results-v2/stuck-loop-budget.json: 完整轨迹 + 分析

运行:
  python stuck-loop-budget-test.py
"""
import io, sys, json, urllib.request, subprocess, tempfile, os, re, sqlite3
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "stuck-loop-budget.json"

MAX_STEPS = 8
CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")


# ---------- 任务集 ----------
# repairable: 语法/边界错误, 迭代可修 (沿用 redline-v2 内置 3 任务)
# conceptual: 测试期望违背描述字面意思, 迭代修不动——红线持续 fail 且签名相似
TASKS = [
    # --- repairable ---
    ("R-is_even", "repairable",
     "写一个 Python 函数 is_even(n), 判断偶数返回 True 否则 False",
     "print(is_even(4)); print(is_even(3))", "True\nFalse"),
    ("R-fizzbuzz", "repairable",
     "写一个 Python 函数 fizzbuzz(n), 返回 1~n 的 FizzBuzz 列表",
     "print(fizzbuzz(5))", "[1, 2, 'Fizz', 4, 'Buzz']"),
    ("R-group_by", "repairable",
     "写一个函数 group_by_first_letter(strings), 按首字母分组为字典",
     "print(group_by_first_letter(['apple','banana','avocado','cherry','blueberry']))",
     "{'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}"),
    # --- conceptual (需求陷阱) ---
    ("C-bin", "conceptual",
     "写函数 to_bin(n): 返回 n 的二进制表示字符串",
     "print(to_bin(8))", "100"),  # 陷阱: 二进制(8)=1000, 期望 100
    ("C-swap", "conceptual",
     "写函数 classify(n): 偶数返回 even 奇数返回 odd",
     "print(classify(2)); print(classify(3))", "odd\neven"),  # 陷阱: 输出反转
    ("C-len", "conceptual",
     "写函数 mylen(s): 返回字符串长度",
     'print(mylen("hello"))', "4"),  # 陷阱: len("hello")=5, 期望 4
    ("C-abs", "conceptual",
     "写函数 myabs(n): 返回绝对值",
     "print(myabs(-5))", "-5"),  # 陷阱: abs(-5)=5, 期望 -5
]


# ---------- 凭证: 从 cc-switch.db 动态读取 ----------
def load_provider(name):
    """从 cc-switch.db 读取指定 provider 的 base_url/token/model。不打印 token。"""
    con = sqlite3.connect(CC_SWITCH_DB)
    cur = con.cursor()
    cur.execute(
        "SELECT settings_config FROM providers WHERE app_type='claude' AND name=?",
        (name,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        raise RuntimeError(f"provider '{name}' not found in cc-switch.db")
    env = json.loads(row[0]).get("env", {})
    base = env.get("ANTHROPIC_BASE_URL")
    tok = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
    model = env.get("ANTHROPIC_MODEL")
    if not (base and tok and model):
        raise RuntimeError(f"provider '{name}' missing base/token/model")
    return {"base": base, "token": tok, "model": model}


PROVIDERS = {
    "DeepSeek": load_provider("DeepSeek"),
    "Zhipu GLM": load_provider("Zhipu GLM"),
}


# ---------- LLM + 代码执行 ----------
def call_llm(prov, prompt, max_tokens=600, retries=4):
    """带指数退避重试。网络瞬断 (WinError 10054 / 超时) 时退避后重试。"""
    import time as _t
    body = json.dumps(
        {
            "model": prov["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
    ).encode()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{prov['base']}/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": prov["token"],
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=90)
            data = json.loads(resp.read())
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
            return str(data.get("content", ""))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                backoff = 2 ** attempt  # 1, 2, 4, 8 秒
                _t.sleep(backoff)
                continue
    raise RuntimeError(f"call_llm failed after {retries} retries: {last_err}")


def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def run_code(code, test_stmt, timeout=10):
    """执行 code + test_stmt, 返回 (status, output)。status: pass/error/timeout。"""
    full = code + "\n\n" + test_stmt
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    tmp.write(full)
    tmp.close()
    try:
        r = subprocess.run(
            [sys.executable, tmp.name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0:
            return ("pass", r.stdout.strip())
        # 取最后一行错误作为签名主体
        err = r.stderr.strip().splitlines()
        return ("error", err[-1] if err else "error")
    except subprocess.TimeoutExpired:
        return ("timeout", "")
    except Exception as e:
        return ("error", str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def error_signature(status, output, expected, passed=False):
    """
    红线失败签名: 用于判断"是否同一个失败重复"。
    - passed: 标 'PASS' (停止策略据此识别收敛, 不计入重复)
    - 编译错误: 取错误类型 (e.g. "NameError")
    - 运行通过但输出不符: 'WRONG_OUTPUT:<actual>' (截断)
    签名应: 同一类错误稳定相同; 不同错误不同; 不依赖完整 trace (一字之 fix 会改行号)。
    """
    if passed:
        return "PASS"
    if status == "error":
        # e.g. "NameError: name 'is_even' is not defined" -> "NameError"
        m = re.match(r"^(\w+:)", output)
        return m.group(1) if m else ("ERR:" + output[:20])
    if status == "timeout":
        return "TIMEOUT"
    # status == 'pass' 但 output != expected
    return "WRONG_OUTPUT:" + output.strip()[:30]


# ---------- 红线轨迹采集 ----------
def run_redline_trajectory(prov, tid, desc, test_stmt, expected):
    """跑一条红线轨迹, 落盘每步。返回 trajectory list。"""
    traj = []
    last_feedback = ""
    last_code = ""
    for step in range(1, MAX_STEPS + 1):
        if step == 1:
            prompt = f"写 Python 代码。{desc}\n只输出代码, 不要解释, 不要包含测试语句。"
        else:
            prompt = (
                f"修复代码。{desc}\n上次代码:\n{last_code}\n"
                f"运行结果: {last_feedback}\n"
                f"输出完整修复后的代码, 只输出代码, 不要包含测试语句。"
            )
        raw = call_llm(prov, prompt)
        code = extract_code(raw)
        last_code = code
        status, output = run_code(code, test_stmt)
        passed = status == "pass" and output.strip() == expected
        sig = error_signature(status, output, expected, passed)
        traj.append(
            {
                "step": step,
                "status": status,
                "output": output[:200],
                "passed": passed,
                "sig": sig,
            }
        )
        if passed:
            break
        last_feedback = (
            output[:120]
            if status == "error"
            else f"运行通过但输出不符。期望: {expected[:40]}, 实际: {output[:40]}"
        )
    return traj


# ---------- 停止策略 (离线分析) ----------
def stop_step_cap(traj):
    """步数硬截断: 永远跑满 MAX_STEPS (除非中途通过)。"""
    for s in traj:
        if s["passed"]:
            return s["step"], "converged"
    return MAX_STEPS, "step_cap"


def stop_sig_budget(traj, N):
    """
    签名重复 budget: 同一 sig 连续重复 N 次即停, 标记 stuck。
    返回 (停止步数, 原因)。若中途通过则 converged。
    """
    streak_sig = None
    streak_len = 0
    for s in traj:
        if s["passed"]:
            return s["step"], "converged"
        if s["sig"] == streak_sig:
            streak_len += 1
        else:
            streak_sig = s["sig"]
            streak_len = 1
        if streak_len >= N:
            return s["step"], "stuck"
    return MAX_STEPS, "step_cap"


def oracle_converge_step(traj):
    """实际首次通过步数; 未通过返回 None。"""
    for s in traj:
        if s["passed"]:
            return s["step"]
    return None


# ---------- 主流程 ----------
def main():
    print("=" * 92)
    print("  Stuck-loop budget 实验: 签名重复检测器 vs 步数硬截断")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}")
    print(f"  Tasks: {len(TASKS)} ({sum(1 for _,c,_ in [(t,k,0) for t,k,d,te,e in TASKS] if False)} -- 见下)")
    rc = sum(1 for t in TASKS if t[1] == "repairable")
    cc = sum(1 for t in TASKS if t[1] == "conceptual")
    print(f"  repairable={rc}  conceptual={cc}  MAX_STEPS={MAX_STEPS}")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> Provider: {prov_name} ({prov['model']}) <<<")
        for tid, klass, desc, test_stmt, expected in TASKS:
            traj = run_redline_trajectory(prov, tid, desc, test_stmt, expected)
            conv = oracle_converge_step(traj)
            sigs = [s["sig"] for s in traj]
            print(f"    [{tid:12}] klass={klass:11} steps={len(traj)} "
                  f"converged={'step'+str(conv) if conv else 'NO'}")
            print(f"      sigs: {sigs}")
            all_runs.append(
                {
                    "provider": prov_name,
                    "model": prov["model"],
                    "task": tid,
                    "klass": klass,
                    "desc": desc,
                    "expected": expected,
                    "converged_step": conv,
                    "trajectory": traj,
                }
            )
        print()

    # ---------- 策略对比 ----------
    print("=" * 92)
    print("  停止策略对比 (sig-budget 用 N=3)")
    print("=" * 92)
    NS = [2, 3, 4]
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        print(f"\n  Provider: {prov_name}")
        print(f"  {'task':14}{'klass':12}{'oracle':>8}{'stepcap':>9}", end="")
        for N in NS:
            print(f"{'sigN='+str(N):>9}", end="")
        print()
        print(f"  {'-'*70}")
        for r in runs:
            cap_step, _ = stop_step_cap(r["trajectory"])
            sig_steps = []
            for N in NS:
                ss, _ = stop_sig_budget(r["trajectory"], N)
                sig_steps.append(ss)
            orc = r["converged_step"]
            orc_s = str(orc) if orc else "—"
            print(f"  {r['task']:14}{r['klass']:12}{orc_s:>8}{cap_step:>9}", end="")
            for ss in sig_steps:
                print(f"{ss:>9}", end="")
            print()

    # ---------- 汇总指标 ----------
    print("\n" + "=" * 92)
    print("  汇总: 两类任务上的平均停止步数 (越早停越省; 但 repairable 早停=误停)")
    print("=" * 92)
    summary = {"by_provider": {}}
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        prov_sum = {}
        for klass in ("repairable", "conceptual"):
            kr = [r for r in runs if r["klass"] == klass]
            if not kr:
                continue
            cap_avg = sum(stop_step_cap(r["trajectory"])[0] for r in kr) / len(kr)
            row = {"n": len(kr), "step_cap_avg": round(cap_avg, 2)}
            for N in NS:
                ss_avg = sum(
                    stop_sig_budget(r["trajectory"], N)[0] for r in kr
                ) / len(kr)
                row[f"sigN{N}_avg"] = round(ss_avg, 2)
            # 误停: repairable 任务若 oracle 收敛, 但 sig-budget 提前停在 stuck
            if klass == "repairable":
                falsestops = 0
                for r in kr:
                    if r["converged_step"] is not None:  # 本会修好
                        for N in NS:
                            ss, why = stop_sig_budget(r["trajectory"], N)
                            if why == "stuck" and ss < r["converged_step"]:
                                falsestops += 1
                                break
                row["falsestop_rate"] = round(falsestops / len(kr), 2)
            prov_sum[klass] = row
        summary["by_provider"][prov_name] = prov_sum

    for prov_name, prov_sum in summary["by_provider"].items():
        print(f"\n  {prov_name}:")
        for klass, row in prov_sum.items():
            extra = ""
            if "falsestop_rate" in row:
                extra = f"  误停率(sig提前停掉本会修好的)={row['falsestop_rate']:.0%}"
            print(f"    {klass:12} n={row['n']}  stepcap_avg={row['step_cap_avg']}  "
                  f"sigN3_avg={row.get('sigN3_avg','?')}{extra}")

    # ---------- 写盘 ----------
    out = {
        "meta": {
            "experiment": "stuck-loop-budget",
            "claim": "Reid Marlow: same failing red line N times -> stop, not keep sampling",
            "max_steps": MAX_STEPS,
            "n_values": NS,
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")
    print()
    print("  解读指引:")
    print("  - conceptual 任务上 sigN3_avg << step_cap_avg -> 签名 budget 显著早停 (主结论)")
    print("  - repairable 任务上 falsestop_rate 低 -> 没有误杀本会修好的任务 (副作用可控)")
    print("  - 若 falsestop_rate 高 -> N 太小, 需上调 (调参信号)")


if __name__ == "__main__":
    main()
