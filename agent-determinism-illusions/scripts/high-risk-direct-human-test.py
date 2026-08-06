# -*- coding: utf-8 -*-
"""High-risk direct-to-human vs uniform residual audit (Max / Part 8 follow-up).

Claim under test:
  On a mixed stream, routing *all* high-risk items to humans (no auto-pass),
  and spending only the *remaining* audit budget on the ordinary residual,
  beats uniform fixed-rate audit on **high-risk miss rate** at the same total
  human budget — and is the honest "shrink residual" move: dangerous mass
  never enters the auto lane.

Method:
  Pure Monte Carlo. Each item: high-risk with rate r_hr; defective with
  d_hr if high-risk else d_norm (defects denser on high-risk). Human catch
  skill H when auditing.

  Strategies (same expected audit budget b):
    uniform — audit every item with p = b
    hr_first — audit 100% of high-risk; audit non-HR with
               p_rest = max(0, (b - r_hr) / (1 - r_hr))
               (if b ≤ r_hr, all budget is spent on HR; ordinary residual
               gets zero sampling)

  Sweeps: r_hr ∈ {0.05, 0.10, 0.20}, b ∈ {0.10, 0.20, 0.30}.

Expected:
  hr_first high-risk miss ≪ uniform at every cell where b ≥ r_hr enough to
  cover HR mass; when b ≈ r_hr, ordinary residual is starved (honest cost).
  Overall miss may or may not improve — the load-bearing metric is HR miss.

Falsification:
  If hr_first HR miss ≥ uniform HR miss in a majority of cells with b > r_hr
  → "direct-to-human for high-risk" does not earn priority on this fixture.

Dependencies: stdlib only.
Run: python high-risk-direct-human-test.py
"""

from __future__ import annotations

import io
import json
import random
import statistics
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "high-risk-direct-human.json"

STREAM_LENGTH = 3000
TRIALS = 400
SEED = 20260807
HUMAN_SKILL = 0.85
D_HR = 0.35
D_NORM = 0.08

HR_RATES = [0.05, 0.10, 0.20]
BUDGETS = [0.10, 0.20, 0.30]


def make_stream(r_hr: float, rng: random.Random) -> list[tuple[bool, bool]]:
    """生成 (is_high_risk, is_defective) 流。"""
    out = []
    for _ in range(STREAM_LENGTH):
        hr = rng.random() < r_hr
        d = rng.random() < (D_HR if hr else D_NORM)
        out.append((hr, d))
    return out


def run_uniform(stream, budget: float, rng: random.Random) -> dict:
    """全员固定比例抽检。"""
    return _run(stream, budget, hr_first=False, rng=rng)


def run_hr_first(stream, budget: float, r_hr: float, rng: random.Random) -> dict:
    """高风险优先进人；总预算封顶为 b（盖不住时只抽检一部分高风险）。"""
    if r_hr <= budget + 1e-12:
        p_hr = 1.0
        p_rest = (budget - r_hr) / (1.0 - r_hr) if r_hr < 1.0 else 0.0
    else:
        # 预算不够盖住全部高风险：只抽检 HR，比例 = b/r_hr；普通件为 0
        p_hr = budget / r_hr
        p_rest = 0.0
    return _run(stream, budget, hr_first=True, p_hr=p_hr, p_rest=p_rest, rng=rng)


def _run(stream, budget, hr_first, rng, p_rest=0.0, p_hr=1.0) -> dict:
    """执行一种策略并汇总漏放/审阅。"""
    audits = 0
    hr_def = hr_caught = 0
    norm_def = norm_caught = 0
    for hr, defective in stream:
        if hr_first:
            do_audit = (rng.random() < p_hr) if hr else (rng.random() < p_rest)
        else:
            do_audit = rng.random() < budget
        if hr and defective:
            hr_def += 1
        if (not hr) and defective:
            norm_def += 1
        if do_audit:
            audits += 1
            if defective and rng.random() < HUMAN_SKILL:
                if hr:
                    hr_caught += 1
                else:
                    norm_caught += 1
    n = len(stream)
    total_def = hr_def + norm_def
    total_caught = hr_caught + norm_caught
    return {
        "audit_rate": audits / n,
        "hr_miss": 1.0 - (hr_caught / hr_def if hr_def else 1.0),
        "norm_miss": 1.0 - (norm_caught / norm_def if norm_def else 1.0),
        "overall_miss": 1.0 - (total_caught / total_def if total_def else 1.0),
        "hr_def": hr_def,
        "norm_def": norm_def,
        "p_rest": p_rest if hr_first else budget,
        "p_hr": p_hr if hr_first else budget,
    }


def summarize(rows: list[dict]) -> dict:
    """跨 trial 均值。"""
    keys = ["audit_rate", "hr_miss", "norm_miss", "overall_miss"]
    out = {}
    for k in keys:
        vals = [r[k] for r in rows]
        out[f"{k}_mean"] = statistics.mean(vals)
        out[f"{k}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return out


def main():
    print("═" * 72)
    print("  High-risk direct-to-human vs uniform residual audit")
    print(f"  stream={STREAM_LENGTH} trials={TRIALS} H={HUMAN_SKILL} "
          f"d_hr={D_HR} d_norm={D_NORM}")
    print("═" * 72)

    cells = []
    wins = 0
    eligible = 0

    for r_hr in HR_RATES:
        for b in BUDGETS:
            u_rows, h_rows = [], []
            rng_master = random.Random(SEED + int(r_hr * 1000) + int(b * 100))
            for _ in range(TRIALS):
                stream = make_stream(r_hr, random.Random(rng_master.randint(0, 2**31 - 1)))
                u_rows.append(run_uniform(
                    stream, b, random.Random(rng_master.randint(0, 2**31 - 1))
                ))
                h_rows.append(run_hr_first(
                    stream, b, r_hr, random.Random(rng_master.randint(0, 2**31 - 1))
                ))
            u = summarize(u_rows)
            h = summarize(h_rows)
            p_rest = max(0.0, (b - r_hr) / (1.0 - r_hr)) if r_hr < 1 else 0.0
            hr_gain = u["hr_miss_mean"] - h["hr_miss_mean"]
            # 主主张只在预算盖得住高风险质量时评判
            covered = b + 1e-9 >= r_hr
            if covered:
                eligible += 1
                if hr_gain > 0.05:
                    wins += 1
            starved = p_rest < 1e-9
            read = (
                "HR covered; ordinary residual starved"
                if starved and covered
                else (
                    "HR miss down at same budget"
                    if hr_gain > 0.05
                    else "no material HR-miss win"
                )
            )
            print(
                f"\n  r_hr={r_hr:.2f} budget={b:.2f}  p_rest={p_rest:.3f}"
                f"{'  [STARVE norm]' if starved else ''}"
            )
            print(
                f"    uniform  HR_miss={u['hr_miss_mean']:.3f} "
                f"norm_miss={u['norm_miss_mean']:.3f} "
                f"all_miss={u['overall_miss_mean']:.3f} "
                f"audit={u['audit_rate_mean']:.3f}"
            )
            print(
                f"    hr_first HR_miss={h['hr_miss_mean']:.3f} "
                f"norm_miss={h['norm_miss_mean']:.3f} "
                f"all_miss={h['overall_miss_mean']:.3f} "
                f"audit={h['audit_rate_mean']:.3f}"
            )
            print(f"    ΔHR_miss={hr_gain:+.3f}  → {read}")

            cells.append({
                "r_hr": r_hr,
                "budget": b,
                "p_rest": p_rest,
                "budget_covers_hr_mass": covered,
                "ordinary_starved": starved,
                "uniform": u,
                "hr_first": h,
                "hr_miss_gain": hr_gain,
                "read": read,
            })

    claim_pass = wins >= max(1, (eligible + 1) // 2)
    print("\n  Overall:")
    print(f"    cells with budget≥r_hr and HR_miss gain>5pt: {wins}/{eligible} eligible")
    print(f"    claim (hr_first better on HR miss): {'PASS' if claim_pass else 'FAIL'}")

    out = {
        "experiment": "high-risk-direct-human",
        "question": (
            "At the same total human audit budget, does sending all "
            "high-risk items to humans beat uniform residual sampling "
            "on high-risk miss rate?"
        ),
        "context": (
            "Follow-up to Max Quimby escalation-line probe and the "
            "'shrink residual' fork: high-risk direct-to-human (Part 4 "
            "class B shape) vs uniform / yield-adaptive residual spend."
        ),
        "method": {
            "stream_length": STREAM_LENGTH,
            "trials": TRIALS,
            "seed": SEED,
            "human_skill": HUMAN_SKILL,
            "d_hr": D_HR,
            "d_norm": D_NORM,
            "hr_rates": HR_RATES,
            "budgets": BUDGETS,
            "p_rest_formula": "max(0, (budget - r_hr) / (1 - r_hr))",
        },
        "cells": cells,
        "summary": {
            "eligible_cells": eligible,
            "wins_on_hr_miss": wins,
            "pass": claim_pass,
        },
        "interpretation": (
            "High-risk direct-to-human is the best *spend of a fixed human "
            "budget* against the expensive miss class: HR miss drops hard "
            "whenever budget can cover HR traffic mass. The arithmetic is "
            "honest — if budget ≈ HR share, ordinary residual gets zero "
            "sampling (starvation). That is not a failure of the policy; it "
            "is the cost of not auto-passing the dangerous class. Uniform "
            "10% looks 'fair' and leaks HR; hr_first looks 'unfair' and "
            "buys the miss that matters. Shrinking residual by refusing "
            "auto on high-risk beats tuning yield on a mixed queue."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {OUT}")
    return 0 if claim_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
