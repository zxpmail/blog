# -*- coding: utf-8 -*-
"""Partial-stale shadow fallback probe — Mike Czerwinski Part 15 follow-up (2026-07-29).

Question (Mike, 2026-07-29, Part 15 thread):
  The fallback trigger `shadow_caught == 0 && oracle > 0` handles the loud
  failure (shadow=0 while oracle>0). What about the quiet failure: a ranker
  that still catches *something* (shadow > 0) but less than what enforce
  would have caught (shadow < enforce)? The vacuous check never fires, and
  dual-line ships a compromised rank believing the fallback would have
  caught it if it mattered.

Predecessor: dual-line-ops-sim.py
  Current rule (line 346):
      if shadow_c == 0 and oracle > 0:
          return enforce, "fallback_arrival"
      return shadow_c, "shadow"

  So shadow ∈ (0, enforce) → ship shadow → loss vs enforce = (enforce - shadow).

Method (pure-math scan, no API):
  Fix oracle = 8 (true misses in queue), budget k = 8.
  Sweep shadow ∈ {0..8} × enforce ∈ {0..8} (all combinations).
  Three rules:
    vacuous:      ship shadow if shadow > 0 else enforce         (current dual-line)
    noninferior:  ship shadow if shadow >= enforce else enforce   (proposed)
    god:          ship max(shadow, enforce)                       (upper bound)

  For each (shadow, enforce) pair, compute:
    ship_vacuous, ship_noninferior, ship_god
    loss_vacuous = oracle - ship_vacuous
    loss_noninferior = oracle - ship_noninferior

  Quiet-failure regime: shadow ∈ (0, enforce) — vacuous rule loses catches
  here vs noninferior.

Falsifiers:
  - If loss_vacuous == loss_noninferior across all (shadow, enforce) →
    vacuous rule is sufficient; Mike's gap doesn't materialize.
  - If loss_vacuous > loss_noninferior on a non-empty region → Mike's gap
    is real; noninferior rule strictly dominates.

Cross-reference to dual-line-ops-sim.json (existing fixture):
  stratified diluted B=0.05, k=8: shadow_R_hist=8, enforce=0 → (s=8, e=0)
  temporal  diluted B=0.05, k=8: shadow_R_hist=0, enforce=0 → (s=0, e=0)
  temporal  class   B=0.05, k=8: shadow_R_hist=0, enforce(arrival)=4 → (s=0, e=4)
  temporal  class   B=0.05, k=8: shadow_conf_desc=8, enforce=4 → (s=8, e=4)
  All current fixture cells are at the corners (shadow ∈ {0, oracle} or
  enforce ∈ {0, oracle}). Partial-stale regime (shadow ∈ (0, enforce)) is
  NOT stressed by current fixture — this scan fills that gap.

Run:
  python partial-stale-shadow-test.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "partial-stale-shadow.json"

ORACLE = 8  # true misses in queue, k=8 budget


def ship_vacuous(shadow: int, enforce: int) -> int:
    """Current dual-line rule: shadow==0 ⟹ fallback."""
    if shadow == 0 and ORACLE > 0:
        return enforce
    return shadow


def ship_noninferior(shadow: int, enforce: int) -> int:
    """Proposed rule: shadow < enforce ⟹ fallback."""
    if shadow < enforce:
        return enforce
    return shadow


def ship_god(shadow: int, enforce: int) -> int:
    """Upper bound: always ship the better of the two."""
    return max(shadow, enforce)


def main() -> int:
    cells = []
    quiet_gap_cells = []
    for shadow in range(ORACLE + 1):
        for enforce in range(ORACLE + 1):
            sv = ship_vacuous(shadow, enforce)
            sn = ship_noninferior(shadow, enforce)
            sg = ship_god(shadow, enforce)
            cell = {
                "shadow": shadow,
                "enforce": enforce,
                "ship_vacuous": sv,
                "ship_noninferior": sn,
                "ship_god": sg,
                "loss_vacuous": ORACLE - sv,
                "loss_noninferior": ORACLE - sn,
                "loss_god": ORACLE - sg,
                "vacuous_loses_vs_noninferior": sn - sv,
                "regime": _regime(shadow, enforce),
            }
            cells.append(cell)
            if sn > sv:
                quiet_gap_cells.append(cell)

    # Summary
    n_total = len(cells)
    n_quiet_gap = len(quiet_gap_cells)
    avg_loss_vacuous_quiet = (
        sum(c["loss_vacuous"] for c in quiet_gap_cells) / n_quiet_gap
        if quiet_gap_cells else 0.0
    )
    avg_loss_noninferior_quiet = (
        sum(c["loss_noninferior"] for c in quiet_gap_cells) / n_quiet_gap
        if quiet_gap_cells else 0.0
    )
    max_loss_gap = max((c["vacuous_loses_vs_noninferior"] for c in quiet_gap_cells), default=0)

    # Where in the (shadow, enforce) grid is the gap?
    gap_region = sorted({(c["shadow"], c["enforce"]) for c in quiet_gap_cells})

    out = {
        "experiment": "partial-stale-shadow-fallback",
        "question": (
            "Does the dual-line fallback rule (shadow==0 ⟹ fallback) handle "
            "the quiet-failure regime where shadow ∈ (0, enforce)?"
        ),
        "source": "Mike Czerwinski comment on Part 15, 2026-07-29",
        "predecessor": "dual-line-ops-sim.py (line 346, current fallback rule)",
        "oracle": ORACLE,
        "rules": {
            "vacuous": "ship shadow if shadow > 0 else enforce (current dual-line)",
            "noninferior": "ship shadow if shadow >= enforce else enforce (proposed)",
            "god": "ship max(shadow, enforce) (upper bound)",
        },
        "current_fixture_cells": [
            {"holdout": "stratified", "stream": "diluted", "B": 0.05, "k": 8,
             "shadow_R_hist": 8, "enforce_arrival": 0, "regime": "shadow=oracle"},
            {"holdout": "within_model_temporal", "stream": "diluted", "B": 0.05, "k": 8,
             "shadow_R_hist": 0, "enforce_arrival": 0, "regime": "loud_failure (both zero)"},
            {"holdout": "within_model_temporal", "stream": "class", "B": 0.05, "k": 8,
             "shadow_R_hist": 0, "enforce_arrival": 4, "regime": "loud_failure (R_hist=0)"},
            {"holdout": "within_model_temporal", "stream": "class", "B": 0.05, "k": 8,
             "shadow_conf_desc": 8, "enforce_arrival": 4, "regime": "shadow=oracle"},
        ],
        "summary": {
            "n_cells_scanned": n_total,
            "n_quiet_gap_cells": n_quiet_gap,
            "quiet_gap_fraction": round(n_quiet_gap / n_total, 3),
            "avg_loss_vacuous_in_gap": round(avg_loss_vacuous_quiet, 2),
            "avg_loss_noninferior_in_gap": round(avg_loss_noninferior_quiet, 2),
            "max_loss_gap_per_cell": max_loss_gap,
            "gap_region_shadow_enforce_pairs": gap_region,
        },
        "cells": cells,
        "interpretation": (
            "Mike's gap is real and bounded: when shadow ∈ (0, enforce), the "
            "vacuous rule ships shadow and loses (enforce - shadow) catches vs "
            "the noninferior rule. Current fixture doesn't stress this regime "
            "— all cells sit at corners (shadow ∈ {0, oracle}). Fix: change "
            "fallback condition from `shadow==0` to `shadow < enforce`."
        ),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("═══ partial-stale shadow fallback probe ═══")
    print(f"oracle = {ORACLE} (true misses, k={ORACLE})")
    print()
    print("Rules:")
    print("  vacuous:     ship shadow if shadow > 0 else enforce     (current)")
    print("  noninferior: ship shadow if shadow >= enforce else enforce (proposed)")
    print("  god:         ship max(shadow, enforce)")
    print()
    print(f"Scanned {n_total} (shadow, enforce) cells; {n_quiet_gap} in quiet-gap regime.")
    print(f"Gap region (shadow, enforce) pairs: {gap_region}")
    print(f"Max catches lost per cell by vacuous: {max_loss_gap}")
    print()

    print("Grid view — loss_vacuous / loss_noninferior (shadow=row, enforce=col):")
    header = "       " + " ".join(f"e={i:<2}" for i in range(ORACLE + 1))
    print(header)
    for s in range(ORACLE, -1, -1):
        cells_row = [c for c in cells if c["shadow"] == s]
        cells_row.sort(key=lambda c: c["enforce"])
        parts = []
        for c in cells_row:
            lv = c["loss_vacuous"]
            ln = c["loss_noninferior"]
            mark = "*" if c["vacuous_loses_vs_noninferior"] > 0 else " "
            parts.append(f"{lv}/{ln}{mark}")
        print(f"  s={s}  " + " ".join(f"{p:<6}" for p in parts))
    print()
    print("  (* = vacuous loses vs noninferior in this cell)")
    print()
    print(f"→ {OUT}")
    return 0


def _regime(shadow: int, enforce: int) -> str:
    if shadow == 0 and enforce == 0:
        return "both_zero"
    if shadow == 0 and enforce > 0:
        return "loud_failure_shadow_zero"
    if shadow > 0 and shadow < enforce:
        return "quiet_failure_partial_stale"
    if shadow == enforce:
        return "tie"
    if shadow > enforce and shadow < ORACLE:
        return "shadow_wins_partial"
    if shadow == ORACLE:
        return "shadow_perfect"
    return "other"


if __name__ == "__main__":
    sys.exit(main())
