"""
Experiment: Multi-layer constraint super-additivity — sensitivity analysis.

Falsifiable claim (from Part 9, Constraint Interaction section):
    L2+L3 combined reduces defective pass-through by ~88.3%, which is 4.6x
    the sum of the individual reductions (L2: 1.7%, L3: 17.3%). The question
    this script answers: is that super-additive interaction a property of one
    calibrated operating point (the specific V1-V4 success rates and the L3
    detection rate), or is it structural across the parameter space?

    Claim: the super-additivity ratio R(L2+L3)/(R(L2)+R(L3)) >= 1 across a
    grid over vector success rates, V4 base rate, and L3 detection rate.
    Falsification: if any cell in a sensible parameter range is sub-additive
    (ratio < 1), the architectural claim is not structural.

Method:
    Exact closed form for defective pass rate under the product-of-failure
    model used by multi-layer-constraint-test.py. For a config with available
    (unblocked) vector set S, P(pass) = 1 - (1-FP) * prod_{v in S}(1 - p_v),
    because the agent passes if any available vector succeeds, else the
    defective hits the baseline verification FP. Reduction vs NONE:
    R(C) = (1-FP) * (prod_C - prod_NONE).

    Interaction term:
        R(L2+L3) - R(L2) - R(L3)
            = (1-FP) * (1 - ab) * (D' - cD)      [lowercase = 1-p for each]
    where a,b are the L2-blocked vectors' failure rates (a = 1-p_V1, b = 1-p_V2),
    c is V3's failure rate, D = 1-p_V4(base), D' = 1-p_V4(under L3). Since
    L3 never *increases* V4 success (D' >= D >= cD), and 1-ab >= 0, the
    interaction is non-negative: super-additivity is structural in this model.

    Grid sweep: V1, V2, V3, V4(base) in {0.2, 0.5, 0.85}, L3 detection rate in
    {0.0, 0.5, 0.918} -> 3^5 = 243 cells. Per cell, compute DPR for NONE/L2/L3/
    L2+L3 and the ratio. Report the ratio distribution and the cells where the
    ratio is minimal / maximal.

    Cross-check: the closed form is validated against the Monte Carlo core from
    multi-layer-constraint-test.py (same simulate logic) on a subset of cells.

    Ordering dimension: all 24 permutations of the 4-vector preference order at
    the article's operating point. First-success pass probability depends only
    on the *set* of available vectors, not their order, so DPR should be
    identical across permutations. This is a model-fidelity limit, not a
    real-world claim.

Dependencies: none (pure Python).

Expected result:
    Zero sub-additive cells (ratio >= 1 everywhere). Ratio ranges from near 1
    (one layer decorative: V1/V2 never succeed, or V3 always succeeds) to
    several x (the article's operating point, boosted by the L3 V4-crush).

    Ordering check: max DPR spread across 24 permutations ~ 0 (order no-op).

How to falsify:
    - Any grid cell with ratio < 1 in a sensible parameter range.
    - Monte Carlo disagreeing with the closed form beyond MC noise.
"""
import sys
import io
import json
import random
import statistics
import itertools
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters ──────────────────────────────────────────────────────────────

BASELINE_VERIFY_FP = 0.05

# Grid levels (vector base success when not blocked)
LEVELS = {
    "V1_modify_verify": [0.20, 0.50, 0.85],
    "V2_modify_routing": [0.20, 0.50, 0.85],
    "V3_fake_signals": [0.20, 0.50, 0.85],
    "V4_skip_base": [0.20, 0.50, 0.85],
    "L3_detection": [0.0, 0.50, 0.918],
}

# Article operating point (Part 9 Constraint Interaction, multi-layer-constraint-test.py)
ARTICLE_POINT = {
    "V1_modify_verify": 0.60,
    "V2_modify_routing": 0.50,
    "V3_fake_signals": 0.85,
    "V4_skip_base": 0.85,
    "L3_detection": 0.918,
}

VECTORS = ["V1_modify_verify", "V2_modify_routing", "V3_fake_signals", "V4_skip"]

CONFIGS = {
    "NONE": set(),
    "L2": {"V1_modify_verify", "V2_modify_routing"},
    "L3": {"V3_fake_signals"},
    "L2+L3": {"V1_modify_verify", "V2_modify_routing", "V3_fake_signals"},
}


# ─── Closed form ─────────────────────────────────────────────────────────────

def v4_success(base: float, detection: float, l3_present: bool) -> float:
    """V4 effective success: base x (1 - detection) only when L3 is in place."""
    return base * (1.0 - detection) if l3_present else base


def prod_fail(available, rates):
    """prod over available vectors of (1 - p_v)."""
    p = 1.0
    for v in available:
        p *= (1.0 - rates[v])
    return p


def dpr_closed(blocked: set, rates: dict, v4_base: float, detection: float) -> float:
    """Defective pass rate for a config, exact closed form.

    V4's effective rate is crushed by L3 only when L3 is present (i.e. the
    V3 signal-producer constraint is blocked), matching multi-layer-constraint-test.py.
    """
    v4 = v4_success(v4_base, detection, l3_present=("V3_fake_signals" in blocked))
    r = {**rates, "V4_skip": v4}
    available = [v for v in VECTORS if v not in blocked]
    return 1.0 - (1.0 - BASELINE_VERIFY_FP) * prod_fail(available, r)


def reductions(cell: dict):
    """Returns (R_L2, R_L3, R_L2L3, ratio) using the closed form, per-config V4."""
    v4_base = cell["V4_skip_base"]
    detection = cell["L3_detection"]
    rates = {
        "V1_modify_verify": cell["V1_modify_verify"],
        "V2_modify_routing": cell["V2_modify_routing"],
        "V3_fake_signals": cell["V3_fake_signals"],
    }
    base = dpr_closed(CONFIGS["NONE"], rates, v4_base, detection)
    l2 = dpr_closed(CONFIGS["L2"], rates, v4_base, detection)
    l3 = dpr_closed(CONFIGS["L3"], rates, v4_base, detection)
    l2l3 = dpr_closed(CONFIGS["L2+L3"], rates, v4_base, detection)
    r_l2 = base - l2
    r_l3 = base - l3
    r_l2l3 = base - l2l3
    ratio = r_l2l3 / (r_l2 + r_l3) if (r_l2 + r_l3) > 1e-12 else float("inf")
    return {"base": base, "l2": l2, "l3": l3, "l2l3": l2l3,
            "r_l2": r_l2, "r_l3": r_l3, "r_l2l3": r_l2l3, "ratio": ratio}


# ─── Monte Carlo core (mirrors multi-layer-constraint-test.py) ───────────────

def mc_simulate_one_defective(blocked: set, rates: dict, v4_base: float, detection: float, pref_order):
    """Same logic as multi-layer-constraint-test.py simulate_one_defective."""
    v4 = v4_success(v4_base, detection, l3_present=("V3_fake_signals" in blocked))
    for v in pref_order:
        if v in blocked:
            continue
        p = v4 if v == "V4_skip" else rates[v]
        if random.random() < p:
            return True
    return random.random() < BASELINE_VERIFY_FP


def mc_run(defect_rate, blocked: set, rates: dict, v4_base: float, detection: float,
           pref_order, n_outputs=2000, n_trials=200):
    dprs = []
    for _ in range(n_trials):
        total_def = 0
        passed = 0
        for _ in range(n_outputs):
            if random.random() < defect_rate:
                total_def += 1
                if mc_simulate_one_defective(blocked, rates, v4_base, detection, pref_order):
                    passed += 1
        dprs.append(passed / total_def if total_def else 0.0)
    return statistics.mean(dprs)


# ─── Ordering check ──────────────────────────────────────────────────────────

def ordering_check(cell: dict, config_name="L2+L3"):
    """All 24 preference permutations; DPR must be identical (order no-op)."""
    v4_base = cell["V4_skip_base"]
    detection = cell["L3_detection"]
    rates = {
        "V1_modify_verify": cell["V1_modify_verify"],
        "V2_modify_routing": cell["V2_modify_routing"],
        "V3_fake_signals": cell["V3_fake_signals"],
    }
    perms = list(itertools.permutations(VECTORS))
    closed = {
        perm: dpr_closed(CONFIGS[config_name], rates, v4_base, detection)
        for perm in perms
    }
    # Monte Carlo on a couple of permutations to confirm empirically
    dprs = []
    for perm in perms[:3] + perms[-1:]:
        dprs.append(mc_run(0.10, CONFIGS[config_name], rates, v4_base, detection,
                           list(perm), n_outputs=2000, n_trials=200))
    return {
        "permutations_tested": len(perms),
        "closed_form_spread": max(closed.values()) - min(closed.values()),
        "mc_dpr_by_perm": [round(x, 6) for x in dprs],
        "mc_spread": max(dprs) - min(dprs),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Multi-layer constraint super-additivity — sensitivity analysis")
    print(f"Baseline verify FP: {BASELINE_VERIFY_FP:.0%}")
    print(f"Grid: V1,V2,V3,V4base x L3 detection — 3^5 = {3**5} cells")
    print("=" * 72)

    # 1) Closed-form grid sweep
    grid_cells = [
        {k: v for k, v in zip(LEVELS.keys(), combo)}
        for combo in itertools.product(*LEVELS.values())
    ]
    assert len(grid_cells) == 243

    cells = []
    for cell in grid_cells:
        r = reductions(cell)
        cells.append({**cell, **r})

    ratios = [c["ratio"] for c in cells if c["ratio"] != float("inf")]
    sub = [c for c in cells if c["ratio"] < 1.0 - 1e-9]
    additive = [c for c in cells if abs(c["ratio"] - 1.0) < 1e-9]
    ratio_min = min(cells, key=lambda c: c["ratio"])
    ratio_max = max(cells, key=lambda c: c["ratio"] if c["ratio"] != float("inf") else 0)
    median = sorted(c["ratio"] for c in cells if c["ratio"] != float("inf"))[len(ratios) // 2]

    print(f"\nGRID RESULT ({len(cells)} cells)")
    print(f"  sub-additive cells (ratio < 1):     {len(sub)}")
    print(f"  additive cells (ratio == 1):        {len(additive)}")
    print(f"  super-additive cells (ratio > 1):   {len(ratios) - len(sub) - len(additive)}")
    print(f"  ratio min: {ratio_min['ratio']:.3f}  @ cell {ratio_min['V1_modify_verify']:.2f}/{ratio_min['V2_modify_routing']:.2f}/{ratio_min['V3_fake_signals']:.2f}/{ratio_min['V4_skip_base']:.2f}/{ratio_min['L3_detection']:.2f}")
    print(f"  ratio max: {ratio_max['ratio']:.3f}  @ cell {ratio_max['V1_modify_verify']:.2f}/{ratio_max['V2_modify_routing']:.2f}/{ratio_max['V3_fake_signals']:.2f}/{ratio_max['V4_skip_base']:.2f}/{ratio_max['L3_detection']:.2f}")
    print(f"  ratio median: {median:.3f}")

    # 2) Article operating point
    art = reductions(ARTICLE_POINT)
    print(f"\nARTICLE OPERATING POINT")
    print(f"  V1={ARTICLE_POINT['V1_modify_verify']:.2f} V2={ARTICLE_POINT['V2_modify_routing']:.2f} "
          f"V3={ARTICLE_POINT['V3_fake_signals']:.2f} V4={ARTICLE_POINT['V4_skip_base']:.2f} "
          f"L3det={ARTICLE_POINT['L3_detection']:.3f}")
    print(f"  DPR: NONE={art['base']:.4f} L2={art['l2']:.4f} L3={art['l3']:.4f} L2+L3={art['l2l3']:.4f}")
    print(f"  Reductions: L2={art['r_l2']:.3f} L3={art['r_l3']:.3f} L2+L3={art['r_l2l3']:.3f}  ratio={art['ratio']:.3f}")

    # no-V4-crush comparison (detection = 0 at article rates)
    no_crush = dict(ARTICLE_POINT)
    no_crush["L3_detection"] = 0.0
    nc = reductions(no_crush)
    print(f"  Same rates, L3 detection=0 (no V4 crush): ratio={nc['ratio']:.3f}")

    # 3) Ordering check
    print(f"\nORDERING CHECK (article operating point)")
    oc = ordering_check(ARTICLE_POINT)
    print(f"  permutations tested: {oc['permutations_tested']}")
    print(f"  closed-form DPR spread across perms: {oc['closed_form_spread']:.2e}")
    print(f"  MC DPR by selected perms: {oc['mc_dpr_by_perm']}")
    print(f"  MC spread: {oc['mc_spread']:.2e}")

    # 4) Closed form vs Monte Carlo on a subset of cells
    print(f"\nCLOSED FORM vs MONTE CARLO (5 representative cells)")
    mc_checks = []
    sample = [cells[0], cells[121], cells[242], cells[60], cells[180]]
    for c in sample:
        rates = {
            "V1_modify_verify": c["V1_modify_verify"],
            "V2_modify_routing": c["V2_modify_routing"],
            "V3_fake_signals": c["V3_fake_signals"],
        }
        row = {"cell": c}
        for name, blocked in CONFIGS.items():
            closed = dpr_closed(blocked, rates, c["V4_skip_base"], c["L3_detection"])
            mc = mc_run(0.10, blocked, rates, c["V4_skip_base"], c["L3_detection"], VECTORS)
            row[name] = {"closed": round(closed, 4), "mc": round(mc, 4), "diff": round(abs(closed - mc), 4)}
            mc_checks.append(row[name])
            print(f"  {name}: closed={closed:.4f} mc={mc:.4f} diff={abs(closed-mc):.4f}")
        print()

    # 5) Slice: min-ratio region characterization (one layer decorative)
    print("DEGENERATE CORNERS (ratio -> 1, one layer decorative)")
    corners = [
        dict(ARTICLE_POINT, V1_modify_verify=0.001, V2_modify_routing=0.001),  # L2 vectors never succeed -> L2 decorative
        dict(ARTICLE_POINT, V3_fake_signals=0.001, L3_detection=0.0),          # V3 never succeeds, no V4 crush -> L3 decorative
    ]
    for i, cor in enumerate(corners):
        r = reductions(cor)
        print(f"  corner {i+1}: ratio={r['ratio']:.3f} (L2 r={r['r_l2']:.3f}, L3 r={r['r_l3']:.3f}, L2+L3 r={r['r_l2l3']:.3f})")

    # ─── Claims ───────────────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS")
    print(f"  structural super-additivity (0 sub-additive cells): {'PASS' if not sub else 'FAIL'}")
    print(f"  ordering no-op in model (MC spread ~ 0):            {'PASS' if oc['mc_spread'] < 1e-3 else 'CHECK'}")
    print(f"  closed form matches MC within noise:                {'PASS' if max(x['diff'] for x in mc_checks) < 0.02 else 'FAIL'}")

    # ─── Write results ─────────────────────────────────────────────────────
    out = {
        "claim": "L2+L3 super-additivity is structural across the vector-rate/L3-detection grid (ratio >= 1), not a single calibrated operating point.",
        "method": "Closed form P(pass)=1-(1-FP)*prod(1-p_v) over 243 grid cells; MC cross-check; 24-perm ordering check.",
        "interaction_identity": "R(L2+L3)-R(L2)-R(L3) = (1-FP)(1-ab)(D'-cD) >= 0 whenever L3 does not increase V4 success.",
        "parameters": {
            "baseline_verify_fp": BASELINE_VERIFY_FP,
            "levels": LEVELS,
            "article_operating_point": ARTICLE_POINT,
        },
        "article_operating_point": {k: round(v, 6) for k, v in art.items()},
        "article_no_v4_crush_ratio": round(nc["ratio"], 6),
        "grid_summary": {
            "cells": len(cells),
            "sub_additive": len(sub),
            "additive": len(additive),
            "super_additive": len(ratios) - len(sub) - len(additive),
            "ratio_min": round(ratio_min["ratio"], 6),
            "ratio_min_cell": {
                "V1": ratio_min["V1_modify_verify"], "V2": ratio_min["V2_modify_routing"],
                "V3": ratio_min["V3_fake_signals"], "V4": ratio_min["V4_skip_base"],
                "L3det": ratio_min["L3_detection"]},
            "ratio_max": round(ratio_max["ratio"], 6),
            "ratio_max_cell": {
                "V1": ratio_max["V1_modify_verify"], "V2": ratio_max["V2_modify_routing"],
                "V3": ratio_max["V3_fake_signals"], "V4": ratio_max["V4_skip_base"],
                "L3det": ratio_max["L3_detection"]},
            "ratio_median": round(median, 6),
        },
        "ordering_check": oc,
        "closed_form_vs_monte_carlo_diff_max": round(max(x["diff"] for x in mc_checks), 6),
    }
    out["degenerate_corners"] = []
    for i, cor in enumerate(corners):
        r = reductions(cor)
        out["degenerate_corners"].append({
            "config": ("V1=V2 near-0, L2 decorative" if i == 0 else "V3 near-0 + no V4 crush, L3 decorative"),
            "ratio": round(r["ratio"], 6),
            "r_L2": round(r["r_l2"], 6), "r_L3": round(r["r_l3"], 6), "r_L2L3": round(r["r_l2l3"], 6),
        })

    out_path = Path(__file__).parent / "results-v2" / "multi-layer-sensitivity.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
