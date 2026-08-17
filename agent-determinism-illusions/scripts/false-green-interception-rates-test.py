#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""False-green interception rates by attack class (synthetic catalog).

Claim under test
----------------
A single "blocks X%" claim is meaningless without a mixture model. This
run builds a **synthetic catalog** of false-green events across classes,
marks which defense layer catches each, and reports interception rates
*within class* and *under two mixture weights* (reporting-heavy vs
word-space-heavy). Numbers are catalog coverage — not field prevalence.

Classes
-------
  R  reporting theft (exit / PASS banner / in-process verdict)
  O  oracle lie (child-filled obs, fixture poison, parent-import)
  D  digest / verifier swap (colocated or writable "external" pin)
  W  word-space DPI (fabricated evidence; needs C3, not parent)
  P  probe/spec error (parent observes wrong referent)
  G  governance fail-open (timeout→warn, digest→warn, retry-pass)

Defense layers (cumulative stacks)
---------------------------------
  L0 none
  L1 Peter parent reporting (ignore child exit/banner; fail-closed IPC shape)
  L2 L1 + parent-owned observation + sealed fixtures
  L3 L2 + external attestation digest pin + ban parent-import
  L4 L3 + argument-space C3 (catches W when claim addressable)
  # P and G never caught by L1–L4 in this model

PASS criteria (falsify if any fails)
------------------------------------
  1. L3 intercepts all R+O+D catalog rows; intercepts none of P+G.
  2. L4 additionally intercepts all W rows; still none of P+G.
  3. Under reporting-heavy mix, L3 rate >> under word-space-heavy mix.
  4. Overall L3 rate is not universal (strictly < 100% on full catalog).

Expected: SUPPORT — rates are class-conditional; mixture decides the headline %.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "false-green-interception-rates.json"

# Each row: id, class, caught_by minimum layer ("L1"|"L2"|"L3"|"L4"|None)
# caught_by = first layer that blocks this false-green shape.
CATALOG = [
    # R — reporting theft
    {"id": "R1", "class": "R", "name": "child exit 0 + PASS banner", "caught_by": "L1"},
    {"id": "R2", "class": "R", "name": "in-process adversary returns PASS", "caught_by": "L1"},
    {"id": "R3", "class": "R", "name": "hang then self-declare PASS", "caught_by": "L1"},
    {"id": "R4", "class": "R", "name": "malformed IPC as success", "caught_by": "L1"},
    # O — oracle lie
    {"id": "O1", "class": "O", "name": "child lies {obs:ok}", "caught_by": "L2"},
    {"id": "O2", "class": "O", "name": "poison shared observation file", "caught_by": "L2"},
    {"id": "O3", "class": "O", "name": "parent import trusts probe_ok()", "caught_by": "L3"},
    {"id": "O4", "class": "O", "name": "child rewrites runtime cache parent reads", "caught_by": "L2"},
    # D — digest / verifier swap
    {"id": "D1", "class": "D", "name": "colocated expected digest rewritten", "caught_by": "L3"},
    {"id": "D2", "class": "D", "name": "writable CI secret pin swapped", "caught_by": "L3"},
    {"id": "D3", "class": "D", "name": "harness body backdoored in-tree", "caught_by": "L3"},
    # W — word-space DPI (parent alone insufficient)
    {"id": "W1", "class": "W", "name": "fabricated evidence snippet", "caught_by": "L4"},
    {"id": "W2", "class": "W", "name": "synonym surface fools C2", "caught_by": "L4"},
    {"id": "W3", "class": "W", "name": "honest thin evidence over-reject≠FG; fabric thick", "caught_by": "L4"},
    {"id": "W4", "class": "W", "name": "broken impl + compliant prose", "caught_by": "L4"},
    # P — probe/spec error (never by these layers)
    {"id": "P1", "class": "P", "name": "runner watches wrong key", "caught_by": None},
    {"id": "P2", "class": "P", "name": "claim names wrong referent", "caught_by": None},
    {"id": "P3", "class": "P", "name": "unaddressable claim forced into C3", "caught_by": None},
    # G — governance fail-open
    {"id": "G1", "class": "G", "name": "timeout downgraded to warn", "caught_by": None},
    {"id": "G2", "class": "G", "name": "digest mismatch warn-only", "caught_by": None},
    {"id": "G3", "class": "G", "name": "retry until green on flake", "caught_by": None},
]

LAYER_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}


def caught_at(row: dict, layer: str) -> bool:
    cb = row["caught_by"]
    if cb is None:
        return False
    return LAYER_ORDER[cb] <= LAYER_ORDER[layer]


def rate(rows: list[dict], layer: str) -> dict:
    n = len(rows)
    k = sum(1 for r in rows if caught_at(r, layer))
    return {"n": n, "caught": k, "rate": (k / n) if n else 0.0}


def weighted_rate(class_rates: dict, weights: dict[str, float], layer: str) -> float:
    """Mixture headline: sum_c w_c * rate_c(layer). Weights must sum to 1."""
    total_w = sum(weights.values())
    assert abs(total_w - 1.0) < 1e-9, total_w
    s = 0.0
    for cls, w in weights.items():
        s += w * class_rates[cls][layer]["rate"]
    return s


def main() -> None:
    classes = sorted({r["class"] for r in CATALOG})
    layers = ["L1", "L2", "L3", "L4"]

    by_class: dict = {}
    for cls in classes:
        rows = [r for r in CATALOG if r["class"] == cls]
        by_class[cls] = {layer: rate(rows, layer) for layer in layers}

    overall = {layer: rate(CATALOG, layer) for layer in layers}

    # Two illustrative mixtures (not field data).
    mix_reporting_heavy = {"R": 0.35, "O": 0.25, "D": 0.15, "W": 0.10, "P": 0.05, "G": 0.10}
    mix_wordspace_heavy = {"R": 0.05, "O": 0.10, "D": 0.05, "W": 0.50, "P": 0.15, "G": 0.15}

    headlines = {
        "reporting_heavy": {
            "weights": mix_reporting_heavy,
            "L3": weighted_rate(by_class, mix_reporting_heavy, "L3"),
            "L4": weighted_rate(by_class, mix_reporting_heavy, "L4"),
        },
        "wordspace_heavy": {
            "weights": mix_wordspace_heavy,
            "L3": weighted_rate(by_class, mix_wordspace_heavy, "L3"),
            "L4": weighted_rate(by_class, mix_wordspace_heavy, "L4"),
        },
    }

    # Claims
    rod = [r for r in CATALOG if r["class"] in ("R", "O", "D")]
    pg = [r for r in CATALOG if r["class"] in ("P", "G")]
    w = [r for r in CATALOG if r["class"] == "W"]

    claim1 = rate(rod, "L3")["rate"] == 1.0 and rate(pg, "L3")["rate"] == 0.0
    claim2 = rate(w, "L4")["rate"] == 1.0 and rate(pg, "L4")["rate"] == 0.0
    claim3 = headlines["reporting_heavy"]["L3"] > headlines["wordspace_heavy"]["L3"] + 0.2
    claim4 = overall["L3"]["rate"] < 1.0

    support = claim1 and claim2 and claim3 and claim4
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "caveat": (
            "Rates are fraction of this synthetic catalog / mixture weights — "
            "not measured field prevalence of false greens"
        ),
        "catalog_size": len(CATALOG),
        "claims": {
            "L3_catches_all_ROD_none_PG": claim1,
            "L4_catches_all_W_none_PG": claim2,
            "reporting_heavy_L3_much_higher": claim3,
            "L3_overall_not_100": claim4,
        },
        "by_class": by_class,
        "overall_catalog_unweighted": overall,
        "mixture_headlines": headlines,
        "catalog": CATALOG,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("false-green-interception-rates — synthetic catalog")
    print(f"verdict: {verdict}")
    print("--- by class @ L3 / L4 ---")
    for cls in classes:
        r3, r4 = by_class[cls]["L3"], by_class[cls]["L4"]
        print(
            f"  {cls}: L3={r3['caught']}/{r3['n']} ({r3['rate']:.0%})  "
            f"L4={r4['caught']}/{r4['n']} ({r4['rate']:.0%})"
        )
    print("--- overall catalog (unweighted) ---")
    for layer in layers:
        o = overall[layer]
        print(f"  {layer}: {o['caught']}/{o['n']} ({o['rate']:.0%})")
    print("--- mixture headlines ---")
    print(
        f"  reporting-heavy: L3={headlines['reporting_heavy']['L3']:.0%}  "
        f"L4={headlines['reporting_heavy']['L4']:.0%}"
    )
    print(
        f"  wordspace-heavy: L3={headlines['wordspace_heavy']['L3']:.0%}  "
        f"L4={headlines['wordspace_heavy']['L4']:.0%}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
