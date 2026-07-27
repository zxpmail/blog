# -*- coding: utf-8 -*-
"""Defect-class concentration histogram vs unique-catch π* fragile zone (Mike).

Claim under test (Mike, after co-occur dose / generative labels):
    π_route_cd is a real-world question: what fraction of the defect population
    is one class where route and CD diagnose the *same* cause. π*≈0.50 flips
    middle; π=1 breaks ends. Order is fragile only under high concentration.
    Cheaper next step before rerunning the fixture: histogram how concentrated
    actual defect classes are.

Method:
    On this repo the available labeled defect taxonomy is DF v2 MISS runs
    (scenario_id / model) — *not* generative route_cd labels on the
    external-signal sim. Histogram that taxonomy as the cheap observational
    step Mike asked for; compare max share and HHI to the dose π* band.

    Metrics:
      max_share = max_c n_c / N
      HHI = sum_c (n_c / N)^2
      fragile_middle if max_share ≥ 0.50 (π* from unique-catch-cooccur-dose)
      extreme_ends   if max_share ≥ 1.00 (only the π=1 dose case)

Caveat (load-bearing):
    scenario_id ≠ route_cd co-occurrence class. This histogram answers
    "how concentrated is *this* fixture's miss taxonomy?" — a gate before
    treating middle prune as locked — not a plug-in for π_route_cd on the
    sampling sim.

Dependencies: none (reads results-v2/*.jsonl).
Run:
    python scripts/defect-class-concentration-histogram.py
"""

from __future__ import annotations

import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
PI_STAR_MIDDLE = 0.50  # from unique-catch-cooccur-dose
PI_EXTREME_ENDS = 1.00


def load_misses() -> list[tuple[str, str]]:
    """Return (model, scenario_id) for each MISS run."""
    out: list[tuple[str, str]] = []
    for model in MODELS:
        path = RESULTS / f"{model}.jsonl"
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            if row.get("is_legit"):
                continue
            sid = row["id"]
            for v in row.get("run_verdicts", []):
                if v.get("passes") and v.get("error_type") == "MISS":
                    out.append((model, sid))
    return out


def histogram(items: list[str]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for x in items:
        counts[x] += 1
    n = len(items)
    shares = {k: v / n for k, v in counts.items()} if n else {}
    hhi = sum(s * s for s in shares.values())
    ranked = sorted(shares.items(), key=lambda kv: -kv[1])
    max_share = ranked[0][1] if ranked else 0.0
    return {
        "n": n,
        "n_classes": len(counts),
        "max_class": ranked[0][0] if ranked else None,
        "max_share": round(max_share, 6),
        "hhi": round(hhi, 6),
        "in_fragile_middle_band": max_share >= PI_STAR_MIDDLE,
        "in_extreme_ends_band": max_share >= PI_EXTREME_ENDS,
        "top": [
            {"id": k, "n": counts[k], "share": round(s, 6)}
            for k, s in ranked[:10]
        ],
        "all_shares": {k: round(s, 6) for k, s in ranked},
    }


def main() -> None:
    misses = load_misses()
    by_scenario = histogram([sid for _, sid in misses])
    by_model = histogram([m for m, _ in misses])
    # model×scenario as finer taxonomy
    by_model_sid = histogram([f"{m}|{sid}" for m, sid in misses])

    print("=" * 72)
    print("Defect-class concentration vs π* fragile zone (Mike cheaper step)")
    print(f"π*_middle={PI_STAR_MIDDLE}, π_extreme_ends={PI_EXTREME_ENDS}")
    print(f"N_MISS={len(misses)}")
    print("=" * 72)

    for name, h in (
        ("scenario_id", by_scenario),
        ("model", by_model),
        ("model|scenario", by_model_sid),
    ):
        print(f"\n{name}: classes={h['n_classes']}  max={h['max_class']} "
              f"share={h['max_share']:.3f}  HHI={h['hhi']:.3f}  "
              f"fragile_middle={h['in_fragile_middle_band']}")
        for row in h["top"][:5]:
            print(f"  {row['id']:20s}  n={row['n']:3d}  share={row['share']:.3f}")

    interpretation = [
        "Taxonomy here = DF v2 MISS runs (scenario / model), not route_cd "
        "labels on the external-signal sim — cheap histogram gate Mike asked for.",
        f"By scenario_id: max_share={by_scenario['max_share']:.3f} "
        f"({by_scenario['max_class']}) — "
        + (
            "IN fragile middle band (≥π*=0.50); middle prune not locked on this cut."
            if by_scenario["in_fragile_middle_band"]
            else "BELOW π*=0.50 fragile band; on this proxy, concentration alone "
            "does not put you in the dose flip regime."
        ),
        f"By model: max_share={by_model['max_share']:.3f} "
        f"({by_model['max_class']}) — model concentration is a different axis "
        "(already reported on Part 6); not π_route_cd.",
        "Next real lock still needs a histogram where the class *is* "
        "'route and CD diagnostic of the same cause' on a production / "
        "external-signal trace — this run only clears the cheaper gate on "
        "available miss taxonomy.",
    ]

    print("\n" + "=" * 72)
    print("INTERPRETATION")
    for line in interpretation:
        print(line)
    print("=" * 72)

    out = {
        "experiment": "defect-class-concentration-histogram",
        "claim": (
            "Histogram available defect-class concentration and compare to "
            "unique-catch dose π*≈0.50 fragile middle band (Mike cheaper step)"
        ),
        "pi_star_middle": PI_STAR_MIDDLE,
        "pi_extreme_ends": PI_EXTREME_ENDS,
        "source": "DF v2 MISS runs from results-v2/*.jsonl",
        "caveat": (
            "scenario_id/model ≠ generative route_cd co-occurrence class on "
            "the sampling fixture"
        ),
        "by_scenario_id": by_scenario,
        "by_model": by_model,
        "by_model_scenario": by_model_sid,
        "interpretation": interpretation,
    }
    out_path = RESULTS / "defect-class-concentration-histogram.json"
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
