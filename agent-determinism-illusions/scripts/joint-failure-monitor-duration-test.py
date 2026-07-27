# -*- coding: utf-8 -*-
"""Joint-failure monitor vs outage lifespan — Mike (accuracy–latency dial).

Claim under test (Mike, after τ=0.03 vs 0.05 result):
    On this sim, raising τ improves FAR *and* detection together; the real
    cost is latency (delay 9 → 15). The dial is accuracy-versus-latency, not
    accuracy-versus-noise. Operational question: is that delay short enough
    relative to how long a sensor outage runs? If the outage ends before the
    alert crosses threshold, the monitor can stay silent (or fire only after
    the failure is already gone) — useless not because wrong, but too slow
    for that failure's lifespan.

Method:
    Same monitor as joint-failure-monitor-test.py (W=200, K=3, excess=ĵ−ĉ·p̂).
    Single common-cause outage of length L starting at t0; sweep L and τ∈{0.03,0.05}.
    Classify each trial:
      live_catch   — first alert while outage still active
      late_only    — first alert only after outage ended (residue still in W)
      miss         — no alert

Primary metrics per (τ, L):
    live_catch_rate, late_only_rate, miss_rate, mean_delay | live_catch
    L*_90 / L*_50 — shortest L with live_catch_rate ≥ 0.90 / 0.50

Falsifiers / interpretation:
    - If live_catch stays high even for L ≪ reported delay → window residue
      rescues short outages (report that; delay≠required lifespan).
    - If live_catch collapses for L below ~delay → Mike's cut confirmed:
      monitor stops being useful when outage lifespan < detection runway.

Dependencies: none (pure Python).
Run:
    python scripts/joint-failure-monitor-duration-test.py
    python scripts/joint-failure-monitor-duration-test.py --trials 100
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

T = 3000
W = 200
K = 3
P_C = 0.12
P_P = 0.10
T0 = 1000  # outage onset
DEFAULT_TRIALS = 100
TAUS = [0.03, 0.05]
# Span below, near, and above the published delays (~9 / ~15)
OUTAGE_LENGTHS = [3, 5, 8, 9, 10, 12, 15, 20, 30, 50, 75, 100, 150, 200, 250]


def gen_stream(
    t: int,
    p_c: float,
    p_p: float,
    onset: int,
    length: int,
) -> list[tuple[bool, bool]]:
    end = onset + length
    pairs = []
    for i in range(t):
        if onset <= i < end:
            pairs.append((True, True))
        else:
            pairs.append((random.random() < p_c, random.random() < p_p))
    return pairs


def first_alert_t(
    pairs: list[tuple[bool, bool]], w: int, tau: float, k: int
) -> int | None:
    n = len(pairs)
    both_ps = [0]
    c_ps = [0]
    p_ps = [0]
    for c, p in pairs:
        both_ps.append(both_ps[-1] + (1 if c and p else 0))
        c_ps.append(c_ps[-1] + (1 if c else 0))
        p_ps.append(p_ps[-1] + (1 if p else 0))
    streak = 0
    for end in range(w, n + 1):
        start = end - w
        both = (both_ps[end] - both_ps[start]) / w
        c_rate = (c_ps[end] - c_ps[start]) / w
        p_rate = (p_ps[end] - p_ps[start]) / w
        excess = both - c_rate * p_rate
        if excess >= tau:
            streak += 1
        else:
            streak = 0
        if streak >= k:
            return end - 1
    return None


def run_cell(
    tau: float, length: int, trials: int, seed: int
) -> dict:
    live = 0
    late = 0
    miss = 0
    early = 0
    delays_live: list[int] = []
    delays_any: list[int] = []

    for trial in range(trials):
        random.seed(seed + trial * 1009 + int(tau * 1000) + length * 17)
        pairs = gen_stream(T, P_C, P_P, T0, length)
        alert = first_alert_t(pairs, W, tau, K)
        outage_end = T0 + length
        if alert is None:
            miss += 1
            continue
        if alert < T0:
            early += 1
            continue
        delay = alert - T0
        delays_any.append(delay)
        if alert < outage_end:
            live += 1
            delays_live.append(delay)
        else:
            late += 1

    n = trials
    return {
        "tau": tau,
        "outage_length": length,
        "trials": trials,
        "live_catch_rate": live / n,
        "late_only_rate": late / n,
        "miss_rate": miss / n,
        "early_false_rate": early / n,
        "mean_delay_live": (
            sum(delays_live) / len(delays_live) if delays_live else None
        ),
        "mean_delay_any": (
            sum(delays_any) / len(delays_any) if delays_any else None
        ),
        "any_alert_rate": (live + late) / n,
    }


def shortest_L(cells: list[dict], key: str, threshold: float) -> int | None:
    for c in sorted(cells, key=lambda x: x["outage_length"]):
        if c[key] >= threshold:
            return c["outage_length"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()

    print("=" * 72)
    print("Joint-failure monitor vs outage lifespan (Mike accuracy–latency)")
    print(f"T={T}, W={W}, K={K}, t0={T0}, trials={args.trials}")
    print(f"taus={TAUS}, L={OUTAGE_LENGTHS}")
    print("=" * 72)

    by_tau: dict[float, list[dict]] = {}
    for tau in TAUS:
        print(f"\n{'─' * 72}\nτ={tau}")
        print(
            f"{'L':>5}  {'live':>6}  {'late':>6}  {'miss':>6}  "
            f"{'any':>6}  {'delay_live':>10}"
        )
        cells = []
        for L in OUTAGE_LENGTHS:
            cell = run_cell(tau, L, args.trials, args.seed)
            cells.append(cell)
            dl = cell["mean_delay_live"]
            print(
                f"{L:5d}  {cell['live_catch_rate']:6.3f}  "
                f"{cell['late_only_rate']:6.3f}  {cell['miss_rate']:6.3f}  "
                f"{cell['any_alert_rate']:6.3f}  "
                f"{(f'{dl:.2f}' if dl is not None else '—'):>10}",
                flush=True,
            )
        by_tau[tau] = cells

    summary = {}
    for tau, cells in by_tau.items():
        summary[str(tau)] = {
            "L_star_live_90": shortest_L(cells, "live_catch_rate", 0.90),
            "L_star_live_50": shortest_L(cells, "live_catch_rate", 0.50),
            "L_star_any_90": shortest_L(cells, "any_alert_rate", 0.90),
            "L_star_any_50": shortest_L(cells, "any_alert_rate", 0.50),
        }

    interpretation = [
        "Dial confirmation: on the long-outage parent sim, τ trades delay "
        "not FAR. This sweep asks when delay exceeds outage lifespan.",
    ]
    for tau_s, s in summary.items():
        interpretation.append(
            f"τ={tau_s}: live_catch ≥90% needs L≥{s['L_star_live_90']}; "
            f"≥50% needs L≥{s['L_star_live_50']}. "
            f"Any-alert (incl. late residue in W) ≥90% at L≥{s['L_star_any_90']}."
        )
    # Compare to published delays
    interpretation.append(
        "If L*_live ≈ published mean delay (≈9 at τ=0.03, ≈15 at τ=0.05), "
        "Mike's cut holds: short-lived outages finish before a live alert. "
        "If L*_any ≪ L*_live, window residue still 'hears' the outage after "
        "it ends — useful for forensics, not for interrupting a live failure."
    )

    print("\n" + "=" * 72)
    print("SUMMARY")
    print(json.dumps(summary, indent=2))
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "joint-failure-monitor-duration",
        "claim": (
            "Monitor usefulness vs outage lifespan: live catch collapses when "
            "L is shorter than detection runway (accuracy–latency dial)"
        ),
        "parent": "joint-failure-monitor-test.py (τ=0.03 delay~9, τ=0.05 delay~15)",
        "params": {
            "T": T,
            "W": W,
            "K": K,
            "p_c": P_C,
            "p_p": P_P,
            "outage_onset": T0,
            "taus": TAUS,
            "outage_lengths": OUTAGE_LENGTHS,
            "trials": args.trials,
            "seed": args.seed,
        },
        "definitions": {
            "live_catch": "first alert while outage still active",
            "late_only": "first alert only after outage ended (W still holds residue)",
            "miss": "no alert",
        },
        "by_tau": {str(k): v for k, v in by_tau.items()},
        "summary": summary,
        "interpretation": interpretation,
    }
    out_path = (
        Path(__file__).parent / "results-v2" / "joint-failure-monitor-duration.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
