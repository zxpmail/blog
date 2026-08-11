"""
Experiment: Multi-layer constraint super-additivity — structural (model-form)
sensitivity. Does the L2+L3 super-additivity survive changes to the MODEL FORM,
not just the rates?

Falsifiable claim (from multi-layer-sensitivity-test.py):
    The L2+L3 super-additive interaction (ratio R(L2+L3)/(R(L2)+R(L3)) >= 1)
    is structural across the rate grid and ordering. This script asks whether
    it is also structural across two model-FORM variations:

    (a) Common-factor correlation: V1/V2/V3 success rates share a latent z
        (p_v = b_v * z, z ~ Beta). Blocking one vector no longer removes an
        independent dial; the harness vectors rise and fall together.
    (b) Capability redundancy: V1/V2/V3 are ONE capability C. L2 (blocks V1,V2)
        and L3 (blocks V3) therefore block the SAME thing — the layers are
        redundant, not complementary. A mixture parameter w interpolates
        between the independent model (w=0) and full redundancy (w=1).

    Claim: super-additivity (ratio >= 1) holds under (a) at any correlation
    strength, but FAILS under (b) at high redundancy (ratio < 1).
    Falsification: if ratio < 1 appears under (a), or if (b) never drops
    below 1, the structural characterization is wrong.

Method:
    Exact closed forms. For (a), E[prod(1 - b_v z)] expands into Beta moments
    E[z^k] = B(alpha+k, beta)/B(alpha,beta), computable via math.gamma, so the
    pass rate is exact, no simulation. For (b), each config's pass rate is the
    mixture (1-w)*P_independent + w*P_redundant, both exact.

    Parameters follow multi-layer-constraint-test.py / the Part 9 article:
    V1=0.60, V2=0.50, V3=0.85, V4=0.85, L3 detection 0.918 (V4 -> 0.0697 under
    L3), baseline verify FP 0.05. For (b), capability C present with q=0.5.

Dependencies: none (pure Python, stdlib only).

Expected result:
    (a) ratio >= 1 for all Beta spreads (correlation does not break it —
        provable pointwise: (1-alpha(z)beta(z))(delta'(z)-gamma(z)delta(z)) >= 0).
    (b) ratio drops below 1 as w -> 1: the layers are redundant, so blocking
        both buys no more than blocking either — the "super-additive" framing
        is an artifact of assuming the layers target distinct capabilities.

How to falsify:
    - (a) any Beta(alpha,beta) with ratio < 1.
    - (b) full-redundancy (w=1) ratio >= 1.
"""
import sys
import io
import json
import math
import itertools
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters (Part 9 article / multi-layer-constraint-test.py) ───────────

FP = 0.05
V1, V2, V3, V4 = 0.60, 0.50, 0.85, 0.85
DET = 0.918
V4_UNDER_L3 = V4 * (1.0 - DET)   # 0.0697

V123 = ["V1", "V2", "V3"]
RATES = {"V1": V1, "V2": V2, "V3": V3}
V4_RATE = {"NONE": V4, "L2": V4, "L3": V4_UNDER_L3, "L2+L3": V4_UNDER_L3}

CONFIGS = {
    "NONE": set(),
    "L2": {"V1", "V2"},
    "L3": {"V3"},
    "L2+L3": {"V1", "V2", "V3"},
}

# ─── Closed-form core (shared) ───────────────────────────────────────────────

def pass_rate_independent(blocked, v4_p):
    """Independent-vector model (the original): P(pass) = 1 - (1-FP)*prod(1-p_v)."""
    prod = 1.0
    for v in V123:
        if v not in blocked:
            prod *= (1.0 - RATES[v])
    if "V4" not in blocked:
        prod *= (1.0 - v4_p)
    return 1.0 - (1.0 - FP) * prod


def beta_moment(alpha, beta, k):
    """E[z^k] for z ~ Beta(alpha, beta) via gamma functions."""
    return math.gamma(alpha + k) * math.gamma(alpha + beta) / (math.gamma(alpha) * math.gamma(alpha + beta + k))


def e_prod_harness(blocked, alpha, beta):
    """E[ prod_{v in unblocked harness set} (1 - b_v z) ], z ~ Beta(alpha,beta)."""
    avail = [v for v in V123 if v not in blocked]
    total = 0.0
    for r in range(len(avail) + 1):
        for combo in itertools.combinations(avail, r):
            coef = 1.0 if r % 2 == 0 else -1.0
            for v in combo:
                coef *= RATES[v]
            total += coef * beta_moment(alpha, beta, r)
    return total


def pass_rate_common_factor(blocked, v4_p, alpha, beta):
    """(a) common-factor model: p_v = b_v*z for V1/V2/V3, V4 independent."""
    prod = e_prod_harness(blocked, alpha, beta)
    if "V4" not in blocked:
        prod *= (1.0 - v4_p)
    return 1.0 - (1.0 - FP) * prod


def pass_rate_redundant(blocked, v4_p, q):
    """(b) redundant model: V1/V2/V3 are ONE capability C. If C present (prob q)
    and NOT blocked by either L2 or L3, the harness vectors succeed; blocking any
    of them removes C entirely. V4 is independent."""
    c_blocked = bool(blocked & {"V1", "V2", "V3"})
    v4_pass = v4_p + (1.0 - v4_p) * FP   # V4 alone, then baseline FP if it fails
    if c_blocked:
        return v4_pass
    # capability active: pass if C present, or (C absent and V4 passes)
    return q + (1.0 - q) * v4_pass


def ratio_from(configs_pass):
    """Super-additivity ratio from per-config pass rates."""
    base, l2, l3, l2l3 = configs_pass
    r_l2 = base - l2
    r_l3 = base - l3
    r_l2l3 = base - l2l3
    denom = r_l2 + r_l3
    return r_l2l3 / denom if denom > 1e-12 else float("inf")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Multi-layer constraint super-additivity — structural (model-form) sensitivity")
    print(f"V1={V1} V2={V2} V3={V3} V4={V4} L3det={DET} (V4->{V4_UNDER_L3:.4f}) FP={FP}")
    print("=" * 72)

    # 0) Baseline: independent model at article rates (sanity: ~4.64)
    base_conf = [pass_rate_independent(b, V4_RATE[n]) for n, b in CONFIGS.items()]
    base_ratio = ratio_from(base_conf)
    print(f"\n0) BASELINE (independent vectors, article rates): ratio = {base_ratio:.3f}")

    # 1) Common-factor correlation: V1/V2/V3 share z ~ Beta(alpha, beta)
    #    All symmetric Betas here have E[z]=0.5, so every row sits at the SAME
    #    effective-strength operating point (all harness vectors at half their
    #    base rates); only the correlation strength varies. The super-additivity
    #    theorem is pointwise in z, so it holds at any operating point.
    print(f"\n1) COMMON-FACTOR CORRELATION (p_v = b_v*z for V1/V2/V3; E[z]=0.5 fixed)")
    print("   z-distribution        | NONE   L2     L3     L2+L3  | ratio")
    cf_results = []
    for name, alpha, beta in [("Beta(50,50) narrow", 50.0, 50.0),
                              ("Beta(10,10) mild", 10.0, 10.0),
                              ("Beta(2,2) moderate", 2.0, 2.0),
                              ("Beta(0.5,0.5) strong", 0.5, 0.5),
                              ("Beta(0.2,0.2) extreme", 0.2, 0.2)]:
        passes = [pass_rate_common_factor(b, V4_RATE[n], alpha, beta) for n, b in CONFIGS.items()]
        r = ratio_from(passes)
        cf_results.append({"z_dist": name, "alpha": alpha, "beta": beta,
                           "pass": [round(p, 4) for p in passes], "ratio": round(r, 4)})
        print(f"   {name:24s} | {passes[0]:.4f} {passes[1]:.4f} {passes[2]:.4f} {passes[3]:.4f}  | {r:.3f}")

    # 2) Capability redundancy mixture: w = probability layers target one capability
    print(f"\n2) CAPABILITY REDUNDANCY (w = share of outputs where V1/V2/V3 are ONE capability)")
    print("   w    | NONE   L2     L3     L2+L3  | ratio")
    q = 0.5
    red_results = []
    for w in [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]:
        passes = []
        for n, b in CONFIGS.items():
            p_ind = pass_rate_independent(b, V4_RATE[n])
            p_red = pass_rate_redundant(b, V4_RATE[n], q)
            passes.append((1 - w) * p_ind + w * p_red)
        r = ratio_from(passes)
        red_results.append({"w": w, "pass": [round(p, 4) for p in passes], "ratio": round(r, 4)})
        tag = "  <-- SUB-ADDITIVE" if r < 1.0 else ""
        print(f"   {w:.2f} | {passes[0]:.4f} {passes[1]:.4f} {passes[2]:.4f} {passes[3]:.4f}  | {r:.3f}{tag}")

    # 3) Crossover w* where ratio drops below 1, as a function of capability
    #    prevalence q (how often the shared capability is present at all).
    print(f"\n3) CROSSOVER w* vs capability prevalence q (q = P(shared capability present))")
    crossover_rows = []
    for qv in [0.3, 0.5, 0.7, 0.9]:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            passes = []
            for n, b in CONFIGS.items():
                p_ind = pass_rate_independent(b, V4_RATE[n])
                p_red = pass_rate_redundant(b, V4_RATE[n], qv)
                passes.append((1 - mid) * p_ind + mid * p_red)
            if ratio_from(passes) >= 1.0:
                lo = mid
            else:
                hi = mid
        w_cross = (lo + hi) / 2
        passes1 = [(pass_rate_redundant(b, V4_RATE[n], qv)) for n, b in CONFIGS.items()]
        r_w1 = ratio_from(passes1)
        crossover_rows.append({"q": qv, "crossover_w": round(w_cross, 4), "ratio_at_w1": round(r_w1, 4)})
        print(f"   q={qv:.1f}: crossover w* = {w_cross:.3f}   (w=1 ratio = {r_w1:.3f})")

    # ─── Claims ───────────────────────────────────────────────────────────
    all_cf_ge1 = all(r["ratio"] >= 1.0 for r in cf_results)
    full_redundant_sub = red_results[-1]["ratio"] < 1.0
    print("=" * 72)
    print("CLAIMS")
    print(f"  (a) common-factor correlation preserves ratio >= 1: {'PASS' if all_cf_ge1 else 'FAIL'}")
    print(f"  (b) full capability redundancy gives ratio < 1:     {'PASS' if full_redundant_sub else 'FAIL'}")

    # ─── Write results ─────────────────────────────────────────────────────
    out = {
        "claim": "Super-additivity survives rate/order/common-factor-correlation variations but flips sub-additive under capability redundancy (layers blocking the same weakness).",
        "parameters": {"V1": V1, "V2": V2, "V3": V3, "V4": V4, "L3_detection": DET,
                       "V4_under_L3": V4_UNDER_L3, "FP": FP, "redundancy_q": q},
        "baseline_ratio": round(base_ratio, 6),
        "common_factor_correlation": cf_results,
        "capability_redundancy": red_results,
        "crossover_by_q": crossover_rows,
        "claims": {
            "common_factor_preserves_superadditivity": all_cf_ge1,
            "full_redundancy_sub_additive": full_redundant_sub,
        },
    }
    out_path = Path(__file__).parent / "results-v2" / "multi-layer-structure.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
