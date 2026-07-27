# -*- coding: utf-8 -*-
"""Induced co-fire unique-catch reorder — Mike Czerwinski (drop-order caveat).

Claim under test (Mike, Part 6 thread, after 3×3 mix sweep):
    Unique-CR rank held identical across all nine (dist × quality) cells under
    *independent* signal fires. That leaves independence itself untested.
    Force route_changed and classifier_disagree to co-fire above baseline on
    the same injected defect class (not emergent from the error model). If
    barely_passed and route_changed still do not swap, the middle-pair order
    is stronger than nine independent cells agreeing. If they do swap, the
    prune order is not locked — only the extremes (CD top / input bottom).

Method:
    Same coupled-Uniform unique-catch definition as external-signal-sampling-
    test.run_unique_catch / unique-catch-mix-sweep:
      unique_catch_i = defective caught by solo arm i
                       (Alex: baseline + esc·signal_i, one Uniform draw)
                       AND not caught by any other solo arm.

    Fixture family (default = published burst / medium):
      - Independent baseline (ρ = 0): signals fire i.i.d. at SIGNAL_MEDIUM TP/FP.
      - Induced co-fire (ρ ∈ {0.2, 0.4, 0.6, 0.8}): after independent draw,
        for each *defective* output, with probability ρ force
        route_changed = 1 AND classifier_disagree = 1 (shared defect class,
        injected directly). Clean outputs untouched (co-fire is a defect-class
        mechanism, not a FP conspiracy).

    Also report pairwise co-fire rate among defectives so the induced
    correlation is observable, not assumed.

    --all-pairs: sweep every C(4,2)=6 forced pairs (same ρ grid). Answers
    whether *any* induced pair reorders unique-CR — especially barely∧route,
    the pair that attacks the middle directly.

Primary metrics per ρ (and per forced pair under --all-pairs):
    unique_rank, middle_pair_order (barely vs route), middle_swapped vs ρ=0,
    extremes_hold (CD first, input last), rank_changed vs independent.

Falsifiers / interpretation:
    - If middle_swapped at any ρ → drop-order middle is NOT structural under
      independence; treat prune as extremes-only until production trace.
    - If middle never swaps even at ρ=0.8 → stronger than nine-cell lock;
      independence was the remaining untested assumption and it held under
      deliberate attack.
    - Extremes flipping would be a larger surprise; report if it happens.
    - Under --all-pairs: if ANY pair flips middle or extremes, prune is not
      locked; report which pairs are load-bearing attacks.

Dependencies: none (pure Python).
Run:
    python scripts/unique-catch-cofire-test.py
    python scripts/unique-catch-cofire-test.py --trials 200
    python scripts/unique-catch-cofire-test.py --all-pairs
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

STREAM_LENGTH = 1500
DEFAULT_TRIALS = 400
ERROR_RATE = 0.10
ERROR_DIST = "burst"
ALEX_BASELINE = 0.10
ALEX_ESCALATION = 0.30

# Indices must match SIGNAL_MEDIUM order
IDX_ROUTE = 0
IDX_CD = 1
IDX_INPUT = 2
IDX_BARELY = 3


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
COFIRE_RHOS = [0.0, 0.2, 0.4, 0.6, 0.8]
# Mike-named attack first; --all-pairs adds the rest
DEFAULT_PAIR = ("route_changed", "classifier_disagree")
BASELINE_RANK = [
    "classifier_disagree",
    "barely_passed",
    "route_changed",
    "input_unusual",
]


def generate_stream(error_rate: float, error_dist: str) -> list[bool]:
    outputs: list[bool] = []
    burst_remaining = 0
    for _ in range(STREAM_LENGTH):
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


def generate_signals_independent(gts: list[bool], configs: list[SignalConfig]) -> list[dict]:
    results = []
    for gt in gts:
        sigs = []
        for sc in configs:
            p = sc.tp if gt else sc.fp
            sigs.append(1 if random.random() < p else 0)
        results.append({"defective": gt, "signals": sigs})
    return results


def inject_pair_cofire(
    outputs: list[dict], rho: float, i: int, j: int
) -> dict:
    """Force signals i∧j = 1 on fraction ρ of *defective* rows."""
    forced = 0
    defective = 0
    for o in outputs:
        if not o["defective"]:
            continue
        defective += 1
        if rho > 0 and random.random() < rho:
            o["signals"][i] = 1
            o["signals"][j] = 1
            forced += 1
    joint = sum(
        1
        for o in outputs
        if o["defective"] and o["signals"][i] and o["signals"][j]
    )
    return {
        "rho": rho,
        "pair": [SIGNAL_NAMES[i], SIGNAL_NAMES[j]],
        "defective": defective,
        "forced_cofire": forced,
        "forced_fraction_of_defective": forced / defective if defective else 0.0,
        "joint_rate": joint / defective if defective else 0.0,
    }


def unique_catch_one_trial(outputs: list[dict], configs: list[SignalConfig]) -> dict:
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
    rho: float,
    trials: int,
    seed: int,
    pair: tuple[str, str],
) -> dict:
    configs = SIGNAL_MEDIUM
    names = SIGNAL_NAMES
    i = names.index(pair[0])
    j = names.index(pair[1])
    unique_tot = [0] * len(configs)
    solo_tot = [0] * len(configs)
    def_tot = 0
    joint_sum = 0.0
    forced_sum = 0.0
    pair_key = f"{pair[0]}+{pair[1]}"

    for t in range(trials):
        # per-trial seed: comparable across ρ; pair hash so pairs differ
        pair_salt = sum(ord(c) for c in pair_key) * 17
        random.seed(seed + t * 10007 + int(rho * 1000) + pair_salt)
        gts = generate_stream(ERROR_RATE, ERROR_DIST)
        outs = generate_signals_independent(gts, configs)
        diag = inject_pair_cofire(outs, rho, i, j)
        stats = unique_catch_one_trial(outs, configs)
        def_tot += stats["total_defective"]
        for k in range(len(configs)):
            unique_tot[k] += stats["unique_catch"][k]
            solo_tot[k] += stats["solo_catch"][k]
        joint_sum += diag["joint_rate"]
        forced_sum += diag["forced_fraction_of_defective"]

    by_signal = {}
    rows = []
    for k, name in enumerate(names):
        solo = solo_tot[k] / def_tot if def_tot else 0.0
        uniq = unique_tot[k] / def_tot if def_tot else 0.0
        share = unique_tot[k] / solo_tot[k] if solo_tot[k] else None
        row = {
            "signal": name,
            "solo_catch_rate": round(solo, 6),
            "unique_catch_rate": round(uniq, 6),
            "unique_share_of_solo": round(share, 4) if share is not None else None,
        }
        rows.append(row)
        by_signal[name] = {
            "solo": round(solo, 4),
            "unique": round(uniq, 4),
            "share": round(share, 3) if share is not None else None,
        }

    ranked = sorted(rows, key=lambda r: -r["unique_catch_rate"])
    unique_rank = [r["signal"] for r in ranked]
    barely_u = by_signal["barely_passed"]["unique"]
    route_u = by_signal["route_changed"]["unique"]
    middle_order = (
        "barely_passed > route_changed"
        if barely_u > route_u
        else (
            "route_changed > barely_passed"
            if route_u > barely_u
            else "barely_passed == route_changed"
        )
    )

    return {
        "cofire_pair": list(pair),
        "rho": rho,
        "trials": trials,
        "error_dist": ERROR_DIST,
        "signal_quality": "medium",
        "total_defective": def_tot,
        "mean_joint_rate": round(joint_sum / trials, 4),
        "mean_forced_fraction": round(forced_sum / trials, 4),
        "unique_rank": unique_rank,
        "drop_first_by_unique": unique_rank[-1],
        "keep_first_by_unique": unique_rank[0],
        "middle_pair_order": middle_order,
        "extremes_hold": (
            unique_rank[0] == "classifier_disagree"
            and unique_rank[-1] == "input_unusual"
        ),
        "rank_equals_baseline": unique_rank == BASELINE_RANK,
        "by_signal": by_signal,
        "by_signal_full": rows,
    }


def run_pair_sweep(
    pair: tuple[str, str], trials: int, seed: int, quiet: bool = False
) -> dict:
    cells = []
    baseline_middle = None
    baseline_rank = None
    for rho in COFIRE_RHOS:
        cell = run_cell(rho, trials, seed, pair)
        if rho == 0.0:
            baseline_middle = cell["middle_pair_order"]
            baseline_rank = cell["unique_rank"]
        cell["middle_swapped_vs_independent"] = (
            cell["middle_pair_order"] != baseline_middle
            if baseline_middle is not None
            else False
        )
        cell["rank_changed_vs_independent"] = (
            cell["unique_rank"] != baseline_rank
            if baseline_rank is not None
            else False
        )
        cells.append(cell)
        if not quiet:
            a, b = pair
            print(
                f"\n  ρ={rho:.1f}  joint({a}∧{b})={cell['mean_joint_rate']:.3f}  "
                f"forced={cell['mean_forced_fraction']:.3f}"
            )
            print(f"    unique_rank: {' > '.join(cell['unique_rank'])}")
            print(
                f"    middle: {cell['middle_pair_order']}  "
                f"swapped={cell['middle_swapped_vs_independent']}  "
                f"extremes_hold={cell['extremes_hold']}  "
                f"rank_changed={cell['rank_changed_vs_independent']}"
            )

    any_middle = any(c["middle_swapped_vs_independent"] for c in cells)
    any_rank = any(c["rank_changed_vs_independent"] for c in cells)
    all_extremes = all(c["extremes_hold"] for c in cells)
    return {
        "cofire_pair": list(pair),
        "any_middle_swap": any_middle,
        "any_rank_change": any_rank,
        "all_extremes_hold": all_extremes,
        "cells": cells,
    }


def interpret_mike_pair(any_middle_swap: bool, all_extremes: bool) -> list[str]:
    if not any_middle_swap and all_extremes:
        return [
            "PASS (stronger than nine-cell): middle pair barely>route never "
            "swapped under deliberate route∧CD co-fire up to ρ=0.8; extremes "
            "still CD top / input bottom. Independence was the untested "
            "assumption — induced correlation did not reorder the prune."
        ]
    if any_middle_swap and all_extremes:
        return [
            "PARTIAL: middle pair reordered under induced co-fire; extremes "
            "held. Drop-order is NOT locked for barely vs route — only "
            "input_unusual first / CD last survive as structural."
        ]
    return [
        "FAIL / surprise: extremes moved under co-fire. Revisit the whole "
        "prune narrative; nine-cell independence result does not generalize."
    ]


def interpret_all_pairs(pair_results: list[dict]) -> list[str]:
    lines = []
    middle_attackers = [
        p["cofire_pair"] for p in pair_results if p["any_middle_swap"]
    ]
    extreme_breakers = [
        p["cofire_pair"] for p in pair_results if not p["all_extremes_hold"]
    ]
    rank_movers = [
        p["cofire_pair"] for p in pair_results if p["any_rank_change"]
    ]
    if not middle_attackers and not extreme_breakers:
        lines.append(
            "PASS (sim family): no forced pair among C(4,2)=6 reordered "
            "middle or broke extremes up to ρ=0.8. Prune order is robust to "
            "single-pair induced co-fire on this fixture — still not a "
            "production lock (need real co-occurrence labels)."
        )
    else:
        if middle_attackers:
            lines.append(
                "Middle (barely vs route) flips under forced pairs: "
                + ", ".join("+".join(p) for p in middle_attackers)
                + ". Middle prune NOT locked."
            )
        if extreme_breakers:
            lines.append(
                "Extremes break under forced pairs: "
                + ", ".join("+".join(p) for p in extreme_breakers)
                + ". Full prune narrative NOT locked."
            )
        if rank_movers and not middle_attackers and not extreme_breakers:
            lines.append(
                "Some non-middle/non-extreme rank jitter under: "
                + ", ".join("+".join(p) for p in rank_movers)
            )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument(
        "--all-pairs",
        action="store_true",
        help="Sweep all C(4,2) forced co-fire pairs (writes *-pairs.json)",
    )
    args = parser.parse_args()

    if args.all_pairs:
        pairs = list(combinations(SIGNAL_NAMES, 2))
        print("=" * 72)
        print("Induced co-fire — ALL pairs sweep")
        print(f"dist={ERROR_DIST}, quality=medium, trials/cell={args.trials}")
        print(f"pairs={len(pairs)}, ρ={COFIRE_RHOS}")
        print("=" * 72)

        pair_results = []
        for pair in pairs:
            print(f"\n{'─' * 72}\nFORCE: {pair[0]} ∧ {pair[1]}")
            pr = run_pair_sweep(pair, args.trials, args.seed, quiet=False)
            pair_results.append(pr)
            print(
                f"  → middle_swap={pr['any_middle_swap']}  "
                f"rank_change={pr['any_rank_change']}  "
                f"extremes_hold={pr['all_extremes_hold']}"
            )

        interpretation = interpret_all_pairs(pair_results)
        print("\n" + "=" * 72)
        print("INTERPRETATION")
        for line in interpretation:
            print(line)
        print("=" * 72)

        out = {
            "experiment": "unique-catch-cofire-pairs",
            "claim": (
                "Does ANY forced single-pair co-fire among the four signals "
                "reorder unique-CR (esp. middle barely vs route)?"
            ),
            "definition": (
                "unique_catch = defective caught by solo-i under "
                "Alex(baseline+esc*s_i) with coupled Uniform draw, and not "
                "caught by any other solo-j"
            ),
            "injection": (
                "After independent SIGNAL_MEDIUM fires, with probability ρ "
                "force the named pair = 1 on defective outputs only"
            ),
            "trials_per_cell": args.trials,
            "seed": args.seed,
            "error_rate": ERROR_RATE,
            "error_dist": ERROR_DIST,
            "signal_quality": "medium",
            "rhos": COFIRE_RHOS,
            "baseline_rank": BASELINE_RANK,
            "any_middle_swap_any_pair": any(
                p["any_middle_swap"] for p in pair_results
            ),
            "any_extremes_break_any_pair": any(
                not p["all_extremes_hold"] for p in pair_results
            ),
            "pair_results": pair_results,
            "interpretation": interpretation,
        }
        out_path = (
            Path(__file__).parent / "results-v2" / "unique-catch-cofire-pairs.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nWritten: {out_path}")
        return

    # Mike default: route ∧ CD only
    print("=" * 72)
    print("Induced co-fire unique-catch reorder (Mike caveat)")
    print(f"dist={ERROR_DIST}, quality=medium, trials/cell={args.trials}")
    print(f"force pair: {DEFAULT_PAIR[0]} ∧ {DEFAULT_PAIR[1]} on ρ of defectives")
    print("=" * 72)

    pr = run_pair_sweep(DEFAULT_PAIR, args.trials, args.seed, quiet=False)
    cells = pr["cells"]
    # back-compat field name in Mike-only JSON
    for c in cells:
        c["mean_route_cd_joint_rate"] = c["mean_joint_rate"]

    any_middle_swap = pr["any_middle_swap"]
    all_extremes = pr["all_extremes_hold"]
    interpretation = interpret_mike_pair(any_middle_swap, all_extremes)

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "unique-catch-cofire",
        "claim": (
            "Forced route_changed∧classifier_disagree co-fire on shared defect "
            "class — does unique-CR middle (barely vs route) reorder?"
        ),
        "definition": (
            "unique_catch = defective caught by solo-i under Alex(baseline+esc*s_i) "
            "with coupled Uniform draw, and not caught by any other solo-j"
        ),
        "injection": (
            "After independent SIGNAL_MEDIUM fires, with probability ρ force "
            "route_changed=1 and classifier_disagree=1 on defective outputs only"
        ),
        "trials_per_cell": args.trials,
        "seed": args.seed,
        "error_rate": ERROR_RATE,
        "error_dist": ERROR_DIST,
        "signal_quality": "medium",
        "cofire_pair": list(DEFAULT_PAIR),
        "rhos": COFIRE_RHOS,
        "any_middle_swap": any_middle_swap,
        "all_extremes_hold": all_extremes,
        "cells": cells,
        "interpretation": interpretation,
    }
    out_path = Path(__file__).parent / "results-v2" / "unique-catch-cofire.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
