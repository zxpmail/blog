# -*- coding: utf-8 -*-
"""Merge-displacement grid — Alexey Spinov's "76/720" wiring-failure shape.

Claim under test (Alexey, Part 6 dev.to thread, 2026-07):
    At a 2% review budget, in 76 of 720 cells, merging a second stream S into
    the divergence stream D under *arrival order* catches FEWER true misses
    than D alone — S arrivals displace D arrivals at the budget cap k instead
    of by miss-yield. Under *precision order*: 0 of 720 cells.

What this script is:
    Empirical test of that *shape* on the df_proxy fixture (single-judge
    all-run traffic, N=585 across 3 models). NOT a reproduction of Alexey's
    720-cell grid — his grid was likely parametric (π·h·r_m model with
    synthetic severity sweeps); this script uses real judge runs.

Why a sibling script (not an edit to rank-inside-stream-test.py):
    The original caps BUDGETS at {1%,2%,5%} — at those budgets D@arrival=0
    on df_proxy (D=conf<0.9 is miss-starved: 2 MISS in D, buried in 585).
    Extending BUDGETS in-place would change n_cells and break the published
    Part 15 §2 numbers (6/18, 10→29, etc.). This script runs an independent
    grid at higher budgets where D@arrival has a chance to exceed 0.

Grid (288 cells per model × 3 models = 864 cells, but reported per-model
AND pooled):
    models   ∈ {qwen3-0.5b, gemma3-latest, deepseek-v4-flash}         (3)
    budgets  ∈ {1, 2, 5, 10, 15, 20, 25, 30}%                         (8)
    added_S  ∈ {UHC, class, UHC∧class, T2}                            (4)
    ordering ∈ {arrival, precision_desc, oracle}                      (3)

Per cell:
    D_catch      = catch(D alone, ordering, k)
    merge_catch  = catch(D ∪ S, ordering, k)  [union, dedup by id]
    delta        = merge_catch - D_catch
    displacement = (delta < 0)

Aggregate per ordering (pooled across models/budgets/S):
    n_cells_displacement / n_cells_total

Falsifier:
    If displacement rate under precision_desc ≈ displacement rate under
    arrival → Alexey's shape does not reproduce on this fixture.
    If D@arrival = 0 across all (model, budget) → fixture is structurally
    miss-starved for this claim; report NULL, do not force a number.

Scope (hard):
    - df_proxy traffic only. Other fixtures (multiperspective N=60) too
      small for a displacement grid.
    - Real judge outputs; no synthetic noise injection.
    - D is conf<0.9 (matches escalation-population-mismatch.json D
      definition); S streams inherit rank-inside-stream-test.py semantics.
    - Not a production warrant; not a causal model of trigger wiring.

Dependencies: none (pure Python, stdlib).
Run:
    python scripts/merge-displacement-grid-test.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT_PATH = RESULTS / "merge-displacement-grid.json"

HIGH = 0.9
BUDGETS = (0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
ADDED_STREAMS = ("UHC", "class", "UHC∧class", "T2")
ORDERINGS = ("arrival", "precision_desc", "oracle")
DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


# ── loader (mirrors rank-inside-stream-test.py df_proxy path) ────────────


def load_df_proxy() -> list[dict]:
    """One item per judge run (pass or reject) — full traffic for budget %."""
    items = []
    order = 0
    for model in DF_MODELS:
        path = RESULTS / f"{model}.jsonl"
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                sid = obj["id"]
                legit = bool(obj.get("is_legit"))
                for v in obj.get("run_verdicts", []):
                    conf = v.get("confidence")
                    if conf is None:
                        continue
                    conf = float(conf)
                    passes = bool(v.get("passes"))
                    is_miss = passes and (not legit) and v.get("error_type") == "MISS"
                    items.append(
                        {
                            "fixture": "df_proxy",
                            "model": model,
                            "id": sid,
                            "order": order,
                            "is_miss": bool(is_miss),
                            "reversal": is_reversal(sid),
                            "conf": conf,
                            "uhc": conf >= HIGH,
                            "split": conf < HIGH,
                            "unanimous_pass": passes and conf >= HIGH,
                            "is_pass_path": passes,
                        }
                    )
                    order += 1
    return items


# ── stream membership (matches rank-inside-stream-test.py) ───────────────


def in_stream(item: dict, stream: str) -> bool:
    rev = item["reversal"]
    if stream == "D":
        return bool(item["split"])
    if stream == "class":
        return bool(rev)
    if stream == "UHC":
        return bool(item["uhc"])
    if stream == "UHC∧class":
        return bool(item["uhc"] and rev)
    if stream == "T2":
        return bool(rev and item["unanimous_pass"])
    raise ValueError(stream)


def union(d_items: list[dict], s_items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for x in d_items + s_items:
        i = id(x)
        if i in seen:
            continue
        seen.add(i)
        out.append(x)
    return out


# ── ordering ─────────────────────────────────────────────────────────────


def ordered(items: list[dict], ordering: str) -> list[dict]:
    if ordering == "arrival":
        return sorted(items, key=lambda x: x["order"])
    if ordering == "precision_desc":
        # conf desc, ties broken by arrival (stable)
        return sorted(items, key=lambda x: (-x["conf"], x["order"]))
    if ordering == "oracle":
        # MISS first, ties by arrival — ceiling, peeks at label
        return sorted(items, key=lambda x: (not x["is_miss"], x["order"]))
    raise ValueError(ordering)


def take_k(items: list[dict], k: int) -> list[dict]:
    return items[:k] if k > 0 else []


def miss_caught(items: list[dict]) -> int:
    return sum(1 for x in items if x["is_miss"])


# ── grid evaluation ──────────────────────────────────────────────────────


def evaluate_model(model: str, all_items: list[dict]) -> dict:
    items = [x for x in all_items if x["model"] == model]
    n = len(items)
    n_miss = sum(1 for x in items if x["is_miss"])

    # Pre-bucket stream memberships once per model.
    buckets = {"D": [x for x in items if in_stream(x, "D")]}
    for s in ADDED_STREAMS:
        buckets[s] = [x for x in items if in_stream(x, s)]

    cells = []
    d_arrival_nonzero_budgets = []  # budgets where D@arrival > 0

    for b in BUDGETS:
        k = int(n * b)  # floor
        d_items = buckets["D"]
        # Quick check: does D@arrival ever exceed 0 at this budget?
        d_arr = miss_caught(take_k(ordered(d_items, "arrival"), k))
        if d_arr > 0:
            d_arrival_nonzero_budgets.append(b)

        for s in ADDED_STREAMS:
            merged = union(d_items, buckets[s])
            for ordering in ORDERINGS:
                d_catch = miss_caught(take_k(ordered(d_items, ordering), k))
                m_catch = miss_caught(take_k(ordered(merged, ordering), k))
                delta = m_catch - d_catch
                cells.append(
                    {
                        "model": model,
                        "budget": b,
                        "k": k,
                        "added_S": s,
                        "ordering": ordering,
                        "D_n": len(d_items),
                        "D_miss": miss_caught(d_items),
                        "merged_n": len(merged),
                        "merged_miss": miss_caught(merged),
                        "D_catch": d_catch,
                        "merge_catch": m_catch,
                        "delta": delta,
                        "displacement": delta < 0,
                    }
                )

    # Aggregate
    def tally(ordering: str) -> dict:
        sub = [c for c in cells if c["ordering"] == ordering]
        n_disp = sum(1 for c in sub if c["displacement"])
        n_zero_d = sum(1 for c in sub if c["D_catch"] == 0)
        n_total = len(sub)
        return {
            "ordering": ordering,
            "n_cells": n_total,
            "n_displacement": n_disp,
            "displacement_rate": n_disp / n_total if n_total else 0.0,
            "n_cells_with_D_catch_0": n_zero_d,
            "n_cells_with_D_catch_gt_0": n_total - n_zero_d,
            "displacement_rate_among_D_gt0": (
                n_disp / (n_total - n_zero_d) if (n_total - n_zero_d) > 0 else 0.0
            ),
        }

    per_ordering = [tally(o) for o in ORDERINGS]

    # Per-budget displacement counts (pooled across S) under arrival vs precision_desc
    by_budget = []
    for b in BUDGETS:
        row = {"budget": b, "k": int(n * b)}
        for ordering in ("arrival", "precision_desc", "oracle"):
            sub = [c for c in cells if c["budget"] == b and c["ordering"] == ordering]
            n_disp = sum(1 for c in sub if c["displacement"])
            row[f"n_displacement_{ordering}"] = n_disp
            row[f"n_total_{ordering}"] = len(sub)
        by_budget.append(row)

    return {
        "model": model,
        "n_traffic": n,
        "n_miss": n_miss,
        "d_stream_size": len(buckets["D"]),
        "d_stream_miss": miss_caught(buckets["D"]),
        "d_arrival_nonzero_budgets": d_arrival_nonzero_budgets,
        "tally_per_ordering": per_ordering,
        "by_budget": by_budget,
        "cells": cells,
    }


def verdict_block(reports: list[dict]) -> str:
    # Pooled across models
    pooled = {}
    for ordering in ORDERINGS:
        n_disp = sum(
            c["displacement"]
            for r in reports
            for c in r["cells"]
            if c["ordering"] == ordering
        )
        n_total = sum(
            1
            for r in reports
            for c in r["cells"]
            if c["ordering"] == ordering
        )
        n_d0 = sum(
            1
            for r in reports
            for c in r["cells"]
            if c["ordering"] == ordering and c["D_catch"] == 0
        )
        pooled[ordering] = (n_disp, n_total, n_d0)

    parts = []
    arr_disp, arr_total, arr_d0 = pooled["arrival"]
    prec_disp, prec_total, prec_d0 = pooled["precision_desc"]
    orc_disp, orc_total, orc_d0 = pooled["oracle"]

    arr_disp_rate = arr_disp / arr_total if arr_total else 0.0
    prec_disp_rate = prec_disp / prec_total if prec_total else 0.0

    if arr_total == arr_d0:
        parts.append(
            "STRUCTURAL NULL: D@arrival = 0 in every cell — fixture is "
            "miss-starved for D, displacement shape cannot show. Do not "
            "report a 76/N number."
        )
    else:
        parts.append(
            f"Arrival-order displacement: {arr_disp}/{arr_total} cells "
            f"({100*arr_disp_rate:.1f}%) — {arr_d0}/{arr_total} had D@arrival=0 "
            f"(excluded from rate)."
        )
        parts.append(
            f"Precision-order displacement: {prec_disp}/{prec_total} cells "
            f"({100*prec_disp_rate:.1f}%)."
        )
        if orc_disp > 0:
            parts.append(
                f"Oracle displacement: {orc_disp}/{orc_total} — unexpected; "
                f"oracle should not displace."
            )

        if arr_disp == 0 and prec_disp == 0:
            parts.append(
                "SHAPE NULL: no displacement under either ordering on this "
                "fixture at the swept budgets."
            )
        elif prec_disp == 0 and arr_disp > 0:
            parts.append(
                "SHAPE CONFIRMED (qualitative): arrival displaces, precision "
                "does not. Magnitude is fixture-specific and not 76/720."
            )
        elif prec_disp > 0 and arr_disp > 0 and arr_disp_rate > 2 * prec_disp_rate:
            parts.append(
                "SHAPE PARTIAL: arrival displacement rate > 2× precision rate, "
                "but precision does not hit zero."
            )
        else:
            parts.append(
                "SHAPE WEAKENED: precision-order displacement rate is within "
                "2× of arrival rate — claim does not reproduce cleanly."
            )
    return " ".join(parts)


def print_report(reports: list[dict], verdict: str) -> None:
    print("=== Merge-displacement grid — Alexey's 76/720 shape test ===")
    print(f"Fixture: df_proxy  Models: {', '.join(DF_MODELS)}")
    print(f"Budgets: {', '.join(f'{b:.0%}' for b in BUDGETS)}")
    print(f"Added streams S: {', '.join(ADDED_STREAMS)}")
    print(f"Orderings: {', '.join(ORDERINGS)}")
    print()
    for r in reports:
        print(f"--- Model: {r['model']} ---")
        print(
            f"  traffic N={r['n_traffic']}  total MISS={r['n_miss']}  "
            f"D-stream size={r['d_stream_size']}  D-stream MISS={r['d_stream_miss']}"
        )
        print(
            f"  D@arrival > 0 at budgets: "
            f"{[f'{b:.0%}' for b in r['d_arrival_nonzero_budgets']] or 'NONE'}"
        )
        print()
        print(
            f"  {'ordering':<14} {'disp_cells':>10} {'/total':>8} "
            f"{'D=0_cells':>10} {'rate_D>0':>10}"
        )
        for t in r["tally_per_ordering"]:
            print(
                f"  {t['ordering']:<14} {t['n_displacement']:>10} "
                f"/{t['n_cells']:<7} {t['n_cells_with_D_catch_0']:>10} "
                f"{100*t['displacement_rate_among_D_gt0']:>9.1f}%"
            )
        print()
        print(
            f"  {'budget':>7} {'k':>4} "
            f"{'arr_disp':>9} {'prec_disp':>10} {'orc_disp':>9}"
        )
        for bb in r["by_budget"]:
            print(
                f"  {bb['budget']:>7.0%} {bb['k']:>4} "
                f"{bb['n_displacement_arrival']:>6}/{bb['n_total_arrival']:<3} "
                f"{bb['n_displacement_precision_desc']:>6}/{bb['n_total_precision_desc']:<4} "
                f"{bb['n_displacement_oracle']:>6}/{bb['n_total_oracle']:<3}"
            )
        print()

    print("=== Pooled verdict ===")
    print(verdict)


def main() -> None:
    all_items = load_df_proxy()
    reports = [evaluate_model(m, all_items) for m in DF_MODELS]
    verdict = verdict_block(reports)
    print_report(reports, verdict)

    payload = {
        "claim": (
            "Alexey's 76/720 wiring-failure shape: merging S into D under "
            "arrival order can catch fewer MISSes than D alone; precision "
            "order does not."
        ),
        "fixture": "df_proxy",
        "budgets": list(BUDGETS),
        "added_streams": list(ADDED_STREAMS),
        "orderings": list(ORDERINGS),
        "models": list(DF_MODELS),
        "scope": (
            "Empirical test on df_proxy judge outputs. NOT a reproduction of "
            "Alexey's 720-cell parametric grid. If D@arrival=0 in every cell, "
            "the shape cannot show — report NULL, do not force a number."
        ),
        "per_model": reports,
        "pooled_verdict": verdict,
    }
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(blob, encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    print(f"\nWrote {OUT_PATH}")
    print(f"sha256(json)={digest}")


if __name__ == "__main__":
    main()
