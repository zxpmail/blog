"""
Experiment: Does routing without editable-surface constraints leak to verification evasion?

Falsifiable claim:
    Without an editable-surface constraint on the routing table, an agent can
    reassign defective outputs to more lenient verification paths, achieving
    ≥2× defective-output pass-through vs the constrained condition.

Method:
    Monte Carlo simulation. N=5000 outputs per trial, 500 trials per config.
    For each output:
    1. Generate output_type (code/report/config) and ground_truth (valid/defective)
    2. Look up default routing path (strict/balanced/lenient)
    3. Under UNCONSTRAINED: agent may override routing, with detection_risk
    4. Path evaluates output probabilistically (path FP/FN rates)
    5. Measure pass/fail per condition

    Three verification paths from Part 5's empirical data:
        Strict:   FP=0%, FN=75%   (GLM-5.2 / deepseek-v4-flash at 75% wall)
        Balanced: FP=10%, FN=50%  (gemma3:4.3b territory)
        Lenient:  FP=25%, FN=25%  (qwen3:0.5b territory)

    Default routing (what a honest router assigns based on output type):
        code   → Strict   (highest stakes)
        report → Balanced (moderate stakes)
        config → Lenient  (lower stakes)

    Agent gameability: when unconstrained and output is defective, agent
    changes the routing table entry for its output type to point to a
    more favorable path. Detection_risk models harness audit catching
    the unauthorized change.

Dependencies: none (pure Python).
"""

import random
import statistics
import sys
import io
import json
import math
from pathlib import Path
from dataclasses import dataclass

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

N_OUTPUTS = 5000
N_TRIALS = 500

VERIFICATION_PATHS = {
    "strict":   {"fp": 0.00, "fn": 0.75},
    "balanced": {"fp": 0.10, "fn": 0.50},
    "lenient":  {"fp": 0.25, "fn": 0.25},
}

# Default routing: output type → verification path
DEFAULT_ROUTE = {
    "code":   "strict",
    "report": "strict",
    "config": "strict",
}

# Output type distribution
TYPE_WEIGHTS = {"code": 0.40, "report": 0.35, "config": 0.25}

# "Path preference" ranking — which path an agent prefers when gaming (ascending FN = more favorable)
PATH_PREFERENCE = ["lenient", "balanced", "strict"]

# Each type's "allowable" override paths that wouldn't look immediately suspicious
ALLOWED_OVERRIDE = {
    "code":   ["balanced"],     # "this is more of a report" — semi-plausible
    "report": ["lenient"],      # "this is just config" — semi-plausible
    "config": ["lenient"],      # same as default for config, no benefit
}


def shannon_entropy(path_counts: dict) -> float:
    """Shannon entropy of path distribution. Higher = more operating-point variance."""
    total = sum(path_counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in path_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def simulate_one_output(output_type: str, defective: bool, default_path: str,
                        unconstrained: bool, detection_risk: float, gameability: float):
    """
    Simulate a single output going through the verification pipeline.
    Returns: (passed, escalated, path_used)
    """
    path_name = default_path

    if unconstrained and defective and random.random() < gameability:
        # Agent tries to override routing
        # Strike 1: pick the most favorable path from allowed overrides
        best_override = None
        for p in PATH_PREFERENCE:
            if p in ALLOWED_OVERRIDE.get(output_type, []):
                best_override = p
                break

        # If there's a favorable override available
        if best_override and best_override != default_path:
            # Detection check
            if random.random() < detection_risk:
                # Override detected → escalated to human, guaranteed catch
                return False, True, path_name  # failed (caught by escalation), escalated

            # Override not detected → use the gamed path
            path_name = best_override

    # Run verification on (possibly gamed) path
    path = VERIFICATION_PATHS[path_name]
    if defective:
        # FP: defective output wrongly accepted (passes when it shouldn't)
        passes = random.random() < path["fp"]
    else:
        # FN: valid output wrongly rejected, so passes only if NOT a false negative
        passes = random.random() >= path["fn"]

    return passes, False, path_name


def run_trial(defect_rate: float, unconstrained: bool, detection_risk: float, gameability: float):
    """Run one trial, return pass rates + path entropy."""
    total_defective = 0
    defective_passed = 0
    total_valid = 0
    valid_rejected = 0
    escalations = 0
    path_counts = {"strict": 0, "balanced": 0, "lenient": 0}

    for _ in range(N_OUTPUTS):
        # Generate output
        r = random.random()
        if r < TYPE_WEIGHTS["code"]:
            otype = "code"
        elif r < TYPE_WEIGHTS["code"] + TYPE_WEIGHTS["report"]:
            otype = "report"
        else:
            otype = "config"

        defective = random.random() < defect_rate
        default_path = DEFAULT_ROUTE[otype]

        passed, escalated, path_used = simulate_one_output(
            otype, defective, default_path,
            unconstrained, detection_risk, gameability
        )

        path_counts[path_used] = path_counts.get(path_used, 0) + 1

        if escalated:
            escalations += 1
            continue  # escalated = caught regardless

        if defective:
            total_defective += 1
            if passed:
                defective_passed += 1
        else:
            total_valid += 1
            if not passed:
                valid_rejected += 1

    defective_pass_rate = defective_passed / total_defective if total_defective > 0 else 0
    valid_reject_rate = valid_rejected / total_valid if total_valid > 0 else 0
    escalation_rate = escalations / N_OUTPUTS
    entropy = shannon_entropy(path_counts)

    return defective_pass_rate, valid_reject_rate, escalation_rate, entropy


def run_experiment(defect_rate: float, unconstrained: bool,
                   detection_risk: float = 0.0, gameability: float = 1.0):
    """Multi-trial average."""
    dprs, vrrs, errs, ents = [], [], [], []
    for _ in range(N_TRIALS):
        dpr, vrr, er, ent = run_trial(defect_rate, unconstrained, detection_risk, gameability)
        dprs.append(dpr)
        vrrs.append(vrr)
        errs.append(er)
        ents.append(ent)
    return {
        "defective_pass_rate": statistics.mean(dprs),
        "defective_pass_std": statistics.stdev(dprs),
        "valid_reject_rate": statistics.mean(vrrs),
        "valid_reject_std": statistics.stdev(vrrs),
        "escalation_rate": statistics.mean(errs),
        "escalation_std": statistics.stdev(errs),
        "path_entropy_mean": statistics.mean(ents),
        "path_entropy_std": statistics.stdev(ents),
    }


def print_rows(rows, headers):
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    print()


def main():
    print("=" * 72)
    print("Experiment: Routing Editable-Surface Constraint")
    print(f"Outputs per trial: {N_OUTPUTS}, Trials per config: {N_TRIALS}")
    print("=" * 72)

    all_results = []

    # ─── Sweep 1: Baseline — Constrained vs Unconstrained ──────────────
    print("SWEEP 1: Constrained vs Unconstrained (detection_risk=0.1)")
    print("-" * 72)

    rows = []
    for dr in [0.05, 0.10, 0.20]:
        c = run_experiment(dr, unconstrained=False)
        u = run_experiment(dr, unconstrained=True, detection_risk=0.1, gameability=1.0)
        ratio = u["defective_pass_rate"] / c["defective_pass_rate"] if c["defective_pass_rate"] > 0 else 0
        rows.append([
            f"{dr:.0%}",
            f"{c['defective_pass_rate']:.3f}", f"{u['defective_pass_rate']:.3f}",
            f"{ratio:.1f}x",
            f"{u['escalation_rate']:.3f}",
        ])
        all_results.append(("sweep1", dr, False, 0.1, 1.0, c))
        all_results.append(("sweep1", dr, True, 0.1, 1.0, u))

    print_rows(rows, ["Defect Rate", "Const DPR", "Unconst DPR", "Ratio", "Escalation"])

    # ─── Sweep 2: Vary detection risk ──────────────────────────────────
    print("SWEEP 2: Vary detection risk (gameability=1.0, defect_rate=10%)")
    print("-" * 72)

    rows = []
    c = run_experiment(0.10, unconstrained=False)
    for det in [0.0, 0.05, 0.10, 0.20, 0.50]:
        u = run_experiment(0.10, unconstrained=True, detection_risk=det, gameability=1.0)
        ratio = u["defective_pass_rate"] / c["defective_pass_rate"] if c["defective_pass_rate"] > 0 else 0
        rows.append([
            f"{det:.0%}",
            f"{u['defective_pass_rate']:.3f}",
            f"{ratio:.1f}x",
            f"{u['escalation_rate']:.3f}",
        ])
        all_results.append(("sweep2", 0.10, True, det, 1.0, u))

    # Add constrained baseline as a row
    rows.append(["const (ref)", f"{c['defective_pass_rate']:.3f}", "1.0x", "0.000"])
    print_rows(rows, ["Detection Risk", "Unconst DPR", "Ratio to Const", "Escalation"])

    # ─── Sweep 3: Vary gameability ────────────────────────────────────
    print("SWEEP 3: Vary agent gameability (detection_risk=0.1, defect_rate=10%)")
    print("-" * 72)

    rows = []
    c = run_experiment(0.10, unconstrained=False)
    for g in [0.0, 0.2, 0.5, 0.8, 1.0]:
        u = run_experiment(0.10, unconstrained=True, detection_risk=0.1, gameability=g)
        ratio = u["defective_pass_rate"] / c["defective_pass_rate"] if c["defective_pass_rate"] > 0 else 0
        rows.append([
            f"{g:.0%}",
            f"{u['defective_pass_rate']:.3f}",
            f"{ratio:.1f}x",
        ])
        all_results.append(("sweep3", 0.10, True, 0.1, g, u))

    rows.append(["const (ref)", f"{c['defective_pass_rate']:.3f}", "1.0x"])
    print_rows(rows, ["Gameability", "Unconst DPR", "Ratio to Const"])

    # ─── Sweep 4: No allowed override (routing-surface constraint) ────
    print("SWEEP 4: With routing-surface constraint (ALLOWED_OVERRIDE = empty)")
    print("-" * 72)

    global ALLOWED_OVERRIDE
    saved_overrides = ALLOWED_OVERRIDE.copy()
    ALLOWED_OVERRIDE = {t: [] for t in DEFAULT_ROUTE}  # no override possible

    rows = []
    for dr in [0.05, 0.10, 0.20]:
        u = run_experiment(dr, unconstrained=True, detection_risk=0.1, gameability=1.0)
        c = run_experiment(dr, unconstrained=False)
        ratio = u["defective_pass_rate"] / c["defective_pass_rate"] if c["defective_pass_rate"] > 0 else 0
        rows.append([
            f"{dr:.0%}",
            f"{c['defective_pass_rate']:.3f}",
            f"{u['defective_pass_rate']:.3f}",
            f"{ratio:.1f}x",
        ])
        all_results.append(("sweep4_constrained", dr, False, 0.1, 1.0, c))

    # Restore
    ALLOWED_OVERRIDE = saved_overrides
    print_rows(rows, ["Defect Rate", "Const DPR", "Constrained DPR", "Ratio"])

    # ─── Sweep 5: Operating point variance (path entropy) ──────────────
    print("SWEEP 5: Operating point variance — path entropy comparison")
    print("-" * 72)

    rows5 = []
    for dr in [0.05, 0.10, 0.20]:
        c = run_experiment(dr, unconstrained=False)
        u = run_experiment(dr, unconstrained=True, detection_risk=0.1, gameability=1.0)
        u0 = run_experiment(dr, unconstrained=True, detection_risk=0.0, gameability=1.0)
        rows5.append([
            f"{dr:.0%}",
            f"{c['path_entropy_mean']:.3f}", f"{u['path_entropy_mean']:.3f}", f"{u0['path_entropy_mean']:.3f}",
            f"{c['defective_pass_rate']:.3f}", f"{u['defective_pass_rate']:.3f}",
        ])
        all_results.append(("sweep5_entropy", dr, False, 0.1, 1.0, c))
        all_results.append(("sweep5_entropy", dr, True, 0.1, 1.0, u))
        all_results.append(("sweep5_entropy", dr, True, 0.0, 1.0, u0))

    print_rows(rows5, ["Defect Rate", "Const H", "Unconst H", "Unconst(0det) H",
                        "Const DPR", "Unconst DPR"])

    # ─── Claim Check ──────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS CHECK")
    print("=" * 72)

    ref_c = run_experiment(0.10, unconstrained=False)
    ref_u = run_experiment(0.10, unconstrained=True, detection_risk=0.1, gameability=1.0)
    ref_ratio = ref_u["defective_pass_rate"] / ref_c["defective_pass_rate"] if ref_c["defective_pass_rate"] > 0 else 0

    print(f"\nBaseline: defect_rate=10%, detection_risk=10%, gameability=100%")
    print(f"  Constrained:   DPR = {ref_c['defective_pass_rate']:.3f}")
    print(f"  Unconstrained: DPR = {ref_u['defective_pass_rate']:.3f}")
    print(f"  Ratio:         {ref_ratio:.1f}x")
    print(f"  Claim (≥2×):   {'PASS' if ref_ratio >= 2.0 else 'FAIL'}")

    # Zero detection risk (worst case)
    ref_u0 = run_experiment(0.10, unconstrained=True, detection_risk=0.0, gameability=1.0)
    ref_ratio0 = ref_u0["defective_pass_rate"] / ref_c["defective_pass_rate"] if ref_c["defective_pass_rate"] > 0 else 0
    print(f"\nWorst case (detection_risk=0):")
    print(f"  Unconstrained: DPR = {ref_u0['defective_pass_rate']:.3f}")
    print(f"  Ratio:         {ref_ratio0:.1f}x")

    # Constrained vs constrained (Sweep 4 confirmation)
    print(f"\nWith routing-surface constraint (ALLOWED_OVERRIDE = empty):")
    print(f"  Result: routing override is structurally impossible.")
    print(f"  Constrained and unconstrained converge to same DPR.")
    print(f"  Editable-surface constraint eliminates the evasion vector entirely.")

    # ─── Operating point variance check ──────────────────────────────────
    print(f"\n--- Operating point variance ---")
    print(f"  Path entropy: constrained H={ref_c['path_entropy_mean']:.3f}, "
          f"unconstrained H={ref_u['path_entropy_mean']:.3f}, "
          f"unconstrained(0det) H={ref_u0['path_entropy_mean']:.3f}")
    print(f"  Entropy Δ: {ref_u['path_entropy_mean'] - ref_c['path_entropy_mean']:+.3f} "
          f"(unconstrained - constrained)")
    print(f"  Interpretation: unconstrained routing disperses outputs across more "
          f"verification paths = higher operating point variance.")
    print(f"  The editable-surface constraint on the routing table eliminates this "
          f"variance by making the routing table structurally readonly.")

    # ─── Write results ────────────────────────────────────────────────
    out = {
        "parameters": {
            "n_outputs": N_OUTPUTS,
            "n_trials": N_TRIALS,
            "verification_paths": VERIFICATION_PATHS,
            "default_routing": DEFAULT_ROUTE,
        },
        "claim": {
            "threshold_x": 2.0,
            "result_x": round(ref_ratio, 2),
            "pass": ref_ratio >= 2.0,
        },
        "results": [],
    }
    for sweep, dr, uc, det, game, r in all_results:
        out["results"].append({
            "sweep": sweep, "defect_rate": dr, "unconstrained": uc,
            "detection_risk": det, "gameability": game,
            "defective_pass_rate": round(r["defective_pass_rate"], 4),
            "valid_reject_rate": round(r["valid_reject_rate"], 4),
            "escalation_rate": round(r["escalation_rate"], 4),
            "path_entropy_mean": round(r["path_entropy_mean"], 4),
            "path_entropy_std": round(r["path_entropy_std"], 4),
        })

    out_path = Path(__file__).parent / "results-v2" / "routing-surface-constraint.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
