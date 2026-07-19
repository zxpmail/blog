# -*- coding: utf-8 -*-
"""
Probe vs Prose — CONFIDENCE-AS-SUPPRESSOR 实验 (回复三十 的 sharpened claim, 正式测)。

CLAIM (nexus-lab-zen, Part 2 评论区, 回复三十 所回应):
  "confidence language in a stale rule isn't neutral decoration, it's an active suppressor."
  即: 规则里的完整性声明("完整清单,无其他") 不只是"没帮助", 而是**主动抑制** generalization,
  把本来能靠命名空间推理抓到 789 的 prose-judge 压回到"信枚举、漏掉 789"。

前置证据 (drift-test, 非正式):
  - drift-enumerated (stale 但无 completeness 声明, 只说"当时的命名空间含 123/456"):
        DeepSeek VCC, GLM CVC → ~1/3 抓 (2/6)
  - drift-closed (stale + 显式"完整清单,无其他"):
        DeepSeek CCC, GLM CCC → 0/6 抓
  差别就在 completeness 声明 —— 但 drift-test 是 N=3、且两 cell 的措辞还混了别的差异。
  本实验正式 isolate "completeness 语言" 这一个变量。

METHOD (2×2 + control, 控制 completeness-language × staleness 两个因素):
  所有违规 cell 同一 ground truth: write(user:123) 应连带失效 user:789, 但 impl 只删 123+456, 789 alive。
  impl 与缓存状态全 cell 一致(789 alive 可见)。两轴的操纵全在 rule 文本:
  - completeness-language:
      none        = 规则枚举受影响 key, 但不声称穷尽 ("必须失效 user:123 和 user:456")
      completeness= 规则枚举 + 显式声称穷尽 ("必须失效以下完整清单, 已确认无其他: 123, 456")
  - staleness:
      fresh = 枚举含 789 (当前 namespace 全集)
      stale = 枚举只含 123/456 (789 是后加的, 规则写于初期)

  四个 cell:
  - none×fresh        : 规则列 123/456/789, 不声称穷尽      → 应 CATCH (789 在枚举里)
  - none×stale        : 规则列 123/456, 不声称穷尽          → ? (靠泛化抓 789?)
  - completeness×fresh: 规则列 123/456/789 + "完整无其他"   → 应 CATCH (789 在枚举里; 声明此刻真)
  - completeness×stale: 规则列 123/456 + "完整无其他"       → 应 MISS (suppressor: 声明此刻假, 压制泛化)
  - control           : none×fresh 规则 + 合规 impl (全删)  → 应 COMPLIANT (排偏置)

  核心 2×2 (前 4 个违规 cell):
                      fresh           stale
  none            CATCH (789列了)    ?        ← staleness-only effect
  completeness    CATCH (789列了)    MISS     ← suppressor effect (这里才漏)

  关键对照: none×stale vs completeness×stale —— 同 stale, 唯一差别 completeness 声明。
  若 none×stale 抓得到(哪怕偶尔)、completeness×stale 6/6 漏 → suppressor 效应干净 isolate。

FAIRNESS: prose-judge 全程看当前缓存状态(789 alive 可见), 不靠扣信息。
两模型 N=5 多数表决。probe 确定性(查 live namespace 全集 {123,456,789})。

EXPECTED:
  - none×fresh: CATCH (两模型, 5/5)
  - completeness×fresh: CATCH (两模型, 5/5) —— 声明此刻真, 不抑制
  - none×stale: 部分 CATCH (~1/3-2/5, 靠泛化) —— 与 drift-enumerated 一致
  - completeness×stale: MISS (两模型, ~0/5) —— suppressor 击溃
  → suppressor = (completeness×stale 的 miss) - (none×stale 的 miss) > 0, 干净可量。

OUTPUT: scripts/results-v2/probe-vs-prose-suppressor.json
USAGE:  python probe-vs-prose-suppressor-test.py
"""
import io, sys, json, urllib.request, sqlite3, time, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "probe-vs-prose-suppressor.json"

CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
N_RUNS = 5


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
        raise RuntimeError(f"provider '{name}' not found")
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


def call_llm(prov, prompt, max_tokens=1500, retries=4):
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
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read())
            thinking_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
                if block.get("type") == "thinking":
                    thinking_text = block.get("thinking", "")
            return thinking_text.strip() if thinking_text else str(data.get("content", ""))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
    raise RuntimeError(f"call_llm failed after {retries} retries: {last_err}")


# ── 2×2 + control: completeness-language × staleness, 同一 ground truth ─────────
# 违规 cell: 789 应失效但 alive。impl 都只 del 123, del 456。状态都给全(789 alive 可见)。
# 两轴操纵全在 rule 文本: 是否声称穷尽 × 枚举是否含 789。

# 枚举片段(随 staleness 变):
_ENUM_FRESH = "user:123、user:456、user:789"
_ENUM_STALE = "user:123、user:456"

# completeness 声明片段(随 completeness-language 变):
_COMP_NONE = "必须失效 {enum}(这些是受影响的 key)。"
_COMP_FULL = "必须失效以下完整清单(已确认无其他受影响 key):{enum}。"

SCENARIOS = [
    {
        "id": "none-fresh",
        "completeness": "none",
        "staleness": "fresh",
        "rule": f"规则(当前版本):当修改 user:123 时,{_COMP_NONE.format(enum=_ENUM_FRESH)}",
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "violated": True,
    },
    {
        "id": "none-stale",
        "completeness": "none",
        "staleness": "stale",
        "rule": f"规则(写于系统初期):当修改 user:123 时,{_COMP_NONE.format(enum=_ENUM_STALE)}",
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "violated": True,
    },
    {
        "id": "completeness-fresh",
        "completeness": "completeness",
        "staleness": "fresh",
        "rule": f"规则(当前版本):当修改 user:123 时,{_COMP_FULL.format(enum=_ENUM_FRESH)}",
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "violated": True,
    },
    {
        "id": "completeness-stale",
        "completeness": "completeness",
        "staleness": "stale",
        "rule": f"规则(写于系统初期,已标注完整):当修改 user:123 时,{_COMP_FULL.format(enum=_ENUM_STALE)}",
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "violated": True,
    },
    {
        "id": "compliant-control",
        "completeness": "none",
        "staleness": "fresh",
        "rule": f"规则(当前版本):当修改 user:123 时,{_COMP_NONE.format(enum=_ENUM_FRESH)}",
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "violated": False,
    },
]

# impl 描述: 违规 cell 都一样(漏删 789); control 合规(全删)
_IMPL_VIOLATION = (
    "实现:write('user:123') 执行后,del data['user:123'], del data['user:456']。"
    "当前缓存状态:\n"
    "  user:123 -> 已删除\n"
    "  user:456 -> 已删除\n"
    "  user:789 -> 仍然存在"
)
_IMPL_COMPLIANT = (
    "实现:write('user:123') 执行后清空整个 user 命名空间。当前缓存状态:\n"
    "  user:123 -> 已删除\n"
    "  user:456 -> 已删除\n"
    "  user:789 -> 已删除"
)

for sc in SCENARIOS:
    sc["impl_description"] = _IMPL_COMPLIANT if sc["id"] == "compliant-control" else _IMPL_VIOLATION


def probe_check(scenario):
    """PROBE: re-execute against LIVE namespace membership (t1 truth = {123,456,789}). 确定性。"""
    leaked = ["user:789"] if "789" in "".join(scenario["live_affected_keys"]) and scenario["violated"] else []
    # 违规 cell: 789 应失效但 alive; control: 无 alive
    detected = scenario["violated"]  # 违规 cell 都漏了 789(probe 查 live 永远抓); control 不违规
    return detected


def extract_verdict(resp):
    """结论 token 首次出现者获胜。True=V / False=C / None=?。"""
    r = resp.upper()
    viol_tokens = ["VIOLATION", "违规", "不合规"]
    comp_tokens = ["COMPLIANT", "合规"]
    viol_idx = min((r.find(t) for t in viol_tokens if r.find(t) >= 0), default=None)
    comp_idx = min((r.find(t) for t in comp_tokens if r.find(t) >= 0), default=None)
    if viol_idx is None and comp_idx is None:
        return None
    if viol_idx is None:
        return False
    if comp_idx is None:
        return True
    return viol_idx < comp_idx


def prompt_for(scenario):
    return f"""你是缓存失效合规审查员。判断以下实现是否符合规则。

{scenario['rule']}

{scenario['impl_description']}

问题: 这个实现是否完全符合规则? (注意检查是否有应该失效但没失效的缓存)
先用一句话给出结论: VIOLATION (违规) 或 COMPLIANT (合规), 再简要说明。"""


def prose_judge_majority(prov, scenario, n=N_RUNS):
    verdicts, raws = [], []
    for _ in range(n):
        raw = call_llm(prov, prompt_for(scenario))
        verdicts.append(extract_verdict(raw))
        raws.append(raw)
    valid = [v for v in verdicts if v is not None]
    majority = (sum(valid) > len(valid) / 2) if valid else None
    return majority, verdicts, raws


def classify(verdicts):
    v = sum(1 for x in verdicts if x is True)
    c = sum(1 for x in verdicts if x is False)
    n = len(verdicts)
    if v == n:
        label = "CATCH"
    elif c == n:
        label = "MISS"
    else:
        label = "DIVERGE"
    return label, f"{v}V/{c}C"


def main():
    print("=" * 92)
    print("  Probe vs Prose — CONFIDENCE-AS-SUPPRESSOR (N=%d)" % N_RUNS)
    print("  回复三十 claim: completeness 声明是 active suppressor, 不是中性装饰")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}")
    print(f"  2×2: completeness-language(none/completeness) × staleness(fresh/stale) + control")
    print(f"  GT: 前 4 个 VIOLATION(789 应失效但 alive); control = COMPLIANT")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        print(f"  {'cell':26}{'GT':>12}{'probe':>10}{'prose 分类':>14}{'per-run':>14}")
        print(f"  {'-'*76}")
        for sc in SCENARIOS:
            p_detect = probe_check(sc)
            majority, verdicts, raws = prose_judge_majority(prov, sc)
            gt = "VIOLATION" if sc["violated"] else "COMPLIANT"
            p_str = "VIOLATION" if p_detect else "COMPLIANT"
            label, split = classify(verdicts)
            p_correct = (p_detect == sc["violated"])
            s_correct = (majority == sc["violated"])
            mark_p = "✓" if p_correct else "✗"
            mark_s = "✓" if s_correct else ("?" if majority is None else "✗")
            per_run = "".join("V" if x else ("C" if x is False else "?") for x in verdicts)
            print(f"  {sc['id']:26}{gt:>12}{p_str+mark_p:>10}{label+mark_s:>14}{per_run:>14}")
            all_runs.append({
                "provider": prov_name,
                "model": prov["model"],
                "scenario": sc["id"],
                "completeness": sc["completeness"],
                "staleness": sc["staleness"],
                "ground_truth": gt,
                "probe_detected": p_detect,
                "probe_correct": p_correct,
                "prose_majority": majority,
                "prose_label": label,
                "prose_split": split,
                "prose_per_run": verdicts,
                "prose_raws": raws,
            })
        print()

    # ── 2×2 汇总 ──
    print("=" * 92)
    print("  2×2: completeness-language × staleness (prose 分类; probe 全单元对)")
    print("=" * 92)
    summary = {"by_provider": {}}
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        print(f"\n  {prov_name}:")
        print(f"  {'':24}{'fresh':>22}{'stale':>22}")
        print(f"  {'-'*66}")
        table = {}
        for comp in ["none", "completeness"]:
            line = f"  {comp:24}"
            row = {}
            for stal in ["fresh", "stale"]:
                cell = [r for r in runs if r["completeness"] == comp and r["staleness"] == stal and r["ground_truth"] == "VIOLATION"]
                if cell:
                    r = cell[0]
                    cell_str = f"{r['prose_label']} {r['prose_split']}"
                    row[stal] = {"label": r["prose_label"], "split": r["prose_split"]}
                else:
                    cell_str = "-"
                    row[stal] = None
                line += f"{cell_str:>22}"
            table[comp] = row
            print(line)
        ctrl = [r for r in runs if r["scenario"] == "compliant-control"]
        ctrl_str = f"{ctrl[0]['prose_label']} {ctrl[0]['prose_split']}" if ctrl else "-"
        probe_ok = all(r["probe_correct"] for r in runs)
        print(f"  control(应COMPLIANT): {ctrl_str}    probe 全对: {probe_ok}")
        summary["by_provider"][prov_name] = {"table": table, "control": ctrl_str, "probe_all_correct": probe_ok}

    print()
    print("  suppressor 量化:")
    print("  - none×stale vs completeness×stale 的抓率差 = suppressor 效应(completeness 声明单独贡献的 miss)")
    print("  - 若 none×stale 抓得到(哪怕 1/5)、completeness×stale 0/5 → suppressor 干净 isolate")

    out = {
        "meta": {
            "experiment": "probe-vs-prose-suppressor",
            "claim": "nexus: confidence language (completeness claim) is an active suppressor, not neutral decoration",
            "predecessors": ["probe-vs-prose-drift-test.py (drift-enumerated ~1/3 vs drift-closed 6/6)"],
            "design": "2x2 completeness-language(none/completeness) x staleness(fresh/stale) + control, same GT, N=%d" % N_RUNS,
            "fairness": "prose sees current state (789 alive visible); both axes manipulated in rule text only",
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")


if __name__ == "__main__":
    main()
