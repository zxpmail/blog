# -*- coding: utf-8 -*-
"""Agree-wrong silence — load sensor mute cell (Xiao Man, 2026-08-03).

Claim under test:
  When primary and secondary anchors agree on the *same wrong key*, the
  disagree-cell load sensor stays quiet — same shape as Part 7 unanimous miss.
  The sensor reports pressure only on disagreement; agree-wrong produces no
  disagree cell, so ops is not pointed at an axis even though both sides miss.

Method:
  Reuse T3 fixture + synonym_list (primary) / structural (secondary) from
  declaration-anchor-fallback-logging-test.py.
  Controls: P2 (disagree, primary dies), P6 (disagree, secondary dies).
  New cell: P8_agree_wrong — true payload moved outside the synonym list;
  a synonym+shape bait ("modules") sits where both anchors land first.

Readouts per cell:
  agree, primary_ok, secondary_ok, sensor_fires (= not agree),
  gate_oracle_ok (= primary == truth; oracle only),
  gate_would_ship (= primary is not None — production has no truth).

Expected:
  P2: sensor_fires, primary under pressure
  P6: sensor_fires, secondary under pressure
  P8: agree=True, both wrong, sensor_fires=False, gate_would_ship=True

Falsification:
  If P8 disagrees, or either side is ok, or sensor_fires on P8 → the mute
  cell is not demonstrated on this fixture. If P2/P6 stop disagreeing →
  controls broke; do not interpret P8.

Dependencies: stdlib only.
Run: python declaration-anchor-agree-wrong-silence-test.py
"""

from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "declaration-anchor-agree-wrong-silence.json"


def base_good_t3() -> dict:
    return {
        "services": [
            {"name": "api", "port": 8080,
             "limits": {"max_connections": 10, "timeout_ms": 5000}},
            {"name": "worker", "port": 8081,
             "limits": {"max_connections": 20, "timeout_ms": 3000}},
        ],
        "_meta": {"ok": True},
    }


def p2_rename_outside_decl(art):
    a = copy.deepcopy(art)
    a["instances"] = a.pop("services")
    return a


def p6_decoy_with_limits(art):
    a = {}
    a["connections"] = [{"limits": {"x": 1}}, {"limits": {"x": 2}}]
    for k, v in art.items():
        a[k] = copy.deepcopy(v)
    return a


def p8_agree_wrong(art):
    """真载荷挪出同义词表；同义词+外形诱饵 modules 抢先被两边命中。"""
    a = {}
    a["modules"] = [
        {"name": "bait", "port": 1,
         "limits": {"max_connections": 1, "timeout_ms": 1}},
        {"name": "bait2", "port": 2,
         "limits": {"max_connections": 1, "timeout_ms": 1}},
    ]
    a["instances"] = copy.deepcopy(art["services"])
    for k, v in art.items():
        if k == "services":
            continue
        a[k] = copy.deepcopy(v)
    return a


CELLS = [
    ("P2_rename_outside_decl", p2_rename_outside_decl, "instances"),
    ("P6_decoy_with_limits", p6_decoy_with_limits, "services"),
    ("P8_agree_wrong", p8_agree_wrong, "instances"),
]


def anchor_synonym_list(art: dict) -> str | None:
    for cand in ["services", "components", "modules"]:
        v = art.get(cand)
        if isinstance(v, list):
            return cand
    return None


def _is_list_of_dicts(v) -> bool:
    return isinstance(v, list) and len(v) > 0 and all(isinstance(x, dict) for x in v)


def anchor_structural(art: dict) -> str | None:
    for k, v in art.items():
        if not _is_list_of_dicts(v):
            continue
        if all("limits" in d for d in v):
            return k
    return None


def eval_cell(name: str, fn, truth: str, base: dict) -> dict:
    """评估单格：同意/对错/传感是否亮/门是否会放行。"""
    art = fn(base)
    primary = anchor_synonym_list(art)
    secondary = anchor_structural(art)
    agree = primary == secondary
    return {
        "perturbation": name,
        "truth": truth,
        "primary_resolved": primary,
        "secondary_resolved": secondary,
        "agree": agree,
        "primary_ok": primary == truth,
        "secondary_ok": secondary == truth,
        "sensor_fires": not agree,
        "gate_oracle_ok": primary == truth,
        "gate_would_ship": primary is not None,
    }


def main():
    base = base_good_t3()
    print("═" * 72)
    print("  Agree-wrong silence — load sensor mute cell")
    print("  primary=synonym_list  secondary=structural")
    print("═" * 72)

    rows = []
    for name, fn, truth in CELLS:
        row = eval_cell(name, fn, truth, base)
        rows.append(row)
        fire = "FIRE" if row["sensor_fires"] else "QUIET"
        print(
            f"  {name:<28} sensor={fire:<5} "
            f"pri={row['primary_resolved'] or 'None':<12} "
            f"sec={row['secondary_resolved'] or 'None':<12} "
            f"pri_ok={row['primary_ok']} sec_ok={row['secondary_ok']} "
            f"ship={row['gate_would_ship']}"
        )

    by = {r["perturbation"]: r for r in rows}
    p2, p6, p8 = by["P2_rename_outside_decl"], by["P6_decoy_with_limits"], by["P8_agree_wrong"]

    controls_ok = (
        p2["sensor_fires"] and (not p2["primary_ok"]) and p2["secondary_ok"]
        and p6["sensor_fires"] and p6["primary_ok"] and (not p6["secondary_ok"])
    )
    mute_ok = (
        p8["agree"]
        and (not p8["primary_ok"])
        and (not p8["secondary_ok"])
        and (not p8["sensor_fires"])
        and p8["gate_would_ship"]
    )
    passed = controls_ok and mute_ok

    print("\n  Verdict:")
    print(f"    Controls P2/P6 still disagree correctly: {'PASS' if controls_ok else 'FAIL'}")
    print(f"    P8 agree-wrong → sensor quiet + would ship: {'PASS' if mute_ok else 'FAIL'}")
    print(f"    Overall: {'PASS' if passed else 'FAIL'}")

    out = {
        "experiment": "declaration-anchor-agree-wrong-silence",
        "question": (
            "When both anchors agree on the same wrong key, does the "
            "disagree-cell load sensor stay quiet while the primary gate "
            "would still ship?"
        ),
        "context": (
            "Xiao Man 2026-08-03: scope note confirmation — sensor is "
            "pressure visibility not verdict; mute on agree-wrong = "
            "Part 7 unanimous-miss shape."
        ),
        "primary": "synonym_list",
        "secondary": "structural",
        "cells": rows,
        "verdict": {
            "controls_pass": controls_ok,
            "mute_cell_pass": mute_ok,
            "pass": passed,
        },
        "interpretation": (
            "P2/P6 still light the sensor on opposite single-side deaths. "
            "P8 both land on modules while truth is instances: agree=true, "
            "sensor quiet, primary non-null → would ship the bait subtree. "
            "No signal is not no problem — same shape as unanimous miss. "
            "Out-of-channel / T2 still required for that population."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {OUT}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
