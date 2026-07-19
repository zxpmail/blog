# -*- coding: utf-8 -*-
"""
Probe vs Prose — 交叉实验 (Part 12 主数据): 清晰度 × 漂移, 同一空间的两轴。

动机:
  前身实验各测一轴, 设计不同、N 不同、场景集不同 —— 不可直接比:
  - probe-vs-prose-expanded.py (20场景×5次): 测**清晰度轴**(vague vs precise),
    结论 "precise → prose=probe; vague → diverge; 检测能力不是裂缝"。
  - probe-vs-prose-drift-test.py (4场景×3次): 测**漂移轴**(fresh vs stale precise),
    结论 "precise-stale → 6/6 漏; drift 制造检测裂缝"。
  两个单轴实验拼出的"两轴综合"会被攻击为不可比。本实验把两轴作为因素**同时控制**,
  在同一场景集、同一 N、同一 ground truth 上交叉, 给 Part 12 一张干净的 2×2 表。

CLAIM (Part 12 两轴综合论点, 待交叉数据钉死):
  prose/probe gap 有两个独立轴, 且 drift **预设** precision (vagueness 所缺乏的):
  - 清晰度轴: vague 规则 → prose **diverge**(trial 间不一致, 时而抓时而漏);
              precise 规则 → 收敛。
  - 漂移轴:   precise-fresh → 抓; precise-stale → **miss**(干净定向失败)。
              vague 规则无从漂移(从没锚定集合), vague-fresh ≈ vague-stale(都 diverge)。
  probe 在所有单元都收敛抓到(确定性, 查 live namespace)。
  → drift 和 vagueness 是两种独立失败; drift 只对 precise 规则有干净定义。

FAIRNESS (与 expanded/drift 一致):
  prose-judge 全程拿到**当前缓存状态**(能看到 789 alive), 不靠扣信息。两轴的操纵
  全在**规则文本**里(枚举与否 = 清晰度; 反映当前 vs 写于初期 = 漂移), 状态给全。

DESIGN (2×2 + 1 control, 同一 ground truth):
  所有违规单元的事实相同: write(user:123) 应连带失效 user:789 (789 是 t1 新增),
  但 impl 只 del user:123, del user:456, 789 仍 alive → VIOLATION。
  - precise-fresh : 规则枚举当前全集(含 789), "当前版本"
  - precise-stale : 规则枚举 123/456 + 声称完整, "写于系统初期"(789 后加)
  - vague-fresh   : 规则"所有受影响", 不枚举, "当前版本"
  - vague-stale   : 规则"所有受影响", 不枚举, "写于系统初期, 可能未反映后续变化"
  - control       : precise-fresh 规则 + 合规 impl(全删) → COMPLIANT
  每单元 5 次 (temp=0, 看稳定性)。probe 确定性。两模型。

EXPECTED:
  - precise-fresh : CATCH (prose 收敛抓)
  - precise-stale : MISS  (drift 干净失败, 两模型一致)
  - vague-fresh   : DIVERGE (trial 间分叉)
  - vague-stale   : DIVERGE ≈ vague-fresh (drift 对 vague 无效 —— 核心交互发现)
  - control       : COMPLIANT
  probe 五单元全对。
  若结果如此 → Part 12 两轴综合论点钉死, "drift 预设 precision" 成立。

OUTPUT: scripts/results-v2/probe-vs-prose-synthesis.json
USAGE:  python probe-vs-prose-synthesis-test.py
"""
import io, sys, json, urllib.request, sqlite3, time, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "probe-vs-prose-synthesis.json"

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


# ── 2×2 + control: 清晰度(precise/vague) × 漂移(fresh/stale), 同一 ground truth ─
# 违规单元: 789 应失效但 alive。impl 都只 del 123, del 456。状态都给全(含 789 alive)。
# 两轴操纵全在 rule 文本: 枚举与否 × 当前/初期。

SCENARIOS = [
    {
        "id": "precise-fresh",
        "clarity": "precise",
        "drift": "fresh",
        "rule": (
            "规则(当前版本):当修改 user:123 时,必须失效 user:123、user:456、user:789"
            "(当前 user 命名空间全集,三者均受影响)。"
        ),
        "impl_description": (
            "实现:write('user:123') 执行后,del data['user:123'], del data['user:456']。"
            "当前缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除\n"
            "  user:789 -> 仍然存在"
        ),
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "alive_keys": ["user:789"],
        "violated": True,
    },
    {
        "id": "precise-stale",
        "clarity": "precise",
        "drift": "stale",
        "rule": (
            "规则(写于系统初期,已标注完整):当修改 user:123 时,必须失效以下完整清单中的 key"
            "(已确认无其他受影响 key):user:123、user:456。"
        ),
        "impl_description": (
            "实现(按上述规则编写):write('user:123') 执行后,del data['user:123'], del data['user:456']。"
            "当前缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除\n"
            "  user:789 -> 仍然存在"
        ),
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "alive_keys": ["user:789"],
        "violated": True,
    },
    {
        "id": "vague-fresh",
        "clarity": "vague",
        "drift": "fresh",
        "rule": (
            "规则(当前版本,与当前缓存状态一致):当修改 user:123 时,必须失效所有受影响的 "
            "user 命名空间缓存。"
        ),
        "impl_description": (
            "实现:write('user:123') 执行后,del data['user:123'], del data['user:456']。"
            "当前缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除\n"
            "  user:789 -> 仍然存在"
        ),
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "alive_keys": ["user:789"],
        "violated": True,
    },
    {
        "id": "vague-stale",
        "clarity": "vague",
        "drift": "stale",
        "rule": (
            "规则(写于系统初期,可能未反映后续命名空间变化):当修改 user:123 时,"
            "必须失效所有受影响的 user 命名空间缓存。"
        ),
        "impl_description": (
            "实现:write('user:123') 执行后,del data['user:123'], del data['user:456']。"
            "当前缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除\n"
            "  user:789 -> 仍然存在"
        ),
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "alive_keys": ["user:789"],
        "violated": True,
    },
    {
        "id": "compliant-control",
        "clarity": "precise",
        "drift": "fresh",
        "rule": (
            "规则(当前版本):当修改 user:123 时,必须失效 user:123、user:456、user:789"
            "(当前 user 命名空间全集,三者均受影响)。"
        ),
        "impl_description": (
            "实现:write('user:123') 执行后清空整个 user 命名空间。当前缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除\n"
            "  user:789 -> 已删除"
        ),
        "live_affected_keys": ["user:123", "user:456", "user:789"],
        "alive_keys": [],
        "violated": False,
    },
]


def probe_check(scenario):
    """PROBE: re-execute against LIVE namespace membership (t1 truth). 确定性。"""
    leaked = [k for k in scenario["live_affected_keys"] if k in scenario["alive_keys"]]
    detected = len(leaked) > 0
    return detected


def extract_verdict(resp):
    """结论 token 首次出现者获胜 (与 drift-test 同修复)。True=V / False=C / None=?。"""
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
    """把 per-run 判决分类为 CATCH/MISS/DIVERGE + split 串。"""
    v = sum(1 for x in verdicts if x is True)
    c = sum(1 for x in verdicts if x is False)
    p = sum(1 for x in verdicts if x is None)
    n = len(verdicts)
    if v == n:
        label = "CATCH"
    elif c == n:
        label = "MISS"
    else:
        label = "DIVERGE"
    split = f"{v}V/{c}C" + (f"/{p}?" if p else "")
    return label, split


def main():
    print("=" * 92)
    print("  Probe vs Prose — 交叉实验: 清晰度 × 漂移 (N=%d)" % N_RUNS)
    print("  Part 12 主数据: 两轴同场景集/N/GT 交叉, 给一张干净的 2×2 表")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}")
    print(f"  单元: precise-fresh / precise-stale / vague-fresh / vague-stale / compliant-control")
    print(f"  GT: 前 4 个 VIOLATION(789 应失效但 alive); control = COMPLIANT")
    print(f"  两轴操纵全在 rule 文本(枚举与否 × 当前/初期); 状态全给(789 alive 可见)")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        print(f"  {'单元':20}{'GT':>12}{'probe':>10}{'prose 分类':>14}{'per-run':>14}")
        print(f"  {'-'*72}")
        for sc in SCENARIOS:
            p_detect = probe_check(sc)
            majority, verdicts, raws = prose_judge_majority(prov, sc)
            gt = "VIOLATION" if sc["violated"] else "COMPLIANT"
            p_str = "VIOLATION" if p_detect else "COMPLIANT"
            label, split = classify(verdicts)
            p_correct = (p_detect == sc["violated"])
            # prose 对违规单元: CATCH=对; 对 control: MISS 才对... 用 majority correctness
            s_correct = (majority == sc["violated"])
            mark_p = "✓" if p_correct else "✗"
            mark_s = "✓" if s_correct else ("?" if majority is None else "✗")
            per_run = "".join("V" if x else ("C" if x is False else "?") for x in verdicts)
            print(f"  {sc['id']:20}{gt:>12}{p_str+mark_p:>10}{label+mark_s:>14}{per_run:>14}")
            all_runs.append({
                "provider": prov_name,
                "model": prov["model"],
                "scenario": sc["id"],
                "clarity": sc["clarity"],
                "drift": sc["drift"],
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

    # ── 2×2 汇总表 ──
    print("=" * 92)
    print("  2×2: 清晰度 × 漂移 (prose 分类; probe 全单元对)")
    print("=" * 92)
    summary = {"by_provider": {}}
    cells = [("precise", "fresh"), ("precise", "stale"),
             ("vague", "fresh"), ("vague", "stale")]
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        print(f"\n  {prov_name}:")
        print(f"  {'':18}{'fresh':>22}{'stale':>22}")
        print(f"  {'-'*62}")
        table = {}
        for clarity in ["precise", "vague"]:
            row = {}
            line = f"  {clarity:18}"
            for drift in ["fresh", "stale"]:
                if clarity == "precise" and drift == "fresh":
                    # precise-fresh 违规单元 + 还有一个 precise-fresh control; 取违规单元
                    cell_runs = [r for r in runs if r["clarity"] == clarity and r["drift"] == drift and r["ground_truth"] == "VIOLATION"]
                else:
                    cell_runs = [r for r in runs if r["clarity"] == clarity and r["drift"] == drift and r["ground_truth"] == "VIOLATION"]
                if cell_runs:
                    r = cell_runs[0]
                    cell_str = f"{r['prose_label']} {r['prose_split']}"
                    row[drift] = {"label": r["prose_label"], "split": r["prose_split"]}
                else:
                    cell_str = "-"
                    row[drift] = None
                line += f"{cell_str:>22}"
            table[clarity] = row
            print(line)
        ctrl = [r for r in runs if r["scenario"] == "compliant-control"]
        ctrl_str = f"{ctrl[0]['prose_label']} {ctrl[0]['prose_split']}" if ctrl else "-"
        probe_ok = all(r["probe_correct"] for r in runs)
        print(f"  control(应COMPLIANT): {ctrl_str}    probe 全对: {probe_ok}")
        summary["by_provider"][prov_name] = {"table": table, "control": ctrl_str, "probe_all_correct": probe_ok}

    print()
    print("  解读:")
    print("  - precise-fresh=CATCH, precise-stale=MISS → drift 在 precise 上是干净定向失败")
    print("  - vague-fresh≈vague-stale=DIVERGE → drift 对 vague 无效 (drift 预设 precision)")
    print("  - 若如此, Part 12 两轴综合 + 'drift 预设精确性' 钉死")

    out = {
        "meta": {
            "experiment": "probe-vs-prose-synthesis",
            "claim": "two independent axes (clarity, drift); drift presupposes precision",
            "predecessors": ["probe-vs-prose-expanded.py (clarity axis)", "probe-vs-prose-drift-test.py (drift axis)"],
            "design": "2x2 clarity(precise/vague) x drift(fresh/stale) + compliant control, same GT, N=%d" % N_RUNS,
            "fairness": "prose sees current state (789 alive visible); both axes manipulated in rule text only",
            "verdict_method": "first-occurrence conclusion tokens, N-run majority + CATCH/MISS/DIVERGE classification",
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")


if __name__ == "__main__":
    main()
