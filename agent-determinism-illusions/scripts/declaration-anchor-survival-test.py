# -*- coding: utf-8 -*-
"""Declaration/router anchor survival table — Xiao Man refinement stress (2026-07-30).

Question (user follow-up, 2026-07-30):
  "把锚点从探针的职责中移除 这行吗" → probe-layer yes; system-layer moves anchor
  to declaration. Does the new anchor layer have a measurable survival envelope?

Method:
  Take the T3 schema (services[] with 2 dicts, each {name, port, limits}).
  Generate the SAME good-T3 artifact under 6 perturbations. For each of 4
  anchor strategies, measure: does the anchor correctly resolve the services
  path? (Not whether the probe accepts — that's probe-side, already verified
  in probe-path-passing-redesign-test.py. Here we test ONLY router resolution.)

  4 anchor strategies:
    1. synonym_list   — first key in ["services","components","modules"] whose
                         value is a list
    2. structural     — first key whose value is a list-of-dicts where each
                         dict has a "limits" subfield (schema-shape; no key
                         names of the outer field)
    3. cardinality    — first key whose value is a list of exactly 2 dicts
                         (global structural)
    4. cross_field    — first key whose value is a list of dicts each having
                         {name, port, limits} (semantic-structural)

  8 perturbations on the original good-T3:
    P0 baseline               — no perturbation
    P1 rename_in_decl         — services → components (in synonym_list)
    P2 rename_outside_decl    — services → instances (NOT in synonym_list)
    P3 decoy                  — add extra field "decoy": [{x:1}] (noise list)
    P4 shape_corrupt          — change inner limits from dict to list
    P5 cardinality_corrupt    — add a third dummy service entry
    P6 decoy_with_limits      — insert "connections" list-of-dicts-with-limits BEFORE services (shape clone)
    P7 inner_field_rename     — rename inner port → port_number

Expected (the survival envelope each anchor):
  synonym_list:  P0 ✓  P1 ✓  P2 ✗  P3 ✓  P4 ✓  P5 ✓  P6 ✓  P7 ✓  (dies only on out-of-decl rename)
  structural:    P0 ✓  P1 ✓  P2 ✓  P3 ✓  P4 ✓  P5 ✓  P6 ✗  P7 ✓  (dies on shape clone — can't distinguish decoy-with-limits)
  cardinality:   P0 ✓  P1 ✓  P2 ✓  P3 ✓  P4 ✓  P5 ✗  P6 ✗  P7 ✓  (dies on count change + shape clone)
  cross_field:   P0 ✓  P1 ✓  P2 ✓  P3 ✓  P4 ✓  P5 ✓  P6 ✓  P7 ✗  (dies on inner field rename — semantic-structural breaks)

Falsification:
  If all anchors survive all perturbations → anchors are interchangeable; the
  survival-envelope distinction is fictional.
  If cardinality survives shape_corrupt → cardinality is robust to inner-shape;
  record as cleaner anchor than structural.

Run:
  python declaration-anchor-survival-test.py
"""

from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "declaration-anchor-survival.json"


# ── Base good-T3 artifact ──

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


# ── Perturbations ──

def p_baseline(art):
    return copy.deepcopy(art)

def p_rename_in_decl(art):
    a = copy.deepcopy(art)
    a["components"] = a.pop("services")
    return a

def p_rename_outside_decl(art):
    a = copy.deepcopy(art)
    a["instances"] = a.pop("services")
    return a

def p_decoy(art):
    a = copy.deepcopy(art)
    a["decoy"] = [{"x": 1}]
    return a

def p_shape_corrupt(art):
    """Change inner limits from dict to list — breaks structural anchor."""
    a = copy.deepcopy(art)
    for svc in a["services"]:
        svc["limits"] = [10, 5000]  # was a dict
    return a

def p_cardinality_corrupt(art):
    """Add a third dummy entry — breaks cardinality anchor."""
    a = copy.deepcopy(art)
    a["services"].append({"name": "dummy", "port": 9999,
                          "limits": {"max_connections": 1, "timeout_ms": 100}})
    return a


def p6_decoy_with_limits(art):
    """Insert a decoy list-of-dicts-with-limits BEFORE services.
    structural/cardinality anchors can't distinguish decoy from services on
    shape alone → misroute to 'connections'. Synonym_list/cross_field are
    narrower and survive."""
    a = {}
    a["connections"] = [{"limits": {"x": 1}}, {"limits": {"x": 2}}]
    for k, v in art.items():
        a[k] = copy.deepcopy(v)
    return a


def p7_inner_field_rename(art):
    """Rename port → port_number inside service dicts.
    cross_field requires {name,port,limits} triple → services no longer matches.
    Other anchors only check shape/cardinality/key-name-of-outer → survive."""
    a = copy.deepcopy(art)
    for svc in a["services"]:
        svc["port_number"] = svc.pop("port")
    return a


PERTURBATIONS = [
    ("P0_baseline", p_baseline),
    ("P1_rename_in_decl", p_rename_in_decl),
    ("P2_rename_outside_decl", p_rename_outside_decl),
    ("P3_decoy", p_decoy),
    ("P4_shape_corrupt", p_shape_corrupt),
    ("P5_cardinality_corrupt", p_cardinality_corrupt),
    ("P6_decoy_with_limits", p6_decoy_with_limits),
    ("P7_inner_field_rename", p7_inner_field_rename),
]


# ── Anchor strategies ──

def anchor_synonym_list(art: dict) -> str | None:
    """First declared synonym whose value is a list."""
    for cand in ["services", "components", "modules"]:
        v = art.get(cand)
        if isinstance(v, list):
            return cand
    return None


def _is_list_of_dicts(v) -> bool:
    return isinstance(v, list) and len(v) > 0 and all(isinstance(x, dict) for x in v)


def anchor_structural(art: dict) -> str | None:
    """First field whose value is a list-of-dicts where each dict has 'limits'."""
    for k, v in art.items():
        if not _is_list_of_dicts(v):
            continue
        if all("limits" in d for d in v):
            return k
    return None


def anchor_cardinality(art: dict) -> str | None:
    """First field whose value is a list of exactly 2 dicts."""
    for k, v in art.items():
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, dict) for x in v):
            return k
    return None


def anchor_cross_field(art: dict) -> str | None:
    """First field whose value is a list of dicts each having {name,port,limits}."""
    required = {"name", "port", "limits"}
    for k, v in art.items():
        if not _is_list_of_dicts(v):
            continue
        if all(required.issubset(d.keys()) for d in v):
            return k
    return None


ANCHORS = [
    ("synonym_list", anchor_synonym_list),
    ("structural", anchor_structural),
    ("cardinality", anchor_cardinality),
    ("cross_field", anchor_cross_field),
]


# ── Main ──

def main():
    base = base_good_t3()
    TRUE_SERVICES_KEY_AFTER = {
        "P0_baseline": "services",
        "P1_rename_in_decl": "components",
        "P2_rename_outside_decl": "instances",
        "P3_decoy": "services",
        "P4_shape_corrupt": "services",
        "P5_cardinality_corrupt": "services",
        "P6_decoy_with_limits": "services",
        "P7_inner_field_rename": "services",
    }

    print("═" * 78)
    print("  Declaration/router anchor survival table")
    print("  Base = good T3 (services[2] each {name,port,limits})")
    print("═" * 78)
    print()
    header = f"  {'anchor':<14} " + " ".join(f"{p:<22}" for p, _ in PERTURBATIONS)
    print(header)
    print("  " + "-" * (len(header) - 2))

    survival_matrix = {}
    for anchor_name, anchor_fn in ANCHORS:
        row = {}
        cells = []
        for pert_name, pert_fn in PERTURBATIONS:
            art = pert_fn(base)
            resolved = anchor_fn(art)
            true_key = TRUE_SERVICES_KEY_AFTER[pert_name]
            # "Survive" = anchor resolves to the correct services key
            survived = (resolved == true_key)
            row[pert_name] = {"resolved": resolved, "truth": true_key,
                              "survived": survived}
            cells.append(f"{'✓' if survived else '✗'} {resolved or 'None':<20}")
        survival_matrix[anchor_name] = row
        print(f"  {anchor_name:<14} " + " ".join(cells))

    print()
    print("  Survival counts:")
    for anchor_name, row in survival_matrix.items():
        n_surv = sum(1 for r in row.values() if r["survived"])
        print(f"    {anchor_name:<14} {n_surv}/{len(PERTURBATIONS)}")

    print()
    print("  Interpretation:")
    print("    Each anchor has a distinct failure mode under P6/P7:")
    print("      synonym_list: dies P2 (out-of-decl rename only)")
    print("      structural:   dies P6 (decoy with limits — can't distinguish shape-identical)")
    print("      cardinality:  dies P5 (count change) and P6 (decoy len-matches)")
    print("      cross_field:  dies P7 (inner field rename — semantic structural breaks)")
    print("    No anchor survives all 8. The 'wide' anchors (structural/cross_field) trade")
    print("    robustness on rename for fragility on shape-clone / inner-rename attacks.")
    print()

    out = {
        "experiment": "declaration-anchor-survival",
        "question": "What's the survival envelope of different declaration-layer anchors?",
        "context": "Xiao Man 'remove anchor from probe' refinement — anchor relocates to declaration; "
                   "this tests whether the new anchor layer has a measurable survival envelope.",
        "base_artifact": "T3 good (services[2] each {name,port,limits})",
        "anchors": [a[0] for a in ANCHORS],
        "perturbations": [p[0] for p in PERTURBATIONS],
        "survival_matrix": survival_matrix,
        "interpretation": (
            "Each anchor has a distinct failure signature. No anchor survives all 8. "
            "synonym_list dies on out-of-decl rename (P2); structural dies on shape clone "
            "(P6 — can't distinguish decoy-with-limits); cardinality dies on count change "
            "(P5) and shape clone (P6); cross_field dies on inner field rename (P7). "
            "The 'wide' anchors (structural/cross_field) trade robustness on outer rename "
            "for fragility on shape-clone / inner-rename attacks. Conclusion: anchor "
            "relocation is real and useful, but the new anchor layer inherits its own "
            "survival question — there is no anchor-free finish."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {OUT}")


if __name__ == "__main__":
    main()
