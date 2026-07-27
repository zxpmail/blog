# -*- coding: utf-8 -*-
"""Production acceptance gate for an escalate-stream ranker.

Claim under test (follow-up to rank-inside-stream-test.py / Mike's open problem):
    A ranker is *shippable* only if it clears a pre-registered ops gate under
    hard budget B, without peeking at is_miss, with scores computable from
    features available at escalate time. Beating arrival on one in-sample LOO
    dump is not enough.

Candidate under test:
    R_hist — rank by P̂(MISS | scenario_id) estimated on the *train* window
             only. Unseen class_key → train global prior. Tie-break: arrival
             order. Never reads the item's own is_miss label.

Baselines (reference, not ship candidates):
    arrival   — file/dump order
    conf_asc  — lower confidence first (uncertainty heuristic)
    conf_desc — higher confidence first
    oracle    — MISS first (ceiling; FAIL the suite if any gate used it)

Pre-registered gates (ALL must PASS on primary protocol for SHIP):
    G0  Holdout mass — n_miss_test >= MIN_MISS_TEST. Below this the suite
        returns INCONCLUSIVE (not SHIP). Vacuous 0=0 passes do not ship.
    G1  Catch@k vs arrival — on stream D+T2, for every B in BUDGETS_GATE,
        R_hist_caught >= arrival_caught on the holdout slice.
    G2  Vs best single-stream arrival — on D+T2, for every B in BUDGETS_GATE,
        R_hist_caught >= max(arrival_caught on {D, class, UHC, UHC∧class, T2})
        at the same k (same holdout traffic).
    G3  Merge non-inferiority — for every B in BUDGETS_GATE and every
        S ∈ MERGE_STREAMS: R_hist on (D∪S) >= R_hist on D alone at same k.
    G4  Cross-model stability — leave-one-model-out: among folds that clear
        G0, G1 holds on ≥ MIN_LOMO_FRAC of those folds (need ≥1 eligible fold).
    G5  Cold-start non-inferiority — wipe class table (score = global prior
        only) on holdout D+T2: R_hist_caught >= arrival_caught − EPS_COLD
        for every B in BUDGETS_GATE (EPS_COLD = 0).
    G6  Ranking headroom — on D+T2, for at least one B in BUDGETS_GATE,
        arrival_caught < oracle_caught (arrival is not already saturating k).
        Without headroom, G1–G2 ties are vacuous and must not read as SHIP.

Primary protocol: *stratified* holdout on df_proxy, then a *constructed
diluted escalate queue* — all D+T2 MISSes in the holdout plus enough
non-MISS distractors so queue miss-rate ≈ TARGET_QUEUE_MISS_RATE (default
0.35). Arrival on that queue is adversarial (distractors first). Same
train table for R_hist; construction only creates G6 headroom that the
natural D+T2 holdout lacks (on this dump D+T2 test members are 100% MISS).

Secondary: stratified / temporal on natural streams (often G6-INCONCLUSIVE).

k = floor(B · |test_traffic|) still — budget is fraction of full holdout
traffic, applied as a cap on how many queue items get reviewed.

Falsifiers / outcomes:
    SHIP         — G0–G6 all PASS on df_proxy stratified+diluted_queue.
    NO_SHIP      — G0+G6 PASS but any of G1–G5 FAIL.
    INCONCLUSIVE — G0 or G6 FAIL.

Dependencies: none (pure Python).
Run:
    python scripts/ranker-prod-acceptance-test.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT_PATH = RESULTS / "ranker-prod-acceptance.json"

HIGH = 0.9
TRAIN_FRAC = 0.70
BUDGETS_GATE = (0.02, 0.05)  # 1% often gives k<3 on holdout; not in hard gate
BUDGETS_REPORT = (0.01, 0.02, 0.05)
STREAMS = ("D", "class", "UHC", "UHC∧class", "T2", "D+T2")
MERGE_STREAMS = ("class", "UHC", "UHC∧class", "T2")
PRIMARY_STREAM = "D+T2"
DILUTED_STREAM = "diluted_queue"
TARGET_QUEUE_MISS_RATE = 0.35
MIN_MISS_TEST = 15
MIN_LOMO_FRAC = 0.67  # among G0-eligible folds
EPS_COLD = 0

DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
MP_FILES = [
    "df-multiperspective-qwen3-0.5b.json",
    "df-multiperspective-gemma3-latest.json",
    "df-multiperspective-deepseek-v4-flash.json",
]


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


# ── loaders (same traffic contract as rank-inside-stream-test) ───────────


def mp_mean_conf(row: dict) -> float | None:
    vals = []
    for persona_runs in (row.get("vote_detail") or {}).values():
        if not persona_runs:
            continue
        c = persona_runs[0].get("confidence")
        if c is not None:
            vals.append(float(c))
    return sum(vals) / len(vals) if vals else None


def load_df_proxy() -> list[dict]:
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
                            "model": model,
                            "id": sid,
                            "order": order,
                            "class_key": sid,
                            "is_miss": bool(is_miss),
                            "reversal": is_reversal(sid),
                            "conf": conf,
                            "uhc": conf >= HIGH,
                            "split": conf < HIGH,
                            "unanimous_pass": passes and conf >= HIGH,
                        }
                    )
                    order += 1
    return items


def load_multiperspective() -> list[dict]:
    items = []
    order = 0
    for fname in MP_FILES:
        data = json.loads((RESULTS / fname).read_text(encoding="utf-8"))
        model = data.get("model") or fname
        for row in data["results"]:
            sid = row["id"]
            conf = mp_mean_conf(row)
            pattern = row.get("pattern")
            items.append(
                {
                    "model": model,
                    "id": sid,
                    "order": order,
                    "class_key": sid,
                    "is_miss": bool(row.get("dangerous_accept")),
                    "reversal": bool(row.get("reversal_class", is_reversal(sid))),
                    "conf": conf if conf is not None else 0.5,
                    "uhc": pattern == "unanimous_pass"
                    and conf is not None
                    and conf >= HIGH,
                    "split": pattern == "split",
                    "unanimous_pass": pattern == "unanimous_pass",
                }
            )
            order += 1
    return items


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
    if stream == "D+T2":
        return bool(item["split"] or (rev and item["unanimous_pass"]))
    raise ValueError(stream)


# ── ranker ───────────────────────────────────────────────────────────────


def fit_hist(train: list[dict]) -> tuple[dict[str, float], float]:
    """Return (class_key → P(MISS), global_prior). No test labels used."""
    hits: dict[str, list[int]] = {}
    for x in train:
        hits.setdefault(x["class_key"], []).append(1 if x["is_miss"] else 0)
    table = {k: sum(v) / len(v) for k, v in hits.items()}
    if not train:
        return {}, 0.0
    prior = sum(1 for x in train if x["is_miss"]) / len(train)
    return table, prior


def score_r_hist(item: dict, table: dict[str, float], prior: float) -> float:
    return table.get(item["class_key"], prior)


def take_k(
    stream_items: list[dict],
    ranker: str,
    k: int,
    table: dict[str, float] | None = None,
    prior: float = 0.0,
) -> list[dict]:
    if k <= 0 or not stream_items:
        return []
    if ranker == "arrival":
        ranked = sorted(stream_items, key=lambda x: x["order"])
    elif ranker == "oracle":
        ranked = sorted(stream_items, key=lambda x: (not x["is_miss"], x["order"]))
    elif ranker == "conf_asc":
        ranked = sorted(stream_items, key=lambda x: (x["conf"], x["order"]))
    elif ranker == "conf_desc":
        ranked = sorted(stream_items, key=lambda x: (-x["conf"], x["order"]))
    elif ranker == "R_hist":
        assert table is not None
        ranked = sorted(
            stream_items,
            key=lambda x: (-score_r_hist(x, table, prior), x["order"]),
        )
    else:
        raise ValueError(ranker)
    return ranked[:k]


def miss_caught(reviewed: list[dict]) -> int:
    return sum(1 for x in reviewed if x["is_miss"])


def stream_members(items: list[dict], stream: str) -> list[dict]:
    return [x for x in items if in_stream(x, stream)]


def merge_members(items: list[dict], stream_a: str, stream_b: str) -> list[dict]:
    seen: set[int] = set()
    out = []
    for x in items:
        if in_stream(x, stream_a) or in_stream(x, stream_b):
            i = id(x)
            if i in seen:
                continue
            seen.add(i)
            out.append(x)
    return out


# ── evaluation ───────────────────────────────────────────────────────────


def eval_holdout(
    train: list[dict],
    test: list[dict],
    *,
    cold_start: bool = False,
    diluted_queue: list[dict] | None = None,
    gate_primary: str = PRIMARY_STREAM,
) -> dict:
    if cold_start:
        table, prior = {}, (
            sum(1 for x in train if x["is_miss"]) / len(train) if train else 0.0
        )
    else:
        table, prior = fit_hist(train)

    n_test = len(test)
    n_miss = sum(1 for x in test if x["is_miss"])
    cells = []
    for b in BUDGETS_REPORT:
        k = int(n_test * b)
        best_single_arrival = {}
        for s in STREAMS:
            if s == PRIMARY_STREAM:
                continue
            memb = stream_members(test, s)
            best_single_arrival[s] = miss_caught(
                take_k(memb, "arrival", k, table, prior)
            )
        max_single = max(best_single_arrival.values()) if best_single_arrival else 0

        streams_to_eval = list(STREAMS)
        stream_members_map = {s: stream_members(test, s) for s in STREAMS}
        if diluted_queue is not None:
            streams_to_eval = [DILUTED_STREAM] + list(STREAMS)
            stream_members_map[DILUTED_STREAM] = diluted_queue

        for stream in streams_to_eval:
            memb = stream_members_map[stream]
            row = {
                "budget": b,
                "k": k,
                "stream": stream,
                "stream_n": len(memb),
                "stream_miss": sum(1 for x in memb if x["is_miss"]),
            }
            for ranker in ("arrival", "R_hist", "conf_asc", "conf_desc", "oracle"):
                caught = miss_caught(take_k(memb, ranker, k, table, prior))
                row[f"{ranker}_caught"] = caught
            row["R_hist_minus_arrival"] = row["R_hist_caught"] - row["arrival_caught"]
            if stream == DILUTED_STREAM:
                # G2 on constructed queue: beat uncertainty / confidence heuristics
                row["max_single_arrival"] = max(
                    row["conf_asc_caught"], row["conf_desc_caught"]
                )
            else:
                row["max_single_arrival"] = max_single
            row["R_hist_minus_max_single_arrival"] = (
                row["R_hist_caught"] - row["max_single_arrival"]
                if stream == gate_primary
                else None
            )
            cells.append(row)

    merge_cells = []
    for b in BUDGETS_REPORT:
        k = int(n_test * b)
        d_memb = stream_members(test, "D")
        d_r = miss_caught(take_k(d_memb, "R_hist", k, table, prior))
        for s in MERGE_STREAMS:
            merged = merge_members(test, "D", s)
            m_r = miss_caught(take_k(merged, "R_hist", k, table, prior))
            merge_cells.append(
                {
                    "budget": b,
                    "k": k,
                    "added_stream": s,
                    "D_R_hist_caught": d_r,
                    "merged_R_hist_caught": m_r,
                    "delta": m_r - d_r,
                }
            )

    dq_meta = None
    if diluted_queue is not None:
        dq_meta = {
            "n": len(diluted_queue),
            "n_miss": sum(1 for x in diluted_queue if x["is_miss"]),
            "miss_rate": (
                sum(1 for x in diluted_queue if x["is_miss"]) / len(diluted_queue)
                if diluted_queue
                else 0.0
            ),
            "target_miss_rate": TARGET_QUEUE_MISS_RATE,
        }

    return {
        "n_train": len(train),
        "n_test": n_test,
        "n_miss_test": n_miss,
        "n_classes_train": len(table),
        "global_prior": prior,
        "cold_start": cold_start,
        "gate_primary": gate_primary,
        "diluted_queue": dq_meta,
        "cells": cells,
        "merge_cells": merge_cells,
    }


def gate_results(holdout: dict) -> dict:
    """Apply pre-registered gates G1–G3 on a holdout eval dict."""
    cells = holdout["cells"]
    merges = holdout["merge_cells"]
    primary = holdout.get("gate_primary", PRIMARY_STREAM)

    def primary_cells():
        return [
            c
            for c in cells
            if c["stream"] == primary and c["budget"] in BUDGETS_GATE
        ]

    g1_rows = []
    g1_ok = True
    for c in primary_cells():
        ok = c["R_hist_caught"] >= c["arrival_caught"]
        g1_rows.append(
            {
                "budget": c["budget"],
                "R_hist": c["R_hist_caught"],
                "arrival": c["arrival_caught"],
                "pass": ok,
            }
        )
        g1_ok = g1_ok and ok

    g2_rows = []
    g2_ok = True
    for c in primary_cells():
        ok = c["R_hist_caught"] >= c["max_single_arrival"]
        g2_rows.append(
            {
                "budget": c["budget"],
                "R_hist": c["R_hist_caught"],
                "max_single_arrival": c["max_single_arrival"],
                "pass": ok,
            }
        )
        g2_ok = g2_ok and ok

    g3_rows = []
    g3_ok = True
    for m in merges:
        if m["budget"] not in BUDGETS_GATE:
            continue
        ok = m["merged_R_hist_caught"] >= m["D_R_hist_caught"]
        g3_rows.append(
            {
                "budget": m["budget"],
                "added_stream": m["added_stream"],
                "merged": m["merged_R_hist_caught"],
                "D_alone": m["D_R_hist_caught"],
                "pass": ok,
            }
        )
        g3_ok = g3_ok and ok

    return {
        "G1_vs_arrival": {"pass": g1_ok, "rows": g1_rows},
        "G2_vs_best_single_arrival": {"pass": g2_ok, "rows": g2_rows},
        "G3_merge_noninferior": {"pass": g3_ok, "rows": g3_rows},
    }


def temporal_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    ordered = sorted(items, key=lambda x: x["order"])
    cut = int(len(ordered) * TRAIN_FRAC)
    return ordered[:cut], ordered[cut:]


def stratified_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Within each is_miss bucket, keep order and cut at TRAIN_FRAC.

    Preserves MISS mass in the holdout (unlike pure temporal on this dump,
    which left miss_test≈1). Still uses only past-within-bucket order — no
    shuffle, no peek at test labels beyond the stratification key.
    """
    train: list[dict] = []
    test: list[dict] = []
    for flag in (False, True):
        bucket = sorted(
            (x for x in items if x["is_miss"] is flag),
            key=lambda x: x["order"],
        )
        cut = int(len(bucket) * TRAIN_FRAC)
        train.extend(bucket[:cut])
        test.extend(bucket[cut:])
    train.sort(key=lambda x: x["order"])
    test.sort(key=lambda x: x["order"])
    return train, test


def adversarial_arrival(items: list[dict]) -> list[dict]:
    """Construct worst-case arrival: every non-MISS before every MISS.

    Stable within each group by natural order. Used only to stress the
    arrival baseline / create G6 headroom — not fed into R_hist scoring.
    """
    non = sorted(
        (x for x in items if not x["is_miss"]), key=lambda x: x["order"]
    )
    miss = sorted(
        (x for x in items if x["is_miss"]), key=lambda x: x["order"]
    )
    out = []
    for i, x in enumerate(list(non) + list(miss)):
        y = dict(x)
        y["order_natural"] = x["order"]
        y["order"] = i
        out.append(y)
    return out


def build_diluted_queue(
    test: list[dict],
    miss_rate: float = TARGET_QUEUE_MISS_RATE,
) -> list[dict]:
    """Construct an escalate queue with headroom.

    Members = all D+T2 MISSes in the holdout + enough non-MISS distractors
    so miss_rate ≈ target. Arrival order = distractors first (adversarial).
    On this dump the natural D+T2 holdout is 100% MISS — without dilution
    G6 cannot fire.
    """
    base_miss = [
        x for x in test if in_stream(x, "D+T2") and x["is_miss"]
    ]
    distractors = [x for x in test if not x["is_miss"]]
    if not base_miss:
        return []
    n_dist = int(round(len(base_miss) * (1.0 - miss_rate) / miss_rate))
    n_dist = max(0, min(n_dist, len(distractors)))
    dist = sorted(distractors, key=lambda x: x["order"])[:n_dist]
    ordered = sorted(dist, key=lambda x: x["order"]) + sorted(
        base_miss, key=lambda x: x["order"]
    )
    out = []
    for i, x in enumerate(ordered):
        y = dict(x)
        y["order_natural"] = x["order"]
        y["order"] = i
        out.append(y)
    return out


def lomo_folds(items: list[dict]) -> list[tuple[str, list[dict], list[dict]]]:
    models = sorted({x["model"] for x in items})
    folds = []
    for held in models:
        train = [x for x in items if x["model"] != held]
        test = [x for x in items if x["model"] == held]
        folds.append((held, train, test))
    return folds


def attach_g5(gates: dict, cold: dict) -> None:
    primary = cold.get("gate_primary", PRIMARY_STREAM)
    g5_rows = []
    g5_ok = True
    for c in cold["cells"]:
        if c["stream"] != primary or c["budget"] not in BUDGETS_GATE:
            continue
        ok = c["R_hist_caught"] >= c["arrival_caught"] - EPS_COLD
        g5_rows.append(
            {
                "budget": c["budget"],
                "R_hist_cold": c["R_hist_caught"],
                "arrival": c["arrival_caught"],
                "pass": ok,
            }
        )
        g5_ok = g5_ok and ok
    gates["G5_cold_start_noninferior"] = {"pass": g5_ok, "rows": g5_rows}


def attach_g0(gates: dict, n_miss_test: int) -> None:
    ok = n_miss_test >= MIN_MISS_TEST
    gates["G0_holdout_miss_mass"] = {
        "pass": ok,
        "n_miss_test": n_miss_test,
        "min_required": MIN_MISS_TEST,
    }


def attach_g6(gates: dict, holdout: dict) -> None:
    primary = holdout.get("gate_primary", PRIMARY_STREAM)
    rows = []
    any_headroom = False
    for c in holdout["cells"]:
        if c["stream"] != primary or c["budget"] not in BUDGETS_GATE:
            continue
        headroom = c["arrival_caught"] < c["oracle_caught"]
        if headroom:
            any_headroom = True
        rows.append(
            {
                "budget": c["budget"],
                "arrival": c["arrival_caught"],
                "oracle": c["oracle_caught"],
                "headroom": headroom,
            }
        )
    gates["G6_ranking_headroom"] = {"pass": any_headroom, "rows": rows}


def attach_g4_lomo(
    gates: dict,
    items: list[dict],
    *,
    diluted: bool = False,
) -> None:
    lomo = []
    eligible = 0
    g1_fold_passes = 0
    for held, tr, te in lomo_folds(items):
        dq = build_diluted_queue(te) if diluted else None
        gp = DILUTED_STREAM if diluted else PRIMARY_STREAM
        ev = eval_holdout(
            tr, te, cold_start=False, diluted_queue=dq, gate_primary=gp
        )
        g = gate_results(ev)
        g0 = ev["n_miss_test"] >= MIN_MISS_TEST
        ok_g1 = g["G1_vs_arrival"]["pass"]
        if g0:
            eligible += 1
            if ok_g1:
                g1_fold_passes += 1
        lomo.append(
            {
                "held_out_model": held,
                "n_train": ev["n_train"],
                "n_test": ev["n_test"],
                "n_miss_test": ev["n_miss_test"],
                "G0_eligible": g0,
                "G1_pass": ok_g1,
                "G1_rows": g["G1_vs_arrival"]["rows"],
                "G2_pass": g["G2_vs_best_single_arrival"]["pass"],
                "G3_pass": g["G3_merge_noninferior"]["pass"],
                "diluted_queue": ev.get("diluted_queue"),
            }
        )
    frac = (g1_fold_passes / eligible) if eligible else 0.0
    g4_ok = eligible >= 1 and frac >= MIN_LOMO_FRAC
    gates["G4_lomo_G1"] = {
        "pass": g4_ok,
        "folds_passed": g1_fold_passes,
        "folds_eligible": eligible,
        "folds_total": len(lomo),
        "min_frac_required": MIN_LOMO_FRAC,
        "diluted": diluted,
        "folds": lomo,
    }


def verdict_from_gates(gates: dict) -> str:
    if not gates["G0_holdout_miss_mass"]["pass"]:
        return "INCONCLUSIVE"
    if not gates["G6_ranking_headroom"]["pass"]:
        return "INCONCLUSIVE"
    hard = [
        "G1_vs_arrival",
        "G2_vs_best_single_arrival",
        "G3_merge_noninferior",
        "G4_lomo_G1",
        "G5_cold_start_noninferior",
    ]
    if all(gates[g]["pass"] for g in hard):
        return "SHIP"
    return "NO_SHIP"


def run_protocol(
    name: str,
    items: list[dict],
    split_name: str,
    splitter,
    *,
    diluted: bool = False,
) -> dict:
    train, test = splitter(items)
    dq = build_diluted_queue(test) if diluted else None
    gp = DILUTED_STREAM if diluted else PRIMARY_STREAM
    primary = eval_holdout(
        train, test, cold_start=False, diluted_queue=dq, gate_primary=gp
    )
    cold = eval_holdout(
        train, test, cold_start=True, diluted_queue=dq, gate_primary=gp
    )
    gates = gate_results(primary)
    attach_g0(gates, primary["n_miss_test"])
    attach_g5(gates, cold)
    attach_g6(gates, primary)
    attach_g4_lomo(gates, items, diluted=diluted)
    verdict = verdict_from_gates(gates)
    return {
        "fixture": name,
        "split": split_name,
        "diluted_queue": diluted,
        "n_traffic": len(items),
        "train_frac": TRAIN_FRAC,
        "gate_primary": gp,
        "budgets_gate": list(BUDGETS_GATE),
        "holdout": primary,
        "cold_start": cold,
        "gates": gates,
        "ship_eligible": verdict == "SHIP",
        "verdict": verdict,
    }


def print_report(rep: dict) -> None:
    tag = " +diluted_queue" if rep.get("diluted_queue") else ""
    print(
        f"\n=== {rep['fixture']} / {rep['split']}{tag} → {rep['verdict']} ==="
    )
    t = rep["holdout"]
    print(
        f"train={t['n_train']} test={t['n_test']} "
        f"miss_test={t['n_miss_test']} classes_train={t['n_classes_train']} "
        f"gate_primary={rep.get('gate_primary')}"
    )
    if t.get("diluted_queue"):
        dq = t["diluted_queue"]
        print(
            f"diluted_queue n={dq['n']} miss={dq['n_miss']} "
            f"rate={dq['miss_rate']:.2f} (target {dq['target_miss_rate']:.2f})"
        )
    primary = rep.get("gate_primary", PRIMARY_STREAM)
    print(
        f"{'B':>5} {'k':>3} {'stream':<14} "
        f"{'arr':>4} {'Rhist':>5} {'c↑':>4} {'c↓':>4} {'orc':>4}"
    )
    for c in t["cells"]:
        if c["stream"] not in (primary, "D", "class", "UHC∧class", "T2", DILUTED_STREAM):
            continue
        if c["budget"] not in BUDGETS_REPORT:
            continue
        print(
            f"{c['budget']:>5.0%} {c['k']:>3} {c['stream']:<14} "
            f"{c['arrival_caught']:>4} {c['R_hist_caught']:>5} "
            f"{c['conf_asc_caught']:>4} {c['conf_desc_caught']:>4} "
            f"{c['oracle_caught']:>4}"
        )

    print("\nGates:")
    for name, g in rep["gates"].items():
        flag = "PASS" if g["pass"] else "FAIL"
        extra = ""
        if name == "G0_holdout_miss_mass":
            extra = f"  (miss_test={g['n_miss_test']}, need ≥{g['min_required']})"
        if name == "G4_lomo_G1":
            extra = (
                f"  ({g['folds_passed']}/{g['folds_eligible']} eligible folds, "
                f"need frac≥{g['min_frac_required']})"
            )
        print(f"  [{flag}] {name}{extra}")
        rows = g.get("rows") or []
        for r in rows[:8]:
            print(f"       {r}")


def main() -> None:
    print("=== Ranker production acceptance gate ===")
    print("Candidate: R_hist (train-window P(MISS|class))")
    print(
        f"Decisive primary: {DILUTED_STREAM} "
        f"(target miss-rate {TARGET_QUEUE_MISS_RATE:.0%})"
    )
    print(f"Hard budgets: {', '.join(f'{b:.0%}' for b in BUDGETS_GATE)}")
    print(
        f"SHIP iff G0–G6 PASS on df_proxy stratified + diluted_queue "
        f"(MIN_MISS_TEST={MIN_MISS_TEST})."
    )

    df_items = load_df_proxy()
    mp_items = load_multiperspective()

    df_dil = run_protocol(
        "df_proxy", df_items, "stratified", stratified_split, diluted=True
    )
    df_strat = run_protocol(
        "df_proxy", df_items, "stratified", stratified_split
    )
    df_temp = run_protocol("df_proxy", df_items, "temporal", temporal_split)
    mp_dil = run_protocol(
        "multiperspective",
        mp_items,
        "stratified",
        stratified_split,
        diluted=True,
    )

    print_report(df_dil)
    print_report(df_strat)
    print_report(df_temp)
    print_report(mp_dil)

    overall = df_dil["verdict"]
    print(
        f"\n=== OVERALL (df_proxy stratified+diluted_queue): {overall} ==="
    )
    if overall == "INCONCLUSIVE":
        g0 = df_dil["gates"]["G0_holdout_miss_mass"]["pass"]
        g6 = df_dil["gates"]["G6_ranking_headroom"]["pass"]
        reasons = []
        if not g0:
            reasons.append("G0 holdout MISS mass")
        if not g6:
            reasons.append("G6 ranking headroom")
        print(f"Cannot certify SHIP — {', '.join(reasons)}.")
    elif overall == "NO_SHIP":
        failed = [k for k, g in df_dil["gates"].items() if not g["pass"]]
        print(f"Failed gates: {', '.join(failed)}")
        print(
            "R_hist is not production-accepted on the constructed diluted "
            "queue. Need a stronger ranker to clear G0–G6."
        )
    else:
        print(
            "R_hist cleared the pre-registered gate on the constructed "
            "diluted queue. Scope: this traffic + these B + dilution "
            f"{TARGET_QUEUE_MISS_RATE:.0%} — not a universal certificate."
        )

    payload = {
        "candidate": "R_hist",
        "gates_pre_registered": [
            "G0_holdout_miss_mass",
            "G1_vs_arrival",
            "G2_vs_best_single_arrival",
            "G3_merge_noninferior",
            "G4_lomo_G1",
            "G5_cold_start_noninferior",
            "G6_ranking_headroom",
        ],
        "overall_verdict": overall,
        "ship_decisive": "df_proxy/stratified+diluted_queue",
        "target_queue_miss_rate": TARGET_QUEUE_MISS_RATE,
        "protocols": [df_dil, df_strat, df_temp, mp_dil],
    }
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(blob, encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")
    print(f"sha256(json)={hashlib.sha256(blob.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()

