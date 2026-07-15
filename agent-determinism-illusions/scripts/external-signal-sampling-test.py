"""
Experiment: Do Alex Shev's four external signals improve sampling over fixed-rate or model-divergence alone?

Claims under test:

  Claim #1 (catch rate): A fixed 10% baseline PLUS binary external signals (route_changed,
  classifier_agreement < threshold, unusual_input_shape, barely_passed_deterministic_check)
  detects >40% of defective outputs — a meaningful improvement over fixed 10% sampling's ~10%.

  Claim #2 (vs Part 6): Alex-style external signals catch ≥30% more defective outputs than
  Part 6's model-divergence-based adaptive sampling at the same audit rate.

Method:
  Monte Carlo simulation — 1500-output verification streams, 1000 trials per config.
  For each output: ground truth (clean/defective), model divergence (unanimous/split),
  4 external signals (each with configurable TP/FP rates).

  Three strategies:
    A: Fixed 10% audit
    B: Part 6 adaptive (audit rate driven by 3-prompt divergence: 5% / 30% / 50%)
    C: Alex external (10% baseline + escalate on signal fire: +30% per signal, cap 100%)

  Swept parameters: signal_quality (low/medium/high), error_distribution (uniform/
  long-tail burst/mixed), base_error_rate (0.05/0.10/0.20).

Falsification:
  - If Signal quality doesn't change relative ranking (C ≈ B or C < B under all conditions),
    Claim #2 is falsified — external signals don't add value beyond divergence.
  - If C's catch rate < 25% under medium signal quality, Claim #1 is falsified.

Dependencies: none (pure Python).
"""

import random
import statistics
import sys
import io
import json
from pathlib import Path
from dataclasses import dataclass

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Parameters ──────────────────────────────────────────────────────────────

STREAM_LENGTH = 1500
TRIALS = 1000

@dataclass
class SignalConfig:
    name: str
    tp: float   # true positive rate (signal fires on defective)
    fp: float   # false positive rate (signal fires on clean)

# Default signal quality: "medium"
SIGNAL_MEDIUM = [
    SignalConfig("route_changed",       0.25, 0.05),
    SignalConfig("classifier_disagree", 0.50, 0.12),
    SignalConfig("input_unusual",       0.20, 0.04),
    SignalConfig("barely_passed",       0.35, 0.08),
]

SIGNAL_LOW = [
    SignalConfig("route_changed",       0.15, 0.08),
    SignalConfig("classifier_disagree", 0.30, 0.18),
    SignalConfig("input_unusual",       0.10, 0.06),
    SignalConfig("barely_passed",       0.20, 0.12),
]

SIGNAL_HIGH = [
    SignalConfig("route_changed",       0.35, 0.03),
    SignalConfig("classifier_disagree", 0.65, 0.08),
    SignalConfig("input_unusual",       0.30, 0.02),
    SignalConfig("barely_passed",       0.50, 0.05),
]

SIGNAL_QUALITY = {"low": SIGNAL_LOW, "medium": SIGNAL_MEDIUM, "high": SIGNAL_HIGH}

# Error distribution modes
ERROR_DISTRIBUTIONS = ["uniform", "burst", "mixed"]

# Model divergence probabilities conditioned on ground truth
# divergence: 0=unanimous, 1=split 2-1, 2=split all 3
DIVERGENCE_CLEAN = [0.80, 0.15, 0.05]
DIVERGENCE_DEFECTIVE = [0.30, 0.40, 0.30]

# Strategy configs
STRATEGY_FIXED_RATE = 0.10

# Part 6: audit rate by divergence level
P6_RATES = {0: 0.05, 1: 0.30, 2: 0.50}

# Alex: baseline + escalation per signal
ALEX_BASELINE = 0.10
ALEX_ESCALATION_PER_SIGNAL = 0.30

# ─── Simulation core ─────────────────────────────────────────────────────────

def generate_stream(error_rate: float, error_dist: str):
    """Yield (ground_truth,) for STREAM_LENGTH outputs."""
    outputs = []
    burst_remaining = 0
    for i in range(STREAM_LENGTH):
        if error_dist == "uniform":
            defective = random.random() < error_rate
        elif error_dist == "burst":
            if burst_remaining > 0:
                defective = random.random() < min(1.0, error_rate * 4)
                burst_remaining -= 1
            else:
                defective = random.random() < error_rate
                if defective:
                    burst_remaining = random.randint(1, 4)
        else:  # mixed
            if random.random() < 0.5:
                defective = random.random() < error_rate
            else:
                if burst_remaining > 0:
                    defective = random.random() < min(1.0, error_rate * 4)
                    burst_remaining -= 1
                else:
                    defective = random.random() < error_rate
                    if defective:
                        burst_remaining = random.randint(1, 4)
        outputs.append(defective)
    return outputs


def generate_signals(ground_truths: list, signal_configs: list):
    """For each output, generate the 4 external signals (0/1) and model divergence (0/1/2)."""
    results = []
    for gt in ground_truths:
        # External signals
        ext_signals = []
        for sc in signal_configs:
            prob = sc.tp if gt else sc.fp
            ext_signals.append(1 if random.random() < prob else 0)

        # Model divergence
        dist = DIVERGENCE_DEFECTIVE if gt else DIVERGENCE_CLEAN
        r = random.random()
        if r < dist[0]:
            divergence = 0
        elif r < dist[0] + dist[1]:
            divergence = 1
        else:
            divergence = 2

        results.append({
            "defective": gt,
            "signals": ext_signals,
            "divergence": divergence,
        })
    return results


def run_strategy_fixed(outputs: list):
    """Fixed 10% audit."""
    audited = []
    catches = 0
    total_defective = sum(1 for o in outputs if o["defective"])
    for o in outputs:
        if random.random() < STRATEGY_FIXED_RATE:
            audited.append(o)
            if o["defective"]:
                catches += 1
    audit_rate = len(audited) / len(outputs)
    catch_rate = catches / total_defective if total_defective > 0 else 0
    efficiency = catch_rate / audit_rate if audit_rate > 0 else 0
    return audit_rate, catch_rate, efficiency


def run_strategy_p6(outputs: list):
    """Part 6 adaptive: audit rate by model divergence."""
    audited = []
    catches = 0
    total_defective = sum(1 for o in outputs if o["defective"])
    for o in outputs:
        rate = P6_RATES[o["divergence"]]
        if random.random() < rate:
            audited.append(o)
            if o["defective"]:
                catches += 1
    audit_rate = len(audited) / len(outputs)
    catch_rate = catches / total_defective if total_defective > 0 else 0
    efficiency = catch_rate / audit_rate if audit_rate > 0 else 0
    return audit_rate, catch_rate, efficiency


def run_strategy_alex(outputs: list, baseline: float = 0.10, escalation: float = 0.30):
    """Alex: baseline + escalate on external signal."""
    audited = []
    catches = 0
    total_defective = sum(1 for o in outputs if o["defective"])
    for o in outputs:
        n_signals = sum(o["signals"])
        rate = baseline + n_signals * escalation
        rate = min(rate, 1.0)  # cap at 100%
        if random.random() < rate:
            audited.append(o)
            if o["defective"]:
                catches += 1
    audit_rate = len(audited) / len(outputs)
    catch_rate = catches / total_defective if total_defective > 0 else 0
    efficiency = catch_rate / audit_rate if audit_rate > 0 else 0
    return audit_rate, catch_rate, efficiency


def run_trial(error_rate: float, error_dist: str, signal_configs: list,
              alex_baseline: float = 0.10, alex_esc: float = 0.30):
    """Run a single trial with all 3 strategies."""
    random.seed()  # use fresh entropy each trial
    ground_truths = generate_stream(error_rate, error_dist)
    outputs = generate_signals(ground_truths, signal_configs)

    fixed = run_strategy_fixed(outputs)
    p6 = run_strategy_p6(outputs)
    alex = run_strategy_alex(outputs, baseline=alex_baseline, escalation=alex_esc)

    return {"fixed": fixed, "p6": p6, "alex": alex}


def run_experiment(error_rate: float, error_dist: str, signal_configs: list, trials: int = TRIALS,
                   alex_baseline: float = 0.10, alex_esc: float = 0.30):
    """Run multi-trial experiment and average results."""
    results = {"fixed": [], "p6": [], "alex": []}
    for _ in range(trials):
        trial = run_trial(error_rate, error_dist, signal_configs,
                          alex_baseline=alex_baseline, alex_esc=alex_esc)
        for k in results:
            results[k].append(trial[k])

    summary = {}
    for k in results:
        ars = [r[0] for r in results[k]]
        crs = [r[1] for r in results[k]]
        effs = [r[2] for r in results[k]]
        summary[k] = {
            "audit_rate_mean": statistics.mean(ars),
            "audit_rate_std": statistics.stdev(ars),
            "catch_rate_mean": statistics.mean(crs),
            "catch_rate_std": statistics.stdev(crs),
            "efficiency_mean": statistics.mean(effs),
            "efficiency_std": statistics.stdev(effs),
        }
    return summary


def print_table(rows, headers):
    """Print a clean table."""
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep = "-+-".join("-" * w for w in col_widths)
    data_lines = []
    for r in rows:
        data_lines.append(" | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers))))
    print(header_line)
    print(sep)
    for l in data_lines:
        print(l)
    print()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Experiment: External Signals for Adaptive Sampling")
    print(f"Stream length: {STREAM_LENGTH}, Trials per config: {TRIALS}")
    print("=" * 72)

    all_results = []

    # Sweep 1: Default sweep (medium signal quality, 10% error rate)
    print("\n" + "─" * 72)
    print("SWEEP 1: Default — medium signal quality, base error rate 10%")
    print("─" * 72)

    rows = []
    for dist in ERROR_DISTRIBUTIONS:
        s = run_experiment(0.10, dist, SIGNAL_MEDIUM)
        rows.append([dist,
                     f"{s['fixed']['audit_rate_mean']:.3f}", f"{s['fixed']['catch_rate_mean']:.3f}",
                     f"{s['p6']['audit_rate_mean']:.3f}", f"{s['p6']['catch_rate_mean']:.3f}",
                     f"{s['alex']['audit_rate_mean']:.3f}", f"{s['alex']['catch_rate_mean']:.3f}"])
        all_results.append((0.10, dist, "medium", s))

    print_table(rows, ["Error Dist", "Fix AR", "Fix CR", "P6 AR", "P6 CR", "Alex AR", "Alex CR"])

    # Sweep 2: Vary error rate
    print("SWEEP 2: Vary error rate — mixed error distribution, medium signal quality")
    print("-" * 72)

    rows = []
    for er in [0.05, 0.10, 0.20]:
        s = run_experiment(er, "mixed", SIGNAL_MEDIUM)
        rows.append([f"{er:.0%}",
                     f"{s['fixed']['catch_rate_mean']:.3f}", f"{s['p6']['catch_rate_mean']:.3f}",
                     f"{s['alex']['catch_rate_mean']:.3f}"])
        all_results.append((er, "mixed", "medium", s))

    print_table(rows, ["Error Rate", "Fixed CR", "P6 CR", "Alex CR"])

    # Sweep 3: Vary signal quality
    print("SWEEP 3: Vary signal quality — mixed error distribution, 10% error rate")
    print("-" * 72)

    rows = []
    for sq_name in ["low", "medium", "high"]:
        s = run_experiment(0.10, "mixed", SIGNAL_QUALITY[sq_name])
        rows.append([sq_name,
                     f"{s['fixed']['catch_rate_mean']:.3f}", f"{s['p6']['catch_rate_mean']:.3f}",
                     f"{s['alex']['catch_rate_mean']:.3f}", f"{s['alex']['audit_rate_mean']:.3f}"])
        all_results.append((0.10, "mixed", sq_name, s))

    print_table(rows, ["Signal Qual", "Fixed CR", "P6 CR", "Alex CR", "Alex AR"])

    # ─── Signal contribution breakdown ─────────────────────────────────────
    print("SWEEP 4: Individual signal contribution — remove one signal at a time")
    print("-" * 72)

    baseline = run_experiment(0.10, "mixed", SIGNAL_MEDIUM)
    rows4 = []
    for drop_idx, name in enumerate(["route_changed", "classifier_disagree", "input_unusual", "barely_passed"]):
        reduced = [sc for i, sc in enumerate(SIGNAL_MEDIUM) if i != drop_idx]
        s = run_experiment(0.10, "mixed", reduced)
        delta = baseline["alex"]["catch_rate_mean"] - s["alex"]["catch_rate_mean"]
        rows4.append([name, f"{s['alex']['catch_rate_mean']:.3f}", f"{delta:+.3f}"])

    print_table(rows4, ["Dropped Signal", "Alex CR (w/o)", "Δ from full"])

    # ─── Justice check: equal audit rate ──────────────────────────────────
    print("SWEEP 5: Calibrate Alex to match P6's audit rate — equal-cost comparison")
    print("-" * 72)

    p6_ref = run_experiment(0.10, "mixed", SIGNAL_MEDIUM)
    p6_ar = p6_ref["p6"]["audit_rate_mean"]
    p6_cr = p6_ref["p6"]["catch_rate_mean"]

    rows5 = []
    for base in [0.03, 0.05, 0.08]:
        for esc in [0.10, 0.15, 0.20]:
            s = run_experiment(0.10, "mixed", SIGNAL_MEDIUM,
                               alex_baseline=base, alex_esc=esc)
            ar = s["alex"]["audit_rate_mean"]
            cr = s["alex"]["catch_rate_mean"]
            rows5.append([f"{base:.0%}+{esc:.0%}", f"{ar:.3f}", f"{cr:.3f}",
                         f"{cr/p6_cr:.2f}x" if p6_cr > 0 else "N/A",
                         "✓" if abs(ar - p6_ar) < 0.01 else ""])

    print(f"P6 reference: AR={p6_ar:.3f} CR={p6_cr:.3f}")
    print_table(rows5, ["Alex(base+esc)", "AR", "CR", "vs P6", "≈P6 AR"])

    # ─── Check Claims ──────────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS CHECK")
    print("=" * 72)

    # Claim #1: Alex catches > 40% under medium signal
    ref = next(r for r in all_results if r[2] == "medium" and r[0] == 0.10 and r[1] == "mixed")
    alex_cr = ref[3]["alex"]["catch_rate_mean"]
    fixed_cr = ref[3]["fixed"]["catch_rate_mean"]
    p6_cr = ref[3]["p6"]["catch_rate_mean"]
    alex_ar = ref[3]["alex"]["audit_rate_mean"]
    fixed_ar = ref[3]["fixed"]["audit_rate_mean"]
    p6_ar = ref[3]["p6"]["audit_rate_mean"]

    print(f"\nBaseline: medium signal, 10% error, mixed distribution")
    print(f"  Fixed:  AR={fixed_ar:.1%} CR={fixed_cr:.1%}")
    print(f"  P6:     AR={p6_ar:.1%} CR={p6_cr:.1%}")
    print(f"  Alex:   AR={alex_ar:.1%} CR={alex_cr:.1%}")

    print(f"\nClaim #1 (Alex > 40% catch): {'PASS' if alex_cr > 0.40 else 'FAIL'} ({alex_cr:.1%})")
    print(f"Claim #2 (Alex ≥ P6 × 1.3): {'PASS' if alex_cr >= p6_cr * 1.3 else 'FAIL'} "
          f"(Alex {alex_cr:.1%} vs P6 {p6_cr:.1%}, ratio {alex_cr/p6_cr:.2f}x)")

    # Cross-check: at matching audit rate
    print(f"\nJustice check — at matching audit rates:")
    # Find an Alex config where audit rate ≈ P6's audit rate
    for er, dist, sq, s in all_results:
        alex_ar_i = s["alex"]["audit_rate_mean"]
        p6_ar_i = s["p6"]["audit_rate_mean"]
        if abs(alex_ar_i - p6_ar_i) < 0.02:
            print(f"  Config: err={er}, dist={dist}, sig={sq}")
            print(f"  P6:   AR={p6_ar_i:.1%} CR={s['p6']['catch_rate_mean']:.1%}")
            print(f"  Alex: AR={alex_ar_i:.1%} CR={s['alex']['catch_rate_mean']:.1%}")

    # ─── Write results ────────────────────────────────────────────────────
    out = {
        "parameters": {
            "stream_length": STREAM_LENGTH,
            "trials": TRIALS,
            "strategies": ["fixed", "p6", "alex"],
            "signal_quality_configs": {
                q: [{"name": sc.name, "tp": sc.tp, "fp": sc.fp} for sc in scs]
                for q, scs in SIGNAL_QUALITY.items()
            },
        },
        "claim1": {"threshold": 0.40, "result": alex_cr, "pass": alex_cr > 0.40},
        "claim2": {"threshold_x": 1.3, "result_x": alex_cr / p6_cr if p6_cr > 0 else None, "pass": alex_cr >= p6_cr * 1.3},
        "results": [],
    }

    for er, dist, sq, s in all_results:
        out["results"].append({
            "error_rate": er, "error_distribution": dist, "signal_quality": sq,
            "fixed": {k: round(v, 4) for k, v in s["fixed"].items()},
            "p6": {k: round(v, 4) for k, v in s["p6"].items()},
            "alex": {k: round(v, 4) for k, v in s["alex"].items()},
        })

    out_path = Path(__file__).parent / "results-v2" / "external-signal-sampling.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
