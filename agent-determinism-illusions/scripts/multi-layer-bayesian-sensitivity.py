"""
Experiment: Multi-layer constraint super-additivity — Bayesian sensitivity over
the assumed V1-V4 success rates.

Falsifiable claim:
    The Part 9 Constraint Interaction conclusion ("L2+L3 reduces defective
    pass-through 4.6x super-additively") is reported at a single calibrated
    operating point: V1=0.60, V2=0.50, V3=0.85, V4=0.85, L3 detection 0.918.
    Those vector rates are *assumed*, not measured. This script treats them as
    random variables with Beta priors centered on the article values and asks:
    how does the prior uncertainty propagate to the super-additivity ratio and
    to the defective pass rate (the "intervals on defective pass rate" Mads
    Hansen asked for)?

    Claim: under the prior, P(ratio >= 1) = 1 (the closed form is non-negative
    for every parameter value), so the *existence* of super-additivity carries
    zero prior sensitivity; the prior uncertainty only moves the *magnitude* —
    the ratio's credible interval and DPR(L2+L3)'s credible interval.

    Falsification: if any sampled parameter draw (within the prior support)
    gives ratio < 1, the closed-form theorem is wrong.

Method:
    Exact closed form per draw: P(pass | config) = 1 - (1-FP)*prod(1-p_v),
    with V4 crushed to V4*(1-det) under L3. Draw N samples from Beta priors,
    push each through the closed form, collect the posterior distribution of
    the ratio and of each config's DPR. Report median, 90% credible interval,
    and tail probabilities. L3 detection is fixed at 0.918 (it is a measured
    quantity from pre-execution-verification-test.py, not an assumption).

    Two prior sets: (i) "article-centered" Beta priors (mode near the article
    values, moderate spread); (ii) "wide" Beta(2,2) priors (near-uniform) as a
    robustness check that the qualitative conclusion is prior-independent.

Dependencies: none (stdlib random.betavariate).

Expected result:
    P(ratio >= 1) = 1.0 under both prior sets. The ratio's 90% CI is wide
    (order ~2x-6x under article-centered priors), and DPR(L2+L3)'s 90% CI
    brackets the article's 11.6% headline. The honest statement is that the
    super-additivity is prior-robust but its magnitude is not pinned down.

How to falsify:
    - any sampled draw with ratio < 1;
    - P(ratio >= 1) < 1 under any prior whose support is [0,1]^4.
"""
import sys
import io
import json
import random
import statistics
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters ──────────────────────────────────────────────────────────────

FP = 0.05
DET = 0.918          # measured (pre-execution-verification-test.py), kept fixed
N_SAMPLES = 200_000

# Article operating point
ARTICLE = {"V1": 0.60, "V2": 0.50, "V3": 0.85, "V4": 0.85}

# Beta prior hyperparameters: (alpha, beta). Article-centered priors have mode
# near the article value; wide priors are near-uniform robustness check.
PRIORS = {
    "article_centered": {
        "V1": (6.0, 4.0),    # mode 0.6, mean 0.6
        "V2": (5.0, 5.0),    # mode 0.5, mean 0.5
        "V3": (8.5, 1.5),    # mode 0.85, mean 0.85
        "V4": (8.5, 1.5),    # mode 0.85, mean 0.85
    },
    "wide": {
        "V1": (2.0, 2.0),
        "V2": (2.0, 2.0),
        "V3": (2.0, 2.0),
        "V4": (2.0, 2.0),
    },
}

V123 = ["V1", "V2", "V3"]
CONFIGS = {
    "NONE": set(),
    "L2": {"V1", "V2"},
    "L3": {"V3"},
    "L2+L3": {"V1", "V2", "V3"},
}


def pass_rate(blocked, rates, v4_p):
    prod = 1.0
    for v in V123:
        if v not in blocked:
            prod *= (1.0 - rates[v])
    if "V4" not in blocked:
        prod *= (1.0 - v4_p)
    return 1.0 - (1.0 - FP) * prod


def ratio_from(passes):
    base, l2, l3, l2l3 = passes
    r_l2 = base - l2
    r_l3 = base - l3
    r_l2l3 = base - l2l3
    denom = r_l2 + r_l3
    return r_l2l3 / denom if denom > 1e-12 else float("inf")


def run_posterior(name, prior_ab, seed):
    rng = random.Random(seed)
    ratios = []
    dprs = {"NONE": [], "L2": [], "L3": [], "L2+L3": []}
    for _ in range(N_SAMPLES):
        rates = {v: rng.betavariate(*prior_ab[v]) for v in ["V1", "V2", "V3"]}
        v4 = rng.betavariate(*prior_ab["V4"])
        v4_under = v4 * (1.0 - DET)
        passes = []
        for n, b in CONFIGS.items():
            v4p = v4 if "V3" not in b else v4_under
            p = pass_rate(b, rates, v4p)
            passes.append(p)
            dprs[n].append(p)
        ratios.append(ratio_from(passes))

    def ci(arr):
        arr_sorted = sorted(arr)
        lo = arr_sorted[int(0.05 * len(arr_sorted))]
        hi = arr_sorted[int(0.95 * len(arr_sorted))]
        return statistics.median(arr_sorted), lo, hi

    med_r, lo_r, hi_r = ci(ratios)
    return {
        "prior": name,
        "samples": N_SAMPLES,
        "ratio": {
            "median": round(med_r, 4),
            "p90_ci": [round(lo_r, 4), round(hi_r, 4)],
            "P_ratio_ge_1": round(sum(1 for r in ratios if r >= 1.0) / len(ratios), 6),
            "P_ratio_ge_2": round(sum(1 for r in ratios if r >= 2.0) / len(ratios), 4),
            "P_ratio_ge_3": round(sum(1 for r in ratios if r >= 3.0) / len(ratios), 4),
            "P_ratio_ge_4_6": round(sum(1 for r in ratios if r >= 4.6) / len(ratios), 4),
        },
        "dpr": {
            n: {"median": round(statistics.median(dprs[n]), 4),
                "p90_ci": [round(sorted(dprs[n])[int(0.05 * len(dprs[n]))], 4),
                           round(sorted(dprs[n])[int(0.95 * len(dprs[n]))], 4)]}
            for n in CONFIGS
        },
    }


def main():
    print("=" * 72)
    print("Multi-layer constraint — Bayesian sensitivity over assumed V1-V4 rates")
    print(f"Samples per prior: {N_SAMPLES} | L3 detection fixed at {DET}")
    print(f"Article point: {ARTICLE}")
    print("=" * 72)

    results = []
    for name in ["article_centered", "wide"]:
        r = run_posterior(name, PRIORS[name], seed=42)
        results.append(r)
        print(f"\n--- PRIOR: {name} ---")
        print(f"  ratio median = {r['ratio']['median']}, 90% CI = {r['ratio']['p90_ci']}")
        print(f"  P(ratio>=1) = {r['ratio']['P_ratio_ge_1']:.4f}   "
              f"P(>=2) = {r['ratio']['P_ratio_ge_2']:.3f}   "
              f"P(>=3) = {r['ratio']['P_ratio_ge_3']:.3f}   "
              f"P(>=4.6) = {r['ratio']['P_ratio_ge_4_6']:.3f}")
        print(f"  DPR(L2+L3): median = {r['dpr']['L2+L3']['median']}, 90% CI = {r['dpr']['L2+L3']['p90_ci']}")
        print(f"  DPR(NONE) median = {r['dpr']['NONE']['median']}   DPR(L2) = {r['dpr']['L2']['median']}   "
              f"DPR(L3) = {r['dpr']['L3']['median']}")

    all_ge1 = all(r["ratio"]["P_ratio_ge_1"] == 1.0 for r in results)
    print("\n" + "=" * 72)
    print(f"CLAIM: P(ratio >= 1) = 1 under both priors -> {'PASS' if all_ge1 else 'FAIL'}")

    out = {
        "claim": "Super-additivity existence is prior-robust (P(ratio>=1)=1 under any [0,1]^4 prior, by closed form); the assumed rates move only the magnitude.",
        "parameters": {"FP": FP, "L3_detection": DET, "n_samples": N_SAMPLES, "article": ARTICLE,
                       "priors": PRIORS},
        "results": results,
    }
    out_path = Path(__file__).parent / "results-v2" / "multi-layer-bayesian.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
