# -*- coding: utf-8 -*-
"""Structural-invariant probe anchors — Xiao Man rename_keys follow-up (2026-07-30).

Question (Xiao Man, 2026-07-29, Part 7 thread):
  rename_keys breaks the probe implementation itself (art.get("services")
  hardcoded at routing AND probe layers). So "anchor to structural
  invariants, not key names" is a probe-authoring principle.

  Concrete candidates for a structural invariant on this fixture:
    1. Position/index     — Nth non-meta top-level field
    2. Type signature     — first list-of-dicts at top level
    3. Cardinality+pattern— exactly one top-level field matching a shape pattern

  Plus the broken baseline:
    0. Key name           — art.get("services")

Predecessor: probe-shape-routing-rename-keys-test.py (proved key-coupling at
both layers). This script asks which of Xiao Man's three candidates actually
survives which perturbation — a mutation suite for the *anchor*, not the
router.

Method (offline, no API — same T3 checksum domain):
  Locate the services-like array via each anchor, then run the existing P3
  leaf checks on that array.

  Perturbation cells (adversarial spectrum, extends the three-cell suite):
    honest      — unmodified T3
    rename_keys — services → components (Xiao Man's cell)
    reorder     — insert decoy scalar key before services (breaks Nth-field)
    type_wrap   — wrap list as {"items": [...]} (breaks list type signature)
    dual_list   — add second list-of-dicts decoy after services
    dual_first  — same decoy inserted *before* services (type latches wrong)

  Metrics per (anchor × perturbation), n good + n bad T3 artifacts:
    locate_rate   — finder returned a list usable by P3
    catch_rate    — among bad, P3 rejects (only counted when located;
                    unlocated bad = miss)
    false_reject  — among good, P3 rejects OR fail-to-locate (fail-closed:
                    cannot locate → treat as reject for specificity)

Claims:
  C1  key_name locate collapses on rename_keys (reproduce prior finding).
  C2  position survives rename, collapses on reorder.
  C3  type survives rename+reorder, collapses on type_wrap.
  C4  cardinality+pattern survives rename+reorder; collapses on dual_list
      and dual_first; type_wrap also collapses it (no list match).
  C4b type "survives" dual_list only when the true list is first; dual_first
      makes type latch the decoy → catch/FR collapse (order is not a type law).
  C5  No single anchor survives all cells → probe authoring needs a
      declared invariant class + a mutation suite, not "pick the cleverest."

Falsifiers:
  C2 fail → position still locates after reorder (definition too loose).
  C3 fail → type still locates after wrap (finder peeks inside wraps).
  C4 fail → cardinality still unique under dual_list.
  C4b fail → type still SURVIVE under dual_first.
  C5 fail → one anchor has locate≥0.95 and catch≥0.95 and FR≤0.05 on all cells.

Run:
  python probe-structural-invariant-anchor-test.py
  python probe-structural-invariant-anchor-test.py --n 40 --seed 7
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import random
import sys
from pathlib import Path
from typing import Any, Callable

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "probe-structural-invariant-anchor.json"

# ── T3 fixture (standalone copy) ──

EXPECT_P3 = [
    ("api", 8080, 10, 5000),
    ("worker", 8081, 20, 3000),
]


def make_good_t3(rng: random.Random) -> dict:
    art = {
        "services": [
            {
                "name": "api",
                "port": 8080,
                "limits": {"max_connections": 10, "timeout_ms": 5000},
            },
            {
                "name": "worker",
                "port": 8081,
                "limits": {"max_connections": 20, "timeout_ms": 3000},
            },
        ]
    }
    art["_meta"] = {"seed": rng.randint(0, 10_000), "ok": True}
    return art


def make_bad_t3(rng: random.Random) -> tuple[dict, str]:
    art = make_good_t3(rng)
    mode = rng.choice(["nested_limit", "port", "drop_leaf"])
    if mode == "nested_limit":
        art["services"][0]["limits"]["max_connections"] = 999
        kind = "nested_limit"
    elif mode == "port":
        art["services"][1]["port"] = 9999
        kind = "wrong_port"
    else:
        del art["services"][0]["limits"]["timeout_ms"]
        kind = "missing_leaf"
    return art, kind


# ── Anchors (Xiao Man's three + key_name baseline) ──

def _content_items(art: dict) -> list[tuple[str, Any]]:
    return [(k, v) for k, v in art.items() if not str(k).startswith("_")]


def _is_svc_list(v: Any) -> bool:
    """Loose type: list of dicts (position/type candidates)."""
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v)


def _is_svc_pattern(v: Any) -> bool:
    """Tight pattern: list of dicts with name+port+limits."""
    if not _is_svc_list(v):
        return False
    return all(
        "name" in x and "port" in x and "limits" in x for x in v
    )


def find_key_name(art: dict) -> Any:
    return art.get("services")


def find_position(art: dict, n: int = 0) -> Any:
    items = _content_items(art)
    if n >= len(items):
        return None
    return items[n][1]


def find_type(art: dict) -> Any:
    for _, v in _content_items(art):
        if _is_svc_list(v):
            return v
    return None


def find_cardinality(art: dict) -> Any:
    matches = [v for _, v in _content_items(art) if _is_svc_pattern(v)]
    if len(matches) == 1:
        return matches[0]
    return None


ANCHORS: dict[str, Callable[[dict], Any]] = {
    "key_name": find_key_name,
    "position": find_position,
    "type": find_type,
    "cardinality": find_cardinality,
}


# ── Perturbations ──

def pert_honest(art: dict) -> dict:
    out = copy.deepcopy(art)
    out["_mutate"] = "honest"
    return out


def pert_rename_keys(art: dict) -> dict:
    out = copy.deepcopy(art)
    if "services" in out:
        out["components"] = out.pop("services")
    out["_mutate"] = "rename_keys"
    return out


def pert_reorder(art: dict) -> dict:
    """Insert a decoy scalar as the first content key — breaks Nth=0 position."""
    out: dict[str, Any] = {"aa_decoy_scalar": 1}
    for k, v in art.items():
        if k.startswith("_"):
            continue
        out[k] = copy.deepcopy(v)
    if "_meta" in art:
        out["_meta"] = copy.deepcopy(art["_meta"])
    out["_mutate"] = "reorder"
    return out


def pert_type_wrap(art: dict) -> dict:
    """Wrap the services list in an object — breaks list type signature."""
    out = copy.deepcopy(art)
    if "services" in out and isinstance(out["services"], list):
        out["services"] = {"items": out["services"]}
    out["_mutate"] = "type_wrap"
    return out


def pert_dual_list(art: dict) -> dict:
    """Second list-of-dicts decoy after services — breaks 'exactly one'."""
    out = copy.deepcopy(art)
    out["decoy_services"] = [
        {"name": "decoy", "port": 1, "limits": {"max_connections": 1, "timeout_ms": 1}}
    ]
    out["_mutate"] = "dual_list"
    return out


def pert_dual_first(art: dict) -> dict:
    """Decoy list-of-dicts *before* services — type finder latches onto decoy."""
    out: dict[str, Any] = {
        "decoy_services": [
            {"name": "decoy", "port": 1, "limits": {"max_connections": 1, "timeout_ms": 1}}
        ]
    }
    for k, v in art.items():
        if k.startswith("_"):
            continue
        out[k] = copy.deepcopy(v)
    if "_meta" in art:
        out["_meta"] = copy.deepcopy(art["_meta"])
    out["_mutate"] = "dual_first"
    return out


PERTURBATIONS: dict[str, Callable[[dict], dict]] = {
    "honest": pert_honest,
    "rename_keys": pert_rename_keys,
    "reorder": pert_reorder,
    "type_wrap": pert_type_wrap,
    "dual_list": pert_dual_list,
    "dual_first": pert_dual_first,
}


# ── P3 leaf check on a located array ──

def p3_reject(services: Any) -> tuple[bool, str]:
    if not isinstance(services, list) or len(services) != 2:
        return True, "P3 services shape"
    for i, (name, port, mc, to) in enumerate(EXPECT_P3):
        if i >= len(services) or not isinstance(services[i], dict):
            return True, f"P3 missing[{i}]"
        svc = services[i]
        if svc.get("name") != name:
            return True, f"P3 name[{i}]"
        if svc.get("port") != port:
            return True, f"P3 port[{i}]"
        lim = svc.get("limits") or {}
        if lim.get("max_connections") != mc:
            return True, f"P3 max_conn[{i}]"
        if lim.get("timeout_ms") != to:
            return True, f"P3 timeout[{i}]"
    return False, "P3 ok"


def located_ok(v: Any) -> bool:
    return isinstance(v, list)


# ── Eval ──

def eval_cell(
    anchor: str,
    pert: str,
    goods: list[dict],
    bads: list[tuple[dict, str]],
) -> dict:
    finder = ANCHORS[anchor]
    mutate = PERTURBATIONS[pert]

    locate_good = 0
    locate_bad = 0
    catch = 0
    false_reject = 0
    miss_kinds: dict[str, int] = {}
    fr_reasons: dict[str, int] = {}

    for art in goods:
        mut = mutate(art)
        found = finder(mut)
        if located_ok(found):
            locate_good += 1
            rej, reason = p3_reject(found)
            if rej:
                false_reject += 1
                fr_reasons[reason] = fr_reasons.get(reason, 0) + 1
        else:
            # fail-closed: cannot locate → count as false reject
            false_reject += 1
            fr_reasons["unlocated"] = fr_reasons.get("unlocated", 0) + 1

    for art, kind in bads:
        mut = mutate(art)
        found = finder(mut)
        if located_ok(found):
            locate_bad += 1
            rej, _ = p3_reject(found)
            if rej:
                catch += 1
            else:
                miss_kinds[kind] = miss_kinds.get(kind, 0) + 1
        else:
            miss_kinds[f"unlocated:{kind}"] = miss_kinds.get(f"unlocated:{kind}", 0) + 1

    n_g, n_b = len(goods), len(bads)
    return {
        "anchor": anchor,
        "perturbation": pert,
        "n_good": n_g,
        "n_bad": n_b,
        "locate_rate_good": locate_good / n_g if n_g else 0.0,
        "locate_rate_bad": locate_bad / n_b if n_b else 0.0,
        "locate_rate": (locate_good + locate_bad) / (n_g + n_b) if (n_g + n_b) else 0.0,
        "catch_rate": catch / n_b if n_b else 0.0,
        "false_reject_rate": false_reject / n_g if n_g else 0.0,
        "miss_kinds": miss_kinds,
        "fr_reasons": fr_reasons,
    }


def survival_matrix(cells: list[dict]) -> dict[str, dict[str, str]]:
    """Per anchor×pert: SURVIVE if locate≥0.95 and catch≥0.95 and FR≤0.05."""
    out: dict[str, dict[str, str]] = {}
    for c in cells:
        a, p = c["anchor"], c["perturbation"]
        out.setdefault(a, {})
        ok = (
            c["locate_rate"] >= 0.95
            and c["catch_rate"] >= 0.95
            and c["false_reject_rate"] <= 0.05
        )
        out[a][p] = "SURVIVE" if ok else "FAIL"
    return out


def check_claims(matrix: dict[str, dict[str, str]]) -> dict[str, Any]:
    def cell(a: str, p: str) -> str:
        return matrix[a][p]

    c1 = cell("key_name", "rename_keys") == "FAIL"
    c2 = (
        cell("position", "rename_keys") == "SURVIVE"
        and cell("position", "reorder") == "FAIL"
    )
    c3 = (
        cell("type", "rename_keys") == "SURVIVE"
        and cell("type", "reorder") == "SURVIVE"
        and cell("type", "type_wrap") == "FAIL"
    )
    c4 = (
        cell("cardinality", "rename_keys") == "SURVIVE"
        and cell("cardinality", "reorder") == "SURVIVE"
        and cell("cardinality", "dual_list") == "FAIL"
        and cell("cardinality", "dual_first") == "FAIL"
    )
    c4b = cell("type", "dual_first") == "FAIL"
    # C5: no anchor survives all perturbations
    all_perts = list(PERTURBATIONS.keys())
    any_full = any(
        all(matrix[a][p] == "SURVIVE" for p in all_perts) for a in ANCHORS
    )
    c5 = not any_full

    return {
        "C1_key_name_dies_on_rename": c1,
        "C2_position_survives_rename_dies_reorder": c2,
        "C3_type_survives_rename_reorder_dies_wrap": c3,
        "C4_cardinality_dies_on_dual_list": c4,
        "C4b_type_dies_when_decoy_first": c4b,
        "C5_no_universal_anchor": c5,
        "all_hold": all([c1, c2, c3, c4, c4b, c5]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="good/bad count per cell")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    goods = [make_good_t3(rng) for _ in range(args.n)]
    bads = [make_bad_t3(rng) for _ in range(args.n)]

    cells = []
    for anchor in ANCHORS:
        for pert in PERTURBATIONS:
            cells.append(eval_cell(anchor, pert, goods, bads))

    matrix = survival_matrix(cells)
    claims = check_claims(matrix)

    # Compact table for stdout
    print("anchor × perturbation — SURVIVE = locate≥0.95 ∧ catch≥0.95 ∧ FR≤0.05")
    print(f"{'anchor':<14}", end="")
    for p in PERTURBATIONS:
        print(f"{p:>12}", end="")
    print()
    for a in ANCHORS:
        print(f"{a:<14}", end="")
        for p in PERTURBATIONS:
            print(f"{matrix[a][p]:>12}", end="")
        print()

    print("\nRates (locate / catch / FR):")
    for c in cells:
        print(
            f"  {c['anchor']:<12} {c['perturbation']:<12} "
            f"loc={c['locate_rate']:.2f} catch={c['catch_rate']:.2f} "
            f"FR={c['false_reject_rate']:.2f}"
        )

    print("\nClaims:", json.dumps(claims, indent=2))

    payload = {
        "claim": (
            "Xiao Man structural-invariant candidates vs key_name baseline "
            "under five T3 perturbations (mutation suite for probe anchors)."
        ),
        "n_per_arm": args.n,
        "seed": args.seed,
        "anchors": list(ANCHORS.keys()),
        "perturbations": list(PERTURBATIONS.keys()),
        "survive_rule": "locate≥0.95 and catch≥0.95 and false_reject≤0.05",
        "survival_matrix": matrix,
        "claims": claims,
        "cells": cells,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
