# -*- coding: utf-8 -*-
"""Simulated co-occurrence labels → unique-catch reorder.

Claim under test (follow-up to Mike's co-fire caveat + all-pairs sweep):
    Single-pair forced co-fire never reordered unique-CR on the burst/medium
    fixture. Production would not hand you a forced pair — it would hand
    *co-occurrence labels*: each defective belongs to a latent defect class
    whose signature is a set of signals that co-fire. Simulate that generative
    model (label → signature → fires) and ask whether unique-CR prune order
    still holds under multi-class co-occurrence structure.

Method:
    Same unique-catch definition (coupled Uniform, Alex baseline+esc).

    Generative model for each defective:
      1. Draw co-occurrence label L ~ Categorical(π)   # the simulated label
      2. For each signal s:
           if s ∈ signature(L): fire with p_sig (=0.90)
           else:                fire i.i.d. at SIGNAL_MEDIUM.tp
      Clean rows: independent FP at SIGNAL_MEDIUM.fp (no labels).

    Label catalog (signatures):
      independent   — empty signature (pure medium i.i.d.)
      route_cd      — {route_changed, classifier_disagree}   # Mike-named
      barely_route  — {barely_passed, route_changed}         # middle attack
      cd_barely     — {classifier_disagree, barely_passed}   # starve barely unique
      input_route   — {input_unusual, route_changed}
      cd_input      — {classifier_disagree, input_unusual}
      triple_rcb    — {route, CD, barely}
      all_four      — all four signals

    Mixture arms (π over labels among defectives):
      independent     — 100% independent (baseline)
      mike_half       — 50% route_cd / 50% independent
      balanced_pairs  — equal mass on six pair labels + residual independent
      middle_attack   — 70% barely_route (direct middle co-fire)
      starve_barely   — 70% cd_barely (barely shares top; route freer)
      cd_hub          — CD paired equally with each of the other three
      triple_heavy    — 50% triple_rcb / 30% all_four / 20% independent
      chaos           — broad mix of pairs + triples + all_four

Primary metrics per mixture:
    unique_rank, middle_swapped vs independent, extremes_hold,
    empirical pairwise joint rates, label mass realized.

Falsifiers:
    - Any mixture flips middle or extremes → prune not locked under
      co-occurrence-label generative model; name the attacking mixture.
    - All mixtures hold → stronger than pair-force; still not production
      (π and signatures are invented, not fit to a real trace).

Dependencies: none (pure Python).
Run:
    python scripts/unique-catch-cooccur-labels-test.py
    python scripts/unique-catch-cooccur-labels-test.py --trials 200
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
P_SIG = 0.90  # fire prob for signals inside a label's signature


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

BASELINE_RANK = [
    "classifier_disagree",
    "barely_passed",
    "route_changed",
    "input_unusual",
]

# Co-occurrence label → signature (set of signal names)
SIGNATURES: dict[str, frozenset[str]] = {
    "independent": frozenset(),
    "route_cd": frozenset({"route_changed", "classifier_disagree"}),
    "barely_route": frozenset({"barely_passed", "route_changed"}),
    "cd_barely": frozenset({"classifier_disagree", "barely_passed"}),
    "input_route": frozenset({"input_unusual", "route_changed"}),
    "cd_input": frozenset({"classifier_disagree", "input_unusual"}),
    "input_barely": frozenset({"input_unusual", "barely_passed"}),
    "triple_rcb": frozenset(
        {"route_changed", "classifier_disagree", "barely_passed"}
    ),
    "all_four": frozenset(SIGNAL_NAMES),
}

# Mixture name → π over labels (must sum ~1)
MIXTURES: dict[str, dict[str, float]] = {
    "independent": {"independent": 1.0},
    "mike_half": {"route_cd": 0.5, "independent": 0.5},
    "balanced_pairs": {
        "route_cd": 1 / 7,
        "barely_route": 1 / 7,
        "cd_barely": 1 / 7,
        "input_route": 1 / 7,
        "cd_input": 1 / 7,
        "input_barely": 1 / 7,
        "independent": 1 / 7,
    },
    "middle_attack": {"barely_route": 0.7, "independent": 0.3},
    "starve_barely": {"cd_barely": 0.7, "independent": 0.3},
    "cd_hub": {
        "route_cd": 0.25,
        "cd_barely": 0.25,
        "cd_input": 0.25,
        "independent": 0.25,
    },
    "triple_heavy": {
        "triple_rcb": 0.5,
        "all_four": 0.3,
        "independent": 0.2,
    },
    "chaos": {
        "route_cd": 0.12,
        "barely_route": 0.12,
        "cd_barely": 0.12,
        "input_route": 0.10,
        "cd_input": 0.10,
        "input_barely": 0.10,
        "triple_rcb": 0.14,
        "all_four": 0.10,
        "independent": 0.10,
    },
}


def _normalize(pi: dict[str, float]) -> dict[str, float]:
    s = sum(pi.values())
    return {k: v / s for k, v in pi.items()}


def draw_label(pi: dict[str, float]) -> str:
    r = random.random()
    acc = 0.0
    items = list(pi.items())
    for name, p in items[:-1]:
        acc += p
        if r < acc:
            return name
    return items[-1][0]


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
        else:
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


def generate_labeled_signals(
    gts: list[bool],
    configs: list[SignalConfig],
    pi: dict[str, float],
    p_sig: float = P_SIG,
) -> tuple[list[dict], dict[str, int]]:
    """Return outputs + label counts among defectives."""
    pi_n = _normalize(pi)
    label_counts = {k: 0 for k in pi_n}
    results = []
    for gt in gts:
        if not gt:
            sigs = [
                1 if random.random() < sc.fp else 0 for sc in configs
            ]
            results.append(
                {"defective": False, "signals": sigs, "label": None}
            )
            continue
        label = draw_label(pi_n)
        label_counts[label] = label_counts.get(label, 0) + 1
        sig_set = SIGNATURES[label]
        sigs = []
        for sc in configs:
            if sc.name in sig_set:
                p = p_sig
            else:
                p = sc.tp
            sigs.append(1 if random.random() < p else 0)
        results.append(
            {"defective": True, "signals": sigs, "label": label}
        )
    return results, label_counts


def unique_catch_one_trial(
    outputs: list[dict], configs: list[SignalConfig]
) -> dict:
    n = len(configs)
    unique_catch = [0] * n
    solo_catch = [0] * n
    total_defective = 0
    # pairwise joints among defectives
    joint = [[0] * n for _ in range(n)]
    for o in outputs:
        if not o["defective"]:
            continue
        total_defective += 1
        sigs = o["signals"]
        for a in range(n):
            for b in range(a, n):
                if sigs[a] and sigs[b]:
                    joint[a][b] += 1
                    if a != b:
                        joint[b][a] += 1
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
        "joint": joint,
    }


def run_mixture(name: str, trials: int, seed: int) -> dict:
    pi = MIXTURES[name]
    configs = SIGNAL_MEDIUM
    names = SIGNAL_NAMES
    n = len(configs)
    unique_tot = [0] * n
    solo_tot = [0] * n
    def_tot = 0
    joint_tot = [[0] * n for _ in range(n)]
    label_tot: dict[str, int] = {}

    for t in range(trials):
        random.seed(seed + t * 10007 + sum(ord(c) for c in name) * 13)
        gts = generate_stream(ERROR_RATE, ERROR_DIST)
        outs, label_counts = generate_labeled_signals(gts, configs, pi)
        stats = unique_catch_one_trial(outs, configs)
        def_tot += stats["total_defective"]
        for i in range(n):
            unique_tot[i] += stats["unique_catch"][i]
            solo_tot[i] += stats["solo_catch"][i]
            for j in range(n):
                joint_tot[i][j] += stats["joint"][i][j]
        for lab, c in label_counts.items():
            label_tot[lab] = label_tot.get(lab, 0) + c

    by_signal = {}
    rows = []
    for i, sig_name in enumerate(names):
        solo = solo_tot[i] / def_tot if def_tot else 0.0
        uniq = unique_tot[i] / def_tot if def_tot else 0.0
        share = unique_tot[i] / solo_tot[i] if solo_tot[i] else None
        rows.append(
            {
                "signal": sig_name,
                "solo_catch_rate": round(solo, 6),
                "unique_catch_rate": round(uniq, 6),
                "unique_share_of_solo": round(share, 4) if share else None,
            }
        )
        by_signal[sig_name] = {
            "solo": round(solo, 4),
            "unique": round(uniq, 4),
            "share": round(share, 3) if share else None,
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

    joint_rates = {}
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i < j:
                joint_rates[f"{a}∧{b}"] = round(
                    joint_tot[i][j] / def_tot if def_tot else 0.0, 4
                )

    label_mass = {
        k: round(v / def_tot, 4) if def_tot else 0.0
        for k, v in sorted(label_tot.items(), key=lambda x: -x[1])
    }

    return {
        "mixture": name,
        "pi": _normalize(pi),
        "p_sig": P_SIG,
        "trials": trials,
        "total_defective": def_tot,
        "label_mass_realized": label_mass,
        "pairwise_joint_rates": joint_rates,
        "unique_rank": unique_rank,
        "middle_pair_order": middle_order,
        "extremes_hold": (
            unique_rank[0] == "classifier_disagree"
            and unique_rank[-1] == "input_unusual"
        ),
        "rank_equals_baseline": unique_rank == BASELINE_RANK,
        "by_signal": by_signal,
    }


def interpret(cells: list[dict], baseline_middle: str) -> list[str]:
    middle_flip = [
        c["mixture"]
        for c in cells
        if c["mixture"] != "independent"
        and c["middle_pair_order"] != baseline_middle
    ]
    extreme_break = [
        c["mixture"] for c in cells if not c["extremes_hold"]
    ]
    rank_move = [
        c["mixture"]
        for c in cells
        if c["mixture"] != "independent" and not c["rank_equals_baseline"]
    ]
    lines = []
    if not middle_flip and not extreme_break:
        lines.append(
            "PASS (sim co-occurrence labels): no mixture flipped middle or "
            "broke extremes. Prune order survives multi-class label→signature "
            "generative structure on this fixture — including starve_barely, "
            "middle_attack, triple_heavy, chaos."
        )
        if rank_move:
            lines.append(
                "Note: non-baseline rank jitter (non-middle/extreme) under: "
                + ", ".join(rank_move)
            )
    else:
        if middle_flip:
            details = []
            for c in cells:
                if c["mixture"] not in middle_flip:
                    continue
                b = c["by_signal"]
                details.append(
                    f"{c['mixture']} "
                    f"(route_u={b['route_changed']['unique']}, "
                    f"barely_u={b['barely_passed']['unique']})"
                )
            lines.append(
                "Middle flips under mixtures: "
                + "; ".join(details)
                + ". Middle prune NOT locked under co-occurrence labels "
                "(even a tiny stable swap counts — pair-force alone missed this)."
            )
        if extreme_break:
            lines.append(
                "Extremes break under mixtures: "
                + ", ".join(extreme_break)
                + ". Full prune NOT locked."
            )
        elif middle_flip:
            lines.append(
                "Extremes still held on every mixture (CD top / input bottom)."
            )
        if rank_move:
            lines.append("Rank moved under: " + ", ".join(rank_move))
    lines.append(
        "Still not a production lock: π and signatures are invented, "
        "not fit to a real trace's co-occurrence labels."
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()

    print("=" * 72)
    print("Simulated co-occurrence labels → unique-catch")
    print(f"dist={ERROR_DIST}, quality=medium, p_sig={P_SIG}, "
          f"trials={args.trials}")
    print(f"mixtures: {list(MIXTURES)}")
    print("=" * 72)

    cells = []
    baseline_middle = None
    for name in MIXTURES:
        cell = run_mixture(name, args.trials, args.seed)
        if name == "independent":
            baseline_middle = cell["middle_pair_order"]
        cell["middle_swapped_vs_independent"] = (
            cell["middle_pair_order"] != baseline_middle
            if baseline_middle is not None
            else False
        )
        cells.append(cell)

        print(f"\n{'─' * 72}\nMIXTURE: {name}")
        print(f"  label_mass: {cell['label_mass_realized']}")
        print(f"  unique_rank: {' > '.join(cell['unique_rank'])}")
        print(
            f"  middle: {cell['middle_pair_order']}  "
            f"swapped={cell['middle_swapped_vs_independent']}  "
            f"extremes_hold={cell['extremes_hold']}  "
            f"rank_eq_baseline={cell['rank_equals_baseline']}"
        )
        for sig in cell["unique_rank"]:
            s = cell["by_signal"][sig]
            print(
                f"    {sig:22s} solo={s['solo']:.3f}  "
                f"unique={s['unique']:.3f}  share={s['share']}"
            )

    assert baseline_middle is not None
    interpretation = interpret(cells, baseline_middle)
    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "unique-catch-cooccur-labels",
        "claim": (
            "Under simulated co-occurrence labels (latent defect class → "
            "signal signature), does unique-CR prune order hold?"
        ),
        "definition": (
            "unique_catch = defective caught by solo-i under "
            "Alex(baseline+esc*s_i) with coupled Uniform draw, not caught "
            "by any other solo-j"
        ),
        "generative_model": (
            "defective ~ label L~π; signal in signature(L) fires @ p_sig; "
            "else @ SIGNAL_MEDIUM.tp; cleans independent FP"
        ),
        "p_sig": P_SIG,
        "signatures": {k: sorted(v) for k, v in SIGNATURES.items()},
        "trials_per_mixture": args.trials,
        "seed": args.seed,
        "error_rate": ERROR_RATE,
        "error_dist": ERROR_DIST,
        "baseline_rank": BASELINE_RANK,
        "any_middle_swap": any(
            c["middle_swapped_vs_independent"] for c in cells
        ),
        "any_extremes_break": any(not c["extremes_hold"] for c in cells),
        "cells": cells,
        "interpretation": interpretation,
    }
    out_path = (
        Path(__file__).parent / "results-v2" / "unique-catch-cooccur-labels.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
