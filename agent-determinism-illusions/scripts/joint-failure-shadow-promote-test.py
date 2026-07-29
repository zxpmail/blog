# -*- coding: utf-8 -*-
"""Shadow-promote ladder for Interrupt-τ — Mike (soft-couple parent mismatch).

Claim under test (Mike, after forensic-τ vs interrupt-τ):
    Picking τ from the live-catch column in a coupled-uniform sim is the
    right *epistemic* cut, but promoting that τ straight to a live interrupt
    trusts the coupled-uniform parent at the moment it matters most. Honest
    sequence: sim → shadow-only on a production-like parent → promote only
    once shadow live-catch matches the sim prediction. Part 15 showed a
    related parent (temporal) does not survive holdout; this script asks
    whether the *monitor's* live-catch number itself collapses under a
    weakened common-cause parent.

Method:
    Same monitor as joint-failure-monitor-duration-test.py (W=200, K=3,
    excess=ĵ−ĉ·p̂). Single outage of length L starting at t0.

    Soft-couple parent: during the outage window, each step forces both-fail
    with probability ρ; otherwise draws the independent baseline (p_c, p_p).
    ρ=1.0 recovers the coupled-uniform parent used to pick Interrupt-τ.

    Ladder:
      1. Calibrate on ρ=1.0 → predicted_live = live_catch_rate(τ, L, ρ=1)
      2. Shadow-eval same (τ, L) across ρ ∈ RHO_GRID
      3. promote_ok iff (predicted_live − realized_live) ≤ PROMOTE_EPS

Primary cell (Interrupt candidate from duration grid):
    τ=0.05, L=20 — under ρ=1 live≈100% in the duration dump.

Also reports τ=0.03 at L=20 (forensic column contrast: any-alert vs live).

Falsifiers:
    - If realized_live stays ≈ predicted across all ρ → soft-couple does not
      stress interrupt claims on this fixture (report; do not claim the ladder
      is load-bearing here).
    - If ρ=1 fails promote_ok → calibration bug.
    - Expected SUPPORT: ρ=1 promote_ok; as ρ drops, live collapses and
      promote_ok flips false — Sim→Interrupt would have overclaimed.

Dependencies: none (pure Python).
Run:
    python scripts/joint-failure-shadow-promote-test.py
    python scripts/joint-failure-shadow-promote-test.py --trials 100
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
T0 = 1000
DEFAULT_TRIALS = 100
PROMOTE_EPS = 0.10  # absolute live-catch gap allowed for promote_ok
RHO_GRID = [1.0, 0.8, 0.6, 0.4, 0.2]
# Interrupt candidate from duration grid; forensic contrast on same L
CELLS = [
    {"role": "interrupt", "tau": 0.05, "L": 20},
    {"role": "forensic", "tau": 0.03, "L": 20},
]


def gen_stream(
    t: int,
    p_c: float,
    p_p: float,
    onset: int,
    length: int,
    rho: float,
) -> list[tuple[bool, bool]]:
    end = onset + length
    pairs: list[tuple[bool, bool]] = []
    for i in range(t):
        if onset <= i < end:
            if random.random() < rho:
                pairs.append((True, True))
            else:
                pairs.append((random.random() < p_c, random.random() < p_p))
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
    tau: float, length: int, rho: float, trials: int, seed: int
) -> dict:
    live = 0
    late = 0
    miss = 0
    early = 0
    delays_live: list[int] = []

    for trial in range(trials):
        random.seed(
            seed
            + trial * 1009
            + int(tau * 1000)
            + length * 17
            + int(rho * 10000)
        )
        pairs = gen_stream(T, P_C, P_P, T0, length, rho)
        alert = first_alert_t(pairs, W, tau, K)
        outage_end = T0 + length
        if alert is None:
            miss += 1
            continue
        if alert < T0:
            early += 1
            continue
        if alert < outage_end:
            live += 1
            delays_live.append(alert - T0)
        else:
            late += 1

    n = trials
    return {
        "tau": tau,
        "outage_length": length,
        "rho": rho,
        "trials": trials,
        "live_catch_rate": live / n,
        "late_only_rate": late / n,
        "miss_rate": miss / n,
        "early_false_rate": early / n,
        "any_alert_rate": (live + late) / n,
        "mean_delay_live": (
            sum(delays_live) / len(delays_live) if delays_live else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument(
        "--promote-eps",
        type=float,
        default=PROMOTE_EPS,
        help="max (predicted − realized) live-catch for promote_ok",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("Joint-failure shadow-promote ladder (Mike soft-couple)")
    print(f"T={T}, W={W}, K={K}, t0={T0}, trials={args.trials}")
    print(f"rho={RHO_GRID}, promote_eps={args.promote_eps}")
    print("=" * 72)

    ladders: list[dict] = []
    for spec in CELLS:
        role = spec["role"]
        tau = float(spec["tau"])
        length = int(spec["L"])
        print(f"\n{'─' * 72}\nrole={role}  τ={tau}  L={length}")
        print(
            f"{'rho':>5}  {'live':>6}  {'late':>6}  {'miss':>6}  "
            f"{'any':>6}  {'gap':>6}  {'promote':>8}"
        )

        predicted = None
        shadow_rows: list[dict] = []
        for rho in RHO_GRID:
            cell = run_cell(tau, length, rho, args.trials, args.seed)
            if rho == 1.0:
                predicted = cell["live_catch_rate"]
            assert predicted is not None
            gap = predicted - cell["live_catch_rate"]
            promote_ok = gap <= args.promote_eps
            row = {
                **cell,
                "predicted_live": predicted,
                "gap_vs_predicted": gap,
                "promote_ok": promote_ok,
            }
            shadow_rows.append(row)
            print(
                f"{rho:5.1f}  {cell['live_catch_rate']:6.3f}  "
                f"{cell['late_only_rate']:6.3f}  {cell['miss_rate']:6.3f}  "
                f"{cell['any_alert_rate']:6.3f}  {gap:6.3f}  "
                f"{'YES' if promote_ok else 'NO':>8}",
                flush=True,
            )

        # First ρ<1 that refuses promote (None if all pass)
        refuse_at = next(
            (r["rho"] for r in shadow_rows if r["rho"] < 1.0 and not r["promote_ok"]),
            None,
        )
        ladders.append(
            {
                "role": role,
                "tau": tau,
                "L": length,
                "predicted_live_rho1": predicted,
                "promote_eps": args.promote_eps,
                "first_refuse_rho": refuse_at,
                "shadow": shadow_rows,
            }
        )

    interrupt = next(x for x in ladders if x["role"] == "interrupt")
    forensic = next(x for x in ladders if x["role"] == "forensic")

    interpretation = [
        "Calibrate Interrupt-τ on coupled-uniform (ρ=1); shadow-eval under "
        "soft-couple ρ<1. promote_ok iff predicted_live − realized ≤ eps.",
        (
            f"Interrupt τ={interrupt['tau']} L={interrupt['L']}: "
            f"predicted_live={interrupt['predicted_live_rho1']:.3f}; "
            f"first_refuse_rho={interrupt['first_refuse_rho']}."
        ),
        (
            f"Forensic contrast τ={forensic['tau']} L={forensic['L']}: "
            f"predicted_live={forensic['predicted_live_rho1']:.3f}; "
            f"first_refuse_rho={forensic['first_refuse_rho']} "
            "(any-alert may stay high longer than live — residue ≠ interrupt)."
        ),
    ]
    if interrupt["first_refuse_rho"] is not None:
        interpretation.append(
            "SUPPORT Mike's ladder: soft-couple drops live-catch below the "
            "sim prediction; Sim→Interrupt would overclaim interrupt capability "
            "that shadow correctly refuses to promote."
        )
    else:
        interpretation.append(
            "WEAK on this grid: live-catch stayed within eps across all ρ — "
            "soft-couple did not open a promote gap here."
        )

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "joint-failure-shadow-promote",
        "claim": (
            "Sim→Interrupt overclaims when production coupling ρ<1; "
            "shadow live-catch vs sim prediction is the promote gate"
        ),
        "parent": (
            "soft-couple extension of joint-failure-monitor-duration-test.py; "
            "ρ=1 recovers coupled-uniform"
        ),
        "params": {
            "T": T,
            "W": W,
            "K": K,
            "p_c": P_C,
            "p_p": P_P,
            "outage_onset": T0,
            "rho_grid": RHO_GRID,
            "promote_eps": args.promote_eps,
            "trials": args.trials,
            "seed": args.seed,
            "cells": CELLS,
        },
        "definitions": {
            "rho": (
                "P(force both-fail) each step inside the outage window; "
                "else independent baseline"
            ),
            "predicted_live": "live_catch_rate at ρ=1.0 (calibrate / sim)",
            "promote_ok": "predicted_live − realized_live ≤ promote_eps",
            "live_catch": "first alert while outage still active",
            "late_only": "first alert only after outage ended",
        },
        "ladders": ladders,
        "interpretation": interpretation,
    }
    out_path = (
        Path(__file__).parent / "results-v2" / "joint-failure-shadow-promote.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
