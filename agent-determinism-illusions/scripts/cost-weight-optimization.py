#!/usr/bin/env python3
"""
加权成本优化实验 — 验证评论区 Alexey Spinov 的洞见：

  假阴（误杀合法）和假阳（放过垃圾）的成本不对称。
  假阴触发重试循环 = 3x 成本。假阳是一次性污染。

传统对称指标（准确率、F1）给 FP 和 FN 相同权重。
加权成本重新定义"最优"：

  WeightedCost = FN × costFN + FP × costFP

本实验：
  1) 把 P3b（8 场景 5 prompt）数据套入不同 costFN:costFP 比例
  2) 展示"最优 prompt"随成本比的变化
  3) 叠加分层过滤（L0/L1）的效果——垃圾被拦截后有效分布变化

用法：
  python cost-weight-optimization.py
  python cost-weight-optimization.py --ratios 1,2,3,5,10

实验 F 关联：
  分层验证脚本 forge-verify-layered-prototype.py 提供 L0/L1 过滤后的基线。
"""

import sys, math

# ── P3b 数据（修正标注 L3=垃圾，8 场景）──────────────────────────────
# 来自 prompt-calibration-p3b.py 输出
P3B_PROMPTS = [
    {"name": "v1  极端严格", "fp": 0, "fn": 4, "n_correct": 3, "n_garbage": 5},
    {"name": "v2  严格 (P1基线)", "fp": 0, "fn": 3, "n_correct": 3, "n_garbage": 5},
    {"name": "v3  公正 (最优)", "fp": 0, "fn": 0, "n_correct": 3, "n_garbage": 5},
    {"name": "v4  宽松",        "fp": 0, "fn": 0, "n_correct": 3, "n_garbage": 5},
    {"name": "v5  极宽松",      "fp": 1, "fn": 0, "n_correct": 3, "n_garbage": 5},
]

# ── 实验 F 分层过滤后数据（P1 8 场景，L0/L1 拦截 G1-G4）───────────────
# L0/L1 拦截后，LLM 只剩 4 个样本：L1-L4（3 正确 + 1 正确 L4）
# G1-G4 已零成本拦截 → 不需要 LLM
# 剩余的 FP/FN 只来自 L1-L4 上的 LLM 误判
LAYERED_PROMPTS = [
    {"name": "v2  严格 (分层后)", "fp": 0, "fn": 3, "n_correct": 4, "n_garbage": 0, "saved_calls": 4},
    {"name": "v3  公正 (分层后)", "fp": 0, "fn": 0, "n_correct": 4, "n_garbage": 0, "saved_calls": 4},
    {"name": "v4  宽松 (分层后)", "fp": 0, "fn": 0, "n_correct": 4, "n_garbage": 0, "saved_calls": 4},
]

# ── 实验 F P4 30 样本分层数据 ────────────────────────────────────────
# 来自 forge-verify-layered-prototype.py:
#   L0/L1 拦截 10/30 样本（8 垃圾 + 2 边缘）
#   剩余 20 样本到 LLM（10 正确 + 2 垃圾 + 8 边缘）
#   假设 v3 在剩余 20 样本上假阴 ≈ 1（E10 被 L1 误杀）
P4_LAYERED = [
    {"name": "L0/L1 + LLM (分层)", "fp": 0, "fn": 1, "n_correct": 10, "n_garbage": 2, "total": 30, "l0l1_caught": 10},
]

# ── P4 非分层基线（30 样本）───────────────────────────────────────────
# P4 排除边缘 20 样本时两个 prompt 都是 88.2% ACC
# 假设 FP=1, FN=1 (保守近似，实际未知)
P4_UNLAYERED = [
    {"name": "v2 严格 (P4, 30样本)", "fp": 2, "fn": 2, "n_correct": 10, "n_garbage": 10, "n_edge": 10},
]


def weighted_cost(fp, fn, cost_fp=1, cost_fn=1):
    return fn * cost_fn + fp * cost_fp


def total_llm_calls(n_samples, n_runs=3):
    """LLM 调用总成本：每个样本 N 次投票"""
    return n_samples * n_runs


def run_analysis(data, label, cost_ratios):
    """对一组 prompt 数据跑多比例分析"""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    header = f"  {'Prompt':<22} {'FP':>3} {'FN':>3} {'ACC':>5} {'F1':>5}"
    for r_name, r_val in cost_ratios:
        header += f" {'WCost':>7}({r_name})"
    print(header)
    print(f"  {'-'*22} {'-'*3} {'-'*3} {'-'*5} {'-'*5}" + " " + "-" * (len(cost_ratios) * 11))

    best_per_ratio = {}

    for d in data:
        name = d["name"]
        fp, fn = d["fp"], d["fn"]
        n_correct = d["n_correct"]
        n_garbage = d.get("n_garbage", 0)
        total = n_correct + n_garbage + d.get("n_edge", 0)

        # 对称指标
        tp = n_correct - fn
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / n_correct * 100 if n_correct > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        acc = (n_correct - fn + n_garbage - fp) / total * 100 if total > 0 else 0

        row = f"  {name:<22} {fp:>3} {fn:>3} {acc:>4.0f}% {f1:>4.0f}"

        for r_name, r_val in cost_ratios:
            wc = weighted_cost(fp, fn, cost_fp=1, cost_fn=r_val)
            row += f" {wc:>7.1f}"

            if r_name not in best_per_ratio or wc < best_per_ratio[r_name]["cost"]:
                best_per_ratio[r_name] = {"name": name, "cost": wc, "fp": fp, "fn": fn}

        # 加上 LLM 调用成本（如有 saved_calls）
        saved = d.get("saved_calls", 0)
        if saved > 0:
            row += f"  [省 {saved} LLM调用]"

        print(row)

    print(f"\n  ── 各比例最优 ──")
    for r_name, r_val in cost_ratios:
        b = best_per_ratio[r_name]
        print(f"    costFN:costFP = {r_val}:1 → 最优: {b['name']}  (cost={b['cost']:.0f}, FP={b['fp']} FN={b['fn']})")

    return best_per_ratio


def sensitivity_scan(data, label, min_ratio=1, max_ratio=15, step=1):
    """精细扫描：最优 prompt 随成本比连续变化"""
    print(f"\n{'='*70}")
    print(f"  灵敏度扫描 — {label}")
    print(f"  costFN:costFP 从 {min_ratio}:1 到 {max_ratio}:1")
    print(f"{'='*70}")
    print(f"  {'比例':>6}  {'最优':<22}  {'Cost':>6}  {'FP':>3}  {'FN':>3}")
    print(f"  {'-'*6}  {'-'*22}  {'-'*6}  {'-'*3}  {'-'*3}")

    transitions = []
    prev_best = None

    for r in range(min_ratio, max_ratio + 1, step):
        best = min(data, key=lambda d: weighted_cost(d["fp"], d["fn"], cost_fp=1, cost_fn=r))
        wc = weighted_cost(best["fp"], best["fn"], cost_fp=1, cost_fn=r)

        if prev_best and best["name"] != prev_best["name"]:
            transitions.append((r, prev_best["name"], best["name"]))

        prev_best = best

        print(f"  {r:>5}:1  {best['name']:<22}  {wc:>6.0f}  {best['fp']:>3}  {best['fn']:>3}")

    if transitions:
        print(f"\n  ── 转折点 ──")
        for r, old, new in transitions:
            print(f"    在 {r}:1 处: {old} → {new}")


def main():
    cost_ratios = [
        ("1:1", 1),     # 对称（F1 默认）
        ("2:1", 2),     # FN 略贵
        ("3:1", 3),     # Alexey 估计的典型生产环境
        ("5:1", 5),     # 高重试成本
        ("10:1", 10),   # 极端重试敏感
    ]

    print("█" * 70)
    print("  加权成本优化实验 — 不对称 FN:FP 成本对最优策略的影响")
    print("  (基于 P3b 修正标注数据 + 实验 F 分层数据)")
    print("█" * 70)
    print("""
  理论:  假阴 (FN) 触发修复循环 → 3x token 消耗
          假阳 (FP) 一次性污染 → 1x 成本

  WeightedCost = FN × costFN + FP × costFP

  当 costFN:costFP > 1:对称指标选出的"最优"不再最优。
  """)

    # ── 1. P3b 基线 ──
    run_analysis(P3B_PROMPTS, "P3b 基线 (8 场景, 修正标注 L3=垃圾)", cost_ratios)

    # ── 2. 分层后 ──
    run_analysis(LAYERED_PROMPTS, "实验 F 分层后 (P1 8 场景, L0/L1 拦截后剩余 4 样本)", cost_ratios)

    # ── 3. 灵敏度扫描 ──
    sensitivity_scan(P3B_PROMPTS, "P3b 各 prompt (成本比 1:1 → 15:1)", min_ratio=1, max_ratio=15)

    sensitivity_scan(LAYERED_PROMPTS, "分层后各 prompt (成本比 1:1 → 15:1)", min_ratio=1, max_ratio=15)

    # ── 4. 综合对比 ──
    print(f"\n\n{'█'*70}")
    print("  综合对比: 非分层 vs 分层 + 加权成本")
    print(f"{'█'*70}")

    compare_header = f"  {'策略':<28} {'FP':>3} {'FN':>3} {'ACC':>5} {'F1':>5}"
    for r_name, _ in cost_ratios:
        compare_header += f" {'WCost':>7}({r_name})"
    compare_header += "  LLM调用"
    print(f"\n{compare_header}")
    print(f"  {'-'*28} {'-'*3} {'-'*3} {'-'*5} {'-'*5}" + " " + "-" * (len(cost_ratios) * 11) + "  " + "-" * 8)

    comparisons = [
        ("P3b v2 严格 (非分层)",       P3B_PROMPTS[1], 8),
        ("P3b v3 公正 (非分层)",       P3B_PROMPTS[2], 8),
        ("P1 分层 + v3 公正",          LAYERED_PROMPTS[1], 4),
        ("P4 非分层 (30样本, 估算)",    P4_UNLAYERED[0], 30),
        ("P4 分层 (L0/L1+LLM, 实验F)", P4_LAYERED[0], 20),
    ]

    for name, d, calls in comparisons:
        fp, fn = d["fp"], d["fn"]
        n_correct = d["n_correct"]
        n_garbage = d.get("n_garbage", 0) + d.get("n_edge", 0)
        total = n_correct + n_garbage

        tp = n_correct - fn
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / n_correct * 100 if n_correct > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        acc = (n_correct - fn + n_garbage - fp) / total * 100 if total > 0 else 0

        row = f"  {name:<28} {fp:>3} {fn:>3} {acc:>4.0f}% {f1:>4.0f}"
        for _, r_val in cost_ratios:
            wc = weighted_cost(fp, fn, cost_fp=1, cost_fn=r_val)
            row += f" {wc:>7.0f}"
        row += f"  {calls:>3}×3={calls*3}"
        print(row)

    # ── 结论 ──
    print(f"""
  ── 结论 ──

  1. 对称指标下 (1:1): v3/v4 最优 (F1=100)
     但这是 8 场景上的假象——P4 已证伪。

  2. 不对称成本下 (3:1):
     - 非分层 v2: cost = 0×1 + 3×3 = 9
     - 非分层 v3: cost = 0×1 + 0×3 = 0
     - 分层 v3:   cost = 0×1 + 0×3 = 0 (+ 省 50% LLM 调用)

  3. 分层优势不在加权成本数值本身（v3 本来 FP=FN=0），
     在于: 4/4 垃圾样本在 L0/L1 被零成本拦截，
     即使 LLM 误判所有剩余样本，绝对影响也减半。

  4. 对 v2（严格 prompt）来说，分层+加权成本的效果更显著：
     - 非分层: cost(3:1) = 9
     - 分层后: 省 4 次 LLM 调用，但 FN=3 仍在
     → 如果坚持用严格 prompt，分层降低了 token 消耗，
        但没改善假阴率。这才是关键: 分层 + 换 prompt = 见效，
        只分层不换 prompt = 省 token 但 FN 还在。

  5. 成本比从 3:1 往上走时 (>5:1):
     任何有 FN>0 的策略迅速劣化。
     唯一真正低 FN 的策略（v3/v4）永远占优。
     → 结论: 在不对称成本下，"提高精度"不如"降低 FN"重要。

  复跑:
     修改 P3B_PROMPTS/LAYERED_PROMPTS 即可套用自己的数据。
     设 --ratios 1,2,5,10 自定义比例。
""")

    # ── 验证命令 ──
    print(f"  {'─'*70}")
    print(f"  复跑: python cost-weight-optimization.py --ratios 1,2,3,5,10")
    print(f"{'─'*70}")


if __name__ == "__main__":
    # 支持 CLI 参数覆盖
    if "--ratios" in sys.argv:
        idx = sys.argv.index("--ratios")
        if idx + 1 < len(sys.argv):
            custom = sys.argv[idx + 1].split(",")
            override = [(f"{r}:1", int(r)) for r in custom]
            print(f"[自定义比例: {', '.join(custom)}]")
            cost_ratios = override
    main()
