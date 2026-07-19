# -*- coding: utf-8 -*-
"""
Self-judge prompt reframe 实验: 点4 局限防守。

被测局限(来自 redline 文章 line 57 Prompt bias note):
  "a different prompt format (e.g., 'output FINISH if code passes all tests')
   would likely change the self-judge convergence rate."

回复二十六 (Luis) 把这列为 approach 1 (reframe the prompt), 但标注为推测:
  "it shifts the false-negative rate, it doesn't eliminate the asymmetry.
   You're tuning a knob on a judge that still has no ground to stand on."

本实验把推测变数据: 同一任务、同一模型, 两种 self-judge prompt 模式,
直接对比假阴性率 (代码对但自判不停) 是否真的随 prompt 改变。

方法:
  redline 原 3 任务 (is_even / fizzbuzz / group_by) — 模型能力范围内, 可写出正确代码。
  两种 self-judge prompt:
    - YESNO: "以下代码满足任务吗? 只回答 YES 或 NO。" (redline 文章原 prompt, 偏向 NO)
    - FINISH: "如果代码完全满足任务, 输出 FINISH; 否则输出 NEEDS_WORK。"
              (reframe: 指令式, 安全默认变为"需要继续")
  每任务 N 次试验, MAX_STEPS=8, temp=0。
  后台始终跑真实代码验证 (作为 ground truth), 但停止信号只看 self-judge。
  测量:
    - 假阴性率 (代码实际通过但 self-judge 未停)
    - 自判收敛步数 (何时 self-judge 触发)
    - 实际收敛率 (代码真的对的比例, 与 prompt 无关, 作对照)

两模型: DeepSeek (deepseek-v4-flash) + Zhipu GLM (glm-5.2), 从 cc-switch.db 读凭证。
依赖: cc-switch.db。无第三方包。
预期: FINISH 可能降低假阴性率 (指令式、默认翻转), 但降幅与方向性是否稳健 = 看数据。
      关键不是"哪个 prompt 更好", 而是"假阴性是否对 prompt 敏感" —— 若敏感,
      则印证"self-judge 结论对外部参数敏感, 非天生不可用, 但也不可依赖"。

输出: scripts/results-v2/selfjudge-prompt-reframe.json
运行: python selfjudge-prompt-reframe-test.py
"""
import io, sys, json, urllib.request, subprocess, tempfile, os, re, sqlite3, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "selfjudge-prompt-reframe.json"

MAX_STEPS = 8
TRIALS = 3
CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")

TASKS = [
    ("is_even", "写一个 Python 函数 is_even(n), 判断偶数返回 True 否则 False",
     "print(is_even(4)); print(is_even(3))", "True\nFalse"),
    ("fizzbuzz", "写一个 Python 函数 fizzbuzz(n), 返回 1~n 的 FizzBuzz 列表",
     "print(fizzbuzz(5))", "[1, 2, 'Fizz', 4, 'Buzz']"),
    ("group_by", "写一个函数 group_by_first_letter(strings), 按首字母分组为字典",
     "print(group_by_first_letter(['apple','banana','avocado','cherry','blueberry']))",
     "{'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}"),
]

# 两种 self-judge prompt 模式
JUDGE_PROMPTS = {
    "YESNO": "以下代码满足这个任务吗?\n任务: {desc}\n---\n{code}\n---\n只回答 YES 或 NO。",
    "FINISH": "判断以下代码是否完全满足任务 (无任何缺陷)。\n任务: {desc}\n---\n{code}\n---\n如果完全满足, 只输出 FINISH; 否则只输出 NEEDS_WORK。",
}


def load_provider(name):
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
    return {
        "base": env["ANTHROPIC_BASE_URL"],
        "token": env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY"),
        "model": env["ANTHROPIC_MODEL"],
    }


PROVIDERS = {
    "DeepSeek": load_provider("DeepSeek"),
    "Zhipu GLM": load_provider("Zhipu GLM"),
}


def call_llm(prov, prompt, max_tokens=600, retries=4):
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
                time.sleep(2 ** attempt)
                continue
    raise RuntimeError(f"call_llm failed after {retries} retries: {last_err}")


def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def run_code(code, test_stmt, timeout=10):
    full = code + "\n\n" + test_stmt
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    tmp.write(full)
    tmp.close()
    try:
        r = subprocess.run(
            [sys.executable, tmp.name], capture_output=True, text=True, timeout=timeout
        )
        if r.returncode == 0:
            return ("pass", r.stdout.strip())
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


def judge_triggered(mode, judge_text):
    """判断 self-judge 是否触发停止。"""
    t = judge_text.strip().upper()
    if mode == "YESNO":
        return t.startswith("YES")
    if mode == "FINISH":
        return "FINISH" in t and "NEEDS_WORK" not in t
    return False


def trial_selfjudge(prov, mode, tid, desc, test_stmt, expected):
    """跑一条 self-judge 轨迹。停止信号 = self-judge; 后台记录真实正确性。"""
    traj = []
    last_code = ""
    for step in range(1, MAX_STEPS + 1):
        if step == 1:
            prompt = f"写 Python 代码。{desc}\n只输出代码, 不要解释, 不要包含测试语句。"
        else:
            prompt = (
                f"改进代码。{desc}\n上次代码:\n{last_code}\n"
                f"输出改进后的完整代码, 只输出代码, 不要包含测试语句。"
            )
        raw = call_llm(prov, prompt)
        code = extract_code(raw)
        last_code = code
        status, output = run_code(code, test_stmt)
        actually_ok = status == "pass" and output.strip() == expected
        judge = call_llm(prov, JUDGE_PROMPTS[mode].format(desc=desc, code=code), max_tokens=20)
        triggered = judge_triggered(mode, judge)
        traj.append({"step": step, "actually_ok": actually_ok, "triggered": triggered})
        if triggered:
            # self-judge 停。若代码实际不对 = 假阳性; 若对 = 正确收敛。
            if actually_ok:
                return {"stop": step, "actually_ok": True, "mode_outcome": "correct"}
            return {"stop": step, "actually_ok": False, "mode_outcome": "false_positive"}
    # 跑满上限未自停。若代码实际对 = 假阴性; 若不对 = 正确拒绝(继续也修不好)。
    final_ok = traj[-1]["actually_ok"] if traj else False
    if final_ok:
        return {"stop": MAX_STEPS, "actually_ok": True, "mode_outcome": "false_negative"}
    return {"stop": MAX_STEPS, "actually_ok": False, "mode_outcome": "correctly_rejected"}


def main():
    print("=" * 92)
    print("  Self-judge prompt reframe: YESNO vs FINISH 对假阴性率的影响")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}  Trials/task={TRIALS}  MAX_STEPS={MAX_STEPS}")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        for mode in ("YESNO", "FINISH"):
            print(f"    --- prompt mode: {mode} ---")
            for tid, desc, test_stmt, expected in TASKS:
                outcomes = []
                for t in range(TRIALS):
                    r = trial_selfjudge(prov, mode, tid, desc, test_stmt, expected)
                    outcomes.append(r)
                fn = sum(1 for o in outcomes if o["mode_outcome"] == "false_negative")
                fp = sum(1 for o in outcomes if o["mode_outcome"] == "false_positive")
                corr = sum(1 for o in outcomes if o["mode_outcome"] == "correct")
                actual_ok = sum(1 for o in outcomes if o["actually_ok"])
                print(f"      [{tid:10}] 实际对={actual_ok}/{TRIALS}  "
                      f"假阴性={fn}  假阳性={fp}  正确停={corr}  "
                      f"stops={[o['stop'] for o in outcomes]}")
                all_runs.append(
                    {
                        "provider": prov_name,
                        "model": prov["model"],
                        "mode": mode,
                        "task": tid,
                        "outcomes": outcomes,
                        "false_negative": fn,
                        "false_positive": fp,
                        "actual_correct": actual_ok,
                    }
                )
        print()

    # ---------- 汇总: 按 (provider, mode) 聚合假阴性率 ----------
    print("=" * 92)
    print("  汇总: 假阴性率 (代码对但 self-judge 未停) 按 prompt 模式对比")
    print("=" * 92)
    print(f"  {'provider':14}{'mode':10}{'总试验':>8}{'实际对':>8}{'假阴性':>8}"
          f"{'假阴性率':>10}{'假阳性':>8}")
    print(f"  {'-'*62}")
    summary = {"by_provider_mode": {}}
    for prov_name in PROVIDERS:
        for mode in ("YESNO", "FINISH"):
            runs = [r for r in all_runs if r["provider"] == prov_name and r["mode"] == mode]
            n_trials = sum(len(r["outcomes"]) for r in runs)
            actual = sum(r["actual_correct"] for r in runs)
            fn = sum(r["false_negative"] for r in runs)
            fp = sum(r["false_positive"] for r in runs)
            fn_rate = round(fn / actual, 3) if actual else None  # 假阴性率 = FN / 实际对的
            row = {
                "n_trials": n_trials,
                "actual_correct": actual,
                "false_negative": fn,
                "false_positive": fp,
                "fn_rate_over_actual": fn_rate,
            }
            summary["by_provider_mode"][f"{prov_name}|{mode}"] = row
            fnr_s = f"{fn_rate:.0%}" if fn_rate is not None else "—"
            print(f"  {prov_name:14}{mode:10}{n_trials:>8}{actual:>8}{fn:>8}"
                  f"{fnr_s:>10}{fp:>8}")

    out = {
        "meta": {
            "experiment": "selfjudge-prompt-reframe",
            "claim": "does reframing the self-judge prompt (YESNO->FINISH) change the false-negative rate?",
            "max_steps": MAX_STEPS,
            "trials_per_task": TRIALS,
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")
    print()
    print("  解读指引:")
    print("  - fn_rate_over_actual: 假阴性/实际正确数。若 FINISH << YESNO -> reframe 有效降假阴性")
    print("  - 若两者都 >0 -> 假阴性是 self-judge 的结构属性, 非 prompt 能消除")
    print("  - 若 FINISH 反升 -> reframe 引入新问题 (如假阳性上升)")


if __name__ == "__main__":
    main()
