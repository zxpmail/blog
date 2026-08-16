#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stamp spread × consumer threshold (Tom Jones, harness-ladder stamp thread).

Claim under test
----------------
Tom Jones (DEV.to follow-up on composite/start-stamp thread): their stamp is
still taken at write time. Spread costs you only when it can cross the
consumer's decision threshold. Their banner decision turns at **hours**; a
~72s healthy spread never reaches it, so per-check stamps buy nothing *today*.
But a spread measured on healthy runs is an **observation**, not a **bound**.
A 600s hang is the same instrument grown past a threshold, and nothing in the
file announces the change under end-of-run stamping. Error pointing at too
old (start-of-run / t0) is a bound; error pointing at too new is a hope.
Third move: live re-read for a load-bearing field removes that field from the
document stamp's authority — cheap only where re-read is cheap.

Method
------
Offline simulation (stdlib). Reuse ~71.7s healthy schedule and hang growth.
Two consumer thresholds:
  T_hours = 3600s  — Tom's "decision turns at hours"
  T_10m   = 600s   — where the prior 600s hang instrument crosses

Policies: END (generated=write_time) vs START (generated=t0).
Live field: decision uses live value, ignores document stamp age.

Cells
-----
  H  healthy ~72s vs T_hours: true spread and END published age both
     below threshold → per-check would not change today's hour-scale decision
  X  hang grown past T_10m: END published age stays ~0 (no announce);
     true oldest and START published age cross T_10m
  B  healthy share is observation not bound: same END policy, larger hang
     can cross T_hours while END still prints ~0
  L  live re-read field: act on live count even when document stamp lies fresh

PASS criteria (falsify if any fails)
------------------------------------
  1. H: healthy true_spread < T_hours and END published_age < T_hours
  2. X: hang END published_age < 5s; true_oldest >= T_10m; START age >= T_10m
  3. B: long hang END published_age < 5s; true_oldest >= T_hours; START >= T_hours
  4. L: live path acts on live value; stamp-only path can skip re-read wrongly

Expected: SUPPORT — today under hours threshold ≠ forever; t0 is the bound;
live re-read covers cheap fields only.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "stamp-spread-vs-threshold.json"

CHECK_OFFSETS_S = [0.0, 12.0, 28.0, 45.0, 60.0]
WRITE_LAG_S = 11.7  # → ~71.7s wall on healthy run
HANG_10M_S = 600.0
HANG_HOURS_S = 4000.0  # 超过 1h 决策阈值
T_HOURS = 3600.0
T_10M = 600.0
FRESH_LIE_MAX_S = 5.0


def run_schedule(hang_s: float | None = None) -> dict:
    """返回 observed_at 列表与 write_time（相对 t0=0）。"""
    if hang_s is None:
        observed = list(CHECK_OFFSETS_S)
    else:
        observed = [0.0] + [hang_s + o for o in CHECK_OFFSETS_S[1:]]
    write_time = max(observed) + WRITE_LAG_S
    true_spread = max(observed) - min(observed)
    return {
        "observed_at": observed,
        "write_time": write_time,
        "true_spread": true_spread,
        "true_oldest_age": write_time - min(observed),
    }


def stamp_ages(sched: dict) -> dict:
    """END vs START 公布年龄。"""
    w = sched["write_time"]
    end_age = w - w  # generated = write_time
    start_age = w - 0.0  # generated = t0
    return {
        "END_published_age": end_age,
        "START_published_age": start_age,
        "true_oldest_age": sched["true_oldest_age"],
        "true_spread": sched["true_spread"],
    }


def crosses(age: float, threshold: float) -> bool:
    """年龄是否跨过消费者决策阈值。"""
    return age + 1e-9 >= threshold


def consumer_reread(published_age: float, threshold: float) -> bool:
    """横幅决策：公布年龄 ≥ 阈值 → 重读时间敏感字段。"""
    return crosses(published_age, threshold)


def main() -> None:
    healthy = run_schedule(None)
    hang_10m = run_schedule(HANG_10M_S)
    hang_hours = run_schedule(HANG_HOURS_S)

    h_ages = stamp_ages(healthy)
    x_ages = stamp_ages(hang_10m)
    b_ages = stamp_ages(hang_hours)

    # --- H：今天相对小时阈值，健康 spread 买不到 per-check ---
    h_true_cross = crosses(h_ages["true_spread"], T_HOURS)
    h_end_cross = crosses(h_ages["END_published_age"], T_HOURS)
    h_start_cross = crosses(h_ages["START_published_age"], T_HOURS)
    # START 在 ~72s 也不跨小时阈值——与 Tom「今天买不到」一致；差异在错误方向
    claim_h = (
        h_ages["true_spread"] < T_HOURS
        and h_ages["END_published_age"] < FRESH_LIE_MAX_S
        and not h_true_cross
        and not h_end_cross
        and not h_start_cross
        and h_ages["END_published_age"] + 1e-9 < h_ages["true_oldest_age"]
    )

    # --- X：600s 仪器跨过 10m 阈值；END 不公告，START 公告 ---
    claim_x = (
        x_ages["END_published_age"] < FRESH_LIE_MAX_S
        and crosses(x_ages["true_oldest_age"], T_10M)
        and crosses(x_ages["START_published_age"], T_10M)
        and not consumer_reread(x_ages["END_published_age"], T_10M)
        and consumer_reread(x_ages["START_published_age"], T_10M)
    )

    # --- B：健康观察不是上界；挂起可跨小时阈值而 END 仍印 ~0 ---
    claim_b = (
        not crosses(h_ages["true_oldest_age"], T_HOURS)
        and crosses(b_ages["true_oldest_age"], T_HOURS)
        and b_ages["END_published_age"] < FRESH_LIE_MAX_S
        and not consumer_reread(b_ages["END_published_age"], T_HOURS)
        and consumer_reread(b_ages["START_published_age"], T_HOURS)
        and crosses(b_ages["START_published_age"], T_HOURS)
    )

    # --- L：现读字段 —— 决策不依赖文档章 ---
    # 文档章 END 说谎新鲜；live count=3 与文档印的 stale count=0 冲突
    doc_alert_count = 0  # 快照里的旧值
    live_alert_count = 3
    stamp_only_acts = not consumer_reread(h_ages["END_published_age"], T_HOURS)
    # stamp-only：章显示新 → 不重读 → 按文档 0 行动
    stamp_only_decision = doc_alert_count if stamp_only_acts else live_alert_count
    live_decision = live_alert_count  # 现读显式覆盖
    claim_l = (
        stamp_only_decision == 0
        and live_decision == 3
        and live_decision != stamp_only_decision
    )

    support = claim_h and claim_x and claim_b and claim_l
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Spread costs a consumer only when it can cross their decision "
            "threshold; healthy ~72s under an hours-scale threshold buys no "
            "per-check fix today, but that measurement is an observation not "
            "a bound — under END stamping a grown hang can cross while the "
            "file still prints ~0; START/t0 makes crossing visible (bound, "
            "not hope); live re-read retires stamp authority only for cheap "
            "fields"
        ),
        "source": (
            "Tom Jones DEV.to follow-up on Weng harness-ladder stamp thread "
            "(threshold / today / t0 bound / live alert count)"
        ),
        "epistemic_bar": (
            "Synthetic schedule (~71.7s / 600s / 4000s). Thresholds are "
            "fixtures matching his hours vs hang instrument, not his field "
            "telemetry. No claim they shipped the t0 fix."
        ),
        "thresholds_s": {"T_hours": T_HOURS, "T_10m": T_10M},
        "claims": {
            "H_healthy_under_hours_threshold_today": claim_h,
            "X_hang_crosses_10m_END_silent_START_announces": claim_x,
            "B_healthy_not_bound_hours_cross_possible": claim_b,
            "L_live_reread_bypasses_lying_stamp": claim_l,
        },
        "cell_H_healthy_vs_hours": {
            "schedule": healthy,
            "ages": h_ages,
            "crosses_T_hours": {
                "true_spread": h_true_cross,
                "END": h_end_cross,
                "START": h_start_cross,
            },
        },
        "cell_X_hang_vs_10m": {
            "schedule": hang_10m,
            "ages": x_ages,
            "consumer_reread_END": consumer_reread(x_ages["END_published_age"], T_10M),
            "consumer_reread_START": consumer_reread(
                x_ages["START_published_age"], T_10M
            ),
        },
        "cell_B_observation_not_bound": {
            "healthy_true_oldest": h_ages["true_oldest_age"],
            "long_hang": {"schedule": hang_hours, "ages": b_ages},
            "consumer_reread_END": consumer_reread(
                b_ages["END_published_age"], T_HOURS
            ),
            "consumer_reread_START": consumer_reread(
                b_ages["START_published_age"], T_HOURS
            ),
        },
        "cell_L_live_reread": {
            "doc_alert_count": doc_alert_count,
            "live_alert_count": live_alert_count,
            "stamp_only_decision": stamp_only_decision,
            "live_supersede_decision": live_decision,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("stamp-spread-vs-threshold — today ≠ bound")
    print(f"verdict: {verdict}")
    print(
        f"H healthy spread={h_ages['true_spread']:.1f}s "
        f"END={h_ages['END_published_age']:.1f}s under T_hours={T_HOURS:.0f}"
    )
    print(
        f"X hang10m END={x_ages['END_published_age']:.1f} "
        f"START={x_ages['START_published_age']:.1f} "
        f"true_oldest={x_ages['true_oldest_age']:.1f}"
    )
    print(
        f"B long hang END={b_ages['END_published_age']:.1f} "
        f"START={b_ages['START_published_age']:.1f} "
        f"crosses_hours START={crosses(b_ages['START_published_age'], T_HOURS)}"
    )
    print(
        f"L stamp_only={stamp_only_decision} live={live_decision}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
