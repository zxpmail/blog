# -*- coding: utf-8 -*-
"""Stress sweep for ranker production acceptance — features × dilution × time.

Claim under test (follow-up to ranker-prod-acceptance-test.py):
    R_hist's SHIP on a 35%-diluted adversarial queue may be fragile. Sweep:
      (1) feature / candidate rankers
      (2) queue miss-rate (dilution)
      (3) holdout protocol including within-model temporal extrapolation
    and report where verdict flips off SHIP.

Candidates (all score without peeking at the item's own is_miss):
    R_hist       — train P(MISS|class_key); unseen → global prior
    R_hist_conf  — R_hist primary, then lower conf (tie-break)
    R_conf_asc   — lower confidence first
    R_conf_desc  — higher confidence first
    R_reversal   — reversal-class first, then arrival
    R_uhc        — UHC flag first, then arrival

Holdout protocols:
    stratified          — within is_miss bucket, first TRAIN_FRAC by order
    within_model_temporal — per model, first TRAIN_FRAC by order (time-like)
    global_temporal     — first TRAIN_FRAC of all traffic by order

Dilution sweep (constructed queue miss-rate):
    0.15, 0.25, 0.35, 0.50, 0.65, 0.80, 0.95
    plus natural_D+T2 (no dilution; usually G6-INCONCLUSIVE)

Gates G0–G6 identical in spirit to ranker-prod-acceptance-test.py
(diluted_queue as gate primary when dilution < 1; else natural D+T2).
G2 on diluted queue = beat max(conf_asc, conf_desc) among *baselines*,
not among candidates under test.
G7 non-vacuous catch — for every gate budget with oracle > 0, candidate > 0
(blocks 0=0 SHIP when every heuristic also catches nothing).

Primary readout:
    For each candidate, the dilution rates where verdict == SHIP, and the
    first rate (ascending miss-rate = less diluted) where it drops.

Dependencies: none (pure Python).
Run:
    python scripts/ranker-acceptance-stress-sweep.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT_PATH = RESULTS / "ranker-acceptance-stress-sweep.json"

HIGH = 0.9
TRAIN_FRAC = 0.70
BUDGETS_GATE = (0.02, 0.05)
DILUTION_RATES = (0.15, 0.25, 0.35, 0.50, 0.65, 0.80, 0.95)
CANDIDATES = (
    "R_hist",
    "R_hist_conf",
    "R_conf_asc",
    "R_conf_desc",
    "R_reversal",
    "R_uhc",
)
PROTOCOLS = ("stratified", "within_model_temporal", "global_temporal")
MIN_MISS_TEST = 15
MIN_LOMO_FRAC = 0.67
EPS_COLD = 0
DILUTED = "diluted_queue"
PRIMARY = "D+T2"
MERGE_STREAMS = ("class", "UHC", "UHC∧class", "T2")

DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


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


def fit_hist(train: list[dict]) -> tuple[dict[str, float], float]:
    hits: dict[str, list[int]] = {}
    for x in train:
        hits.setdefault(x["class_key"], []).append(1 if x["is_miss"] else 0)
    table = {k: sum(v) / len(v) for k, v in hits.items()}
    prior = (
        sum(1 for x in train if x["is_miss"]) / len(train) if train else 0.0
    )
    return table, prior


def score(item: dict, cand: str, table: dict[str, float], prior: float) -> tuple:
    """Higher tuple sorts first (we negate where needed in key)."""
    hist = table.get(item["class_key"], prior)
    if cand == "R_hist":
        return (hist, 0.0, -item["order"])
    if cand == "R_hist_conf":
        return (hist, -item["conf"], -item["order"])
    if cand == "R_conf_asc":
        return (-item["conf"], -item["order"])
    if cand == "R_conf_desc":
        return (item["conf"], -item["order"])
    if cand == "R_reversal":
        return (1.0 if item["reversal"] else 0.0, -item["order"])
    if cand == "R_uhc":
        return (1.0 if item["uhc"] else 0.0, -item["order"])
    raise ValueError(cand)


def take_k(
    items: list[dict],
    how: str,
    k: int,
    table: dict[str, float],
    prior: float,
    cand: str | None = None,
) -> list[dict]:
    if k <= 0 or not items:
        return []
    if how == "arrival":
        ranked = sorted(items, key=lambda x: x["order"])
    elif how == "oracle":
        ranked = sorted(items, key=lambda x: (not x["is_miss"], x["order"]))
    elif how == "conf_asc":
        ranked = sorted(items, key=lambda x: (x["conf"], x["order"]))
    elif how == "conf_desc":
        ranked = sorted(items, key=lambda x: (-x["conf"], x["order"]))
    elif how == "candidate":
        assert cand is not None
        ranked = sorted(
            items, key=lambda x: score(x, cand, table, prior), reverse=True
        )
    else:
        raise ValueError(how)
    return ranked[:k]


def caught(xs: list[dict]) -> int:
    return sum(1 for x in xs if x["is_miss"])


def stratified_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
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


def global_temporal_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    ordered = sorted(items, key=lambda x: x["order"])
    cut = int(len(ordered) * TRAIN_FRAC)
    return ordered[:cut], ordered[cut:]


def within_model_temporal_split(
    items: list[dict],
) -> tuple[list[dict], list[dict]]:
    train: list[dict] = []
    test: list[dict] = []
    for model in sorted({x["model"] for x in items}):
        sub = sorted(
            (x for x in items if x["model"] == model), key=lambda x: x["order"]
        )
        cut = int(len(sub) * TRAIN_FRAC)
        train.extend(sub[:cut])
        test.extend(sub[cut:])
    train.sort(key=lambda x: x["order"])
    test.sort(key=lambda x: x["order"])
    return train, test


SPLITTERS = {
    "stratified": stratified_split,
    "global_temporal": global_temporal_split,
    "within_model_temporal": within_model_temporal_split,
}


def build_diluted_queue(
    test: list[dict], miss_rate: float
) -> list[dict]:
    base_miss = [x for x in test if in_stream(x, "D+T2") and x["is_miss"]]
    distractors = [x for x in test if not x["is_miss"]]
    if not base_miss:
        return []
    if miss_rate >= 0.999:
        # natural: MISS-only queue (adversarial order irrelevant)
        ordered = sorted(base_miss, key=lambda x: x["order"])
    else:
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


def evaluate_cell(
    train: list[dict],
    test: list[dict],
    cand: str,
    miss_rate: float | None,
    *,
    cold: bool = False,
) -> dict:
    """One (cand, dilution) eval on fixed train/test. miss_rate=None → natural D+T2."""
    if cold:
        table, prior = {}, (
            sum(1 for x in train if x["is_miss"]) / len(train) if train else 0.0
        )
    else:
        table, prior = fit_hist(train)

    n_test = len(test)
    n_miss = sum(1 for x in test if x["is_miss"])

    if miss_rate is None:
        q = sorted(
            (x for x in test if in_stream(x, PRIMARY)),
            key=lambda x: x["order"],
        )
        queue = []
        for i, x in enumerate(q):
            y = dict(x)
            y["order"] = i
            queue.append(y)
        gate_primary = PRIMARY
    else:
        queue = build_diluted_queue(test, miss_rate)
        gate_primary = DILUTED

    rows = []
    for b in BUDGETS_GATE:
        k = int(n_test * b)
        arr = caught(take_k(queue, "arrival", k, table, prior))
        orc = caught(take_k(queue, "oracle", k, table, prior))
        c_asc = caught(take_k(queue, "conf_asc", k, table, prior))
        c_desc = caught(take_k(queue, "conf_desc", k, table, prior))
        rh = caught(take_k(queue, "candidate", k, table, prior, cand=cand))
        rows.append(
            {
                "budget": b,
                "k": k,
                "arrival": arr,
                "oracle": orc,
                "conf_asc": c_asc,
                "conf_desc": c_desc,
                "candidate": rh,
                "headroom": arr < orc,
            }
        )

    # G3 merge on natural streams with candidate ranking
    merge_ok = True
    merge_rows = []
    for b in BUDGETS_GATE:
        k = int(n_test * b)
        d_mem = [x for x in test if in_stream(x, "D")]
        d_c = caught(take_k(d_mem, "candidate", k, table, prior, cand=cand))
        for s in MERGE_STREAMS:
            seen: set[int] = set()
            merged = []
            for x in test:
                if in_stream(x, "D") or in_stream(x, s):
                    i = id(x)
                    if i in seen:
                        continue
                    seen.add(i)
                    merged.append(x)
            m_c = caught(
                take_k(merged, "candidate", k, table, prior, cand=cand)
            )
            ok = m_c >= d_c
            merge_ok = merge_ok and ok
            merge_rows.append(
                {
                    "budget": b,
                    "added": s,
                    "D": d_c,
                    "merged": m_c,
                    "pass": ok,
                }
            )

    g0 = n_miss >= MIN_MISS_TEST
    g1 = all(r["candidate"] >= r["arrival"] for r in rows)
    g2 = all(
        r["candidate"] >= max(r["conf_asc"], r["conf_desc"]) for r in rows
    )
    g3 = merge_ok
    g6 = any(r["headroom"] for r in rows)
    g7 = all(
        (r["oracle"] == 0) or (r["candidate"] > 0) for r in rows
    )

    return {
        "gate_primary": gate_primary,
        "queue_n": len(queue),
        "queue_miss": sum(1 for x in queue if x["is_miss"]),
        "queue_miss_rate": (
            sum(1 for x in queue if x["is_miss"]) / len(queue) if queue else 0.0
        ),
        "n_train": len(train),
        "n_test": n_test,
        "n_miss_test": n_miss,
        "rows": rows,
        "merge_rows": merge_rows,
        "G0": g0,
        "G1": g1,
        "G2": g2,
        "G3": g3,
        "G6": g6,
        "G7": g7,
    }


def lomo_g1_frac(items: list[dict], cand: str, miss_rate: float | None) -> dict:
    models = sorted({x["model"] for x in items})
    eligible = passed = 0
    folds = []
    for held in models:
        tr = [x for x in items if x["model"] != held]
        te = [x for x in items if x["model"] == held]
        cell = evaluate_cell(tr, te, cand, miss_rate, cold=False)
        g0 = cell["G0"]
        if g0:
            eligible += 1
            if cell["G1"]:
                passed += 1
        folds.append(
            {
                "held": held,
                "n_miss_test": cell["n_miss_test"],
                "G0": g0,
                "G1": cell["G1"],
            }
        )
    frac = (passed / eligible) if eligible else 0.0
    return {
        "pass": eligible >= 1 and frac >= MIN_LOMO_FRAC,
        "passed": passed,
        "eligible": eligible,
        "frac": frac,
        "folds": folds,
    }


def verdict_for(cell: dict, g4: dict, cold_cell: dict) -> str:
    if not cell["G0"] or not cell["G6"]:
        return "INCONCLUSIVE"
    g5 = all(
        r["candidate"] >= r["arrival"] - EPS_COLD for r in cold_cell["rows"]
    )
    if (
        cell["G1"]
        and cell["G2"]
        and cell["G3"]
        and g4["pass"]
        and g5
        and cell["G7"]
    ):
        return "SHIP"
    return "NO_SHIP"


def run_sweep(items: list[dict]) -> dict:
    results = []
    for proto in PROTOCOLS:
        splitter = SPLITTERS[proto]
        train, test = splitter(items)
        rates: list[float | None] = list(DILUTION_RATES) + [None]
        for cand in CANDIDATES:
            for rate in rates:
                cell = evaluate_cell(train, test, cand, rate, cold=False)
                cold = evaluate_cell(train, test, cand, rate, cold=True)
                g4 = lomo_g1_frac(items, cand, rate)
                # G5 from cold rows
                g5 = all(
                    r["candidate"] >= r["arrival"] - EPS_COLD
                    for r in cold["rows"]
                )
                ver = verdict_for(cell, g4, cold)
                failed = []
                if ver == "NO_SHIP":
                    if not cell["G1"]:
                        failed.append("G1")
                    if not cell["G2"]:
                        failed.append("G2")
                    if not cell["G3"]:
                        failed.append("G3")
                    if not g4["pass"]:
                        failed.append("G4")
                    if not g5:
                        failed.append("G5")
                    if not cell["G7"]:
                        failed.append("G7")
                results.append(
                    {
                        "protocol": proto,
                        "candidate": cand,
                        "dilution": rate if rate is not None else "natural_D+T2",
                        "verdict": ver,
                        "failed_gates": failed,
                        "n_miss_test": cell["n_miss_test"],
                        "queue_n": cell["queue_n"],
                        "queue_miss_rate": cell["queue_miss_rate"],
                        "G0": cell["G0"],
                        "G1": cell["G1"],
                        "G2": cell["G2"],
                        "G3": cell["G3"],
                        "G4": g4["pass"],
                        "G4_detail": {
                            "passed": g4["passed"],
                            "eligible": g4["eligible"],
                            "frac": g4["frac"],
                        },
                        "G5": g5,
                        "G6": cell["G6"],
                        "G7": cell["G7"],
                        "rows": cell["rows"],
                    }
                )
    return {"cells": results}


def summarize(cells: list[dict]) -> dict:
    """Per candidate × protocol: SHIP dilutions and drop point."""
    summary = []
    for proto in PROTOCOLS:
        for cand in CANDIDATES:
            sub = [
                c
                for c in cells
                if c["protocol"] == proto and c["candidate"] == cand
            ]
            ships = [
                c["dilution"]
                for c in sub
                if c["verdict"] == "SHIP" and isinstance(c["dilution"], float)
            ]
            # ascending miss-rate = denser queue = easier; drop = first FAIL
            # walking from sparse (hard) to dense (easy)
            ordered = sorted(
                (
                    c
                    for c in sub
                    if isinstance(c["dilution"], float)
                ),
                key=lambda c: c["dilution"],
            )
            first_ship = next(
                (c["dilution"] for c in ordered if c["verdict"] == "SHIP"),
                None,
            )
            # drop when moving toward harder (lower miss-rate): last SHIP then next miss
            ships_asc = [c for c in ordered if c["verdict"] == "SHIP"]
            drop_below = None
            if ships_asc:
                lowest_ship = ships_asc[0]["dilution"]
                harder = [
                    c
                    for c in ordered
                    if c["dilution"] < lowest_ship and c["verdict"] != "SHIP"
                ]
                if harder:
                    drop_below = lowest_ship
            natural = next(
                (
                    c
                    for c in sub
                    if c["dilution"] == "natural_D+T2"
                ),
                None,
            )
            summary.append(
                {
                    "protocol": proto,
                    "candidate": cand,
                    "ship_dilutions": ships,
                    "n_ship": len(ships),
                    "lowest_ship_miss_rate": first_ship,
                    "drops_below_miss_rate": drop_below,
                    "natural_verdict": natural["verdict"] if natural else None,
                }
            )
    return {"by_candidate_protocol": summary}


def main() -> None:
    print("=== Ranker acceptance stress sweep ===")
    print(f"Candidates: {', '.join(CANDIDATES)}")
    print(f"Protocols: {', '.join(PROTOCOLS)}")
    print(
        f"Dilution miss-rates: {', '.join(f'{r:.0%}' for r in DILUTION_RATES)}"
        " + natural_D+T2"
    )

    items = load_df_proxy()
    payload_inner = run_sweep(items)
    cells = payload_inner["cells"]
    summary = summarize(cells)

    # Print matrix: protocol × candidate × dilution verdict
    print("\n--- Verdict grid (stratified) ---")
    strat = [c for c in cells if c["protocol"] == "stratified"]
    rates = list(DILUTION_RATES) + ["nat"]
    hdr = f"{'cand':<12} " + " ".join(
        f"{(f'{r:.0%}' if isinstance(r, float) else r):>5}" for r in rates
    )
    print(hdr)
    for cand in CANDIDATES:
        bits = []
        for r in DILUTION_RATES:
            cell = next(
                c
                for c in strat
                if c["candidate"] == cand and c["dilution"] == r
            )
            bits.append(
                {"SHIP": "SHIP", "NO_SHIP": "FAIL", "INCONCLUSIVE": "INC"}[
                    cell["verdict"]
                ]
            )
        nat = next(
            c
            for c in strat
            if c["candidate"] == cand and c["dilution"] == "natural_D+T2"
        )
        bits.append(
            {"SHIP": "SHIP", "NO_SHIP": "FAIL", "INCONCLUSIVE": "INC"}[
                nat["verdict"]
            ]
        )
        print(f"{cand:<12} " + " ".join(f"{b:>5}" for b in bits))

    print("\n--- within_model_temporal (time-like) ---")
    wmt = [c for c in cells if c["protocol"] == "within_model_temporal"]
    print(hdr)
    for cand in CANDIDATES:
        bits = []
        for r in DILUTION_RATES:
            cell = next(
                c
                for c in wmt
                if c["candidate"] == cand and c["dilution"] == r
            )
            bits.append(
                {"SHIP": "SHIP", "NO_SHIP": "FAIL", "INCONCLUSIVE": "INC"}[
                    cell["verdict"]
                ]
            )
        nat = next(
            c
            for c in wmt
            if c["candidate"] == cand and c["dilution"] == "natural_D+T2"
        )
        bits.append(
            {"SHIP": "SHIP", "NO_SHIP": "FAIL", "INCONCLUSIVE": "INC"}[
                nat["verdict"]
            ]
        )
        print(f"{cand:<12} " + " ".join(f"{b:>5}" for b in bits))

    print("\n--- Drop points (stratified, lower miss-rate = harder) ---")
    for row in summary["by_candidate_protocol"]:
        if row["protocol"] != "stratified":
            continue
        ships = ", ".join(f"{x:.0%}" for x in row["ship_dilutions"]) or "—"
        n_all = len(DILUTION_RATES)
        if row["n_ship"] == n_all:
            drop_s = "SHIP at all swept dilutions"
        elif row["n_ship"] == 0:
            drop_s = "no SHIP"
        else:
            fails = [
                f"{c['dilution']:.0%}"
                for c in cells
                if c["protocol"] == "stratified"
                and c["candidate"] == row["candidate"]
                and isinstance(c["dilution"], float)
                and c["verdict"] != "SHIP"
            ]
            drop_s = f"partial; non-SHIP at [{', '.join(fails)}]"
        print(f"  {row['candidate']:<12} ships=[{ships}]  {drop_s}")

    print("\n--- within_model_temporal R_hist failures ---")
    for c in cells:
        if (
            c["protocol"] == "within_model_temporal"
            and c["candidate"] == "R_hist"
            and isinstance(c["dilution"], float)
        ):
            print(
                f"  {c['dilution']:.0%} {c['verdict']:<12} "
                f"fail={c['failed_gates'] or '—'} "
                f"cand@5%={c['rows'][1]['candidate']}/"
                f"orc={c['rows'][1]['oracle']}"
            )
    print("\n--- Temporal protocols miss mass ---")
    for proto in ("within_model_temporal", "global_temporal"):
        sample = next(
            c
            for c in cells
            if c["protocol"] == proto
            and c["candidate"] == "R_hist"
            and c["dilution"] == 0.35
        )
        print(
            f"  {proto}: miss_test={sample['n_miss_test']} "
            f"G0={sample['G0']} verdict@35%={sample['verdict']}"
        )

    payload = {
        "claim": (
            "Sweep features × dilution × holdout; locate where R_hist "
            "(and alternates) fall off SHIP."
        ),
        "candidates": list(CANDIDATES),
        "protocols": list(PROTOCOLS),
        "dilution_rates": list(DILUTION_RATES),
        "summary": summary,
        "cells": cells,
    }
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(blob, encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")
    print(f"sha256={hashlib.sha256(blob.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
