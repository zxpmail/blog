# -*- coding: utf-8 -*-
"""
Probe vs Prose — DRIFT 实验 (P2 探针的正半 claim, 实测)。

承接 probe-vs-prose-test.py。那个实验测了**同步全信息**情形:
prose-judge 拿到规则 + 完整实现 + 当前缓存状态 → prose = probe,
证伪了"prose 结构性无法检测"(unverifiable-by-construction)。

但那只测了负半(refute structure)。refined claim 的正半——
**"gap 是 drift(时序)的:描述从现实漂移后,prose 失败,probe 因 re-execute 而免疫"**——
还靠 nexus 的 incident(传闻,我无法核实)支撑。本实验直接测这一半。

CLAIM (refined, 待测):
  当规则的**静态枚举**与现实漂移(命名空间长出新 key,规则没更新)时,
  prose-judge(读规则的静态枚举)会漏掉新 key 的违规;
  probe(re-execute,查 live namespace membership)按构造必抓。
  → drift 是制造 prose 信息不对称的机制;gap 是时序的,不是结构的。

FAIRNESS (最会被攻击的点, 设计上先堵):
  prose-judge 仍拿到**当前缓存状态**(能看到 user:789 alive —— 不靠扣信息取胜)。
  唯一变量是**规则的枚举是否过时**:fresh 场景规则列了 789;drift 场景规则只列
  123/456(写于 t0,789 是 t1 新增)。prose 能看到 789 alive,问题是它会不会把
  "规则枚举"当穷尽(漏)还是把"规则意图(所有受影响)"当准绳(泛化抓到)。
  这正是 nexus 的 TTL 原型:detector 曾经 wired/firing,premise(命名空间={123,456})
  死了(长出 789),wire(规则文本)还绿着。

  probe 侧建模为**查 live namespace membership**(t1 = {123,456,789})再核对每个
  受影响 key 是否失效 —— "runner, not reader",对照环境而非对照规则文本。

DESIGN (4 场景, 控制"枚举新鲜度"这一个变量):
  - fresh-violation: 规则当前(列 123/456/789),impl 漏删 789,789 alive → VIOLATION
        锚定:无 drift 时 prose 应抓(证明 prose 没坏, namespace 推理做得到)。
  - drift-enumerated: 规则写于 t0(只列 123/456, "当时的命名空间"), impl 漏删 789 → VIOLATION
        测:prose 信枚举(漏)还是泛化(抓)?
  - drift-closed:    规则写于 t0 + 显式"完整清单,无其他"(只列 123/456), impl 漏删 789 → VIOLATION
        最强 drift:显式完整性声明抑制泛化, prose 最可能漏。
  - compliant-control:规则当前(列 123/456/789), impl 全删, 全 gone → COMPLIANT
        排除"总判违规"偏置。

  关键对照: fresh-violation vs drift-enumerated vs drift-closed ——
  同一个 ground-truth 违规(789 应失效但 alive)、同一个 impl、唯一差别是规则枚举是否新鲜。
  若 prose 抓 fresh 漏 drift → drift 盲点干净分离。

VERDICT PARSING (v1 踩的坑, v2 修):
  v1 用关键词扫描全文, 把"没有**遗漏**""没有应失效但**未失效**"误判成 VIOLATION ——
  解释性措辞污染了结论提取, 把两个 control 的真 COMPLIANT 翻成假 VIOLATION。
  v2: 只认**结论性 token**(VIOLATION/违规/不合规 vs COMPLIANT/合规), 取**首次出现**者
  (prompt 要求结论先行), 并对违规场景跑 N=3 多数表决(DeepSeek 在静态/动态歧义上会
  长篇 ramble 甚至截断, 单次不可靠)。

两模型: DeepSeek (deepseek-v4-flash) + Zhipu GLM (glm-5.2), 从 cc-switch.db 读凭证。

EXPECTED:
  - probe 四场景全对(确定性, 按构造)。
  - fresh-violation: prose 多数抓(无 drift)。
  - drift-enumerated / drift-closed: prose 多数漏(尤其 drift-closed)。
  - compliant-control: prose 多数判 COMPLIANT。
  若 drift 两档多数漏而 fresh 多数抓 → refined claim 正半成立
       (reply 29 升级为"我的两个实验 + 你的 incident 作 field 确认")。

OUTPUT: scripts/results-v2/probe-vs-prose-drift.json
USAGE:  python probe-vs-prose-drift-test.py
"""
import io, sys, json, urllib.request, sqlite3, time, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "probe-vs-prose-drift.json"

CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
N_RUNS = 3  # 违规场景 prose 单次不可靠(DeepSeek ramble), 多数表决


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


# ── 场景: 控制"规则枚举是否新鲜"这一个变量 ────────────────────────────
# 所有违规场景的 ground truth 相同: user:789 在 t1 新增, 应失效但 alive。
# impl 都一样: del user:123, del user:456 (按 t0 规则写的), 789 未动。
# 唯一差别: prose 看到的"规则文本"列了哪些 key —— fresh 列了 789, drift 没列。

SCENARIOS = [
    {
        "id": "fresh-violation",
        "kind": "fresh",
        "rule": (
            "规则(当前版本):当修改 user:123 时,必须失效 user 命名空间下所有受影响的 key。"
            "当前 user 命名空间包含:user:123、user:456、user:789(三者均受影响)。"
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
        "violation_reason": "无 drift: 规则列了 789, prose 应抓",
    },
    {
        "id": "drift-enumerated",
        "kind": "drift",
        "rule": (
            "规则(写于系统初期):当修改 user:123 时,必须失效 user 命名空间下所有受影响的 key。"
            "当时的 user 命名空间包含:user:123、user:456。"
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
        "violation_reason": "drift: 规则写于 t0 只列 123/456, t1 长出 789, prose 读静态枚举可能漏",
    },
    {
        "id": "drift-closed",
        "kind": "drift",
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
        "violation_reason": "最强 drift: 规则显式声称完整无其他, prose 若信完整性声明则漏 789",
    },
    {
        "id": "compliant-control",
        "kind": "control",
        "rule": (
            "规则(当前版本):当修改 user:123 时,必须失效 user 命名空间下所有受影响的 key。"
            "当前 user 命名空间包含:user:123、user:456、user:789(三者均受影响)。"
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
        "violation_reason": "合规(无缺口): 三 key 全失效",
    },
]


def probe_check(scenario):
    """
    PROBE 侧: re-execute against LIVE namespace membership (t1 truth), 不读规则文本。
    drift 场景下, probe 仍看见 789 ∈ live namespace 且 alive → 抓到。纯确定性。
    """
    leaked = [k for k in scenario["live_affected_keys"] if k in scenario["alive_keys"]]
    detected = len(leaked) > 0
    reason = (f"probe 查 live namespace, {leaked} 仍 alive (drift 下规则没列但 live 有)"
              if detected else "probe 确认所有 live 受影响 key 均已失效 (合规)")
    return detected, reason


def extract_verdict(resp):
    """
    结论性 token 首次出现者获胜。v1 的全文关键词扫描会把"没有遗漏"误判, v2 只认结论词。
    返回 True(VIOLATION) / False(COMPLIANT) / None(PARSE_FAIL)。
    '不合规' 含 '合规' 但 '不' 在前 → viol_idx < comp_idx → 判 violation, 正确。
    """
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
    """跑 n 次, 多数表决。返回 (majority_verdict, [per-run verdicts], [per-run raws])。"""
    verdicts, raws = [], []
    for _ in range(n):
        raw = call_llm(prov, prompt_for(scenario))
        verdicts.append(extract_verdict(raw))
        raws.append(raw)
    valid = [v for v in verdicts if v is not None]
    if not valid:
        majority = None
    else:
        majority = sum(valid) > len(valid) / 2  # True = 多数判 violation
    return majority, verdicts, raws


def main():
    print("=" * 92)
    print("  Probe vs Prose — DRIFT: 规则枚举漂移下, prose 还抓得到吗? (N=%d 多数表决)" % N_RUNS)
    print("  (承接 probe-vs-prose: 同步全信息 prose=probe 已证伪 structure; 本实验测 drift 正半)")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}")
    print(f"  Scenarios: {len(SCENARIOS)} (fresh-violation / drift-enumerated / drift-closed / compliant-control)")
    print(f"  Ground truth: 前 3 个 VIOLATION(789 应失效但 alive); control = COMPLIANT")
    print(f"  关键变量: prose 看到的规则枚举是否新鲜(fresh 列 789, drift 只列 123/456)")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        print(f"  {'场景':22}{'kind':>10}{'ground truth':>14}{'probe':>10}{'prose 多数':>12}{'per-run':>14}")
        print(f"  {'-'*84}")
        for sc in SCENARIOS:
            p_detect, _ = probe_check(sc)
            majority, verdicts, raws = prose_judge_majority(prov, sc)
            gt = "VIOLATION" if sc["violated"] else "COMPLIANT"
            p_str = "VIOLATION" if p_detect else "COMPLIANT"
            if majority is None:
                m_str = "PARSE_FAIL"
            else:
                m_str = "VIOLATION" if majority else "COMPLIANT"
            p_correct = (p_detect == sc["violated"])
            s_correct = (majority == sc["violated"])
            mark_p = "✓" if p_correct else "✗"
            mark_s = "✓" if s_correct else ("?" if majority is None else "✗")
            # per-run 记号: V=violation C=compliant ?=parse_fail
            per_run = "".join("V" if v else ("C" if v is False else "?") for v in verdicts)
            print(f"  {sc['id']:22}{sc['kind']:>10}{gt:>14}{p_str+mark_p:>10}{m_str+mark_s:>12}{per_run:>14}")
            all_runs.append({
                "provider": prov_name,
                "model": prov["model"],
                "scenario": sc["id"],
                "kind": sc["kind"],
                "ground_truth": gt,
                "probe_detected": p_detect,
                "probe_correct": p_correct,
                "prose_majority": majority,
                "prose_correct": s_correct,
                "prose_per_run": verdicts,
                "prose_raws": raws,
            })
        print()

    # ── 汇总 ──
    print("=" * 92)
    print("  汇总: fresh vs drift 下 prose 多数抓取率 (核心对照)")
    print("=" * 92)
    summary = {"by_provider": {}}
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        fresh = [r for r in runs if r["scenario"] == "fresh-violation"]
        drift = [r for r in runs if r["kind"] == "drift"]
        ctrl = [r for r in runs if r["kind"] == "control"]

        def verdict_str(r):
            m = r["prose_majority"]
            return "VIOLATION" if m else ("COMPLIANT" if m is False else "PARSE_FAIL")

        fresh_verdicts = [verdict_str(r) for r in fresh]
        drift_verdicts = [verdict_str(r) for r in drift]
        ctrl_verdicts = [verdict_str(r) for r in ctrl]

        fresh_caught = sum(1 for r in fresh if r["prose_correct"])
        drift_caught = sum(1 for r in drift if r["prose_correct"])
        drift_missed = [r["scenario"] for r in drift if not r["prose_correct"]]
        ctrl_ok = sum(1 for r in ctrl if r["prose_correct"])

        row = {
            "fresh_verdicts": fresh_verdicts,
            "drift_verdicts": drift_verdicts,
            "drift_missed": drift_missed,
            "control_verdicts": ctrl_verdicts,
            "probe_all_correct": all(r["probe_correct"] for r in runs),
        }
        summary["by_provider"][prov_name] = row
        print(f"\n  {prov_name}:")
        print(f"    fresh-violation (无drift, 应 VIOLATION): {fresh_verdicts}")
        print(f"    drift (规则枚举过时, 应 VIOLATION):      {drift_verdicts}  漏: {drift_missed or '无'}")
        print(f"    control (合规, 应 COMPLIANT):            {ctrl_verdicts}")
        print(f"    probe 全对: {row['probe_all_correct']}")

    print()
    print("  解读指引:")
    print("  - fresh=VIOLATION + drift=COMPLIANT → drift 盲点成立 (reply 29 正半 claim 升级为两实验佐证)")
    print("  - fresh=VIOLATION + drift=VIOLATION → prose 对枚举漂移 robust, claim 收窄 (仍诚实)")
    print("  - control 必须 COMPLIANT, 否则偏置/解析问题, 数据作废")

    out = {
        "meta": {
            "experiment": "probe-vs-prose-drift",
            "claim": "refined: gap is drift (temporal), not structure — drift defeats prose, probe is drift-immune",
            "predecessor": "probe-vs-prose-test.py (同步全信息 prose=probe, 已证伪 structure)",
            "fairness": "prose sees current state (789 alive visible); only variable is whether rule enumeration is fresh or stale",
            "n_runs": N_RUNS,
            "verdict_method": "first-occurrence of conclusion tokens (VIOLATION/违规/不合规 vs COMPLIANT/合规), majority over N runs",
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")


if __name__ == "__main__":
    main()
