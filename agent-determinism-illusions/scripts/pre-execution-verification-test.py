"""
Experiment: Can independent observability signals detect skipped-step self-reports?

Falsifiable claim:
    When an agent reports "step done" without actually executing the step,
    independent observability signals (filesystem state changes, tool-call
    logs, process execution traces, resource usage, time elapsed) — sourced
    from outside the agent's control flow — detect the skipped step at a
    measurable rate, with false-positive rate bounded on real executions.

    Claim: any non-baseline strategy (any-signal, 2+-signal, TP-weighted)
    achieves ≥30% skipped-step detection with <15% FP rate on real executions.

    Falsification: if all independent-signal strategies achieve <30% detection
    on skipped steps at FP <15%, pre-execution verification is impractical.

Method:
    Monte Carlo simulation. N=2000 step reports per trial, 500 trials per config.
    Each step: ground_truth (executed/skipped), 5 observability signals with
    configurable TP/FP rates calibrated to "agent can fake this signal" cost.

    Five strategies compared:
        A: Baseline (trust self-report, no audit)
        B: Fixed 10% random sampling
        C: Any-signal audit (audit if ≥1 signal fires)
        D: 2+-signal audit (audit if ≥2 signals fire)
        E: TP-weighted (audit probability = sum(signal_TP × fired), capped)

Signal taxonomy (by agent falsifiability):
    state_change     — pre/post filesystem diff, agent must write real file
    tool_call_log    — readonly wrapper records every tool call
    process_trace    — exit code, requires readonly runner
    resource_usage   — CPU/network observable from outside agent control flow
    time_elapsed     — universal but easily faked (agent can wait)

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

STREAM_LENGTH = 2000
TRIALS = 500

@dataclass
class SignalConfig:
    name: str
    tp: float   # P(signal fires | step actually executed)
    fp: float   # P(signal fires | step skipped but agent claimed done)
    falsifiability: str  # how easily the agent can fake this signal

# Default: medium-quality signals
SIGNAL_MEDIUM = [
    SignalConfig("state_change",   0.90, 0.05, "low"),    # must write real file
    SignalConfig("tool_call_log",  0.95, 0.02, "low"),    # readonly wrapper
    SignalConfig("process_trace",  0.85, 0.10, "medium"), # agent can fake log if wrapper not readonly
    SignalConfig("resource_usage", 0.80, 0.15, "medium"), # agent can burn CPU
    SignalConfig("time_elapsed",   0.50, 0.20, "high"),   # agent can just wait
]

SIGNAL_LOW = [
    SignalConfig("state_change",   0.75, 0.12, "low"),
    SignalConfig("tool_call_log",  0.80, 0.08, "low"),
    SignalConfig("process_trace",  0.70, 0.20, "medium"),
    SignalConfig("resource_usage", 0.60, 0.25, "medium"),
    SignalConfig("time_elapsed",   0.40, 0.30, "high"),
]

SIGNAL_HIGH = [
    SignalConfig("state_change",   0.97, 0.02, "low"),
    SignalConfig("tool_call_log",  0.98, 0.01, "low"),
    SignalConfig("process_trace",  0.92, 0.05, "medium"),
    SignalConfig("resource_usage", 0.90, 0.08, "medium"),
    SignalConfig("time_elapsed",   0.60, 0.15, "high"),
]

SIGNAL_QUALITY = {"low": SIGNAL_LOW, "medium": SIGNAL_MEDIUM, "high": SIGNAL_HIGH}

EXEC_RATE = 0.70  # 70% of steps actually execute, 30% are skipped self-reports

# ─── Simulation core ─────────────────────────────────────────────────────────

def generate_step():
    """Generate one step's ground truth."""
    return "executed" if random.random() < EXEC_RATE else "skipped"


def generate_signals(ground_truth: str, signal_configs: list):
    """Generate the 5 signal values (0/1) for one step."""
    signals = []
    for sc in signal_configs:
        prob = sc.tp if ground_truth == "executed" else sc.fp
        signals.append(1 if random.random() < prob else 0)
    return signals


def run_strategy_baseline(steps, signals):
    """A: Trust the self-report, no audit."""
    audit_count = 0
    skipped_caught = 0
    total_skipped = sum(1 for s in steps if s == "skipped")
    return audit_count, skipped_caught, total_skipped


def run_strategy_fixed_sample(steps, signals, rate=0.10):
    """B: Fixed 10% random sampling."""
    audit_count = 0
    skipped_caught = 0
    total_skipped = 0
    for gt, sigs in zip(steps, signals):
        if gt == "skipped":
            total_skipped += 1
        if random.random() < rate:
            audit_count += 1
            if gt == "skipped":
                skipped_caught += 1
    return audit_count, skipped_caught, total_skipped


def run_strategy_any_signal(steps, signals):
    """C: Audit if zero signals fire (no evidence of execution)."""
    audit_count = 0
    skipped_caught = 0
    total_skipped = 0
    for gt, sigs in zip(steps, signals):
        if gt == "skipped":
            total_skipped += 1
        if sum(sigs) == 0:
            audit_count += 1
            if gt == "skipped":
                skipped_caught += 1
    return audit_count, skipped_caught, total_skipped


def run_strategy_two_plus_signal(steps, signals):
    """D: Audit if at most 1 signal fires (very little evidence)."""
    audit_count = 0
    skipped_caught = 0
    total_skipped = 0
    for gt, sigs in zip(steps, signals):
        if gt == "skipped":
            total_skipped += 1
        if sum(sigs) <= 1:
            audit_count += 1
            if gt == "skipped":
                skipped_caught += 1
    return audit_count, skipped_caught, total_skipped


def run_strategy_tp_weighted(steps, signals, signal_configs):
    """E: Audit probability inversely weighted by signal presence.

    P(audit) = (N - sum(fired)) / N — fewer firing signals = higher audit probability.
    """
    n_signals = len(signal_configs)
    audit_count = 0
    skipped_caught = 0
    total_skipped = 0
    for gt, sigs in zip(steps, signals):
        if gt == "skipped":
            total_skipped += 1
        absence_ratio = (n_signals - sum(sigs)) / n_signals
        if random.random() < absence_ratio:
            audit_count += 1
            if gt == "skipped":
                skipped_caught += 1
    return audit_count, skipped_caught, total_skipped


def run_trial(signal_configs: list):
    """Run one trial with all 5 strategies."""
    random.seed()
    steps = [generate_step() for _ in range(STREAM_LENGTH)]
    signals = [generate_signals(gt, signal_configs) for gt in steps]

    results = {
        "baseline":     run_strategy_baseline(steps, signals),
        "fixed_sample": run_strategy_fixed_sample(steps, signals),
        "any_signal":   run_strategy_any_signal(steps, signals),
        "two_plus":     run_strategy_two_plus_signal(steps, signals),
        "tp_weighted":  run_strategy_tp_weighted(steps, signals, signal_configs),
    }
    return results


def run_experiment(signal_configs: list, trials: int = TRIALS):
    """Multi-trial average."""
    aggregated = {k: [] for k in ["baseline", "fixed_sample", "any_signal", "two_plus", "tp_weighted"]}
    for _ in range(trials):
        trial = run_trial(signal_configs)
        for k in aggregated:
            aggregated[k].append(trial[k])

    summary = {}
    for k, results in aggregated.items():
        detection_rates = []
        audit_rates = []
        fp_rates = []
        for audit_count, skipped_caught, total_skipped in results:
            total_executed = STREAM_LENGTH - total_skipped
            # Detection rate: skipped steps caught / total skipped
            dr = skipped_caught / total_skipped if total_skipped > 0 else 0
            # Audit rate: fraction of steps audited
            ar = audit_count / STREAM_LENGTH
            # FP rate: real executions audited / total executions
            real_audited = audit_count - skipped_caught
            fp = real_audited / total_executed if total_executed > 0 else 0
            detection_rates.append(dr)
            audit_rates.append(ar)
            fp_rates.append(fp)
        summary[k] = {
            "detection_rate_mean": statistics.mean(detection_rates),
            "detection_rate_std": statistics.stdev(detection_rates),
            "audit_rate_mean": statistics.mean(audit_rates),
            "audit_rate_std": statistics.stdev(audit_rates),
            "fp_rate_mean": statistics.mean(fp_rates),
            "fp_rate_std": statistics.stdev(fp_rates),
        }
    return summary


def print_table(rows, headers):
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    print()


def main():
    global EXEC_RATE
    print("=" * 72)
    print("Experiment: Pre-Execution Verification Signal Effectiveness")
    print(f"Stream length: {STREAM_LENGTH}, Trials per config: {TRIALS}")
    print(f"Execution rate: {EXEC_RATE:.0%} (so skipped self-reports = {1-EXEC_RATE:.0%} of stream)")
    print("=" * 72)

    all_results = []

    # Sweep 1: Default — medium signal quality
    print("\n" + "─" * 72)
    print("SWEEP 1: Default — medium signal quality")
    print("─" * 72)

    s = run_experiment(SIGNAL_MEDIUM)
    rows = []
    for k in ["baseline", "fixed_sample", "any_signal", "two_plus", "tp_weighted"]:
        rows.append([
            k,
            f"{s[k]['detection_rate_mean']:.3f}",
            f"{s[k]['audit_rate_mean']:.3f}",
            f"{s[k]['fp_rate_mean']:.3f}",
        ])
    print_table(rows, ["Strategy", "Detection", "Audit Rate", "FP on Real"])
    all_results.append(("medium", s))

    # Sweep 2: Vary signal quality
    print("SWEEP 2: Vary signal quality")
    print("-" * 72)
    rows = []
    for sq in ["low", "medium", "high"]:
        s = run_experiment(SIGNAL_QUALITY[sq])
        for k in ["fixed_sample", "any_signal", "two_plus", "tp_weighted"]:
            rows.append([
                f"{sq}/{k}",
                f"{s[k]['detection_rate_mean']:.3f}",
                f"{s[k]['audit_rate_mean']:.3f}",
                f"{s[k]['fp_rate_mean']:.3f}",
            ])
        all_results.append((sq, s))
    print_table(rows, ["Config", "Detection", "Audit Rate", "FP on Real"])

    # Sweep 3: Individual signal contribution
    print("SWEEP 3: Drop one signal at a time — which signal carries the most weight?")
    print("-" * 72)
    baseline_full = run_experiment(SIGNAL_MEDIUM)
    rows = []
    for drop_idx, drop_name in enumerate([sc.name for sc in SIGNAL_MEDIUM]):
        reduced = [sc for i, sc in enumerate(SIGNAL_MEDIUM) if i != drop_idx]
        s = run_experiment(reduced)
        delta = baseline_full["any_signal"]["detection_rate_mean"] - s["any_signal"]["detection_rate_mean"]
        rows.append([
            drop_name,
            f"{s['any_signal']['detection_rate_mean']:.3f}",
            f"{delta:+.3f}",
            f"{s['any_signal']['fp_rate_mean']:.3f}",
        ])
    print_table(rows, ["Dropped Signal", "Any-Signal Detection (w/o)", "Δ from full", "FP on Real"])

    # Sweep 4: Vary execution rate
    print("SWEEP 4: Vary execution rate (skipped fraction changes)")
    print("-" * 72)
    saved_exec_rate = EXEC_RATE
    rows = []
    for er in [0.50, 0.70, 0.90]:
        EXEC_RATE = er
        s = run_experiment(SIGNAL_MEDIUM)
        rows.append([
            f"{er:.0%}",
            f"{1-er:.0%}",
            f"{s['any_signal']['detection_rate_mean']:.3f}",
            f"{s['two_plus']['detection_rate_mean']:.3f}",
            f"{s['tp_weighted']['detection_rate_mean']:.3f}",
        ])
        all_results.append((f"exec_{er}", s))
    EXEC_RATE = saved_exec_rate
    print_table(rows, ["Exec Rate", "Skip Rate", "Any-Sig Det", "2+-Sig Det", "TP-Weight Det"])

    # ─── Claims check ─────────────────────────────────────────────────────
    print("=" * 72)
    print("CLAIMS CHECK")
    print("=" * 72)

    ref = next(r for r in all_results if r[0] == "medium")[1]
    print(f"\nBaseline config: medium signals, exec_rate=70% (skip_rate=30%)")
    print(f"  Strategy A (baseline trust):     detection = {ref['baseline']['detection_rate_mean']:.1%}")
    print(f"  Strategy B (10% random sample):  detection = {ref['fixed_sample']['detection_rate_mean']:.1%}, FP = {ref['fixed_sample']['fp_rate_mean']:.1%}")
    print(f"  Strategy C (any signal):         detection = {ref['any_signal']['detection_rate_mean']:.1%}, FP = {ref['any_signal']['fp_rate_mean']:.1%}")
    print(f"  Strategy D (2+ signals):         detection = {ref['two_plus']['detection_rate_mean']:.1%}, FP = {ref['two_plus']['fp_rate_mean']:.1%}")
    print(f"  Strategy E (TP-weighted):        detection = {ref['tp_weighted']['detection_rate_mean']:.1%}, FP = {ref['tp_weighted']['fp_rate_mean']:.1%}")

    # Claim 1: any non-baseline ≥30% detection
    c1_det = max(
        ref['fixed_sample']['detection_rate_mean'],
        ref['any_signal']['detection_rate_mean'],
        ref['two_plus']['detection_rate_mean'],
        ref['tp_weighted']['detection_rate_mean'],
    )
    c1_fp = min(
        ref['any_signal']['fp_rate_mean'],
        ref['two_plus']['fp_rate_mean'],
        ref['tp_weighted']['fp_rate_mean'],
    )
    print(f"\nClaim 1 (any signal strategy ≥30% detection): {'PASS' if c1_det >= 0.30 else 'FAIL'} ({c1_det:.1%})")
    print(f"Claim 2 (independent-signal strategies FP <15%): {'PASS' if c1_fp < 0.15 else 'FAIL'} ({c1_fp:.1%})")

    # ─── Write results ─────────────────────────────────────────────────────
    out = {
        "parameters": {
            "stream_length": STREAM_LENGTH,
            "trials": TRIALS,
            "execution_rate_default": 0.70,
            "signal_quality_configs": {
                q: [{"name": sc.name, "tp": sc.tp, "fp": sc.fp, "falsifiability": sc.falsifiability}
                    for sc in scs]
                for q, scs in SIGNAL_QUALITY.items()
            },
        },
        "claim1_detection_threshold": {"threshold": 0.30, "result": c1_det, "pass": c1_det >= 0.30},
        "claim2_fp_threshold": {"threshold": 0.15, "result": c1_fp, "pass": c1_fp < 0.15},
        "results": [],
    }

    for tag, summary in all_results:
        for strategy, metrics in summary.items():
            out["results"].append({
                "config": tag, "strategy": strategy,
                "detection_rate": round(metrics["detection_rate_mean"], 4),
                "audit_rate": round(metrics["audit_rate_mean"], 4),
                "fp_rate": round(metrics["fp_rate_mean"], 4),
            })

    out_path = Path(__file__).parent / "results-v2" / "pre-execution-verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
