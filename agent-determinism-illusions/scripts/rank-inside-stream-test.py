# -*- coding: utf-8 -*-
"""Rank-inside-stream under a hard human budget — Mike Czerwinski / Alexey Spinov.

Claim under test (Mike, Part 6 thread, after Alexey's 720-cell grid):
    Trigger choice only decides who *enters* the escalate stream. Under a hard
    human budget B smaller than stream volume (and especially smaller than the
    unshrinkable floor π·h·r_m), catch is decided by *rank inside the stream*.
    Arrival-order can catch fewer MISSes than a smaller high-precision stream
    (Alexey's 76/720 wiring failure). Precision-order should not.

Arms compared on each stream:
    arrival   — keep file / dump order, take first k
    oracle    — MISS first (ceiling; NOT deployable; peeks at labels)
    loo_class — leave-one-out P(MISS | scenario_id) from the same fixture
                (deployable proxy; no peek at the held-out item's label)

Streams (who enters):
    D            divergence / split  (MP: pattern==split;
                                      DF-proxy: PASS ∧ conf < 0.9)
    class        known-reversal class DF*/DS*  (T1)
    UHC          unanimous ∧ conf≥0.9
                 (MP: unanimous_pass ∧ mean persona conf ≥ 0.9;
                  DF-proxy: PASS ∧ conf ≥ 0.9)
    UHC∧class    UHC ∩ class
    T2           class ∩ unanimous_pass / (PASS ∧ conf≥0.9)   # Part 7 T2
    D+T2         D ∪ T2

Budgets: B ∈ {0.01, 0.02, 0.05} of *all traffic* rows. k = floor(B · N).

Fixtures (offline, no API):
    1) multiperspective — results-v2/df-multiperspective-*.json
       (Strict/Balanced/Lenient × DF v2 × 3 models; N=60 scenario-rows)
    2) df_proxy — results-v2/{qwen3-0-5b,gemma3-latest,deepseek-v4-flash}.jsonl
       (single-judge *all* runs as traffic; conf≥0.9 ≈ UHC proxy.
        PASS-only would make class/UHC streams ~all-MISS and vacate ranking.)

Primary metrics:
    miss_caught under (stream, ranker, B)
    delta vs arrival
    bad_wiring (Alexey shape): merged queue D∪S under arrival catches fewer
      MISSes than D-alone under arrival at the same k
    oracle − loo gap

Falsifiers:
    - If loo_class never beats arrival on any B → deployable rank claim WEAK.
    - If oracle still misses when B < stream's true-positive mass → floor-volume
      confirmed (expected; not a failure of the ranker claim).
    - If bad_wiring count is 0 for arrival on this traffic → Alexey's wiring
      warning does not reproduce here (report NULL, do not force).

Dependencies: none (pure Python, stdlib).
Run:
    python scripts/rank-inside-stream-test.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT_PATH = RESULTS / "rank-inside-stream.json"

HIGH = 0.9
BUDGETS = (0.01, 0.02, 0.05)
STREAMS = ("D", "class", "UHC", "UHC∧class", "T2", "D+T2")
RANKERS = ("arrival", "oracle", "loo_class")

MP_FILES = [
    "df-multiperspective-qwen3-0.5b.json",
    "df-multiperspective-gemma3-latest.json",
    "df-multiperspective-deepseek-v4-flash.json",
]
DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


# ── loaders ──────────────────────────────────────────────────────────────


def mp_mean_conf(row: dict) -> float | None:
    vals = []
    detail = row.get("vote_detail") or {}
    for persona_runs in detail.values():
        if not persona_runs:
            continue
        c = persona_runs[0].get("confidence")
        if c is not None:
            vals.append(float(c))
    if not vals:
        return None
    return sum(vals) / len(vals)


def load_multiperspective() -> list[dict]:
    items = []
    order = 0
    for fname in MP_FILES:
        path = RESULTS / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        model = data.get("model") or fname
        for row in data["results"]:
            sid = row["id"]
            conf = mp_mean_conf(row)
            pattern = row.get("pattern")
            uhc = pattern == "unanimous_pass" and conf is not None and conf >= HIGH
            items.append(
                {
                    "fixture": "multiperspective",
                    "model": model,
                    "id": sid,
                    "order": order,
                    "class_key": sid,
                    "is_miss": bool(row.get("dangerous_accept")),
                    "reversal": bool(row.get("reversal_class", is_reversal(sid))),
                    "pattern": pattern,
                    "conf": conf,
                    "uhc": uhc,
                    "split": pattern == "split",
                    "unanimous_pass": pattern == "unanimous_pass",
                    "is_pass_path": row.get("majority_pass") is True,
                }
            )
            order += 1
    return items


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
                    is_miss = (
                        passes and (not legit) and v.get("error_type") == "MISS"
                    )
                    items.append(
                        {
                            "fixture": "df_proxy",
                            "model": model,
                            "id": sid,
                            "order": order,
                            "class_key": sid,
                            "is_miss": bool(is_miss),
                            "reversal": is_reversal(sid),
                            "pattern": None,
                            "conf": conf,
                            "uhc": conf >= HIGH,
                            # divergence-proxy: low conf (agree with
                            # escalation-population-mismatch D definition)
                            "split": conf < HIGH,
                            "unanimous_pass": passes and conf >= HIGH,
                            "is_pass_path": passes,
                        }
                    )
                    order += 1
    return items


# ── stream membership ───────────────────────────────────────────────────


def in_stream(item: dict, stream: str) -> bool:
    """Escalate-stream membership.

    For df_proxy, universe is already PASS runs, so D/UHC/T2 keys are conf-based.
    For multiperspective, D fires on any split (Dipankar); class on reversal;
    UHC/T2 require accept-path semantics for T2-style arms — UHC is defined on
    unanimous_pass (which is already an accept-path pattern).
    """
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
        # Part 7: reversal ∩ unanimous_pass (MP) / reversal ∩ conf≥0.9 (proxy)
        return bool(rev and item["unanimous_pass"])
    if stream == "D+T2":
        return bool(item["split"] or (rev and item["unanimous_pass"]))
    raise ValueError(stream)


# ── ranking ──────────────────────────────────────────────────────────────


def loo_class_score(item: dict, items: list[dict]) -> float:
    """P(MISS | class_key) excluding this item. Falls back to global prior."""
    key = item["class_key"]
    hits = misses = 0
    for other in items:
        if other is item:
            continue
        if other["class_key"] != key:
            continue
        hits += 1
        if other["is_miss"]:
            misses += 1
    if hits > 0:
        return misses / hits
    # global prior excluding self
    n = len(items) - 1
    if n <= 0:
        return 0.0
    return sum(1 for o in items if o is not item and o["is_miss"]) / n


def take_k(stream_items: list[dict], ranker: str, k: int, all_items: list[dict]) -> list[dict]:
    if k <= 0 or not stream_items:
        return []
    if ranker == "arrival":
        ranked = sorted(stream_items, key=lambda x: x["order"])
    elif ranker == "oracle":
        ranked = sorted(stream_items, key=lambda x: (not x["is_miss"], x["order"]))
    elif ranker == "loo_class":
        scored = [(loo_class_score(x, all_items), x["order"], x) for x in stream_items]
        ranked = [t[2] for t in sorted(scored, key=lambda t: (-t[0], t[1]))]
    else:
        raise ValueError(ranker)
    return ranked[:k]


def miss_caught(reviewed: list[dict]) -> int:
    return sum(1 for x in reviewed if x["is_miss"])


# ── evaluation ───────────────────────────────────────────────────────────


def evaluate_fixture(name: str, items: list[dict]) -> dict:
    n = len(items)
    n_miss = sum(1 for x in items if x["is_miss"])
    stream_sizes = {}
    stream_miss = {}
    for s in STREAMS:
        memb = [x for x in items if in_stream(x, s)]
        stream_sizes[s] = len(memb)
        stream_miss[s] = sum(1 for x in memb if x["is_miss"])

    cells = []
    bad_wiring_arrival = []  # merged D∪S @arrival < D @arrival
    bad_wiring_oracle = []  # same under oracle — should stay ~0 if claim holds
    merge_cells = []

    for b in BUDGETS:
        k = int(n * b)  # floor
        d_stream = [x for x in items if in_stream(x, "D")]
        d_arrival_catch = miss_caught(take_k(d_stream, "arrival", k, items))
        d_oracle_catch = miss_caught(take_k(d_stream, "oracle", k, items))
        d_loo_catch = miss_caught(take_k(d_stream, "loo_class", k, items))

        for stream in STREAMS:
            memb = [x for x in items if in_stream(x, stream)]
            row = {
                "budget": b,
                "k": k,
                "stream": stream,
                "stream_n": len(memb),
                "stream_miss": sum(1 for x in memb if x["is_miss"]),
                "stream_fire_rate": len(memb) / n if n else 0.0,
            }
            for ranker in RANKERS:
                reviewed = take_k(memb, ranker, k, items)
                caught = miss_caught(reviewed)
                row[f"{ranker}_caught"] = caught
                row[f"{ranker}_catch_rate_of_all_miss"] = (
                    caught / n_miss if n_miss else 0.0
                )
            row["loo_minus_arrival"] = row["loo_class_caught"] - row["arrival_caught"]
            row["oracle_minus_loo"] = row["oracle_caught"] - row["loo_class_caught"]
            row["oracle_minus_arrival"] = row["oracle_caught"] - row["arrival_caught"]
            cells.append(row)

            if stream == "D":
                continue
            # Merged queue = D ∪ stream (Alexey's "add this stream to the queue")
            seen = set()
            merged = []
            for x in items:
                if in_stream(x, "D") or in_stream(x, stream):
                    i = id(x)
                    if i in seen:
                        continue
                    seen.add(i)
                    merged.append(x)
            m_arr = miss_caught(take_k(merged, "arrival", k, items))
            m_loo = miss_caught(take_k(merged, "loo_class", k, items))
            m_orc = miss_caught(take_k(merged, "oracle", k, items))
            merge_row = {
                "budget": b,
                "k": k,
                "added_stream": stream,
                "merged_n": len(merged),
                "D_arrival_caught": d_arrival_catch,
                "D_loo_caught": d_loo_catch,
                "D_oracle_caught": d_oracle_catch,
                "merged_arrival_caught": m_arr,
                "merged_loo_caught": m_loo,
                "merged_oracle_caught": m_orc,
                "arrival_delta_vs_D": m_arr - d_arrival_catch,
                "loo_delta_vs_D": m_loo - d_loo_catch,
                "oracle_delta_vs_D": m_orc - d_oracle_catch,
            }
            merge_cells.append(merge_row)
            if m_arr < d_arrival_catch:
                bad_wiring_arrival.append(
                    {
                        "budget": b,
                        "added_stream": stream,
                        "merged_arrival_caught": m_arr,
                        "D_arrival_caught": d_arrival_catch,
                    }
                )
            if m_orc < d_oracle_catch:
                bad_wiring_oracle.append(
                    {
                        "budget": b,
                        "added_stream": stream,
                        "merged_oracle_caught": m_orc,
                        "D_oracle_caught": d_oracle_catch,
                    }
                )

    # Aggregate: does loo ever beat arrival?
    loo_beats = sum(1 for c in cells if c["loo_minus_arrival"] > 0)
    loo_ties = sum(1 for c in cells if c["loo_minus_arrival"] == 0)
    loo_worse = sum(1 for c in cells if c["loo_minus_arrival"] < 0)
    oracle_beats = sum(1 for c in cells if c["oracle_minus_arrival"] > 0)

    # Floor-volume style: for each stream, TP mass / N
    floor_by_stream = {
        s: (stream_miss[s] / n if n else 0.0) for s in STREAMS
    }

    verdict_parts = []
    if loo_beats == 0:
        verdict_parts.append(
            "WEAK deployable-rank: loo_class never beats arrival on this fixture."
        )
    else:
        verdict_parts.append(
            f"SUPPORT deployable-rank shape: loo_class beats arrival in "
            f"{loo_beats}/{len(cells)} cells "
            f"(tie {loo_ties}, worse {loo_worse})."
        )
    if not bad_wiring_arrival:
        verdict_parts.append(
            "NULL on Alexey wiring: merging S into D never reduced arrival "
            "catch vs D-alone under tested budgets."
        )
    else:
        verdict_parts.append(
            f"SUPPORT Alexey wiring shape: {len(bad_wiring_arrival)} "
            f"(budget,added_stream) cells where D∪S @arrival catches fewer "
            f"MISSes than D @arrival."
        )
    if bad_wiring_oracle:
        verdict_parts.append(
            f"NOTE: {len(bad_wiring_oracle)} cells where even oracle merge "
            f"underperformed D — unexpected under precision ordering."
        )
    else:
        verdict_parts.append(
            "Oracle merge never worse than D-alone (0 bad_wiring under oracle)."
        )
    # Floor check at B=2%: oracle catch < stream_miss when k < stream_miss
    floor_notes = []
    for s in STREAMS:
        k2 = int(n * 0.02)
        tp = stream_miss[s]
        if tp > k2 > 0:
            memb = [x for x in items if in_stream(x, s)]
            oc = miss_caught(take_k(memb, "oracle", k2, items))
            floor_notes.append(
                {
                    "stream": s,
                    "tp_mass": tp,
                    "tp_rate": tp / n if n else 0.0,
                    "k_at_2pct": k2,
                    "oracle_caught_at_2pct": oc,
                    "residual_unseen_tp": tp - oc,
                }
            )
    if floor_notes:
        verdict_parts.append(
            "Floor-volume confirmed: at B=2%, oracle cannot absorb full TP "
            "mass on streams where tp > k (budget, not trigger, is the bind)."
        )

    return {
        "fixture": name,
        "n_traffic": n,
        "n_miss": n_miss,
        "miss_rate": n_miss / n if n else 0.0,
        "stream_sizes": stream_sizes,
        "stream_miss": stream_miss,
        "floor_tp_rate_by_stream": floor_by_stream,
        "loo_beats_arrival_cells": loo_beats,
        "loo_ties_arrival_cells": loo_ties,
        "loo_worse_arrival_cells": loo_worse,
        "oracle_beats_arrival_cells": oracle_beats,
        "n_cells": len(cells),
        "bad_wiring_arrival": bad_wiring_arrival,
        "bad_wiring_oracle": bad_wiring_oracle,
        "floor_at_2pct": floor_notes,
        "cells": cells,
        "merge_cells": merge_cells,
        "verdict": " ".join(verdict_parts),
    }


def print_fixture(rep: dict) -> None:
    print(f"\n=== Fixture: {rep['fixture']} ===")
    print(
        f"traffic N={rep['n_traffic']}  MISS={rep['n_miss']} "
        f"({100*rep['miss_rate']:.1f}%)"
    )
    print(f"{'stream':<12} {'n':>5} {'miss':>5} {'fire%':>7} {'tp%':>7}")
    for s in STREAMS:
        n = rep["stream_sizes"][s]
        m = rep["stream_miss"][s]
        fire = 100 * n / rep["n_traffic"] if rep["n_traffic"] else 0
        tp = 100 * rep["floor_tp_rate_by_stream"][s]
        print(f"{s:<12} {n:>5} {m:>5} {fire:>6.1f}% {tp:>6.1f}%")

    print(
        f"\n{'B':>5} {'k':>3} {'stream':<12} "
        f"{'arr':>4} {'loo':>4} {'orc':>4} "
        f"{'Δloo':>5} {'Δorc':>5}"
    )
    for c in rep["cells"]:
        print(
            f"{c['budget']:>5.0%} {c['k']:>3} {c['stream']:<12} "
            f"{c['arrival_caught']:>4} {c['loo_class_caught']:>4} "
            f"{c['oracle_caught']:>4} "
            f"{c['loo_minus_arrival']:>+5} {c['oracle_minus_arrival']:>+5}"
        )

    bw = rep["bad_wiring_arrival"]
    print(f"\nbad_wiring D∪S @arrival < D @arrival: {len(bw)}")
    for x in bw[:12]:
        print(
            f"  B={x['budget']:.0%} +{x['added_stream']} "
            f"merged={x['merged_arrival_caught']} < D={x['D_arrival_caught']}"
        )
    print(
        f"bad_wiring under oracle merge: {len(rep['bad_wiring_oracle'])} "
        f"(claim expects 0)"
    )
    # Show merge deltas at B=2% when present
    m2 = [m for m in rep["merge_cells"] if m["budget"] == 0.02]
    if m2:
        print(f"{'add':<12} {'D_arr':>5} {'∪arr':>5} {'∪loo':>5} {'∪orc':>5}")
        for m in m2:
            print(
                f"{m['added_stream']:<12} {m['D_arrival_caught']:>5} "
                f"{m['merged_arrival_caught']:>5} {m['merged_loo_caught']:>5} "
                f"{m['merged_oracle_caught']:>5}"
            )
    if rep["floor_at_2pct"]:
        print("floor at B=2% (oracle cannot clear TP mass):")
        for f in rep["floor_at_2pct"]:
            print(
                f"  {f['stream']:<12} tp={f['tp_mass']} k={f['k_at_2pct']} "
                f"oracle={f['oracle_caught_at_2pct']} "
                f"unseen_tp={f['residual_unseen_tp']}"
            )
    print(f"\nVerdict: {rep['verdict']}")


def main() -> None:
    print("=== Rank-inside-stream under hard budget ===")
    print("Arms: arrival | loo_class (deployable) | oracle (ceiling)")
    print(f"Budgets: {', '.join(f'{b:.0%}' for b in BUDGETS)}")
    print(f"Streams: {', '.join(STREAMS)}")

    reports = []
    for name, loader in [
        ("multiperspective", load_multiperspective),
        ("df_proxy", load_df_proxy),
    ]:
        items = loader()
        rep = evaluate_fixture(name, items)
        print_fixture(rep)
        reports.append(rep)

    payload = {
        "claim": (
            "Under hard budget B < stream volume, rank-inside-stream decides "
            "MISS catch; arrival can underperform; loo_class is a deployable "
            "proxy; oracle is the ceiling."
        ),
        "budgets": list(BUDGETS),
        "streams": list(STREAMS),
        "rankers": list(RANKERS),
        "fixtures": reports,
    }
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(blob, encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    print(f"\nWrote {OUT_PATH}")
    print(f"sha256(json)={digest}")


if __name__ == "__main__":
    main()
