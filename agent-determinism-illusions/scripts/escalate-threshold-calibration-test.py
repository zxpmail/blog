# -*- coding: utf-8 -*-
"""Escalate-threshold calibration — fixed vs human-yield adaptive (Max Quimby).

Claim under test (Max Quimby on Part 8, 2026-08-06):
  Once named evasions are deterministic catches and the unenumerated residual
  routes to humans, the load-bearing knob is the escalation line. Does adapting
  the audit rate to reviewers' *observed yield* (catches / audits in a recent
  window) beat a fixed audit fraction on the residual stream — lower miss rate
  at similar queue cost, or same miss at lower cost?

Method:
  Pure Monte Carlo. Stream = post-L0/L1 residual only (named evasions already
  filtered). Each item is defective with base rate d. When audited, a human
  catches a defective with skill H (misses with 1−H); clean audits never "catch".

  Strategies:
    fixed     — audit each item with p = FIXED_P (default 0.10)
    adaptive  — start at FIXED_P; every WINDOW stream items, set next p from
                window yield = catches/audits:
                  yield > YIELD_HIGH → p += STEP (residual looks dirty)
                  yield < YIELD_LOW  → p -= STEP (queue returning little)
                  else hold; clamp to [P_MIN, P_MAX]

  Sweeps: defect rate d ∈ {0.05, 0.15, 0.30}, human skill H ∈ {0.60, 0.85}.
  Also reports fixed-at-matched-budget: fixed p set to adaptive's mean audit
  rate in that trial (oracle-matched cost), to separate "right average rate"
  from "online adaptation".

Expected:
  Adaptive reduces miss rate vs fixed-0.10 when d is high/unstable, at higher
  or similar audit cost; vs matched-budget fixed, gain shrinks — adaptation
  mainly tracks the right operating point, not magic.

Falsification:
  If adaptive miss ≥ fixed-0.10 miss in every (d, H) cell *and* never beats
  matched-budget fixed on miss → "adapt-to-yield" does not earn its complexity
  on this fixture; the line stays a budget choice.

Dependencies: stdlib only.
Run: python escalate-threshold-calibration-test.py
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
OUT = RESULTS / "escalate-threshold-calibration.json"

STREAM_LENGTH = 2000
TRIALS = 400
WINDOW = 50
FIXED_P = 0.10
P_MIN, P_MAX = 0.05, 0.50
YIELD_LOW, YIELD_HIGH = 0.05, 0.15
STEP = 0.05
SEED = 20260807

DEFECT_RATES = [0.05, 0.15, 0.30]
HUMAN_SKILLS = [0.60, 0.85]


def run_fixed(stream: list[bool], p: float, human_skill: float, rng: random.Random) -> dict:
    """固定比例抽检。"""
    audits = catches = defect_caught = 0
    n_def = sum(stream)
    for defective in stream:
        if rng.random() < p:
            audits += 1
            if defective and rng.random() < human_skill:
                catches += 1
                defect_caught += 1
    return _metrics(len(stream), n_def, audits, defect_caught)


def run_adaptive(
    stream: list[bool], human_skill: float, rng: random.Random
) -> tuple[dict, float]:
    """按近窗人工 yield 调节下一窗抽检比例。"""
    p = FIXED_P
    audits = catches = defect_caught = 0
    n_def = sum(stream)
    win_audits = win_catches = 0
    p_sum = 0.0

    for i, defective in enumerate(stream):
        p_sum += p
        if rng.random() < p:
            audits += 1
            win_audits += 1
            if defective and rng.random() < human_skill:
                catches += 1
                win_catches += 1
                defect_caught += 1

        if (i + 1) % WINDOW == 0:
            if win_audits > 0:
                y = win_catches / win_audits
                if y > YIELD_HIGH:
                    p = min(P_MAX, p + STEP)
                elif y < YIELD_LOW:
                    p = max(P_MIN, p - STEP)
            win_audits = win_catches = 0

    mean_p = p_sum / len(stream)
    return _metrics(len(stream), n_def, audits, defect_caught), mean_p


def _metrics(n: int, n_def: int, audits: int, defect_caught: int) -> dict:
    """汇总审阅率、抓漏率、漏放率、效率。"""
    audit_rate = audits / n if n else 0.0
    catch_rate = defect_caught / n_def if n_def else 0.0
    miss_rate = 1.0 - catch_rate if n_def else 0.0
    efficiency = catch_rate / audit_rate if audit_rate > 0 else 0.0
    yield_rate = defect_caught / audits if audits else 0.0
    return {
        "audit_rate": audit_rate,
        "catch_rate": catch_rate,
        "miss_rate": miss_rate,
        "efficiency": efficiency,
        "yield_rate": yield_rate,
        "n_defective": n_def,
        "n_audits": audits,
        "n_caught": defect_caught,
    }


def one_trial(d: float, h: float, rng: random.Random) -> dict:
    """单次试验：生成残差流，三种策略各用独立 RNG（共享同一缺陷流）。"""
    stream = [rng.random() < d for _ in range(STREAM_LENGTH)]
    fixed = run_fixed(stream, FIXED_P, h, random.Random(rng.randint(0, 2**31 - 1)))
    adaptive, mean_p = run_adaptive(
        stream, h, random.Random(rng.randint(0, 2**31 - 1))
    )
    # 匹配预算：用本 trial 自适应的平均审阅率做固定对照
    matched = run_fixed(
        stream, mean_p, h, random.Random(rng.randint(0, 2**31 - 1))
    )
    return {
        "fixed": fixed,
        "adaptive": {**adaptive, "mean_p": mean_p},
        "matched_budget_fixed": matched,
    }


def summarize(trials: list[dict], key: str) -> dict:
    """跨 trial 均值/标准差。"""
    fields = ["audit_rate", "catch_rate", "miss_rate", "efficiency", "yield_rate"]
    out = {}
    for f in fields:
        vals = [t[key][f] for t in trials]
        out[f"{f}_mean"] = statistics.mean(vals)
        out[f"{f}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
    if key == "adaptive":
        ps = [t[key]["mean_p"] for t in trials]
        out["mean_p_mean"] = statistics.mean(ps)
        out["mean_p_std"] = statistics.stdev(ps) if len(ps) > 1 else 0.0
    return out


def cell_verdict(fixed: dict, adaptive: dict, matched: dict) -> dict:
    """单格判读：自适应是否赢固定 / 是否只是调到了平均预算。"""
    miss_gain_vs_fixed = fixed["miss_rate_mean"] - adaptive["miss_rate_mean"]
    miss_gain_vs_matched = matched["miss_rate_mean"] - adaptive["miss_rate_mean"]
    audit_delta_vs_fixed = adaptive["audit_rate_mean"] - fixed["audit_rate_mean"]
    beats_fixed = miss_gain_vs_fixed > 0.02  # ≥2pt miss drop
    beats_matched = miss_gain_vs_matched > 0.02
    return {
        "miss_gain_vs_fixed_0_10": miss_gain_vs_fixed,
        "miss_gain_vs_matched_budget": miss_gain_vs_matched,
        "audit_delta_vs_fixed_0_10": audit_delta_vs_fixed,
        "beats_fixed_on_miss": beats_fixed,
        "beats_matched_on_miss": beats_matched,
        "read": (
            "adaptation earns miss reduction beyond average-rate choice"
            if beats_matched
            else (
                "mostly tracks a better average audit rate"
                if beats_fixed and not beats_matched
                else "no material miss win vs fixed-0.10"
            )
        ),
    }


def main():
    print("═" * 72)
    print("  Escalate-threshold calibration — fixed vs yield-adaptive")
    print(f"  stream={STREAM_LENGTH} trials={TRIALS} window={WINDOW} "
          f"fixed_p={FIXED_P}")
    print("═" * 72)

    cells = []
    beats_fixed_count = 0
    beats_matched_count = 0

    for d in DEFECT_RATES:
        for h in HUMAN_SKILLS:
            rng = random.Random(SEED + int(d * 1000) + int(h * 100))
            trials = [one_trial(d, h, rng) for _ in range(TRIALS)]
            fixed_s = summarize(trials, "fixed")
            adap_s = summarize(trials, "adaptive")
            match_s = summarize(trials, "matched_budget_fixed")
            v = cell_verdict(fixed_s, adap_s, match_s)
            if v["beats_fixed_on_miss"]:
                beats_fixed_count += 1
            if v["beats_matched_on_miss"]:
                beats_matched_count += 1

            print(
                f"\n  d={d:.2f} H={h:.2f}  |  "
                f"fixed miss={fixed_s['miss_rate_mean']:.3f} "
                f"audit={fixed_s['audit_rate_mean']:.3f}  |  "
                f"adapt miss={adap_s['miss_rate_mean']:.3f} "
                f"audit={adap_s['audit_rate_mean']:.3f} "
                f"(mean_p={adap_s['mean_p_mean']:.3f})  |  "
                f"matched miss={match_s['miss_rate_mean']:.3f}"
            )
            print(f"    → {v['read']}")

            cells.append({
                "defect_rate": d,
                "human_skill": h,
                "fixed": fixed_s,
                "adaptive": adap_s,
                "matched_budget_fixed": match_s,
                "verdict": v,
            })

    n_cells = len(cells)
    # 主张：自适应至少在半数格上相对 fixed-0.10 降 miss；相对匹配预算则多数只是调率
    claim_beats_fixed = beats_fixed_count >= max(1, n_cells // 2)
    mostly_rate_tracking = (
        beats_fixed_count > 0 and beats_matched_count <= beats_fixed_count // 2
    )
    overall_pass = claim_beats_fixed  # 主主张：对固定线有用；匹配预算解读进 interpretation

    print("\n  Overall:")
    print(f"    cells beating fixed-0.10 on miss: {beats_fixed_count}/{n_cells}")
    print(f"    cells beating matched-budget fixed: {beats_matched_count}/{n_cells}")
    print(f"    claim (adaptive helps vs fixed line): "
          f"{'PASS' if claim_beats_fixed else 'FAIL'}")
    print(f"    read: {'mostly average-rate tracking' if mostly_rate_tracking else 'has beyond-rate adaptation gain' if beats_matched_count else 'weak/no gain'}")

    out = {
        "experiment": "escalate-threshold-calibration",
        "question": (
            "On the unenumerated residual, does adapting audit rate to "
            "reviewers' observed yield beat a fixed escalation fraction?"
        ),
        "context": (
            "Max Quimby on Part 8 (2026-08-06): FS channel is Goodhart-able; "
            "named-evasion = blocklist; the ballgame is escalation calibration "
            "— fixed vs adapt to human catch/yield."
        ),
        "method": {
            "stream_length": STREAM_LENGTH,
            "trials": TRIALS,
            "window": WINDOW,
            "fixed_p": FIXED_P,
            "p_bounds": [P_MIN, P_MAX],
            "yield_band": [YIELD_LOW, YIELD_HIGH],
            "step": STEP,
            "seed": SEED,
            "defect_rates": DEFECT_RATES,
            "human_skills": HUMAN_SKILLS,
            "note": (
                "Residual-only stream (post named-evasion filters). "
                "Yield = human catches / audits in window. Matched-budget "
                "fixed uses that trial's adaptive mean_p."
            ),
        },
        "cells": cells,
        "summary": {
            "n_cells": n_cells,
            "beats_fixed_count": beats_fixed_count,
            "beats_matched_count": beats_matched_count,
            "claim_beats_fixed": claim_beats_fixed,
            "mostly_rate_tracking": mostly_rate_tracking,
            "pass": overall_pass,
        },
        "interpretation": (
            "Yield-adaptive audit moves the operating point when residual "
            "defect mass is high enough for windows to see yield — beating "
            "naive fixed-0.10 on miss. Against a fixed rate set to the same "
            "average audit budget, the extra gain usually shrinks: adaptation "
            "mostly discovers the right average rate online. It does not "
            "close unenumerated miss by itself; it spends human queue where "
            "recent yield says the residual is dirty. Goodhart on the FS "
            "surface remains a separate ratchet (name the evasion → L0/L1)."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {OUT}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
