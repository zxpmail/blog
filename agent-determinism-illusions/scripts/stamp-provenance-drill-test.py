#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provenance drill: COUNT honest, VERDICT wrong channel (Tom Jones, fourth cell).

Claim under test
----------------
Tom Jones (DEV.to stamp thread, round-2): beside age and coverage, a third
predicate is **provenance** — what kind of run produced the document.

Install-verification drill: monitor forced to low thresholds to prove alert
path. Instrument printed COUNT; reader promoted to VERDICT on the alert board.
Every character of "month-to-date $2.15 >= $0.01" was true. Live monitor under
$8/day and $100/month limits reported OK throughout. Nothing stale, no missing
join — absent was run_kind naming what produced the row.

Method
------
Offline synthetic (stdlib).

  P  unlabeled drill count → reader fires critical alert
  F  labeled drill (run_kind in body) → ingest drops from alert channel
  T  temporal controls silent (drill row is fresh)
  L  live monitor on same metric → OK under real limits

PASS criteria (falsify if any fails)
------------------------------------
  1. P: unlabeled drill count triggers reader VERDICT=ALERT
  2. F: ingest gate DROP when run_kind labels install_verification_drill
  3. T: age threshold does not explain the twelve-day false critical
  4. L: live path under real limits stays OK

Expected: SUPPORT — age, coverage, provenance are three separate predicates;
only age was getting printed.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "stamp-provenance-drill.json"

# 现场：live 限额 $100/month；drill 用 $0.01 逼通 alert 路径
LIVE_MONTH_LIMIT = 100.0
LIVE_MONTH_TO_DATE = 8.50
DRILL_THRESHOLD = 0.01
DRILL_MONTH_TO_DATE = 2.15


def drill_count_document(*, labeled: bool, generated: float) -> dict:
    """安装验证 drill 产出的 COUNT 行。"""
    doc = {
        "metric": "month_to_date_usd",
        "value": DRILL_MONTH_TO_DATE,
        "threshold": DRILL_THRESHOLD,
        "comparison": ">=",
        "generated": generated,
        "stores_touched": ["metrics_db"],
    }
    if labeled:
        doc["run_kind"] = "install_verification_drill"
    return doc


def reader_promotes_count_to_verdict(doc: dict) -> dict:
    """读者把 COUNT 收成 VERDICT 上板。"""
    fires = doc["value"] >= doc["threshold"]
    if not fires:
        return {"verdict": "OK", "message": None}
    msg = (
        f"{doc['metric']} ${doc['value']:.2f} "
        f"{doc['comparison']} ${doc['threshold']:.2f}"
    )
    return {"verdict": "ALERT", "message": msg, "severity": "critical"}


def live_monitor_read(generated: float) -> dict:
    """线上 monitor：真限额下的读。"""
    ok = LIVE_MONTH_TO_DATE < LIVE_MONTH_LIMIT
    return {
        "metric": "month_to_date_usd",
        "value": LIVE_MONTH_TO_DATE,
        "limit": LIVE_MONTH_LIMIT,
        "generated": generated,
        "run_kind": "live_scheduled_hourly",
        "stores_touched": ["metrics_db"],
        "verdict": "OK" if ok else "ALERT",
    }


def ingest_gate(doc: dict, channel: str) -> dict:
    """ingest：自签 drill 不得进 alert 通道。"""
    if channel != "alert":
        return {"admit": "PASS", "channel": channel}
    if doc.get("run_kind") == "install_verification_drill":
        return {
            "admit": "DROP",
            "reason": "self_labelled_drill",
            "run_kind": doc["run_kind"],
        }
    if "run_kind" not in doc:
        return {
            "admit": "PASS_TO_BOARD",
            "reason": "unlabeled_reaches_board",
        }
    return {"admit": "PASS", "channel": channel}


def age_threshold_fires(published_age: float, threshold: float) -> bool:
    """时间阈值是否开火。"""
    return published_age + 1e-9 >= threshold


def main() -> None:
    generated = 1000.0
    now = 1005.0  # 5s — 新鲜，不是 twelve-day stale 的根因
    threshold_hours = 3600.0

    unlabeled = drill_count_document(labeled=False, generated=generated)
    labeled = drill_count_document(labeled=True, generated=generated)
    live = live_monitor_read(generated=generated)

    verdict_unlabeled = reader_promotes_count_to_verdict(unlabeled)
    verdict_labeled = reader_promotes_count_to_verdict(labeled)
    gate_unlabeled = ingest_gate(unlabeled, "alert")
    gate_labeled = ingest_gate(labeled, "alert")

    claim_p = (
        verdict_unlabeled["verdict"] == "ALERT"
        and "2.15" in verdict_unlabeled["message"]
        and gate_unlabeled["admit"] == "PASS_TO_BOARD"
    )
    claim_f = (
        verdict_labeled["verdict"] == "ALERT"
        and gate_labeled["admit"] == "DROP"
        and gate_labeled["reason"] == "self_labelled_drill"
    )
    claim_t = not age_threshold_fires(now - generated, threshold_hours)
    claim_l = live["verdict"] == "OK" and live["value"] < live["limit"]

    support = claim_p and claim_f and claim_t and claim_l
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Age, coverage, and provenance are three separate predicates; "
            "a fresh honest COUNT promoted to VERDICT without run_kind "
            "can hold a critical alert open while live reads stay OK — "
            "provenance is stores_touched moved from coverage to run type"
        ),
        "source": (
            "Tom Jones DEV.to round-2 — install-verification drill on alert "
            "channel (twelve-day false critical)"
        ),
        "epistemic_bar": (
            "Synthetic shape of his drill vs live monitor story; ingest gate "
            "is a fixture, not his production board."
        ),
        "claims": {
            "P_unlabeled_drill_fires_board": claim_p,
            "F_labeled_drill_ingest_drops": claim_f,
            "T_temporal_silent": claim_t,
            "L_live_monitor_ok": claim_l,
        },
        "cell_P_unlabeled": {
            "document": unlabeled,
            "reader_verdict": verdict_unlabeled,
            "ingest": gate_unlabeled,
        },
        "cell_F_labeled": {
            "document": labeled,
            "reader_verdict": verdict_labeled,
            "ingest": gate_labeled,
        },
        "cell_T_temporal": {
            "published_age": now - generated,
            "threshold_s": threshold_hours,
            "age_fires": age_threshold_fires(now - generated, threshold_hours),
        },
        "cell_L_live": live,
        "three_predicates": ["age", "coverage", "provenance"],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("stamp-provenance-drill — COUNT honest / VERDICT wrong kind")
    print(f"verdict: {verdict}")
    print(f"P alert={verdict_unlabeled['verdict']} ingest={gate_unlabeled['admit']}")
    print(f"F labeled ingest={gate_labeled['admit']}")
    print(f"L live={live['verdict']} value={live['value']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
