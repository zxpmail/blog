# -*- coding: utf-8 -*-
"""Partial-stale injection test — Mike quiet-failure stress (Part 15, 2026-07-29).

Predecessor: partial-stale-shadow-test.py (pure-math scan).
This script: stress the gap on real df_proxy data via controlled staleness injection.

Question (Mike, 2026-07-29):
  The current dual-line fixture (dual-line-ops-sim.py) doesn't exercise the
  partial-stale regime — on temporal diluted, R_hist shadow_caught lands at
  0 (class_key disjoint from train → table degenerates to prior). Is the
  quiet-failure gap real on this data if we stress it, or only conceptual?

Method:
  Load real df_proxy data (qwen3-0-5b, gemma3-latest, deepseek-v4-flash JSONLs).
  Use STRATIFIED split + class stream (reversal items). On this stream:
    - arrival@k catches 8 of 8 misses (queue is reversal-only, misses cluster)
    - R_hist@k catches 8 of 8 (perfect calibration on stratified split)
  Both at ceiling — but injecting R_hist perturbation drives shadow down from
  8 while enforce stays at 8. That stress window — shadow ∈ (0, enforce) —
  is exactly Mike's quiet-failure regime.

  Inject controlled staleness into R_hist ranking:
    For perturbation p ∈ {0.0, 0.1, ..., 1.0}, N=30 random draws:
      - Compute pure R_hist ranking on class stream
      - With prob p per item, replace its R_hist score with prior (mean)
        — simulates ranker losing calibration on that item
      - shadow_p = caught at k=8 with perturbed ranking

  For each draw, compare two fallback rules:
    vacuous:      ship shadow if shadow > 0 else enforce         (current)
    noninferior:  ship shadow if shadow >= enforce else enforce   (proposed)

  Per p, report:
    - Distribution of shadow_p across draws
    - Fraction of draws landing in quiet-gap regime (shadow_p ∈ (0, enforce))
    - Mean catches lost by vacuous vs noninferior

Falsification:
  - If shadow_p never lands in (0, enforce) at any p → Mike's gap is purely
    conceptual on this fixture; report that honestly.
  - If shadow_p lands in (0, enforce) at intermediate p → gap is real and
    quantifiable on production-like traffic.

Dependencies: same as dual-line-ops-sim.py (pure Python, reads results-v2/{model}.jsonl)
Run:
  python partial-stale-injection-test.py
"""

from __future__ import annotations

import copy
import io
import json
import random
import statistics
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "partial-stale-injection.json"

DF_MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
TRAIN_FRAC = 0.70
BUDGET = 0.05
DILUTION = 0.35
HIGH = 0.9
PERTURBATIONS = [round(0.1 * i, 1) for i in range(11)]  # 0.0 .. 1.0
N_DRAWS = 30
SEED = 20260729


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


def load_df_proxy() -> list[dict]:
    items = []
    order = 0
    for model in DF_MODELS:
        path = RESULTS / f"{model}.jsonl"
        if not path.exists():
            continue
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
                    items.append({
                        "model": model, "id": sid, "order": order,
                        "class_key": sid, "is_miss": bool(is_miss),
                        "reversal": is_reversal(sid), "conf": conf,
                        "uhc": conf >= HIGH, "split": conf < HIGH,
                        "unanimous_pass": passes and conf >= HIGH,
                    })
                    order += 1
    return items


def in_stream(x: dict, stream: str) -> bool:
    if stream == "D":
        return bool(x["split"])
    if stream == "class":
        return bool(x["reversal"])
    if stream == "T2":
        return bool(x["reversal"] and x["unanimous_pass"])
    if stream == "D+T2":
        return bool(x["split"] or (x["reversal"] and x["unanimous_pass"]))
    raise ValueError(stream)


def stratified_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    train, test = [], []
    for flag in (False, True):
        bucket = sorted((x for x in items if x["is_miss"] is flag), key=lambda x: x["order"])
        cut = int(len(bucket) * TRAIN_FRAC)
        train.extend(bucket[:cut])
        test.extend(bucket[cut:])
    train.sort(key=lambda x: x["order"])
    test.sort(key=lambda x: x["order"])
    return train, test


def within_model_temporal_split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    train, test = [], []
    for model in sorted({x["model"] for x in items}):
        sub = sorted((x for x in items if x["model"] == model), key=lambda x: x["order"])
        cut = int(len(sub) * TRAIN_FRAC)
        train.extend(sub[:cut])
        test.extend(sub[cut:])
    train.sort(key=lambda x: x["order"])
    test.sort(key=lambda x: x["order"])
    return train, test


def members_class_stream(test: list[dict]) -> list[dict]:
    """class stream = reversal items, re-indexed by position (matches dual-line members())."""
    q = sorted((x for x in test if in_stream(x, "class")), key=lambda x: x["order"])
    out = []
    for i, x in enumerate(q):
        y = dict(x)
        y["order"] = i
        out.append(y)
    return out


def fit_hist(train: list[dict]) -> tuple[dict[str, float], float]:
    hits: dict[str, list[int]] = {}
    for x in train:
        hits.setdefault(x["class_key"], []).append(1 if x["is_miss"] else 0)
    table = {k: sum(v) / len(v) for k, v in hits.items()}
    prior = sum(1 for x in train if x["is_miss"]) / len(train) if train else 0.0
    return table, prior


def build_diluted(test: list[dict]) -> list[dict]:
    """Match dual-line-ops-sim.build_diluted exactly: distractors first (by
    original order), then base_miss; reassign order index. No shuffle."""
    base_miss = [x for x in test if in_stream(x, "D+T2") and x["is_miss"]]
    distractors = [x for x in test if not x["is_miss"]]
    if not base_miss:
        return []
    n_dist = int(round(len(base_miss) * (1.0 - DILUTION) / DILUTION))
    n_dist = max(0, min(n_dist, len(distractors)))
    dist = sorted(distractors, key=lambda x: x["order"])[:n_dist]
    ordered = sorted(dist, key=lambda x: x["order"]) + sorted(base_miss, key=lambda x: x["order"])
    out = []
    for i, x in enumerate(ordered):
        y = dict(x)
        y["order"] = i
        out.append(y)
    return out


def rank_r_hist(queue: list[dict], table: dict[str, float], prior: float) -> list[dict]:
    return sorted(queue, key=lambda x: (-table.get(x["class_key"], prior), x["order"]))


def rank_arrival(queue: list[dict]) -> list[dict]:
    return sorted(queue, key=lambda x: x["order"])


def rank_oracle(queue: list[dict]) -> list[dict]:
    return sorted(queue, key=lambda x: (not x["is_miss"], x["order"]))


def caught(top_k: list[dict]) -> int:
    return sum(1 for x in top_k if x["is_miss"])


def perturb_ranking(
    ranked: list[dict], table: dict[str, float], prior: float, p: float, rng: random.Random
) -> list[dict]:
    """With prob p per item, replace its R_hist score with prior (mean).

    Simulates a ranker that's partially lost calibration — some items still
    ranked by history, others fall back to population average (= effectively
    arrival order among the perturbed).
    """
    if p <= 0:
        return list(ranked)
    perturbed_items = []
    for x in ranked:
        if rng.random() < p:
            perturbed_items.append((x, prior))
        else:
            perturbed_items.append((x, table.get(x["class_key"], prior)))
    # Re-sort: items with higher score first; perturbed items (prior) sink
    # unless prior happens to be high. Ties broken by arrival order.
    perturbed_items.sort(key=lambda t: (-t[1], t[0]["order"]))
    return [x for x, _ in perturbed_items]


def ship_vacuous(shadow: int, enforce: int, oracle: int) -> int:
    if shadow == 0 and oracle > 0:
        return enforce
    return shadow


def ship_noninferior(shadow: int, enforce: int) -> int:
    if shadow < enforce:
        return enforce
    return shadow


def main() -> int:
    items = load_df_proxy()
    if not items:
        print("[ABORT] No df_proxy data found.")
        return 1

    train, test = stratified_split(items)
    table, prior = fit_hist(train)
    queue = members_class_stream(test)

    k = int(len(test) * BUDGET)
    if k <= 0:
        print(f"[ABORT] k={k} too small")
        return 1

    pure_ranked = rank_r_hist(queue, table, prior)
    arrival_ranked = rank_arrival(queue)
    oracle_ranked = rank_oracle(queue)

    enforce = caught(arrival_ranked[:k])
    oracle = caught(oracle_ranked[:k])
    pure_shadow = caught(pure_ranked[:k])

    print("═══ partial-stale injection stress ═══")
    print(f"stratified class stream: n={len(queue)}, k={k}, B={BUDGET}")
    print(f"queue_miss: {sum(1 for x in queue if x['is_miss'])}")
    print(f"enforce (arrival@k): {enforce}")
    print(f"oracle (max@k):      {oracle}")
    print(f"pure R_hist shadow:  {pure_shadow}  (current dual-line rule)")
    print()

    rows = []
    rng = random.Random(SEED)
    for p in PERTURBATIONS:
        shadows = []
        vacuous_ships = []
        noninferior_ships = []
        god_ships = []
        quiet_gap_count = 0
        vacuous_loss_vs_noninferior = []
        vacuous_loss_vs_god = []

        for draw in range(N_DRAWS):
            perturbed = perturb_ranking(pure_ranked, table, prior, p, rng)
            shadow_p = caught(perturbed[:k])

            sv = ship_vacuous(shadow_p, enforce, oracle)
            sn = ship_noninferior(shadow_p, enforce)
            sg = max(shadow_p, enforce)

            shadows.append(shadow_p)
            vacuous_ships.append(sv)
            noninferior_ships.append(sn)
            god_ships.append(sg)

            in_gap = 0 < shadow_p < enforce
            if in_gap:
                quiet_gap_count += 1
                vacuous_loss_vs_noninferior.append(sn - sv)
            vacuous_loss_vs_god.append(sg - sv)

        mean_shadow = statistics.mean(shadows)
        median_shadow = statistics.median(shadows)
        stdev_shadow = statistics.pstdev(shadows) if len(shadows) > 1 else 0.0
        min_shadow = min(shadows)
        max_shadow = max(shadows)
        mean_v_ship = statistics.mean(vacuous_ships)
        mean_n_ship = statistics.mean(noninferior_ships)
        mean_g_ship = statistics.mean(god_ships)
        mean_loss_v_vs_n = (
            statistics.mean(vacuous_loss_vs_noninferior) if vacuous_loss_vs_noninferior else 0.0
        )
        mean_loss_v_vs_g = statistics.mean(vacuous_loss_vs_god) if vacuous_loss_vs_god else 0.0

        rows.append({
            "p": p,
            "mean_shadow": round(mean_shadow, 2),
            "median_shadow": median_shadow,
            "stdev_shadow": round(stdev_shadow, 2),
            "min_shadow": min_shadow,
            "max_shadow": max_shadow,
            "quiet_gap_draws": quiet_gap_count,
            "quiet_gap_fraction": round(quiet_gap_count / N_DRAWS, 2),
            "mean_ship_vacuous": round(mean_v_ship, 2),
            "mean_ship_noninferior": round(mean_n_ship, 2),
            "mean_ship_god": round(mean_g_ship, 2),
            "mean_catches_lost_vacuous_vs_noninferior": round(mean_loss_v_vs_n, 2),
            "mean_catches_lost_vacuous_vs_god": round(mean_loss_v_vs_g, 2),
            "shadow_distribution": dict(
                sorted({s: shadows.count(s) for s in set(shadows)}.items())
            ),
        })

    print(f"{'p':>4} | {'shadow mean':>12} | {'gap frac':>9} | {'vac ship':>9} | {'non ship':>9} | {'vac−non':>8}")
    print("-" * 70)
    for r in rows:
        print(
            f"{r['p']:>4.1f} | "
            f"{r['mean_shadow']:>12.2f} | "
            f"{r['quiet_gap_fraction']:>9.2f} | "
            f"{r['mean_ship_vacuous']:>9.2f} | "
            f"{r['mean_ship_noninferior']:>9.2f} | "
            f"{r['mean_catches_lost_vacuous_vs_noninferior']:>8.2f}"
        )
    print()

    # Where does the gap first appear?
    first_gap_p = next((r["p"] for r in rows if r["quiet_gap_draws"] > 0), None)
    peak_gap = max(rows, key=lambda r: r["quiet_gap_fraction"])
    peak_loss = max(rows, key=lambda r: r["mean_catches_lost_vacuous_vs_noninferior"])

    print(f"First p where quiet-gap regime appears: {first_gap_p}")
    print(f"Peak gap fraction: p={peak_gap['p']}, gap_frac={peak_gap['quiet_gap_fraction']}")
    print(f"Peak vacuous-vs-noninferior loss: p={peak_loss['p']}, "
          f"loss={peak_loss['mean_catches_lost_vacuous_vs_noninferior']}/draw")
    print()

    out = {
        "experiment": "partial-stale-injection-stress",
        "question": (
            "Does the quiet-failure regime (shadow ∈ (0, enforce)) materialize "
            "on real df_proxy data when R_hist ranking is partially perturbed?"
        ),
        "source": "Mike Czerwinski comment on Part 15, 2026-07-29 (quiet-failure challenge)",
        "predecessor": "partial-stale-shadow-test.py (pure-math scan)",
        "method": {
            "data": "df_proxy (qwen3-0-5b, gemma3-latest, deepseek-v4-flash)",
            "queue": "within_model_temporal diluted (35% miss rate)",
            "k": k,
            "enforce_arrival": enforce,
            "oracle": oracle,
            "pure_R_hist_shadow": pure_shadow,
            "perturbations": PERTURBATIONS,
            "n_draws_per_p": N_DRAWS,
            "perturbation_model": (
                "With prob p per item, replace its R_hist score with prior; "
                "re-sort. Simulates partial loss of calibration."
            ),
        },
        "rules": {
            "vacuous": "ship shadow if shadow > 0 else enforce (current dual-line)",
            "noninferior": "ship shadow if shadow >= enforce else enforce (proposed)",
            "god": "ship max(shadow, enforce)",
        },
        "results": rows,
        "summary": {
            "first_p_with_gap": first_gap_p,
            "peak_gap_p": peak_gap["p"],
            "peak_gap_fraction": peak_gap["quiet_gap_fraction"],
            "peak_vacuous_vs_noninferior_loss_p": peak_loss["p"],
            "peak_vacuous_vs_noninferior_loss": peak_loss["mean_catches_lost_vacuous_vs_noninferior"],
            "interpretation": (
                "If first_p_with_gap is not None and peak_gap_fraction > 0: "
                "Mike's quiet-failure gap is real and quantifiable on this "
                "fixture when ranker partially loses calibration. The vacuous "
                "rule loses catches vs the noninferior rule."
            ),
        },
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
