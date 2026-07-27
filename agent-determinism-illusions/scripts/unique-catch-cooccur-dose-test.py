# -*- coding: utf-8 -*-
"""Co-occurrence-label dose-response — critical π that flips middle unique-CR.

Claim under test (after unique-catch-cooccur-labels):
    Under the label→signature generative model, mike_half (π_route_cd=0.5)
    flipped barely vs route by a tiny margin. That leaves the actionable
    question open: *how much* co-occurrence-label mass on Mike's named class
    is enough to unlock the middle? Also: do other single-class doses
    (barely_route, cd_barely) flip at all, and at what π?

Method:
    Same unique-catch + label generative model as
    unique-catch-cooccur-labels-test.py (p_sig=0.90, burst/medium).

    For each attacking label L ∈ {route_cd, barely_route, cd_barely}:
      sweep π_L ∈ {0.00, 0.05, …, 1.00}, remainder = independent.
      Record unique rates, middle order, extremes.

    Critical mass π* = smallest π where middle_order ≠ independent baseline
    (barely > route), requiring the flip to hold at the next step too
    (anti-flicker). If never flips, π* = null.

Falsifiers / interpretation:
    - If π*(route_cd) is small (≲0.3) → middle prune is fragile under
      modest Mike-class mass; do not lock middle on independence sweeps.
    - If π*(route_cd) is large (≳0.7) or null → middle is robust except
      under extreme label concentration.
    - If barely_route / cd_barely never flip → only Mike's named pairing
      (route with CD) is the load-bearing middle unlock on this fixture.

Dependencies: none (pure Python).
Run:
    python scripts/unique-catch-cooccur-dose-test.py
    python scripts/unique-catch-cooccur-dose-test.py --trials 200 --step 0.1
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

STREAM_LENGTH = 1500
DEFAULT_TRIALS = 400
ERROR_RATE = 0.10
ERROR_DIST = "burst"
ALEX_BASELINE = 0.10
ALEX_ESCALATION = 0.30
P_SIG = 0.90

ATTACK_LABELS = ("route_cd", "barely_route", "cd_barely")


@dataclass
class SignalConfig:
    name: str
    tp: float
    fp: float


SIGNAL_MEDIUM = [
    SignalConfig("route_changed", 0.25, 0.05),
    SignalConfig("classifier_disagree", 0.50, 0.12),
    SignalConfig("input_unusual", 0.20, 0.04),
    SignalConfig("barely_passed", 0.35, 0.08),
]
SIGNAL_NAMES = [sc.name for sc in SIGNAL_MEDIUM]

SIGNATURES: dict[str, frozenset[str]] = {
    "independent": frozenset(),
    "route_cd": frozenset({"route_changed", "classifier_disagree"}),
    "barely_route": frozenset({"barely_passed", "route_changed"}),
    "cd_barely": frozenset({"classifier_disagree", "barely_passed"}),
}


def generate_stream(error_rate: float, error_dist: str) -> list[bool]:
    outputs: list[bool] = []
    burst_remaining = 0
    for _ in range(STREAM_LENGTH):
        if error_dist == "burst":
            if burst_remaining > 0:
                defective = random.random() < min(1.0, error_rate * 4)
                burst_remaining -= 1
            else:
                defective = random.random() < error_rate
                if defective:
                    burst_remaining = random.randint(1, 4)
        else:
            defective = random.random() < error_rate
        outputs.append(defective)
    return outputs


def draw_label(pi_attack: float, attack: str) -> str:
    if random.random() < pi_attack:
        return attack
    return "independent"


def generate_labeled(
    gts: list[bool],
    configs: list[SignalConfig],
    pi_attack: float,
    attack: str,
) -> list[dict]:
    results = []
    for gt in gts:
        if not gt:
            sigs = [1 if random.random() < sc.fp else 0 for sc in configs]
            results.append({"defective": False, "signals": sigs})
            continue
        label = draw_label(pi_attack, attack)
        sig_set = SIGNATURES[label]
        sigs = []
        for sc in configs:
            p = P_SIG if sc.name in sig_set else sc.tp
            sigs.append(1 if random.random() < p else 0)
        results.append({"defective": True, "signals": sigs, "label": label})
    return results


def unique_catch_stats(outputs: list[dict], configs: list[SignalConfig]) -> dict:
    n = len(configs)
    unique_catch = [0] * n
    solo_catch = [0] * n
    total_defective = 0
    for o in outputs:
        if not o["defective"]:
            continue
        total_defective += 1
        sigs = o["signals"]
        u = random.random()
        caught = []
        for i, s in enumerate(sigs):
            rate = min(1.0, ALEX_BASELINE + s * ALEX_ESCALATION)
            c = u < rate
            caught.append(c)
            if c:
                solo_catch[i] += 1
        for i in range(n):
            if caught[i] and not any(caught[j] for j in range(n) if j != i):
                unique_catch[i] += 1
    return {
        "total_defective": total_defective,
        "unique_catch": unique_catch,
        "solo_catch": solo_catch,
    }


def run_cell(
    attack: str, pi: float, trials: int, seed: int
) -> dict:
    configs = SIGNAL_MEDIUM
    names = SIGNAL_NAMES
    n = len(configs)
    unique_tot = [0] * n
    solo_tot = [0] * n
    def_tot = 0
    for t in range(trials):
        random.seed(
            seed
            + t * 10007
            + int(pi * 10000)
            + sum(ord(c) for c in attack) * 19
        )
        gts = generate_stream(ERROR_RATE, ERROR_DIST)
        outs = generate_labeled(gts, configs, pi, attack)
        stats = unique_catch_stats(outs, configs)
        def_tot += stats["total_defective"]
        for i in range(n):
            unique_tot[i] += stats["unique_catch"][i]
            solo_tot[i] += stats["solo_catch"][i]

    by_signal = {}
    for i, name in enumerate(names):
        solo = solo_tot[i] / def_tot if def_tot else 0.0
        uniq = unique_tot[i] / def_tot if def_tot else 0.0
        by_signal[name] = {
            "solo": round(solo, 6),
            "unique": round(uniq, 6),
        }

    ranked = sorted(names, key=lambda s: -by_signal[s]["unique"])
    barely_u = by_signal["barely_passed"]["unique"]
    route_u = by_signal["route_changed"]["unique"]
    if barely_u > route_u:
        middle = "barely_passed > route_changed"
    elif route_u > barely_u:
        middle = "route_changed > barely_passed"
    else:
        middle = "barely_passed == route_changed"

    return {
        "attack_label": attack,
        "pi": round(pi, 4),
        "total_defective": def_tot,
        "unique_rank": ranked,
        "middle_pair_order": middle,
        "middle_flipped": middle != "barely_passed > route_changed",
        "extremes_hold": (
            ranked[0] == "classifier_disagree"
            and ranked[-1] == "input_unusual"
        ),
        "route_unique": by_signal["route_changed"]["unique"],
        "barely_unique": by_signal["barely_passed"]["unique"],
        "cd_unique": by_signal["classifier_disagree"]["unique"],
        "input_unique": by_signal["input_unusual"]["unique"],
        "delta_barely_minus_route": round(barely_u - route_u, 6),
        "by_signal": by_signal,
    }


def find_critical_pi(cells: list[dict]) -> float | None:
    """Smallest π where flip holds for this step and the next (anti-flicker)."""
    for i, c in enumerate(cells):
        if not c["middle_flipped"]:
            continue
        if i + 1 < len(cells) and cells[i + 1]["middle_flipped"]:
            return c["pi"]
        if i == len(cells) - 1:
            return c["pi"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--step", type=float, default=0.05)
    args = parser.parse_args()

    pis = []
    x = 0.0
    while x <= 1.0001:
        pis.append(round(x, 4))
        x += args.step

    print("=" * 72)
    print("Co-occurrence-label dose-response (critical π for middle flip)")
    print(
        f"dist={ERROR_DIST}, p_sig={P_SIG}, trials/cell={args.trials}, "
        f"step={args.step}"
    )
    print(f"attacks: {ATTACK_LABELS}")
    print("=" * 72)

    by_attack = {}
    for attack in ATTACK_LABELS:
        print(f"\n{'─' * 72}\nATTACK LABEL: {attack}")
        print(
            f"{'π':>6}  {'Δ(b−r)':>10}  {'middle':<32}  "
            f"{'ext':>3}  rank"
        )
        cells = []
        for pi in pis:
            cell = run_cell(attack, pi, args.trials, args.seed)
            cells.append(cell)
            flag = "FLIP" if cell["middle_flipped"] else "ok"
            print(
                f"{pi:6.2f}  {cell['delta_barely_minus_route']:+10.5f}  "
                f"{flag:<4} {cell['middle_pair_order']:<27}  "
                f"{'Y' if cell['extremes_hold'] else 'N':>3}  "
                f"{' > '.join(cell['unique_rank'])}"
            )
        pi_star = find_critical_pi(cells)
        extremes_always = all(c["extremes_hold"] for c in cells)
        by_attack[attack] = {
            "pi_star_middle_flip": pi_star,
            "extremes_always_hold": extremes_always,
            "cells": cells,
        }
        print(
            f"  → π* (middle flip, anti-flicker) = {pi_star}  "
            f"extremes_always={extremes_always}"
        )

    interpretation = []
    rc = by_attack["route_cd"]["pi_star_middle_flip"]
    br = by_attack["barely_route"]["pi_star_middle_flip"]
    cb = by_attack["cd_barely"]["pi_star_middle_flip"]
    if rc is None:
        interpretation.append(
            "route_cd never stably flips middle on this grid — middle "
            "robust to Mike-class concentration up to π=1."
        )
    elif rc <= 0.30:
        interpretation.append(
            f"route_cd π*={rc}: middle fragile — modest Mike-class mass "
            f"unlocks barely↔route. Do not lock middle on independence sweeps."
        )
    elif rc <= 0.60:
        interpretation.append(
            f"route_cd π*={rc}: middle unlocks at moderate Mike-class mass "
            f"(around half is enough; matches mike_half). Middle not locked; "
            f"needs real π estimate before prune."
        )
    else:
        interpretation.append(
            f"route_cd π*={rc}: middle only flips under heavy Mike-class "
            f"concentration. Moderately robust, still not a hard lock."
        )
    interpretation.append(
        f"barely_route π*={br}; cd_barely π*={cb} "
        f"(null = that single-class dose never flips middle)."
    )
    if all(by_attack[a]["extremes_always_hold"] for a in ATTACK_LABELS):
        interpretation.append(
            "Extremes (CD top / input bottom) held across all doses — "
            "ends look structural; middle does not."
        )

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "unique-catch-cooccur-dose",
        "claim": (
            "Critical co-occurrence-label mass π* on a single defect class "
            "that flips unique-CR middle (barely vs route)"
        ),
        "p_sig": P_SIG,
        "error_dist": ERROR_DIST,
        "signal_quality": "medium",
        "trials_per_cell": args.trials,
        "seed": args.seed,
        "step": args.step,
        "pi_grid": pis,
        "attack_labels": list(ATTACK_LABELS),
        "by_attack": by_attack,
        "interpretation": interpretation,
    }
    out_path = (
        Path(__file__).parent / "results-v2" / "unique-catch-cooccur-dose.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
