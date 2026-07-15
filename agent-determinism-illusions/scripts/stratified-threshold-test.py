"""
Experiment: ANP2's Stratified Threshold Test — discrimination vs calibration

Falsifiable claim:
    ANP2 Network's proposal (dev.to, July 2026): the 75% wall is either a
    discrimination ceiling (d' bounded) or collapsed operating points
    (one threshold across heterogeneous d'). The disambiguation test is:
    stratify by request difficulty, re-fit threshold per stratum, check
    whether the aggregate moves.

    Claim: in a heterogeneous population (different d' per stratum), per-stratum
    threshold fitting beats shared threshold by ≥5 accuracy points when base
    rates also differ across strata. In a homogeneous population, the gap is
    <1 point. The gap IS the test — its size tells you which hypothesis holds.

    Falsification: if heterogeneity in d' alone (equal base rates) produces a
    <1 point gap, then varying d' is not sufficient to demonstrate the
    calibration hypothesis — ANP2's test would need richer asymmetry (costs,
    base rates, variances) to be diagnostic.

Method:
    Signal detection theory. N=2000 requests/trial, 500 trials.
    Each request belongs to a difficulty stratum with its own d' and base rate.
    Judge observes evidence ~ N(±d'/2, 1), says "defective" if evidence > c.

    Three conditions tested:
    - Shared threshold: one c* maximizing aggregate accuracy
    - Per-stratum threshold: c*_s maximizing each stratum's accuracy
    - Δ = per-stratum aggregate − shared aggregate

    Four scenarios:
    - HET+d'/BASE: d' varies, base rate varies (most realistic)
    - HET-d'/BASE: d' varies, base rate equal (tests whether d' alone suffices)
    - HOM+d'/BASE: d' equal, base rate varies (control: does base rate alone do it?)
    - HOM-d'/BASE: d' equal, base rate equal (null control: should give Δ≈0)

Dependencies: none (pure Python).
"""

import random
import statistics
import sys
import io
import json
import math
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters ──────────────────────────────────────────────────────────────

N_REQUESTS = 2000
N_TRIALS = 500

# Difficulty strata configurations (4 scenarios)
# d' values grounded in DF v2 data: easy≈2.5 (obvious defect), medium≈1.0
# (subtle reversal), hard≈0.3 (no-change rationalization).
STRATA_CONFIGS = {
    "HET+d'/BASE": {
        "easy":   {"d_prime": 2.5, "weight": 0.40, "base_rate": 0.30},
        "medium": {"d_prime": 1.0, "weight": 0.40, "base_rate": 0.50},
        "hard":   {"d_prime": 0.3, "weight": 0.20, "base_rate": 0.70},
    },
    "HET-d'/BASE": {
        "easy":   {"d_prime": 2.5, "weight": 0.40, "base_rate": 0.50},
        "medium": {"d_prime": 1.0, "weight": 0.40, "base_rate": 0.50},
        "hard":   {"d_prime": 0.3, "weight": 0.20, "base_rate": 0.50},
    },
    "HOM+d'/BASE": {
        "easy":   {"d_prime": 1.27, "weight": 0.40, "base_rate": 0.30},  # weighted-mean d'
        "medium": {"d_prime": 1.27, "weight": 0.40, "base_rate": 0.50},
        "hard":   {"d_prime": 1.27, "weight": 0.20, "base_rate": 0.70},
    },
    "HOM-d'/BASE (null)": {
        "easy":   {"d_prime": 1.27, "weight": 0.40, "base_rate": 0.50},
        "medium": {"d_prime": 1.27, "weight": 0.40, "base_rate": 0.50},
        "hard":   {"d_prime": 1.27, "weight": 0.20, "base_rate": 0.50},
    },
}


# ─── Signal detection theory ─────────────────────────────────────────────────

def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def hit_rate(d_prime, c):
    """P(say defective | defective) = P(X > c | X ~ N(d'/2, 1))."""
    return 1 - normal_cdf(c - d_prime / 2)


def false_alarm_rate(d_prime, c):
    """P(say defective | valid) = P(X > c | X ~ N(-d'/2, 1))."""
    return 1 - normal_cdf(c + d_prime / 2)


def accuracy_at(d_prime, c, base_rate):
    """P(correct) = base_rate·hit + (1-base_rate)·(1-FA)."""
    return base_rate * hit_rate(d_prime, c) + (1 - base_rate) * (1 - false_alarm_rate(d_prime, c))


def miss_rate_at(d_prime, c):
    """P(say valid | defective) = 1 - hit."""
    return 1 - hit_rate(d_prime, c)


# ─── Optimization ────────────────────────────────────────────────────────────

def find_optimal_c_shared(strata):
    """Find c maximizing aggregate accuracy (closed-form via grid search)."""
    best_c, best_acc = 0.0, 0.0
    for i in range(-500, 501):
        c = i / 100.0
        acc = sum(cfg["weight"] * accuracy_at(cfg["d_prime"], c, cfg["base_rate"])
                  for cfg in strata.values())
        if acc > best_acc:
            best_acc = acc
            best_c = c
    return best_c, best_acc


def find_optimal_c_per_stratum(strata):
    """Find c_s maximizing each stratum's accuracy."""
    result = {}
    for s, cfg in strata.items():
        best_c, best_acc = 0.0, 0.0
        for i in range(-500, 501):
            c = i / 100.0
            acc = accuracy_at(cfg["d_prime"], c, cfg["base_rate"])
            if acc > best_acc:
                best_acc = acc
                best_c = c
        result[s] = best_c
    return result


def aggregate_at_per_stratum(strata, c_per_stratum):
    """Aggregate accuracy when each stratum uses its own c."""
    return sum(cfg["weight"] * accuracy_at(cfg["d_prime"], c_per_stratum[s], cfg["base_rate"])
               for s, cfg in strata.items())


# ─── Monte Carlo validation ──────────────────────────────────────────────────

def monte_carlo_shared(strata, c, trials=N_TRIALS):
    accs = []
    for _ in range(trials):
        correct = 0
        total = 0
        for cfg in strata.values():
            n = int(N_REQUESTS * cfg["weight"])
            for _ in range(n):
                defective = random.random() < cfg["base_rate"]
                mean = cfg["d_prime"] / 2 if defective else -cfg["d_prime"] / 2
                evidence = random.gauss(mean, 1.0)
                if (evidence > c) == defective:
                    correct += 1
                total += 1
        accs.append(correct / total)
    return statistics.mean(accs), statistics.stdev(accs)


def monte_carlo_per_stratum(strata, c_per_stratum, trials=N_TRIALS):
    accs = []
    for _ in range(trials):
        correct = 0
        total = 0
        for s, cfg in strata.items():
            n = int(N_REQUESTS * cfg["weight"])
            c = c_per_stratum[s]
            for _ in range(n):
                defective = random.random() < cfg["base_rate"]
                mean = cfg["d_prime"] / 2 if defective else -cfg["d_prime"] / 2
                evidence = random.gauss(mean, 1.0)
                if (evidence > c) == defective:
                    correct += 1
                total += 1
        accs.append(correct / total)
    return statistics.mean(accs), statistics.stdev(accs)


# ─── Main ────────────────────────────────────────────────────────────────────

def print_table(rows, headers):
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    print()


def main():
    print("=" * 72)
    print("Experiment: ANP2's Stratified Threshold Test")
    print("Question: Is the 75% wall a discrimination ceiling or collapsed operating points?")
    print(f"N={N_REQUESTS}/trial, {N_TRIALS} trials/config")
    print("=" * 72)

    all_results = []

    # Sweep 1: Per-config summary
    print("\n" + "─" * 72)
    print("SWEEP 1: Shared vs per-stratum threshold, 4 population structures")
    print("─" * 72)
    rows = []
    for name, strata in STRATA_CONFIGS.items():
        c_shared, acc_shared_th = find_optimal_c_shared(strata)
        c_per = find_optimal_c_per_stratum(strata)
        acc_per_th = aggregate_at_per_stratum(strata, c_per)
        delta_th = acc_per_th - acc_shared_th

        # Monte Carlo validation
        acc_shared_mc, std_shared = monte_carlo_shared(strata, c_shared)
        acc_per_mc, std_per = monte_carlo_per_stratum(strata, c_per)
        delta_mc = acc_per_mc - acc_shared_mc

        rows.append([
            name,
            f"{acc_shared_mc:.3f}±{std_shared:.3f}",
            f"{acc_per_mc:.3f}±{std_per:.3f}",
            f"{delta_mc:+.3f}",
            "calibration" if delta_mc >= 0.05 else ("discrimination" if delta_mc < 0.01 else "ambiguous"),
        ])
        all_results.append({
            "config": name, "strata": strata,
            "c_shared": c_shared, "c_per_stratum": c_per,
            "acc_shared_theoretical": acc_shared_th,
            "acc_per_stratum_theoretical": acc_per_th,
            "delta_theoretical": delta_th,
            "acc_shared_mc": acc_shared_mc, "acc_shared_std": std_shared,
            "acc_per_stratum_mc": acc_per_mc, "acc_per_stratum_std": std_per,
            "delta_mc": delta_mc,
        })
    print_table(rows, ["Config", "Shared Acc (MC)", "Per-Stratum Acc (MC)", "Δ", "Diagnosis"])

    # Sweep 2: Show per-stratum optimal c for the HET+d'/BASE case
    print("─" * 72)
    print("SWEEP 2: Per-stratum detail for HET+d'/BASE (realistic case)")
    print("─" * 72)
    strata = STRATA_CONFIGS["HET+d'/BASE"]
    c_per = find_optimal_c_per_stratum(strata)
    c_shared, _ = find_optimal_c_shared(strata)
    rows = []
    for s, cfg in strata.items():
        acc_at_shared = accuracy_at(cfg["d_prime"], c_shared, cfg["base_rate"])
        acc_at_per = accuracy_at(cfg["d_prime"], c_per[s], cfg["base_rate"])
        rows.append([
            s, f"{cfg['d_prime']:.2f}", f"{cfg['base_rate']:.2f}",
            f"{c_shared:+.2f}", f"{c_per[s]:+.2f}",
            f"{acc_at_shared:.3f}", f"{acc_at_per:.3f}",
            f"{acc_at_per - acc_at_shared:+.3f}",
        ])
    print_table(rows, ["Stratum", "d'", "base_rate", "c_shared", "c*_s",
                       "Acc@shared", "Acc@per-stratum", "Δ"])

    # Sweep 3: Vary d' heterogeneity, show Δ sensitivity
    print("─" * 72)
    print("SWEEP 3: Vary d' heterogeneity (base rates held varied as in HET+d'/BASE)")
    print("─" * 72)
    rows = []
    for d_easy in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
        strata_sens = {
            "easy":   {"d_prime": d_easy,   "weight": 0.40, "base_rate": 0.30},
            "medium": {"d_prime": 1.0,      "weight": 0.40, "base_rate": 0.50},
            "hard":   {"d_prime": max(0.3, 2.0 - d_easy * 0.5), "weight": 0.20, "base_rate": 0.70},
        }
        c_s, _ = find_optimal_c_shared(strata_sens)
        c_p = find_optimal_c_per_stratum(strata_sens)
        acc_s = sum(cfg["weight"] * accuracy_at(cfg["d_prime"], c_s, cfg["base_rate"])
                    for cfg in strata_sens.values())
        acc_p = aggregate_at_per_stratum(strata_sens, c_p)
        rows.append([
            f"{d_easy:.1f}",
            f"{strata_sens['easy']['d_prime']:.1f}",
            f"{strata_sens['medium']['d_prime']:.1f}",
            f"{strata_sens['hard']['d_prime']:.1f}",
            f"{acc_s:.3f}", f"{acc_p:.3f}", f"{acc_p - acc_s:+.3f}",
        ])
        all_results.append({
            "config": f"sensitivity_d_easy={d_easy}", "strata": strata_sens,
            "acc_shared_theoretical": acc_s, "acc_per_stratum_theoretical": acc_p,
            "delta_theoretical": acc_p - acc_s,
        })
    print_table(rows, ["d'_easy", "d'_easy", "d'_med", "d'_hard",
                       "Shared", "Per-Stratum", "Δ"])
    print("(d'_hard decreases as d'_easy increases — keeping weighted-mean d' roughly constant)")

    # ─── Claims check ─────────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS CHECK")
    print("=" * 72)

    het = next(r for r in all_results if r["config"] == "HET+d'/BASE")
    het_d_only = next(r for r in all_results if r["config"] == "HET-d'/BASE")
    hom_b_only = next(r for r in all_results if r["config"] == "HOM+d'/BASE")
    null = next(r for r in all_results if r["config"] == "HOM-d'/BASE (null)")

    print(f"\nΔ accuracy (per-stratum threshold − shared threshold, MC):")
    print(f"  HET d' + HET base (realistic):  {het['delta_mc']:+.3f}")
    print(f"  HET d' + HOM base (d' only):    {het_d_only['delta_mc']:+.3f}")
    print(f"  HOM d' + HET base (base only):  {hom_b_only['delta_mc']:+.3f}")
    print(f"  HOM d' + HOM base (null):       {null['delta_mc']:+.3f}")

    print(f"\nClaim 1 (heterogeneous case ≥5 point gain): "
          f"{'PASS' if het['delta_mc'] >= 0.05 else 'FAIL'} "
          f"(Δ = {het['delta_mc']:+.3f})")
    print(f"Claim 2 (null case <1 point gain): "
          f"{'PASS' if abs(null['delta_mc']) < 0.01 else 'FAIL'} "
          f"(Δ = {null['delta_mc']:+.3f})")

    print(f"\nInterpretation (per ANP2's falsification condition):")
    print(f"  The Δ IS the diagnostic. Large Δ in realistic case + ~0 in null case")
    print(f"  = stratification works when population is heterogeneous.")
    print(f"  Applied to the 75% wall: if real per-difficulty data shows Δ ≥ 5 points,")
    print(f"  the wall is collapsed operating points (calibration). If Δ ≈ 0, it is")
    print(f"  discrimination (d' bounded).")
    print(f"\n  Note: d' heterogeneity alone (equal base rates) gives only "
          f"{het_d_only['delta_mc']:+.3f} — the test is most diagnostic when")
    print(f"  base rates also vary across strata (selection effects in real data).")

    # ─── Write results ─────────────────────────────────────────────────────
    out = {
        "parameters": {
            "n_requests": N_REQUESTS,
            "n_trials": N_TRIALS,
            "strata_configs": STRATA_CONFIGS,
        },
        "claim1_heterogeneous_threshold": {"threshold": 0.05, "result": het["delta_mc"],
                                           "pass": het["delta_mc"] >= 0.05},
        "claim2_null_threshold": {"threshold": 0.01, "result": abs(null["delta_mc"]),
                                  "pass": abs(null["delta_mc"]) < 0.01},
        "results": [],
    }
    for r in all_results:
        out["results"].append({k: v for k, v in r.items()})

    out_path = Path(__file__).parent / "results-v2" / "stratified-threshold-test.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
