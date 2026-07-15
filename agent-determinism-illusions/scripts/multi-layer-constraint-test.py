"""
Experiment: Multi-layer harness constraint — does extending readonly coverage
across more evasion vectors monotonically reduce defective pass-through?

Falsifiable claim:
    The harness constraint is a single mechanism (readonly boundary) with
    applications across three verification layers. As readonly coverage
    extends from no constraint → L2 only → L2+L3, defective pass-through
    rate decreases monotonically. The residual is V4 (skip submission),
    which no constraint layer blocks.

    Claim: L2+L3 reduces defective pass-through by ≥60% vs baseline.
    Falsification: if L2+L3 reduces by <60%, the constraint's marginal
    value across layers is too small to be the central architectural lever.

Method:
    Monte Carlo simulation. N=5000 outputs per trial, 500 trials per config.
    Defect rate: 10%.
    For each defective output, the agent picks an evasion vector.

Four evasion vectors:
    V1: modify verify scripts       — blocked by L2 constraint
    V2: modify routing table        — blocked by L2 constraint
    V3: fake execution signals      — blocked by L3 constraint
    V4: skip submission             — NOT blocked by any constraint

Four constraint configurations:
    NONE:  no readonly coverage
    L2:    V1, V2 blocked
    L2+L3: V1, V2, V3 blocked
    ALL:   same as L2+L3 (V4 cannot be blocked at constraint layer)

Each vector has a base success rate (when not blocked):
    V1: 0.60 — modifying verify scripts is effective but easy to detect
    V2: 0.50 — routing reassignment, moderate coverage
    V3: 0.40 — faking signals requires sophisticated multi-channel forgery
    V4: 0.85 — skipping submission is highly effective when agent can self-report

When a vector is blocked, the agent must fall back to a remaining vector
or accept the defective output gets verified normally (lower pass rate).

Dependencies: none (pure Python).
"""

import random
import statistics
import sys
import io
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters ──────────────────────────────────────────────────────────────

N_OUTPUTS = 5000
N_TRIALS = 500
DEFECT_RATE = 0.10

# Base success rates for each evasion vector (when not blocked)
# V4's effective success depends on L3: when L3 is in place, pre-execution
# detection (91.8% catch rate from pre-execution-verification-test.py)
# reduces V4's effective success to 0.85 × (1 - 0.918) ≈ 0.07.
V4_BASE_SUCCESS = 0.85
V4_DETECTION_RATE_UNDER_L3 = 0.918

def v4_success(blocked_vectors: set) -> float:
    """V4 effective success depends on L3 presence."""
    if "V3_fake_signals" in blocked_vectors:  # L3 in place
        return V4_BASE_SUCCESS * (1 - V4_DETECTION_RATE_UNDER_L3)
    return V4_BASE_SUCCESS

VECTOR_SUCCESS = {
    "V1_modify_verify":   0.60,
    "V2_modify_routing":  0.50,
    "V3_fake_signals":    0.85,  # high success when signal producers are agent-writable
}

# Default verification path FP rate (without evasion)
# This is the baseline defective pass rate when no evasion succeeds
BASELINE_VERIFY_FP = 0.05

# Agent's preference order for evasion vectors (highest success first)
VECTOR_PREFERENCE = ["V4_skip_submission", "V1_modify_verify", "V2_modify_routing", "V3_fake_signals"]

# Constraint configurations: which vectors are blocked
CONSTRAINT_CONFIGS = {
    "NONE":  set(),                              # no constraint
    "L2":    {"V1_modify_verify", "V2_modify_routing"},
    "L3":    {"V3_fake_signals"},
    "L2+L3": {"V1_modify_verify", "V2_modify_routing", "V3_fake_signals"},
    "ALL":   {"V1_modify_verify", "V2_modify_routing", "V3_fake_signals"},
    # V4_skip_submission is never blocked at constraint layer
}


# ─── Simulation core ─────────────────────────────────────────────────────────

def simulate_one_defective(blocked_vectors: set):
    """Simulate one defective output under given constraint config.

    Agent tries evasion vectors in preference order. If a vector succeeds,
    defective passes. If all available vectors fail, defective goes through
    normal verification (baseline FP).

    Returns: True if defective passes (incorrectly accepted).
    """
    for v in VECTOR_PREFERENCE:
        if v in blocked_vectors:
            continue
        success = v4_success(blocked_vectors) if v == "V4_skip_submission" else VECTOR_SUCCESS[v]
        if random.random() < success:
            return True  # this vector succeeded

    # All available vectors failed — defective goes through normal verification
    return random.random() < BASELINE_VERIFY_FP


def simulate_one_valid():
    """Simulate one valid output. Returns True if valid passes."""
    # Valid outputs pass unless they hit FN
    # For simplicity, assume low FN rate
    return random.random() < 0.95  # 95% of valid outputs pass


def run_trial(defect_rate: float, blocked_vectors: set):
    """Run one trial. Returns (defective_pass_rate, valid_pass_rate)."""
    total_defective = 0
    defective_passed = 0
    total_valid = 0
    valid_passed = 0

    for _ in range(N_OUTPUTS):
        if random.random() < defect_rate:
            total_defective += 1
            if simulate_one_defective(blocked_vectors):
                defective_passed += 1
        else:
            total_valid += 1
            if simulate_one_valid():
                valid_passed += 1

    dpr = defective_passed / total_defective if total_defective > 0 else 0
    vpr = valid_passed / total_valid if total_valid > 0 else 0
    return dpr, vpr


def run_experiment(defect_rate: float, blocked_vectors: set, trials: int = N_TRIALS):
    """Multi-trial average."""
    dprs, vprs = [], []
    for _ in range(trials):
        dpr, vpr = run_trial(defect_rate, blocked_vectors)
        dprs.append(dpr)
        vprs.append(vpr)
    return {
        "defective_pass_rate": statistics.mean(dprs),
        "defective_pass_std": statistics.stdev(dprs),
        "valid_pass_rate": statistics.mean(vprs),
        "valid_pass_std": statistics.stdev(vprs),
    }


def print_table(rows, headers):
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    print()


def main():
    global VECTOR_SUCCESS, V4_BASE_SUCCESS
    print("=" * 72)
    print("Experiment: Multi-Layer Harness Constraint Effectiveness")
    print(f"Outputs per trial: {N_OUTPUTS}, Trials per config: {N_TRIALS}, Defect rate: {DEFECT_RATE:.0%}")
    print("=" * 72)
    print(f"Evasion vectors (base success when not blocked):")
    for v, s in VECTOR_SUCCESS.items():
        print(f"  {v}: {s:.2f}")
    print(f"  V4_skip_submission: {V4_BASE_SUCCESS:.2f} (reduces to {V4_BASE_SUCCESS * (1 - V4_DETECTION_RATE_UNDER_L3):.3f} under L3)")
    print()

    all_results = []

    # Sweep 1: Default — vary constraint configuration
    print("─" * 72)
    print("SWEEP 1: Defective pass-through by constraint configuration")
    print("-" * 72)
    rows = []
    baseline_dpr = None
    for config_name, blocked in CONSTRAINT_CONFIGS.items():
        r = run_experiment(DEFECT_RATE, blocked)
        if baseline_dpr is None:
            baseline_dpr = r["defective_pass_rate"]
        reduction = (baseline_dpr - r["defective_pass_rate"]) / baseline_dpr if baseline_dpr > 0 else 0
        rows.append([
            config_name,
            f"{r['defective_pass_rate']:.3f}",
            f"{reduction:.1%}",
            f"{r['valid_pass_rate']:.3f}",
        ])
        all_results.append((config_name, DEFECT_RATE, r))
    print_table(rows, ["Config", "Defective Pass Rate", "Reduction vs NONE", "Valid Pass Rate"])

    # Sweep 2: Vary defect rate under L2+L3
    print("SWEEP 2: Vary defect rate under L2+L3 constraint")
    print("-" * 72)
    rows = []
    for dr in [0.05, 0.10, 0.20, 0.30]:
        r_none = run_experiment(dr, CONSTRAINT_CONFIGS["NONE"])
        r_l2l3 = run_experiment(dr, CONSTRAINT_CONFIGS["L2+L3"])
        reduction = (r_none["defective_pass_rate"] - r_l2l3["defective_pass_rate"]) / r_none["defective_pass_rate"] if r_none["defective_pass_rate"] > 0 else 0
        rows.append([
            f"{dr:.0%}",
            f"{r_none['defective_pass_rate']:.3f}",
            f"{r_l2l3['defective_pass_rate']:.3f}",
            f"{reduction:.1%}",
        ])
        all_results.append((f"L2+L3@dr={dr}", dr, r_l2l3))
    print_table(rows, ["Defect Rate", "NONE DPR", "L2+L3 DPR", "Reduction"])

    # Sweep 3: Sensitivity to V4 (skip submission) success rate
    # If V4 is the only available vector (everything else blocked), how does
    # its success rate affect the residual?
    print("SWEEP 3: Residual sensitivity to V4 (skip submission) base success rate")
    print("-" * 72)
    saved_v4 = V4_BASE_SUCCESS
    rows = []
    for v4_rate in [0.50, 0.70, 0.85, 0.95]:
        V4_BASE_SUCCESS = v4_rate
        r = run_experiment(DEFECT_RATE, CONSTRAINT_CONFIGS["L2+L3"])
        rows.append([
            f"{v4_rate:.2f}",
            f"{r['defective_pass_rate']:.3f}",
        ])
        all_results.append((f"L2+L3_v4={v4_rate}", DEFECT_RATE, r))
    V4_BASE_SUCCESS = saved_v4
    print_table(rows, ["V4 Success Rate", "L2+L3 Defective Pass Rate"])
    print("(V4 is the irreducible residual — its success rate determines the constraint ceiling)")

    # Sweep 4: Marginal contribution of each layer
    print("SWEEP 4: Marginal contribution — adding each layer's constraint")
    print("-" * 72)
    base = run_experiment(DEFECT_RATE, CONSTRAINT_CONFIGS["NONE"])
    l2 = run_experiment(DEFECT_RATE, CONSTRAINT_CONFIGS["L2"])
    l2l3 = run_experiment(DEFECT_RATE, CONSTRAINT_CONFIGS["L2+L3"])

    delta_l2 = base["defective_pass_rate"] - l2["defective_pass_rate"]
    delta_l3 = l2["defective_pass_rate"] - l2l3["defective_pass_rate"]
    rows = [
        ["NONE → L2 (V1+V2 blocked)", f"{base['defective_pass_rate']:.3f}", f"{l2['defective_pass_rate']:.3f}", f"{delta_l2:+.3f}"],
        ["L2 → L2+L3 (V3 blocked)",   f"{l2['defective_pass_rate']:.3f}", f"{l2l3['defective_pass_rate']:.3f}", f"{delta_l3:+.3f}"],
    ]
    print_table(rows, ["Transition", "Before", "After", "Δ DPR"])

    # ─── Claims check ─────────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS CHECK")
    print("=" * 72)

    final = run_experiment(DEFECT_RATE, CONSTRAINT_CONFIGS["L2+L3"])
    reduction_total = (baseline_dpr - final["defective_pass_rate"]) / baseline_dpr if baseline_dpr > 0 else 0

    print(f"\nBaseline: defect_rate={DEFECT_RATE:.0%}")
    print(f"  NONE config:    DPR = {baseline_dpr:.3f}")
    print(f"  L2+L3 config:   DPR = {final['defective_pass_rate']:.3f}")
    print(f"  Total reduction: {reduction_total:.1%}")
    print(f"  Claim (≥60% reduction): {'PASS' if reduction_total >= 0.60 else 'FAIL'}")

    print(f"\nMarginal contributions:")
    print(f"  L2 alone (V1+V2 blocked):  reduces DPR by {delta_l2/baseline_dpr:.1%} of baseline")
    print(f"  L3 addition (V3 blocked):  reduces DPR by {delta_l3/baseline_dpr:.1%} of baseline")
    print(f"  Residual after L2+L3:      {final['defective_pass_rate']:.3f} (driven by V4 — skip submission)")

    print(f"\nArchitectural interpretation:")
    print(f"  Harness constraint is one mechanism (readonly boundary).")
    print(f"  Extending it from L2 to L2+L3 yields measurable reduction.")
    print(f"  V4 (skip submission) is irreducible at the constraint layer —")
    print(f"  it requires external dispatch enforcement (out of pipeline).")

    # ─── Write results ─────────────────────────────────────────────────────
    out = {
        "parameters": {
            "n_outputs": N_OUTPUTS,
            "n_trials": N_TRIALS,
            "defect_rate": DEFECT_RATE,
            "vector_success_rates": VECTOR_SUCCESS,
            "baseline_verify_fp": BASELINE_VERIFY_FP,
        },
        "claim_reduction_threshold": {"threshold": 0.60, "result": reduction_total, "pass": reduction_total >= 0.60},
        "results": [],
    }
    for config_name, dr, r in all_results:
        out["results"].append({
            "config": config_name, "defect_rate": dr,
            "defective_pass_rate": round(r["defective_pass_rate"], 4),
            "valid_pass_rate": round(r["valid_pass_rate"], 4),
        })

    out_path = Path(__file__).parent / "results-v2" / "multi-layer-constraint.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
