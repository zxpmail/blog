# -*- coding: utf-8 -*-
"""
Probe vs Prose 扩展实验 (Part 12 核心数据): 20 场景 × 5 次 × 2 模型。

CLAIM (Part 12 核心论点, 待数据钉死):
  nexus 的 probe-vs-prose 命题对, 但对在执行频率, 不对在检测能力。
  给 LLM 充分信息时, prose 单次检测能力与 probe 相当 (探针 P2: 两模型 3/3 vs 3/3)。
  prose 的"腐烂"是时间函数 (需求漂移让其过期), 不是能力函数。
  本实验把探针扩到 20 场景 × 5 次, 测核心论点在更大样本上是否站得住。

DESIGN:
  20 场景 = 5 缺口类型 × 4 (3 难度档 + 1 合规对照)
  缺口类型 (ground truth 来源 = referent-mismatch 的 cache 类):
    - key-miss:    write(k) 只删触发 key, 漏同空间其他 key (TargetedCache)
    - prefix-miss: 删了部分 prefix, 漏其他 (变种)
    - tier-miss:   删 L1 漏 L2 (TieredCache)
    - cascade-miss: 未级联到依赖项 (变种)
    - referent-wrong: 删错对象 (如 user vs session)
  难度档 (控制给 prose-judge 的实现描述详细程度 —— 公平性核心):
    - easy:   缺口显眼 (注释明说 / 状态直白列出所有 key)
    - medium: 缺口藏在 write 函数体 (要看代码逻辑)
    - hard:   缺口需跨步推理 (规则未列全受影响项, 要从命名空间/依赖推断)
    - control: 合规实现 (flush all), 排除"总判违规"偏置

  每场景 5 次试验 (temp=0, 看稳定性 —— 探针 n=1 不够)。
  probe 确定性 (按构造全抓)。
  prose = LLM judge, 给充分信息 (规则全文 + 完整实现描述 + 缓存状态)。

FAIRNESS:
  prose 侧信息给全, 不靠 prompt 模糊取胜。若 prose 在信息充分时仍漏,
  那是文本信道结构性限制 (DPI), 不是 prompt 质量。
  反过来, 若 prose 全抓 (探针结果), 说明检测能力不是裂缝 —— 执行频率才是。

EXPECTED (决定 Part 12 论点):
  - 若 prose 在 hard 档大面积漏 → 探针结果是偶然, 论点要改 (检测能力也是裂缝)
  - 若 prose 各档稳定高正确率 (含 hard) → 论点钉死: 裂缝在执行频率

OUTPUT: scripts/results-v2/probe-vs-prose-expanded.json
USAGE:  python probe-vs-prose-expanded.py
"""
import io, sys, json, urllib.request, sqlite3, time, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "probe-vs-prose-expanded.json"
CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
TRIALS = 5


def load_provider(name):
    con = sqlite3.connect(CC_SWITCH_DB)
    cur = con.cursor()
    cur.execute(
        "SELECT settings_config FROM providers WHERE app_type='claude' AND name=?",
        (name,),
    )
    row = cur.fetchone()
    con.close()
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


def call_llm(prov, prompt, max_tokens=800, retries=4):
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


# ── 20 场景 ─────────────────────────────────────────────────────────────
# 每场景: id, gap_type, difficulty, rule, impl_description, violated
# ground truth: violated=True 表示有 under-inv 缺口 (应失效未失效)

def _key_rule(explicit_456=True):
    """key-miss 规则。explicit_456=True 时规则点名 456 (easy/medium); False 时需推理 (hard)。"""
    if explicit_456:
        return ("规则: 修改 user:123 时, 所有受影响的 user 命名空间缓存都必须失效。"
                "已知 user:456 属于同一 user 命名空间, 也受影响。")
    return ("规则: 修改 user:123 时, 所有受影响的缓存都必须失效。"
            "(规则未显式列出受影响项 —— 需从命名空间推理。)")


SCENARIOS = [
    # ── key-miss (TargetedCache): write(k) 只删触发 key ──
    {"id": "key-easy", "gap": "key-miss", "diff": "easy", "violated": True,
     "rule": _key_rule(True),
     "impl": "实现: write('user:123') 执行后缓存状态:\n  user:123 -> 已删除\n  user:456 -> 仍然存在\n注释: '只删除被直接修改的 key, 其他不动。'"},
    {"id": "key-medium", "gap": "key-miss", "diff": "medium", "violated": True,
     "rule": _key_rule(True),
     "impl": "实现: write 函数体:\n  def write(k):\n      if k in data: del data[k]\n执行 write('user:123') 后:\n  user:123 -> 已删除\n  user:456 -> 仍然存在"},
    {"id": "key-hard", "gap": "key-miss", "diff": "hard", "violated": True,
     "rule": _key_rule(False),
     "impl": "实现: write 函数体:\n  def write(k): del data[k]\n执行 write('user:123') 后:\n  user:123 -> 已删除\n  user:456 -> 仍然存在\n(缓存初始含 user:123 和 user:456, 同属 user 命名空间)"},
    {"id": "key-control", "gap": "key-miss", "diff": "control", "violated": False,
     "rule": _key_rule(True),
     "impl": "实现: write('user:123') 清空整个缓存:\n  user:123 -> 已删除\n  user:456 -> 已删除"},

    # ── prefix-miss: 删了部分 prefix 漏其他 ──
    {"id": "prefix-easy", "gap": "prefix-miss", "diff": "easy", "violated": True,
     "rule": "规则: 修改任何 user:* 缓存时, 所有 user:* 都必须失效。已知有 user:123, user:456, user:789。",
     "impl": "实现: write('user:123') 删除 user:123 和 user:456, 但保留 user:789。\n  user:123 -> 已删除\n  user:456 -> 已删除\n  user:789 -> 仍然存在\n注释: '只删前两个匹配项。'"},
    {"id": "prefix-medium", "gap": "prefix-miss", "diff": "medium", "violated": True,
     "rule": "规则: 修改任何 user:* 缓存时, 所有 user:* 都必须失效。有 user:123, user:456, user:789。",
     "impl": "实现: write 函数体:\n  def write(k):\n      for key in list(data)[:2]: del data[key]\n执行后:\n  user:123 -> 已删除\n  user:456 -> 已删除\n  user:789 -> 仍然存在"},
    {"id": "prefix-hard", "gap": "prefix-miss", "diff": "hard", "violated": True,
     "rule": "规则: 修改任何 user:* 缓存时, 所有同前缀缓存都必须失效。",
     "impl": "实现: write 函数体:\n  def write(k): del data[k]; del data[next(iter(data))]\n执行 write('user:123') 后 (初始 user:123/456/789):\n  user:123 -> 已删除\n  user:456 -> 已删除\n  user:789 -> 仍然存在"},
    {"id": "prefix-control", "gap": "prefix-miss", "diff": "control", "violated": False,
     "rule": "规则: 修改任何 user:* 缓存时, 所有 user:* 都必须失效。有 user:123/456/789。",
     "impl": "实现: write('user:123') 删除所有 user:* :\n  user:123/456/789 -> 全部已删除"},

    # ── tier-miss (TieredCache): 删 L1 漏 L2 ──
    {"id": "tier-easy", "gap": "tier-miss", "diff": "easy", "violated": True,
     "rule": "规则: 修改 user:123 时, L1 和 L2 两层缓存都必须失效。user:456 在两层都有。",
     "impl": "实现: write('user:123') 删除 L1[user:456], 但 L2[user:456] 保留。\n  L1 user:456 -> 已删除\n  L2 user:456 -> 仍然存在\n注释: '只清 L1。'"},
    {"id": "tier-medium", "gap": "tier-miss", "diff": "medium", "violated": True,
     "rule": "规则: 修改 user:123 时, L1 和 L2 两层缓存都必须失效。user:456 在两层都有。",
     "impl": "实现: write 函数体:\n  def write(k):\n      if k in l1: del l1[k]\n执行后:\n  L1 user:456 -> 已删除\n  L2 user:456 -> 仍然存在"},
    {"id": "tier-hard", "gap": "tier-miss", "diff": "hard", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有缓存层都必须失效。",
     "impl": "实现: write 函数体:\n  def write(k): del l1[k]\n执行后 (user:456 在 l1 和 l2):\n  L1 user:456 -> 已删除\n  L2 user:456 -> 仍然存在"},
    {"id": "tier-control", "gap": "tier-miss", "diff": "control", "violated": False,
     "rule": "规则: 修改 user:123 时, L1 和 L2 都必须失效。user:456 在两层。",
     "impl": "实现: write('user:123') 清 L1 和 L2:\n  L1 user:456 -> 已删除\n  L2 user:456 -> 已删除"},

    # ── cascade-miss: 未级联到依赖项 ──
    {"id": "casc-easy", "gap": "cascade-miss", "diff": "easy", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有派生缓存必须失效。session:abc 由 user:123 派生。",
     "impl": "实现: write('user:123') 删除 user:123, 但 session:abc (派生项) 保留。\n  user:123 -> 已删除\n  session:abc -> 仍然存在\n注释: '不级联到派生。'"},
    {"id": "casc-medium", "gap": "cascade-miss", "diff": "medium", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有派生缓存必须失效。session:abc 由 user:123 派生。",
     "impl": "实现: write 函数体:\n  def write(k): del data[k]\n执行后:\n  user:123 -> 已删除\n  session:abc -> 仍然存在"},
    {"id": "casc-hard", "gap": "cascade-miss", "diff": "hard", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有依赖该用户的缓存必须失效。",
     "impl": "实现: write 函数体:\n  def write(k): del data[k]\n执行后 (session:abc 和 decision:xyz 都派生自 user:123):\n  user:123 -> 已删除\n  session:abc -> 仍然存在\n  decision:xyz -> 仍然存在"},
    {"id": "casc-control", "gap": "cascade-miss", "diff": "control", "violated": False,
     "rule": "规则: 修改 user:123 时, 所有派生缓存必须失效。session:abc 派生自 user:123。",
     "impl": "实现: write('user:123') 删除 user:123 和所有派生:\n  user:123 -> 已删除\n  session:abc -> 已删除"},

    # ── referent-wrong: 删错对象 (user vs session) ──
    {"id": "ref-easy", "gap": "referent-wrong", "diff": "easy", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有 user:123 相关缓存失效。注意是 user 命名空间。",
     "impl": "实现: write 误删了 session:123 (而非 user:123 相关)。\n  user:123 -> 仍然存在 (应失效未失效)\n  session:123 -> 已删除 (误删)\n注释: '误用了 session 前缀。'"},
    {"id": "ref-medium", "gap": "referent-wrong", "diff": "medium", "violated": True,
     "rule": "规则: 修改 user:123 时, 所有 user:123 相关缓存失效。",
     "impl": "实现: write 函数体:\n  def write(k): del data['session:'+k.split(':')[1]]\n执行 write('user:123') 后:\n  user:123 -> 仍然存在\n  session:123 -> 已删除"},
    {"id": "ref-hard", "gap": "referent-wrong", "diff": "hard", "violated": True,
     "rule": "规则: 修改 user:123 时, 相关缓存失效。",
     "impl": "实现: write 函数体:\n  def write(k): del data['session:'+k.split(':')[1]]\n执行后:\n  user:123 -> 仍然存在\n  session:123 -> 已删除"},
    {"id": "ref-control", "gap": "referent-wrong", "diff": "control", "violated": False,
     "rule": "规则: 修改 user:123 时, user:123 相关缓存失效。",
     "impl": "实现: write('user:123') 删除 user:123:\n  user:123 -> 已删除"},
]


def probe_check(scenario):
    """PROBE: 确定性检查。直接看 ground truth (实现描述里是否声明了应失效项仍存在)。"""
    impl = scenario["impl"]
    # probe 跑的是事实: 扫描 impl 描述里"仍然存在"且属于应失效集合的项
    has_leftover = "仍然存在" in impl
    # 对照场景 impl 里所有项都"已删除", probe 判合规
    return has_leftover, ("probe 检测到应失效项仍存在" if has_leftover else "probe 确认全部已失效")


V_KEYWORDS = ["VIOLATION", "违规", "不合规"]
C_KEYWORDS = ["COMPLIANT", "合规"]


def prose_judge(prov, scenario):
    """PROSE: LLM judge, 给充分信息。返回 (detected, raw_text)。
    判定: 只看第一行是否是 VIOLATION/违规 系 —— 避免正文里"没有遗漏"等否定表达误命中。
    v2: 落盘 raw_text 以便复现 (探针版未存, 导致 bug 无法离线重判)。
    """
    prompt = f"""你是缓存失效合规审查员。判断以下实现是否符合规则。

{scenario['rule']}

{scenario['impl']}

问题: 这个实现是否完全符合规则? (注意检查是否有应该失效但没失效的缓存)
格式要求: 第一行只写一个词 —— VIOLATION 或 COMPLIANT, 不要其他内容。从第二行起简要说明。"""
    resp = call_llm(prov, prompt)
    first_line = resp.strip().split("\n", 1)[0].upper()
    # 第一行判定: 严格只看是否以 VIOLATION 系开头
    detected = any(first_line.startswith(k) for k in V_KEYWORDS)
    return detected, resp


def main():
    print("=" * 92)
    print(f"  Probe vs Prose 扩展 (Part 12): {len(SCENARIOS)} 场景 × {TRIALS} 次 × {len(PROVIDERS)} 模型")
    print("=" * 92)
    gaps = {}
    for s in SCENARIOS:
        gaps.setdefault(s["gap"], 0)
        gaps[s["gap"]] += 1
    print(f"  缺口类型分布: {gaps}")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        for sc in SCENARIOS:
            p_det, _ = probe_check(sc)
            prose_dets = []
            prose_raws = []
            for t in range(TRIALS):
                s_det, s_raw = prose_judge(prov, sc)
                prose_dets.append(int(s_det))
                prose_raws.append(s_raw[:120])  # 落盘前120字, 便于复现/审计
            prose_caught = sum(prose_dets)
            p_correct = (p_det == sc["violated"])
            s_rate = prose_caught / TRIALS
            s_majority = s_rate >= 0.6  # 多数票
            s_correct = (s_majority == sc["violated"])
            gt = "VIOL" if sc["violated"] else "COMP"
            mark = "✓" if s_correct else "✗"
            print(f"    {sc['id']:14} {sc['gap']:14} {sc['diff']:8} gt={gt} "
                  f"probe={'V' if p_det else 'C'}{mark if p_correct else '✗'} "
                  f"prose={prose_dets} {mark}({s_rate:.0%})")
            all_runs.append({
                "provider": prov_name, "model": prov["model"],
                "scenario": sc["id"], "gap": sc["gap"], "difficulty": sc["diff"],
                "ground_truth": sc["violated"],
                "probe_detected": p_det, "probe_correct": p_correct,
                "prose_detections_per_trial": prose_dets,
                "prose_raws_per_trial": prose_raws,
                "prose_majority_detected": s_majority,
                "prose_majority_correct": s_correct,
                "prose_rate": s_rate,
            })
        print()

    # ── 汇总 ──
    print("=" * 92)
    print("  汇总: probe vs prose 正确率 (按缺口类型 × 难度)")
    print("=" * 92)
    summary = {"by_provider": {}}
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        viol = [r for r in runs if r["ground_truth"]]
        ctrl = [r for r in runs if not r["ground_truth"]]
        probe_correct_viol = sum(1 for r in viol if r["probe_correct"])
        prose_correct_viol = sum(1 for r in viol if r["prose_majority_correct"])
        probe_correct_ctrl = sum(1 for r in ctrl if r["probe_correct"])
        prose_correct_ctrl = sum(1 for r in ctrl if r["prose_majority_correct"])
        # 按难度细分 (prose 漏在哪一档)
        by_diff = {}
        for d in ("easy", "medium", "hard", "control"):
            dr = [r for r in runs if r["difficulty"] == d]
            by_diff[d] = {
                "n": len(dr),
                "probe_correct": sum(1 for r in dr if r["probe_correct"]),
                "prose_majority_correct": sum(1 for r in dr if r["prose_majority_correct"]),
                "prose_missed": [r["scenario"] for r in dr if not r["prose_majority_correct"]],
            }
        summary["by_provider"][prov_name] = {
            "violation_n": len(viol),
            "probe_correct_on_violations": probe_correct_viol,
            "prose_majority_correct_on_violations": prose_correct_viol,
            "control_n": len(ctrl),
            "probe_correct_on_control": probe_correct_ctrl,
            "prose_majority_correct_on_control": prose_correct_ctrl,
            "by_difficulty": by_diff,
        }
        print(f"\n  {prov_name}:")
        print(f"    违规场景 (n={len(viol)}): probe {probe_correct_viol}/{len(viol)}, "
              f"prose {prose_correct_viol}/{len(viol)}")
        print(f"    对照场景 (n={len(ctrl)}): probe {probe_correct_ctrl}/{len(ctrl)}, "
              f"prose {prose_correct_ctrl}/{len(ctrl)}")
        for d in ("easy", "medium", "hard", "control"):
            dd = by_diff[d]
            print(f"    [{d:8}] n={dd['n']}  probe={dd['probe_correct']}/{dd['n']}  "
                  f"prose={dd['prose_majority_correct']}/{dd['n']}  "
                  f"missed={dd['prose_missed'] or '-'}")

    out = {
        "meta": {
            "experiment": "probe-vs-prose-expanded",
            "claim": "Part 12: prose detection ability matches probe when info is full; gap is execution frequency",
            "n_scenarios": len(SCENARIOS),
            "trials_per_scenario": TRIALS,
            "fairness": "prose given full info; tests text-channel structural limit",
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")
    print()
    print("  Part 12 论点判定:")
    print("  - 若 prose 在 hard 档大面积漏 (missed 多) → 论点要改 (检测能力也是裂缝)")
    print("  - 若 prose 各档稳定高正确率 → 论点钉死 (裂缝在执行频率)")


if __name__ == "__main__":
    main()
