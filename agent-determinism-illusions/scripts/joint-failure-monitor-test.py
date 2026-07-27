# -*- coding: utf-8 -*-
"""Joint-failure monitor — Mike Czerwinski (causal independence is post-hoc).

Claim under test (Mike, Part 6/7 checksum thread, after structural≠causal):
    Structural independence is checkable in advance; causal independence usually
    only shows up after the fact, when claim and probe fail together. The
    practical fix is not a stronger definition of independence — it is a
    *monitor*: track the joint failure rate of claim and probe over time, and
    treat a correlated-failure spike as its own alert. You cannot certify
    causal independence up front. You can notice when it turns out you didn't
    have it.

Method (offline sim, no API):
    Stream of T binary pairs (claim_fail, probe_fail).

    Generative regimes:
      independent — each fails i.i.d. at p_c, p_p (causal independence holds).
      common_cause — same baseline, plus scheduled outage windows where BOTH
                     are forced to fail (shared upstream; checksum still
                     "structurally" writable — we never grade agreement).

    Monitor (deployable, no oracle of the outage schedule):
      rolling window W: ĵ = rate(both fail), ĉ = rate(claim fail),
                        p̂ = rate(probe fail), ĵ_indep = ĉ·p̂
      excess = ĵ − ĵ_indep
      alert when excess ≥ τ for K consecutive windows

Primary metrics:
    - under independent: false-alert rate (windows / episodes)
    - under common_cause: detection delay (steps after first outage onset
      until first alert), whether every outage episode is eventually flagged
    - excess time series summary (mean/max in/out of outage)

Falsifiers:
    - If common_cause never alerts at a τ that keeps independent FAR low
      → monitor claim WEAK on this fixture.
    - If independent FAR is high at any τ that catches outages → useless
      as an ops alert (report the ROC-ish tradeoff; do not claim a free lunch).

Dependencies: none (pure Python).
Run:
    python scripts/joint-failure-monitor-test.py
    python scripts/joint-failure-monitor-test.py --trials 50
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

T = 5000
W = 200
K = 3
P_C = 0.12
P_P = 0.10
DEFAULT_TRIALS = 100
# Outage episodes: (start, length) within [0, T)
OUTAGE_EPISODES = [(1200, 250), (3200, 300)]
# Threshold sweep for tradeoff table
TAUS = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10]


def gen_stream(
    t: int,
    p_c: float,
    p_p: float,
    outages: list[tuple[int, int]] | None,
) -> list[tuple[bool, bool]]:
    outage_set: set[int] = set()
    if outages:
        for start, length in outages:
            for i in range(start, min(t, start + length)):
                outage_set.add(i)
    pairs = []
    for i in range(t):
        if i in outage_set:
            pairs.append((True, True))
        else:
            pairs.append((random.random() < p_c, random.random() < p_p))
    return pairs


def rolling_monitor(
    pairs: list[tuple[bool, bool]],
    w: int,
    tau: float,
    k: int,
    keep_sample: bool = False,
) -> dict:
    """O(T) rolling excess via prefix sums."""
    n = len(pairs)
    both_ps = [0]
    c_ps = [0]
    p_ps = [0]
    for c, p in pairs:
        both_ps.append(both_ps[-1] + (1 if c and p else 0))
        c_ps.append(c_ps[-1] + (1 if c else 0))
        p_ps.append(p_ps[-1] + (1 if p else 0))

    alert_windows = 0
    streak = 0
    first_alert_t = None
    max_excess = -1.0
    sum_excess = 0.0
    n_series = 0
    sample = []

    for end in range(w, n + 1):
        start = end - w
        both = (both_ps[end] - both_ps[start]) / w
        c_rate = (c_ps[end] - c_ps[start]) / w
        p_rate = (p_ps[end] - p_ps[start]) / w
        indep = c_rate * p_rate
        excess = both - indep
        n_series += 1
        sum_excess += excess
        if excess > max_excess:
            max_excess = excess
        if keep_sample and (n_series - 1) % 50 == 0:
            sample.append(
                {
                    "t_end": end - 1,
                    "joint": round(both, 6),
                    "indep_baseline": round(indep, 6),
                    "excess": round(excess, 6),
                }
            )
        if excess >= tau:
            streak += 1
        else:
            streak = 0
        if streak >= k:
            alert_windows += 1
            if first_alert_t is None:
                first_alert_t = end - 1

    return {
        "excess_series_len": n_series,
        "n_alert_windows": alert_windows,
        "first_alert_t": first_alert_t,
        "max_excess": max_excess if n_series else 0.0,
        "mean_excess": sum_excess / n_series if n_series else 0.0,
        "excess_sample": sample,
    }


def detection_delay(first_alert_t: int | None, outages: list[tuple[int, int]]) -> int | None:
    if first_alert_t is None or not outages:
        return None
    first_onset = min(s for s, _ in outages)
    if first_alert_t < first_onset:
        return None  # early false alert before first outage
    return first_alert_t - first_onset


def run_regime(
    name: str,
    outages: list[tuple[int, int]] | None,
    trials: int,
    seed: int,
    tau: float,
) -> dict:
    far_trials = 0  # trials with any alert under independent intent
    detected = 0
    delays: list[int] = []
    early_false = 0
    max_excesses: list[float] = []
    mean_excesses: list[float] = []

    for trial in range(trials):
        random.seed(seed + trial * 1009 + sum(ord(c) for c in name) * 17)
        pairs = gen_stream(T, P_C, P_P, outages)
        mon = rolling_monitor(pairs, W, tau, K, keep_sample=False)
        max_excesses.append(mon["max_excess"])
        mean_excesses.append(mon["mean_excess"])
        if mon["first_alert_t"] is not None:
            far_trials += 1
        if outages:
            d = detection_delay(mon["first_alert_t"], outages)
            if d is None and mon["first_alert_t"] is not None:
                early_false += 1
            if d is not None:
                detected += 1
                delays.append(d)
            elif mon["first_alert_t"] is None:
                pass  # miss
        # store one example series from last trial only at end

    result = {
        "regime": name,
        "tau": tau,
        "trials": trials,
        "alert_trial_rate": far_trials / trials if trials else 0.0,
        "mean_max_excess": sum(max_excesses) / trials if trials else 0.0,
        "mean_mean_excess": sum(mean_excesses) / trials if trials else 0.0,
    }
    if outages:
        result["outage_episodes"] = [
            {"start": s, "length": L} for s, L in outages
        ]
        result["detection_rate"] = detected / trials if trials else 0.0
        result["early_false_before_outage_rate"] = (
            early_false / trials if trials else 0.0
        )
        result["mean_detection_delay"] = (
            sum(delays) / len(delays) if delays else None
        )
        result["median_detection_delay"] = (
            sorted(delays)[len(delays) // 2] if delays else None
        )
    return result


def pick_operating_point(rows: list[dict]) -> dict:
    """Prefer high detection with independent alert_trial_rate ≤ 0.05."""
    feasible = [
        r
        for r in rows
        if r["independent"]["alert_trial_rate"] <= 0.05
        and r["common_cause"]["detection_rate"] >= 0.90
    ]
    if feasible:
        # minimize delay among feasible
        best = min(
            feasible,
            key=lambda r: (
                r["common_cause"]["mean_detection_delay"]
                if r["common_cause"]["mean_detection_delay"] is not None
                else 1e9
            ),
        )
        return {
            "rule": "FAR≤0.05 and detection≥0.90, then min mean delay",
            "tau": best["tau"],
            "independent_FAR": best["independent"]["alert_trial_rate"],
            "detection_rate": best["common_cause"]["detection_rate"],
            "mean_detection_delay": best["common_cause"]["mean_detection_delay"],
        }
    # else best detection among FAR≤0.10
    soft = [
        r for r in rows if r["independent"]["alert_trial_rate"] <= 0.10
    ]
    if soft:
        best = max(soft, key=lambda r: r["common_cause"]["detection_rate"])
        return {
            "rule": "FAR≤0.10, maximize detection (no point met 0.05/0.90)",
            "tau": best["tau"],
            "independent_FAR": best["independent"]["alert_trial_rate"],
            "detection_rate": best["common_cause"]["detection_rate"],
            "mean_detection_delay": best["common_cause"]["mean_detection_delay"],
        }
    best = max(rows, key=lambda r: r["common_cause"]["detection_rate"])
    return {
        "rule": "maximize detection (no low-FAR point)",
        "tau": best["tau"],
        "independent_FAR": best["independent"]["alert_trial_rate"],
        "detection_rate": best["common_cause"]["detection_rate"],
        "mean_detection_delay": best["common_cause"]["mean_detection_delay"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()

    print("=" * 72)
    print("Joint-failure monitor (Mike: notice when you didn't have causal independence)")
    print(f"T={T}, W={W}, K={K}, p_c={P_C}, p_p={P_P}, trials={args.trials}")
    print(f"outages={OUTAGE_EPISODES}")
    print("=" * 72)

    sweep = []
    for tau in TAUS:
        ind = run_regime("independent", None, args.trials, args.seed, tau)
        cc = run_regime(
            "common_cause", OUTAGE_EPISODES, args.trials, args.seed, tau
        )
        sweep.append({"tau": tau, "independent": ind, "common_cause": cc})
        print(
            f"τ={tau:.2f}  indep FAR={ind['alert_trial_rate']:.3f}  "
            f"cc detect={cc['detection_rate']:.3f}  "
            f"delay={cc['mean_detection_delay']}  "
            f"early_false={cc['early_false_before_outage_rate']:.3f}",
            flush=True,
        )

    op = pick_operating_point(sweep)
    print("\nOperating point:", op)

    # One illustrative series at chosen tau
    random.seed(args.seed)
    example_pairs = gen_stream(T, P_C, P_P, OUTAGE_EPISODES)
    example_mon = rolling_monitor(example_pairs, W, op["tau"], K, keep_sample=True)

    interpretation = []
    if (
        op.get("independent_FAR", 1) <= 0.05
        and op.get("detection_rate", 0) >= 0.90
    ):
        interpretation.append(
            f"SUPPORT: at τ={op['tau']}, independent FAR="
            f"{op['independent_FAR']:.3f} while common-cause detection="
            f"{op['detection_rate']:.3f} (mean delay "
            f"{op['mean_detection_delay']} steps after first outage onset). "
            "Joint-failure excess is an actionable post-hoc alert for lost "
            "causal independence — without requiring an upfront certificate."
        )
    else:
        interpretation.append(
            f"PARTIAL/WEAK on this grid: best point τ={op['tau']} under "
            f"rule '{op['rule']}' — FAR={op['independent_FAR']:.3f}, "
            f"detection={op['detection_rate']:.3f}. Tune W/K/τ before "
            "claiming ops-ready; the *shape* (spike under common cause) "
            "is still the point Mike named."
        )
    interpretation.append(
        "Checksum still only buys structural independence. This monitor "
        "does not create causal independence — it notices when joint "
        "failures exceed the ĉ·p̂ baseline."
    )

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "joint-failure-monitor",
        "claim": (
            "Rolling joint-failure excess (ĵ − ĉ·p̂) alerts on common-cause "
            "spikes that structural checksum cannot certify against upfront"
        ),
        "params": {
            "T": T,
            "W": W,
            "K": K,
            "p_c": P_C,
            "p_p": P_P,
            "outage_episodes": [
                {"start": s, "length": L} for s, L in OUTAGE_EPISODES
            ],
            "taus": TAUS,
            "trials": args.trials,
            "seed": args.seed,
        },
        "monitor_definition": (
            "excess = rate(claim∧probe fail) − rate(claim fail)·rate(probe fail) "
            f"over rolling W; alert if excess≥τ for K={K} consecutive windows"
        ),
        "sweep": sweep,
        "operating_point": op,
        "example_series_at_op_tau": {
            "first_alert_t": example_mon["first_alert_t"],
            "max_excess": example_mon["max_excess"],
            "excess_sample": example_mon["excess_sample"],
        },
        "interpretation": interpretation,
    }
    out_path = Path(__file__).parent / "results-v2" / "joint-failure-monitor.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
