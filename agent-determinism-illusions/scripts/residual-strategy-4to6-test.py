# -*- coding: utf-8 -*-
"""Residual strategies 4–6 vs uniform / HR-first (Max Quimby follow-up).

Claim under test:
  On one residual stream with hard human budget b, do Part-7/Alex/Part-15
  style *who-to-show* policies beat uniform sampling — and how do they
  compare to high-risk-direct (strategy from the prior knife)?

  4) T2 tripwire-first: reverse-prone class ∧ UHC goes to human before others
  5) Alex external-signal rank: more fired signals → earlier in the queue
  6) Dual-line rank: enter = D∨T2, then rank-inside-stream under budget b

Method:
  Pure Monte Carlo. Each item draws:
    high_risk, reversal_class, uhc, defective, divergence, 4 Alex signals.
  Defect denser on high-risk and on reversal_class; UHC denser on defect
  (unanimous-miss shape); signals use medium TP/FP; divergence denser on
  defect (but T2 is the load-bearing tripwire, not D alone).

  All strategies audit exactly K = round(b · N) items (rank + cut).
  Human catch skill H on audited defectives.

  Also report uniform and hr_first at the same K for continuity.

Expected:
  At fixed b, hr_first wins HR miss; t2_first wins reversal-class miss;
  alex / dual_line beat uniform on overall miss when signals/T2 correlate;
  none closes the residual — they only reallocate the same human eyes.

Falsification:
  If t2 / alex / dual_line overall miss ≥ uniform in a majority of budget
  cells → those "smarter packets" do not earn complexity on this fixture.

Dependencies: stdlib only.
Run: python residual-strategy-4to6-test.py
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
OUT = RESULTS / "residual-strategy-4to6.json"

N = 3000
TRIALS = 300
SEED = 20260807
H = 0.85
BUDGETS = [0.10, 0.15, 0.25]

# 流量与缺陷
P_HR = 0.10
P_REVERSAL = 0.18
D_HR, D_REV, D_BASE = 0.35, 0.28, 0.06

# UHC / 分歧（条件于是否缺陷）
P_UHC_DEF, P_UHC_CLEAN = 0.90, 0.25
P_DIV_DEF, P_DIV_CLEAN = 0.35, 0.12

# Alex medium signals: (tp, fp)
SIGNALS = [
    ("route_changed", 0.25, 0.05),
    ("classifier_disagree", 0.50, 0.12),
    ("input_unusual", 0.20, 0.04),
    ("barely_passed", 0.35, 0.08),
]


def draw_item(rng: random.Random) -> dict:
    """抽一件残差样本（带标签与信号）。"""
    hr = rng.random() < P_HR
    rev = rng.random() < P_REVERSAL
    if hr:
        d_rate = D_HR
    elif rev:
        d_rate = D_REV
    else:
        d_rate = D_BASE
    defective = rng.random() < d_rate
    uhc = rng.random() < (P_UHC_DEF if defective else P_UHC_CLEAN)
    div = rng.random() < (P_DIV_DEF if defective else P_DIV_CLEAN)
    sigs = []
    for _name, tp, fp in SIGNALS:
        p = tp if defective else fp
        sigs.append(1 if rng.random() < p else 0)
    t2 = rev and uhc
    return {
        "hr": hr,
        "rev": rev,
        "uhc": uhc,
        "div": div,
        "t2": t2,
        "defective": defective,
        "n_sig": sum(sigs),
        "enter": div or t2,  # dual-line 进门集
    }


def audit_top_k(stream: list[dict], scores: list[float], k: int,
                rng: random.Random) -> dict:
    """按分数取前 K 件给人审（同分随机打破）。"""
    order = list(range(len(stream)))
    # 加极小噪声，保证同分可复现打乱
    keyed = [(scores[i] + rng.random() * 1e-9, i) for i in order]
    keyed.sort(reverse=True)
    chosen = {i for _s, i in keyed[:k]}

    hr_def = hr_c = rev_def = rev_c = all_def = all_c = 0
    for i, it in enumerate(stream):
        if it["defective"]:
            all_def += 1
            if it["hr"]:
                hr_def += 1
            if it["rev"]:
                rev_def += 1
            if i in chosen and rng.random() < H:
                all_c += 1
                if it["hr"]:
                    hr_c += 1
                if it["rev"]:
                    rev_c += 1
    return {
        "audit_rate": k / len(stream),
        "overall_miss": 1.0 - (all_c / all_def if all_def else 1.0),
        "hr_miss": 1.0 - (hr_c / hr_def if hr_def else 1.0),
        "rev_miss": 1.0 - (rev_c / rev_def if rev_def else 1.0),
    }


def scores_uniform(stream, rng):
    return [rng.random() for _ in stream]


def scores_hr_first(stream, rng):
    return [2.0 + rng.random() if it["hr"] else rng.random() for it in stream]


def scores_t2_first(stream, rng):
    """策略4：T2 绊索优先。"""
    return [2.0 + rng.random() if it["t2"] else rng.random() for it in stream]


def scores_alex(stream, rng):
    """策略5：外部信号条数越高越先看。"""
    return [float(it["n_sig"]) + rng.random() * 0.01 for it in stream]


def scores_dual_rank(stream, rng):
    """策略6：先 D∨T2 进门，门内 T2>D，再看信号。"""
    out = []
    for it in stream:
        if not it["enter"]:
            out.append(rng.random() * 0.1)  # 未进门：几乎排最后
        else:
            base = 2.0 + (1.0 if it["t2"] else 0.0) + 0.15 * it["n_sig"]
            out.append(base + rng.random() * 0.01)
    return out


STRATEGIES = [
    ("uniform", scores_uniform),
    ("hr_first", scores_hr_first),
    ("t2_first", scores_t2_first),
    ("alex_signals", scores_alex),
    ("dual_line_rank", scores_dual_rank),
]


def mean_std(vals):
    return {
        "mean": statistics.mean(vals),
        "std": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def main():
    print("═" * 72)
    print("  Residual strategies 4–6 (T2 / Alex / dual-line) @ hard budget")
    print(f"  N={N} trials={TRIALS} H={H}")
    print("═" * 72)

    cells = []
    for b in BUDGETS:
        k = max(1, int(round(b * N)))
        print(f"\n  budget={b:.2f}  K={k}")
        bucket = {name: [] for name, _ in STRATEGIES}
        master = random.Random(SEED + int(b * 1000))
        for _ in range(TRIALS):
            stream = [draw_item(random.Random(master.randint(0, 2**31 - 1)))
                      for __ in range(N)]
            for name, scorer in STRATEGIES:
                rng = random.Random(master.randint(0, 2**31 - 1))
                scores = scorer(stream, rng)
                bucket[name].append(audit_top_k(stream, scores, k, rng))

        row = {"budget": b, "K": k, "strategies": {}}
        # 与 uniform 比 overall_miss
        u_miss = statistics.mean([r["overall_miss"] for r in bucket["uniform"]])
        for name, _ in STRATEGIES:
            om = [r["overall_miss"] for r in bucket[name]]
            hm = [r["hr_miss"] for r in bucket[name]]
            rm = [r["rev_miss"] for r in bucket[name]]
            summary = {
                "overall_miss": mean_std(om),
                "hr_miss": mean_std(hm),
                "rev_miss": mean_std(rm),
                "overall_miss_gain_vs_uniform": u_miss - statistics.mean(om),
            }
            row["strategies"][name] = summary
            print(
                f"    {name:<16} all_miss={summary['overall_miss']['mean']:.3f}  "
                f"HR={summary['hr_miss']['mean']:.3f}  "
                f"rev={summary['rev_miss']['mean']:.3f}  "
                f"Δall vs uni={summary['overall_miss_gain_vs_uniform']:+.3f}"
            )
        cells.append(row)

    # 主张：在每个预算格，t2/alex/dual 至少一个 overall 优于 uniform ≥2pt
    wins = 0
    for row in cells:
        best = max(
            row["strategies"][n]["overall_miss_gain_vs_uniform"]
            for n in ("t2_first", "alex_signals", "dual_line_rank")
        )
        if best > 0.02:
            wins += 1
    claim_pass = wins >= (len(BUDGETS) + 1) // 2

    # 谁在 HR / rev 上最尖
    tips = []
    for row in cells:
        hr_best = min(STRATEGIES, key=lambda s: row["strategies"][s[0]]["hr_miss"]["mean"])
        rev_best = min(STRATEGIES, key=lambda s: row["strategies"][s[0]]["rev_miss"]["mean"])
        tips.append({
            "budget": row["budget"],
            "best_hr": hr_best[0],
            "best_rev": rev_best[0],
        })

    print(f"\n  cells where 4–6 beat uniform on overall miss: {wins}/{len(BUDGETS)}")
    print(f"  claim: {'PASS' if claim_pass else 'FAIL'}")
    for t in tips:
        print(f"    budget={t['budget']:.2f}: best HR={t['best_hr']}  best rev={t['best_rev']}")

    out = {
        "experiment": "residual-strategy-4to6",
        "question": (
            "Under a hard human budget, do T2-first, Alex signal-rank, and "
            "dual-line rank beat uniform sampling on the residual — and how "
            "do they trade off against hr_first?"
        ),
        "context": (
            "Max Quimby escalation probe; strategies 4–6 from the "
            "'who gets human eyes' fork (Part 7 T2, Alex signals, Part 15 "
            "rank-inside-stream)."
        ),
        "method": {
            "N": N,
            "trials": TRIALS,
            "seed": SEED,
            "human_skill": H,
            "budgets": BUDGETS,
            "p_hr": P_HR,
            "p_reversal": P_REVERSAL,
            "mechanics": "all strategies audit exactly K=round(b·N) via score rank",
        },
        "cells": cells,
        "tips": tips,
        "summary": {
            "wins_vs_uniform": wins,
            "n_budgets": len(BUDGETS),
            "pass": claim_pass,
        },
        "interpretation": (
            "Hard budget turns 'escalation policy' into rank-who-gets-seen. "
            "T2-first spends eyes on the unanimous-miss-shaped packet; "
            "Alex ranks by external dirt signals; dual-line restricts the "
            "enter set then ranks inside it; hr_first still wins the "
            "expensive class when that class is labeled. None removes the "
            "human layer — they only choose which miss you buy less of."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {OUT}")
    return 0 if claim_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
