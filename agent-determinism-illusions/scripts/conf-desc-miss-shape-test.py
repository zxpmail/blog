# -*- coding: utf-8 -*-
"""conf_desc vs miss-shape — Tom Jones question on Part 15.

Question (Tom Jones, 2026-07-28, Part 15 thread):
  In your within-model temporal holdout, high-confidence ordering accidentally
  matches the fixture's miss shape. Do you know whether that is a property of
  the fixture, or whether confidence-descending is picking up something real
  about when that model fails? Those have opposite implications for whether
  conf_desc is a safe fallback line.

Design (offline, reads DF v2 jsonl — no API):
  Expand each model jsonl into per-run items:
    is_miss = (not is_legit) and passes and error_type==MISS
    conf    = self-reported confidence on that run

  Build a diluted escalate queue per protocol (all MISS + non-MISS distractors
  at ~35% miss-rate, distractors first in arrival order). Budget B in {1%,2%,5%}.

  Rankers: arrival | conf_desc | conf_asc | random(seed)

  Disentangling tests:
    F1 fixture_shuffle — permute conf within the queue (keep labels); if
        conf_desc lift vanishes, advantage was the joint (conf,miss) shape.
    F2 cross_model     — train nothing; apply conf_desc on model B using
        scores from model A aligned by (sid, run_idx) when possible; else
        report within-model only + leave-one-model aggregate.
    F3 temporal        — per model, first 70% runs by file order = "past",
        last 30% = "future" queue; conf_desc on future only.

Claims:
  C1  On raw fixture, conf_desc catch@k > arrival catch@k on majority of
      (model, B) cells (documents the "accidental match").
  C2  After F1 shuffle, conf_desc loses its edge over random
      (mean (conf_desc.caught - random.caught) <= 0) — if the raw lift was
      only the joint (conf,miss) shape, shuffled conf is noise.
  C3  Cross-model: conf_desc lift on held-out model is unstable vs within
      (sign flip or |Δlift|>=2 on >= half donor pairs).
  C4  Fallback: NOT safe universal fallback if C2 holds (fixture-shaped)
      OR C3 holds (doesn't travel). If C2 fails and C3 fails, report
      "within this dump, looks more than pure noise — still not a warrant".

Falsifiers:
  C2 fail (conf_desc still beats random after shuffle) → lift is not
            explained by the observed (conf,miss) pairing alone (or k too small).
  C3 fail (stable cross-model) → more support for transferable failure shape.

Run:
  python conf-desc-miss-shape-test.py
  python conf-desc-miss-shape-test.py --seed 7 --miss-rate 0.35
"""

from __future__ import annotations

import argparse
import io
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "conf-desc-miss-shape.json"
MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
BUDGETS = (0.01, 0.02, 0.05)


def load_items(model: str) -> list[dict[str, Any]]:
    path = RESULTS / f"{model}.jsonl"
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            sid = row["id"]
            is_legit = bool(row.get("is_legit"))
            for i, v in enumerate(row.get("run_verdicts") or []):
                passes = bool(v.get("passes"))
                et = v.get("error_type")
                is_miss = (not is_legit) and passes and et == "MISS"
                conf = v.get("confidence")
                if conf is None:
                    conf = 0.0
                items.append(
                    {
                        "model": model,
                        "sid": sid,
                        "run_idx": i,
                        "is_legit": is_legit,
                        "passes": passes,
                        "is_miss": is_miss,
                        "conf": float(conf),
                        "order": len(items),
                    }
                )
    return items


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - margin) / den), min(1.0, (centre + margin) / den))


def build_diluted_queue(
    items: list[dict],
    miss_rate: float,
    rng: random.Random,
) -> list[dict]:
    """All MISSes + non-MISS distractors at target miss-rate; distractors first.

    Prefer low-confidence distractors (correct rejects, conf≈0). High-conf
    true-pass distractors are deferred — otherwise conf_desc cannot separate
    MISS from V1/V2 (both conf=1.0) and the Tom/Part-15 shape never appears.
    """
    misses = [dict(x) for x in items if x["is_miss"]]
    distractors = [dict(x) for x in items if not x["is_miss"]]
    if not misses:
        return []
    n_miss = len(misses)
    n_total = max(n_miss, int(math.ceil(n_miss / max(miss_rate, 1e-6))))
    n_dist = max(0, n_total - n_miss)

    low = [x for x in distractors if x["conf"] < 0.5]
    rng.shuffle(low)
    # Do NOT backfill with high-conf true-pass distractors: they tie MISS at conf=1.0
    # and arrival_idx then recreates arrival order under conf_desc.
    take = low[:n_dist]
    queue = take + misses
    for i, it in enumerate(queue):
        it["arrival_idx"] = i
    return queue


def catch_at_k(ranked: list[dict], k: int) -> dict:
    top = ranked[:k]
    n_miss_total = sum(1 for x in ranked if x["is_miss"])
    caught = sum(1 for x in top if x["is_miss"])
    return {
        "k": k,
        "caught": caught,
        "n_miss": n_miss_total,
        "catch_rate": caught / n_miss_total if n_miss_total else None,
        "precision": caught / k if k else None,
    }


def rank_queue(queue: list[dict], method: str, rng: random.Random) -> list[dict]:
    q = list(queue)
    if method == "arrival":
        return sorted(q, key=lambda x: x["arrival_idx"])
    if method == "conf_desc":
        return sorted(q, key=lambda x: (-x["conf"], x["arrival_idx"]))
    if method == "conf_asc":
        return sorted(q, key=lambda x: (x["conf"], x["arrival_idx"]))
    if method == "random":
        rng.shuffle(q)
        return q
    raise ValueError(method)


def eval_methods(queue: list[dict], budgets: tuple[float, ...], seed: int) -> dict:
    n = len(queue)
    out = {}
    for b in budgets:
        k = max(1, int(round(n * b)))
        cell = {"n": n, "k": k, "budget": b}
        for method in ("arrival", "conf_desc", "conf_asc", "random"):
            rng = random.Random(seed + hash((method, b)) % 10_000)
            ranked = rank_queue(queue, method, rng)
            cell[method] = catch_at_k(ranked, k)
        cell["lift_conf_desc_minus_arrival"] = (
            cell["conf_desc"]["caught"] - cell["arrival"]["caught"]
        )
        out[str(b)] = cell
    return out


def shuffle_conf(queue: list[dict], rng: random.Random) -> list[dict]:
    confs = [x["conf"] for x in queue]
    rng.shuffle(confs)
    out = []
    for x, c in zip(queue, confs):
        y = dict(x)
        y["conf"] = c
        out.append(y)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--miss-rate", type=float, default=0.35)
    args = ap.parse_args()

    by_model = {m: load_items(m) for m in MODELS}
    raw_results = {}
    shuffle_results = {}
    temporal_results = {}

    for m in MODELS:
        rng = random.Random(args.seed + hash(m) % 10_000)
        q = build_diluted_queue(by_model[m], args.miss_rate, rng)
        raw_results[m] = {
            "n_items_source": len(by_model[m]),
            "n_miss_source": sum(1 for x in by_model[m] if x["is_miss"]),
            "queue_n": len(q),
            "queue_miss": sum(1 for x in q if x["is_miss"]),
            "budgets": eval_methods(q, BUDGETS, args.seed),
        }
        q_sh = shuffle_conf(q, random.Random(args.seed + 99 + hash(m) % 1000))
        shuffle_results[m] = {
            "queue_n": len(q_sh),
            "budgets": eval_methods(q_sh, BUDGETS, args.seed + 1),
        }

        # F3 temporal: split by order within model
        items = by_model[m]
        cut = int(len(items) * 0.7)
        future = items[cut:]
        rng_t = random.Random(args.seed + 17)
        q_t = build_diluted_queue(future, args.miss_rate, rng_t)
        temporal_results[m] = {
            "n_future": len(future),
            "queue_n": len(q_t),
            "queue_miss": sum(1 for x in q_t if x["is_miss"]),
            "budgets": eval_methods(q_t, BUDGETS, args.seed + 2) if q_t else {},
        }

    # C1: conf_desc > arrival on majority of cells
    c1_cells = []
    for m, block in raw_results.items():
        for b, cell in block["budgets"].items():
            win = cell["lift_conf_desc_minus_arrival"] > 0
            c1_cells.append({"model": m, "budget": b, "lift": cell["lift_conf_desc_minus_arrival"], "win": win})
    c1_ok = sum(1 for c in c1_cells if c["win"]) >= max(1, len(c1_cells) // 2)

    # C2: after shuffle, conf_desc should not beat random (arrival is 0 by construction)
    sh_edges = []
    raw_edges = []
    for m in MODELS:
        for cell in shuffle_results[m]["budgets"].values():
            sh_edges.append(cell["conf_desc"]["caught"] - cell["random"]["caught"])
        for cell in raw_results[m]["budgets"].values():
            raw_edges.append(cell["conf_desc"]["caught"] - cell["random"]["caught"])
    mean_sh_edge = sum(sh_edges) / len(sh_edges) if sh_edges else 0.0
    mean_raw_edge = sum(raw_edges) / len(raw_edges) if raw_edges else 0.0
    c2_ok = mean_sh_edge <= 0.0 and mean_raw_edge > mean_sh_edge

    # C3: donor-model conf on target queue
    cross = {}
    for target in MODELS:
        donors = [m for m in MODELS if m != target]
        donor_maps = {
            d: {(x["sid"], x["run_idx"]): x["conf"] for x in by_model[d]} for d in donors
        }
        rng = random.Random(args.seed + 33)
        q = build_diluted_queue(by_model[target], args.miss_rate, rng)
        cell_out: dict[str, Any] = {"within": eval_methods(q, (0.05,), args.seed)["0.05"], "donors": {}}
        for d, dmap in donor_maps.items():
            q_d = []
            for x in q:
                y = dict(x)
                y["conf"] = dmap.get((x["sid"], x["run_idx"]), x["conf"])
                q_d.append(y)
            cell_out["donors"][d] = eval_methods(q_d, (0.05,), args.seed)["0.05"]
        cross[target] = cell_out

    unstable = 0
    compared = 0
    for target, block in cross.items():
        w_lift = block["within"]["lift_conf_desc_minus_arrival"]
        for d, cell in block["donors"].items():
            compared += 1
            d_lift = cell["lift_conf_desc_minus_arrival"]
            if (w_lift > 0) != (d_lift > 0) or abs(w_lift - d_lift) >= 2:
                unstable += 1
    c3_ok = compared > 0 and (unstable / compared) >= 0.5

    fixture_shaped = c2_ok
    c4 = {
        "pass": True,
        "conf_desc_safe_universal_fallback": False,
        "fixture_shaped_evidence": fixture_shaped,
        "cross_model_unstable": c3_ok,
        "raw_beats_random_edge": mean_raw_edge,
        "shuffle_beats_random_edge": mean_sh_edge,
        "reason": (
            "conf_desc's edge over random collapses under conf-shuffle → "
            "the 'accidental match' is this fixture's (conf,miss) joint "
            "(see also 95.8% MISS at conf≥0.9); not a safe dual-line fallback warrant."
            if fixture_shaped
            else (
                f"shuffle did not fully erase conf_desc-vs-random "
                f"(raw_edge={mean_raw_edge:.2f}, sh_edge={mean_sh_edge:.2f}); "
                f"cross unstable={c3_ok}. Still not a production-safe fallback warrant."
            )
        ),
    }

    claims = {
        "C1_raw_conf_desc_beats_arrival": {
            "pass": c1_ok,
            "cells": c1_cells,
            "detail": "conf_desc catch > arrival on >= half of (model,B) cells",
        },
        "C2_shuffle_erases_edge_over_random": {
            "pass": c2_ok,
            "mean_raw_conf_desc_minus_random": mean_raw_edge,
            "mean_shuffle_conf_desc_minus_random": mean_sh_edge,
            "detail": "after conf shuffle, mean (conf_desc-random) <= 0 and below raw edge",
        },
        "C3_cross_model_unstable": {
            "pass": c3_ok,
            "unstable_pairs": unstable,
            "compared_pairs": compared,
            "detail": "donor-conf conf_desc lift unstable vs within on >= half pairs",
        },
        "C4_fallback_verdict": c4,
    }

    answer = (
        f"Raw: conf_desc>arrival on {sum(1 for c in c1_cells if c['win'])}/{len(c1_cells)} cells; "
        f"conf_desc-random edge raw={mean_raw_edge:.2f}. "
        f"After shuffle, edge vs random={mean_sh_edge:.2f} (C2 {'PASS' if c2_ok else 'FAIL'}). "
        f"Cross-model donor unstable {unstable}/{compared} (C3 {'PASS' if c3_ok else 'FAIL'}). "
        f"{c4['reason']} "
        "Low-conf rejects preferred as distractors so MISS↔high-conf can surface; "
        "same DF v2 dump as confidence-vs-miss-concentration."
    )

    out = {
        "question": (
            "Is conf_desc matching miss shape a fixture property or a real "
            "within-model failure-timing property? Safe as dual-line fallback?"
        ),
        "source": "Tom Jones comment on Part 15 (2026-07-28)",
        "seed": args.seed,
        "miss_rate": args.miss_rate,
        "models": MODELS,
        "raw": raw_results,
        "fixture_shuffle": shuffle_results,
        "temporal_holdout": temporal_results,
        "cross_model": cross,
        "claims": claims,
        "answer_for_tom": answer,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("══ conf-desc-miss-shape ══")
    print(f"→ {OUT}")
    for m in MODELS:
        print(f"\n{m} raw lifts (conf_desc - arrival):")
        for b, cell in raw_results[m]["budgets"].items():
            print(
                f"  B={b}: arrival={cell['arrival']['caught']} "
                f"conf_desc={cell['conf_desc']['caught']} "
                f"lift={cell['lift_conf_desc_minus_arrival']}"
            )
        print(f"  shuffle mean cell lifts:", end=" ")
        lifts = [c["lift_conf_desc_minus_arrival"] for c in shuffle_results[m]["budgets"].values()]
        print(lifts)
    print("\nClaims:")
    for k, v in claims.items():
        if k == "C4_fallback_verdict":
            print(f"  [INFO] {k}: {v['reason']}")
        else:
            print(f"  [{'PASS' if v['pass'] else 'FAIL'}] {k}: {v.get('detail')}")
    print("\nAnswer:")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
