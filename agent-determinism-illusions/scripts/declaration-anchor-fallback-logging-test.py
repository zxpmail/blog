# -*- coding: utf-8 -*-
"""Fallback-with-logging + retirement signal — Xiao Man lock (2026-08-01).

Claim under test:
  Primary synonym_list + secondary structural, with disagreement logging (no vote),
  is a design that stays falsifiable in traffic: the *cell* where disagreements
  cluster tells you which side is under pressure — not a committee at commit time.

Method:
  Reuse the 8-perturbation T3 fixture from declaration-anchor-survival-test.py.
  Gate = primary resolution only. Secondary runs in parallel; log agree/disagree.

  Part A — disagreement ledger (n=8 cells): for each perturbation, record
    primary_resolved, secondary_resolved, agree?, primary_ok, secondary_ok.
  Part B — two production mixes (n=400 draws each, seed=7):
    rename_heavy:   mass on P0/P1/P2/P3 (declaration-rename world)
    shape_clone_heavy: mass on P0/P3/P6/P7 (shape-clone world)
  For each mix: disagreement rate, histogram of disagree cells, and a
  retirement read — on the modal disagree cell, which side mismatches truth?

Expected:
  Part A: disagree exactly on P2 (primary dies, secondary lives) and P6
          (primary lives, secondary dies). Agree elsewhere.
  Part B:
    rename_heavy → disagreements cluster on P2 → primary under pressure
                   (known blind spot live; human decl-review must cover /
                   widen synonyms — do not open a vote).
    shape_clone_heavy → disagreements cluster on P6 → secondary under pressure
                   (primary never dies on that cell; secondary is telemetry
                   noise for this traffic — do not promote secondary to co-gate).

Falsification:
  If Part A disagrees on more/fewer than {P2,P6}; or both mixes share the same
  modal disagree cell; or modal cell has both sides wrong / both right →
  "cluster cell ⇒ which side to retire" is not a usable decision rule.

Dependencies: stdlib only.
Run: python declaration-anchor-fallback-logging-test.py
"""

from __future__ import annotations

import copy
import io
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "declaration-anchor-fallback-logging.json"
SEED = 7
N_DRAWS = 400


# ── Base + perturbations（与 survival 脚本同夹具）──

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
    a = copy.deepcopy(art)
    for svc in a["services"]:
        svc["limits"] = [10, 5000]
    return a


def p_cardinality_corrupt(art):
    a = copy.deepcopy(art)
    a["services"].append({"name": "dummy", "port": 9999,
                          "limits": {"max_connections": 1, "timeout_ms": 100}})
    return a


def p6_decoy_with_limits(art):
    a = {}
    a["connections"] = [{"limits": {"x": 1}}, {"limits": {"x": 2}}]
    for k, v in art.items():
        a[k] = copy.deepcopy(v)
    return a


def p7_inner_field_rename(art):
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

TRUE_KEY = {
    "P0_baseline": "services",
    "P1_rename_in_decl": "components",
    "P2_rename_outside_decl": "instances",
    "P3_decoy": "services",
    "P4_shape_corrupt": "services",
    "P5_cardinality_corrupt": "services",
    "P6_decoy_with_limits": "services",
    "P7_inner_field_rename": "services",
}


# ── Anchors：主 synonym_list / 次 structural ──

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


# 生产混合权重（其余扰动给极小质量，避免零）
MIXES = {
    "rename_heavy": {
        "P0_baseline": 0.35,
        "P1_rename_in_decl": 0.20,
        "P2_rename_outside_decl": 0.25,
        "P3_decoy": 0.12,
        "P4_shape_corrupt": 0.02,
        "P5_cardinality_corrupt": 0.02,
        "P6_decoy_with_limits": 0.02,
        "P7_inner_field_rename": 0.02,
    },
    "shape_clone_heavy": {
        "P0_baseline": 0.30,
        "P1_rename_in_decl": 0.05,
        "P2_rename_outside_decl": 0.05,
        "P3_decoy": 0.15,
        "P4_shape_corrupt": 0.05,
        "P5_cardinality_corrupt": 0.05,
        "P6_decoy_with_limits": 0.30,
        "P7_inner_field_rename": 0.05,
    },
}


def eval_cell(pert_name: str, pert_fn, base: dict) -> dict:
    """评估单格：主/次解析、是否同意、谁对。"""
    art = pert_fn(base)
    truth = TRUE_KEY[pert_name]
    primary = anchor_synonym_list(art)
    secondary = anchor_structural(art)
    return {
        "perturbation": pert_name,
        "truth": truth,
        "primary_resolved": primary,
        "secondary_resolved": secondary,
        "agree": primary == secondary,
        "primary_ok": primary == truth,
        "secondary_ok": secondary == truth,
        "gate_ok": primary == truth,  # 门只听主锚
    }


def retirement_read(modal_cell: str, cell_row: dict) -> dict:
    """分歧众数格上：哪一侧与 truth 不符 → 退役压力落在哪一侧。"""
    p_ok = cell_row["primary_ok"]
    s_ok = cell_row["secondary_ok"]
    if not p_ok and s_ok:
        pressure = "primary"
        note = (
            "Modal disagree cell is a known primary death; "
            "human declaration cover / synonym widen — not a commit-time vote."
        )
    elif p_ok and not s_ok:
        pressure = "secondary"
        note = (
            "Modal disagree cell is one the primary never dies on; "
            "secondary is telemetry noise for this traffic — do not promote to co-gate."
        )
    elif not p_ok and not s_ok:
        pressure = "both"
        note = "Both wrong on modal cell — logging alone does not pick a side."
    else:
        pressure = "neither"
        note = "Both right yet disagree (should not happen if agree⇔same key)."
    return {
        "modal_disagree_cell": modal_cell,
        "primary_ok_on_modal": p_ok,
        "secondary_ok_on_modal": s_ok,
        "retirement_pressure": pressure,
        "note": note,
    }


def run_mix(name: str, weights: dict, ledger_by_pert: dict, rng: random.Random) -> dict:
    """按权重抽样扰动，累计分歧直方图与门错误率。"""
    names = list(weights.keys())
    probs = [weights[n] for n in names]
    disagree_cells: list[str] = []
    primary_errs = 0
    secondary_errs = 0
    disagrees = 0
    for _ in range(N_DRAWS):
        pert = rng.choices(names, weights=probs, k=1)[0]
        row = ledger_by_pert[pert]
        if not row["primary_ok"]:
            primary_errs += 1
        if not row["secondary_ok"]:
            secondary_errs += 1
        if not row["agree"]:
            disagrees += 1
            disagree_cells.append(pert)
    hist = Counter(disagree_cells)
    modal = hist.most_common(1)[0][0] if hist else None
    read = retirement_read(modal, ledger_by_pert[modal]) if modal else {
        "modal_disagree_cell": None,
        "retirement_pressure": "none",
        "note": "No disagreements in mix.",
    }
    return {
        "mix": name,
        "n": N_DRAWS,
        "weights": weights,
        "disagree_rate": disagrees / N_DRAWS,
        "primary_error_rate": primary_errs / N_DRAWS,
        "secondary_error_rate": secondary_errs / N_DRAWS,
        "disagree_histogram": dict(hist),
        "retirement": read,
    }


def main():
    base = base_good_t3()
    print("═" * 72)
    print("  Fallback-with-logging + retirement signal")
    print("  primary=synonym_list  secondary=structural  (no vote)")
    print("═" * 72)

    # Part A：分歧台账
    print("\n  Part A — disagreement ledger")
    ledger = []
    ledger_by_pert = {}
    disagree_set = []
    for pert_name, pert_fn in PERTURBATIONS:
        row = eval_cell(pert_name, pert_fn, base)
        ledger.append(row)
        ledger_by_pert[pert_name] = row
        mark = "AGREE" if row["agree"] else "DISAGREE"
        print(
            f"    {pert_name:<26} {mark:<8} "
            f"pri={row['primary_resolved'] or 'None':<12} "
            f"sec={row['secondary_resolved'] or 'None':<12} "
            f"pri_ok={row['primary_ok']} sec_ok={row['secondary_ok']}"
        )
        if not row["agree"]:
            disagree_set.append(pert_name)

    print(f"\n  Disagree cells: {disagree_set}")

    # Part B：两种流量混合
    print(f"\n  Part B — production mixes (n={N_DRAWS}, seed={SEED})")
    rng = random.Random(SEED)
    mix_results = []
    for mix_name, weights in MIXES.items():
        # 每个 mix 用独立但可复现的子序列：推进同一 rng
        result = run_mix(mix_name, weights, ledger_by_pert, rng)
        mix_results.append(result)
        r = result["retirement"]
        print(f"\n    [{mix_name}]")
        print(f"      disagree_rate={result['disagree_rate']:.3f}  "
              f"primary_err={result['primary_error_rate']:.3f}  "
              f"secondary_err={result['secondary_error_rate']:.3f}")
        print(f"      hist={result['disagree_histogram']}")
        print(f"      pressure → {r['retirement_pressure']}  "
              f"(modal={r['modal_disagree_cell']})")
        print(f"      {r['note']}")

    # 判决
    expected_disagree = {"P2_rename_outside_decl", "P6_decoy_with_limits"}
    actual_disagree = set(disagree_set)
    part_a_ok = actual_disagree == expected_disagree

    pressures = {m["mix"]: m["retirement"]["retirement_pressure"] for m in mix_results}
    part_b_ok = (
        pressures.get("rename_heavy") == "primary"
        and pressures.get("shape_clone_heavy") == "secondary"
    )

    print("\n  Verdict:")
    print(f"    Part A (disagree={{P2,P6}}): {'PASS' if part_a_ok else 'FAIL'} "
          f"got {sorted(actual_disagree)}")
    print(f"    Part B (rename→primary pressure, shape→secondary pressure): "
          f"{'PASS' if part_b_ok else 'FAIL'} got {pressures}")
    print()

    out = {
        "experiment": "declaration-anchor-fallback-logging",
        "question": (
            "Does primary+secondary disagreement logging yield a usable "
            "retirement signal under different production mixes — without voting?"
        ),
        "context": (
            "Xiao Man 2026-08-01 lock: failure mode over rate; synonym_list "
            "primary; fallback-with-logging as design not compromise."
        ),
        "primary": "synonym_list",
        "secondary": "structural",
        "seed": SEED,
        "n_draws_per_mix": N_DRAWS,
        "part_a_ledger": ledger,
        "part_a_disagree_cells": disagree_set,
        "part_b_mixes": mix_results,
        "verdict": {
            "part_a_pass": part_a_ok,
            "part_b_pass": part_b_ok,
            "pass": part_a_ok and part_b_ok,
        },
        "interpretation": (
            "Disagreement is not a vote request. The modal disagree cell under "
            "traffic says which side is under pressure: P2-cluster → primary "
            "(cover with declaration review); P6-cluster → secondary (keep as "
            "telemetry, do not promote). Same gate, different retirement reads."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {OUT}")


if __name__ == "__main__":
    main()
