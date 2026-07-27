# -*- coding: utf-8 -*-
"""Dual-line ops simulation — Trigger∥Rank and Shadow∥Enforce.

Claim under test (production dual-line, offline):
    Under a hard human budget k, two control planes should be separated:

      Trigger line — who *enters* the escalate set (stream membership)
      Rank line    — who is *seen* inside that set (order under k)

    And Rank itself should run dual-publish:

      Enforce — what humans actually review (baseline: arrival)
      Shadow  — what a ranker *would* have reviewed at the same k
      Fallback — if shadow looks vacuous / stale, enforce stays on arrival

Method (offline, df_proxy traffic, no API):
    A) Trigger∥Rank factorial on stratified holdout + diluted queue (35%):
         - Trigger-only: streams {D, class, T2, D+T2, diluted}, arrival, catch@k
         - Rank-only:    fix diluted queue, rankers {arrival, R_hist, conf_desc},
                         catch@k
         - Combined:     each stream × each ranker at same k
       Primary readout: under budget bind, max Rank-only lift on a *fixed*
       trigger vs max Trigger-only lift under arrival — which knob moves catch?

    B) Shadow∥Enforce on diluted queue:
         Enforce = arrival@k
         Shadow  = R_hist@k  (and conf_desc@k as alternate)
         Lift    = shadow − enforce
         Fallback rule (pre-registered): if shadow_caught == 0 and oracle > 0,
         treat shadow as FAILED and fall back to enforce (arrival) for the
         "safe enforce" policy — catch must be ≥ enforce (non-inferior).

    C) Stale-table stress (within_model_temporal holdout):
         Same B with R_hist shadow — expect shadow lift to collapse; fallback
         must keep safe-enforce ≥ arrival; raw R_hist enforce would be unsafe.

Budgets: B ∈ {0.02, 0.05} of holdout traffic; k = floor(B · n_test).
Dilution: 0.35 miss-rate constructed queue (distractors first) when noted.

Falsifiers:
    - If Trigger-only arrival on stream choice always beats Rank-only on fixed
      diluted queue by a wide margin, "Rank line is the budget knob" is WEAK.
    - If Shadow never lifts Enforce on stratified+diluted, dual-publish has
      nothing to show on this fixture.
    - If on temporal holdout, fallback safe-enforce < arrival, fallback rule
      is broken.

Dependencies: none (pure Python).
Run:
    python scripts/dual-line-ops-sim.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT_PATH = RESULTS / "dual-line-ops-sim.json"

HIGH = 0.9
TRAIN_FRAC = 0.70
BUDGETS = (0.02, 0.05)
DILUTION = 0.35
DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
TRIGGER_STREAMS = ("D", "class", "T2", "D+T2", "diluted")
RANKERS = ("arrival", "R_hist", "conf_desc")


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


def load_df_proxy() -> list[dict]:
    items = []
    order = 0
    for model in DF_MODELS:
        with (RESULTS / f"{model}.jsonl").open(encoding="utf-8") as f:
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
    if stream == "D":
        return bool(item["split"])
    if stream == "class":
        return bool(item["reversal"])
    if stream == "T2":
        return bool(item["reversal"] and item["unanimous_pass"])
    if stream == "D+T2":
        return bool(item["split"] or (item["reversal"] and item["unanimous_pass"]))
    raise ValueError(stream)


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


def fit_hist(train: list[dict]) -> tuple[dict[str, float], float]:
    hits: dict[str, list[int]] = {}
    for x in train:
        hits.setdefault(x["class_key"], []).append(1 if x["is_miss"] else 0)
    table = {k: sum(v) / len(v) for k, v in hits.items()}
    prior = (
        sum(1 for x in train if x["is_miss"]) / len(train) if train else 0.0
    )
    return table, prior


def build_diluted(test: list[dict], miss_rate: float = DILUTION) -> list[dict]:
    base_miss = [x for x in test if in_stream(x, "D+T2") and x["is_miss"]]
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
        y["order"] = i
        out.append(y)
    return out


def members(test: list[dict], stream: str, diluted: list[dict]) -> list[dict]:
    if stream == "diluted":
        return list(diluted)
    q = sorted(
        (x for x in test if in_stream(x, stream)), key=lambda x: x["order"]
    )
    out = []
    for i, x in enumerate(q):
        y = dict(x)
        y["order"] = i
        out.append(y)
    return out


def take_k(
    queue: list[dict],
    ranker: str,
    k: int,
    table: dict[str, float],
    prior: float,
) -> list[dict]:
    if k <= 0 or not queue:
        return []
    if ranker == "arrival":
        ranked = sorted(queue, key=lambda x: x["order"])
    elif ranker == "oracle":
        ranked = sorted(queue, key=lambda x: (not x["is_miss"], x["order"]))
    elif ranker == "conf_desc":
        ranked = sorted(queue, key=lambda x: (-x["conf"], x["order"]))
    elif ranker == "R_hist":
        ranked = sorted(
            queue,
            key=lambda x: (
                -table.get(x["class_key"], prior),
                x["order"],
            ),
        )
    else:
        raise ValueError(ranker)
    return ranked[:k]


def caught(xs: list[dict]) -> int:
    return sum(1 for x in xs if x["is_miss"])


def run_factorial(
    train: list[dict], test: list[dict], label: str
) -> dict:
    table, prior = fit_hist(train)
    diluted = build_diluted(test)
    n_test = len(test)
    n_miss = sum(1 for x in test if x["is_miss"])
    cells = []
    for b in BUDGETS:
        k = int(n_test * b)
        for stream in TRIGGER_STREAMS:
            q = members(test, stream, diluted)
            for ranker in RANKERS:
                c = caught(take_k(q, ranker, k, table, prior))
                o = caught(take_k(q, "oracle", k, table, prior))
                cells.append(
                    {
                        "budget": b,
                        "k": k,
                        "stream": stream,
                        "ranker": ranker,
                        "queue_n": len(q),
                        "queue_miss": sum(1 for x in q if x["is_miss"]),
                        "caught": c,
                        "oracle": o,
                        "headroom": c < o if ranker == "arrival" else o > 0,
                    }
                )

    # Readouts per budget
    readouts = []
    for b in BUDGETS:
        k = int(n_test * b)
        sub = [c for c in cells if c["budget"] == b]
        trigger_only = [
            c for c in sub if c["ranker"] == "arrival"
        ]
        best_trigger = max(trigger_only, key=lambda c: c["caught"])
        rank_only = [
            c for c in sub if c["stream"] == "diluted"
        ]
        best_rank = max(rank_only, key=lambda c: c["caught"])
        arrival_diluted = next(
            c
            for c in sub
            if c["stream"] == "diluted" and c["ranker"] == "arrival"
        )
        hist_diluted = next(
            c
            for c in sub
            if c["stream"] == "diluted" and c["ranker"] == "R_hist"
        )
        # Lift from Rank knob (fixed diluted trigger) vs Trigger knob (arrival)
        rank_lift = hist_diluted["caught"] - arrival_diluted["caught"]
        # best trigger under arrival vs arrival on diluted
        trigger_lift = best_trigger["caught"] - arrival_diluted["caught"]
        readouts.append(
            {
                "budget": b,
                "k": k,
                "best_trigger_only": {
                    "stream": best_trigger["stream"],
                    "caught": best_trigger["caught"],
                },
                "best_rank_only_on_diluted": {
                    "ranker": best_rank["ranker"],
                    "caught": best_rank["caught"],
                },
                "diluted_arrival": arrival_diluted["caught"],
                "diluted_R_hist": hist_diluted["caught"],
                "rank_lift_on_fixed_diluted": rank_lift,
                "trigger_lift_vs_diluted_arrival": trigger_lift,
                "rank_knob_wins": rank_lift >= trigger_lift,
            }
        )

    return {
        "holdout": label,
        "n_train": len(train),
        "n_test": n_test,
        "n_miss_test": n_miss,
        "diluted_n": len(diluted),
        "diluted_miss_rate": (
            sum(1 for x in diluted if x["is_miss"]) / len(diluted)
            if diluted
            else 0.0
        ),
        "cells": cells,
        "readouts": readouts,
    }


def run_shadow_enforce(
    train: list[dict], test: list[dict], label: str
) -> dict:
    table, prior = fit_hist(train)
    diluted = build_diluted(test)
    n_test = len(test)
    rows = []
    for b in BUDGETS:
        k = int(n_test * b)
        enforce = caught(take_k(diluted, "arrival", k, table, prior))
        shadow_hist = caught(take_k(diluted, "R_hist", k, table, prior))
        shadow_conf = caught(take_k(diluted, "conf_desc", k, table, prior))
        oracle = caught(take_k(diluted, "oracle", k, table, prior))

        # Fallback: if shadow catches nothing while oracle could, fail closed
        def safe(shadow_c: int) -> tuple[int, str]:
            if shadow_c == 0 and oracle > 0:
                return enforce, "fallback_arrival"
            return shadow_c, "shadow"

        safe_hist_c, safe_hist_mode = safe(shadow_hist)
        safe_conf_c, safe_conf_mode = safe(shadow_conf)
        rows.append(
            {
                "budget": b,
                "k": k,
                "enforce_arrival": enforce,
                "shadow_R_hist": shadow_hist,
                "shadow_conf_desc": shadow_conf,
                "oracle": oracle,
                "lift_hist": shadow_hist - enforce,
                "lift_conf": shadow_conf - enforce,
                "safe_enforce_hist": safe_hist_c,
                "safe_hist_mode": safe_hist_mode,
                "safe_enforce_conf": safe_conf_c,
                "safe_conf_mode": safe_conf_mode,
                "safe_hist_noninferior": safe_hist_c >= enforce,
                "safe_conf_noninferior": safe_conf_c >= enforce,
                "raw_hist_would_hurt": shadow_hist < enforce,
            }
        )

    n_lift = sum(1 for r in rows if r["lift_hist"] > 0)
    n_safe = sum(1 for r in rows if r["safe_hist_noninferior"])
    return {
        "holdout": label,
        "n_test": n_test,
        "n_miss_test": sum(1 for x in test if x["is_miss"]),
        "rows": rows,
        "shadow_lifts_on_budgets": n_lift,
        "safe_hist_noninferior_all": n_safe == len(rows),
        "verdict": (
            "SUPPORT shadow dual-publish"
            if n_lift > 0 and n_safe == len(rows)
            else (
                "SUPPORT fallback-only (no lift, safe)"
                if n_lift == 0 and n_safe == len(rows)
                else "FAIL fallback or unsafe shadow"
            )
        ),
    }


def main() -> None:
    print("=== Dual-line ops simulation (Trigger∥Rank, Shadow∥Enforce) ===")
    items = load_df_proxy()

    tr_s, te_s = stratified_split(items)
    tr_t, te_t = within_model_temporal_split(items)

    fac_s = run_factorial(tr_s, te_s, "stratified")
    fac_t = run_factorial(tr_t, te_t, "within_model_temporal")
    sh_s = run_shadow_enforce(tr_s, te_s, "stratified")
    sh_t = run_shadow_enforce(tr_t, te_t, "within_model_temporal")

    print("\n--- A) Trigger∥Rank (which knob moves catch@k?) ---")
    for fac in (fac_s, fac_t):
        print(
            f"\n[{fac['holdout']}] test={fac['n_test']} miss={fac['n_miss_test']} "
            f"diluted={fac['diluted_n']} (miss_rate={fac['diluted_miss_rate']:.2f})"
        )
        for r in fac["readouts"]:
            print(
                f"  B={r['budget']:.0%} k={r['k']}: "
                f"diluted arrival={r['diluted_arrival']} "
                f"R_hist={r['diluted_R_hist']} (rank_lift={r['rank_lift_on_fixed_diluted']:+d}) | "
                f"best trigger@arrival={r['best_trigger_only']['stream']}:"
                f"{r['best_trigger_only']['caught']} "
                f"(trigger_lift vs diluted_arr={r['trigger_lift_vs_diluted_arrival']:+d}) | "
                f"rank_knob_wins={r['rank_knob_wins']}"
            )

    print("\n--- B/C) Shadow∥Enforce (+ fallback) ---")
    for sh in (sh_s, sh_t):
        print(f"\n[{sh['holdout']}] {sh['verdict']}")
        for r in sh["rows"]:
            print(
                f"  B={r['budget']:.0%} k={r['k']}: "
                f"enforce={r['enforce_arrival']} "
                f"shadow_hist={r['shadow_R_hist']} (lift={r['lift_hist']:+d}, "
                f"safe={r['safe_enforce_hist']}/{r['safe_hist_mode']}) "
                f"shadow_conf={r['shadow_conf_desc']} "
                f"oracle={r['oracle']} "
                f"raw_hist_hurts={r['raw_hist_would_hurt']}"
            )

    # Overall claims
    strat_rank_wins = all(r["rank_knob_wins"] for r in fac_s["readouts"])
    temp_shadow = sh_t["verdict"]
    print("\n--- Verdict ---")
    if strat_rank_wins:
        print(
            "SUPPORT Trigger∥Rank split on stratified+diluted: "
            "Rank lift on fixed diluted ≥ Trigger-only lift vs that baseline."
        )
    else:
        print(
            "WEAK/MIXED on Trigger∥Rank: trigger stream choice under arrival "
            "sometimes beats ranking the diluted queue — report cells, don't force."
        )
    print(f"Shadow∥Enforce stratified: {sh_s['verdict']}")
    print(
        f"Shadow∥Enforce temporal (stale table): {temp_shadow} "
        "— fallback must keep safe ≥ arrival when hist goes vacuous."
    )

    payload = {
        "claim": (
            "Dual-line ops: Trigger∥Rank knobs under budget; "
            "Shadow∥Enforce with fail-closed fallback."
        ),
        "dilution": DILUTION,
        "budgets": list(BUDGETS),
        "factorial": [fac_s, fac_t],
        "shadow_enforce": [sh_s, sh_t],
    }
    # Drop bulky factorial cells from default? Keep for audit.
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(blob, encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")
    print(f"sha256={hashlib.sha256(blob.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
