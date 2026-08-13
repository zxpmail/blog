# -*- coding: utf-8 -*-
"""Watermark-bootstrap collapse — Tom Jones stale-snapshot sub-thread (2026-08-13).

Question (Tom Jones, DEV.to, Weng's Harness Ladder thread):
  Drain keeps a watermark so it only reports what is new. On a cold start it
  returned the current time as that watermark without persisting it, so every
  call recomputed "now" and any alert arriving between two tool calls was
  always older than the cutoff. Never reported, no error, no exception,
  nothing in any log. A bootstrap value that gets returned and not written
  is an alarm channel that reads healthy while dropping everything through
  the floor.

Claims under test:
  C1  Unpersisted `now` watermark: alert between two drain calls is not
      reported; drain reads healthy (no error, dropped_window=0).
  C2  Same timeline, persist the cold-start `now`: between-call alert is
      reported. Isolates persist as the load-bearing axis — not "having a
      watermark", not the clock.
  C3  Persist-now against an alert already in the file at cold start: still
      silent on the window count (dropped_window=0, reported=0) while the
      file count would declare the drop (dropped_file=1). Naive persist-now
      leaves the silent cap Tom named; declaration has to be over the
      append-only file, not over the already-watermarked window.

Falsifiers:
  C1 fail → unpersisted now still reports the between-call alert (bug is
            clock granularity / implementation, not structural).
  C2 fail → persisting the bootstrap does not surface the between-call
            alert (persist is not load-bearing).
  C3 fail → persist-now already declares pre-boot drops on the window
            count, OR window count equals file count (no silent-cap residue).

Method (offline sim, no API):
  Append-only log + drain with an optional persisted watermark. Simulated
  integer clock. Three configs; only persist and alert-timing vary. Drain
  logic held fixed: cutoff = persisted watermark, or `now` on cold start.

Run:
  python watermark-bootstrap-collapse-test.py
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "watermark-bootstrap-collapse.json"

# Simulated clock (integer ticks). Not wall-clock — the incident's 17:04/19:27
# gap is a different face (stale snapshot). This fixture isolates the drain.
T_PREBOOT = 50
T_COLD = 100
T_BETWEEN = 150
T_SECOND = 200

ALERT_BETWEEN = {"id": "between-call", "ts": T_BETWEEN}
ALERT_PREBOOT = {"id": "pre-boot", "ts": T_PREBOOT}


@dataclass
class DrainState:
    watermark: int | None = None  # persisted cutoff; None = never written
    acked: set[str] = field(default_factory=set)


def drain(log: list[dict[str, Any]], state: DrainState, now: int, persist: bool) -> dict[str, Any]:
    """One drain call. Cold start (watermark is None) uses cutoff = now.

    Candidates this call = items with ts > cutoff. The silent cap is that
    items at or before cutoff are not candidates, so they do not increment
    dropped_window. dropped_file counts every unacked item in the log that
    this call did not report.
    """
    error = None
    if state.watermark is None:
        cutoff = now
        if persist:
            state.watermark = now
    else:
        cutoff = state.watermark

    reported = [
        a for a in log
        if a["ts"] > cutoff and a["id"] not in state.acked
    ]
    reported_ids = {a["id"] for a in reported}

    # Window: only what this call treated as a candidate, then capped.
    # This drain reports every candidate, so the window drop count is 0.
    dropped_window = []
    dropped_file = [
        a for a in log
        if a["id"] not in state.acked and a["id"] not in reported_ids
    ]

    for a in reported:
        state.acked.add(a["id"])
    if persist and reported:
        state.watermark = max(a["ts"] for a in reported)

    silent_healthy = (
        error is None
        and len(reported) == 0
        and len(dropped_window) == 0
    )
    return {
        "now": now,
        "cutoff": cutoff,
        "persist": persist,
        "watermark_after": state.watermark,
        "reported_ids": [a["id"] for a in reported],
        "reported_n": len(reported),
        "dropped_window_n": len(dropped_window),
        "dropped_file_n": len(dropped_file),
        "dropped_file_ids": [a["id"] for a in dropped_file],
        "error": error,
        "silent_healthy": silent_healthy,
    }


def run_scenario(
    persist: bool,
    pre_alerts: list[dict[str, Any]],
    between_alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    log = list(pre_alerts)
    state = DrainState()
    first = drain(log, state, now=T_COLD, persist=persist)
    log.extend(between_alerts)
    second = drain(log, state, now=T_SECOND, persist=persist)
    return {
        "persist": persist,
        "log_ids": [a["id"] for a in log],
        "first": first,
        "second": second,
        "watermark_final": state.watermark,
        "acked": sorted(state.acked),
    }


def main() -> None:
    c1 = run_scenario(persist=False, pre_alerts=[], between_alerts=[ALERT_BETWEEN])
    c2 = run_scenario(persist=True, pre_alerts=[], between_alerts=[ALERT_BETWEEN])
    c3 = run_scenario(persist=True, pre_alerts=[ALERT_PREBOOT], between_alerts=[])

    # C1/C2: damage or fix is on the second call (alert arrived in the gap).
    # C3: silent cap is already on the cold-start call against a non-empty file.
    c1_face = c1["second"]
    c2_face = c2["second"]
    c3_face = c3["first"]

    claims = {
        "C1_unpersisted_now_drops_between_and_reads_healthy": (
            c1_face["reported_n"] == 0
            and c1_face["error"] is None
            and c1_face["silent_healthy"] is True
            and c1_face["dropped_window_n"] == 0
            and c1_face["dropped_file_n"] == 1
            and c1["watermark_final"] is None
        ),
        "C2_persisted_now_reports_between": (
            c2_face["reported_n"] == 1
            and c2_face["reported_ids"] == ["between-call"]
            and c2_face["silent_healthy"] is False
            and c2["watermark_final"] is not None
        ),
        "C3_persist_now_silently_caps_preboot_unless_dropped_over_file": (
            c3_face["reported_n"] == 0
            and c3_face["silent_healthy"] is True
            and c3_face["dropped_window_n"] == 0
            and c3_face["dropped_file_n"] == 1
            and c3_face["dropped_file_ids"] == ["pre-boot"]
            and c3["watermark_final"] == T_COLD
        ),
    }

    payload = {
        "claim": (
            "Watermark bootstrap: returning now without persisting it drops "
            "between-call alerts and reads healthy; persist isolates the axis; "
            "persist-now still silently caps pre-boot alerts on the window count"
        ),
        "clock": {
            "t_preboot": T_PREBOOT,
            "t_cold": T_COLD,
            "t_between": T_BETWEEN,
            "t_second": T_SECOND,
        },
        "configs": {
            "C1_unpersisted_now": c1,
            "C2_persisted_now": c2,
            "C3_persist_now_preboot": c3,
        },
        "faces": {
            "C1_second_call": c1_face,
            "C2_second_call": c2_face,
            "C3_cold_start": c3_face,
        },
        "claims": claims,
        "all_pass": all(claims.values()),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("watermark-bootstrap collapse — Tom Jones / stale-snapshot sub-thread")
    print(
        f"clock cold={T_COLD} between={T_BETWEEN} second={T_SECOND} preboot={T_PREBOOT}"
    )
    print()
    rows = [
        ("C1_unpersisted_now", "N", "between", c1_face),
        ("C2_persisted_now", "Y", "between", c2_face),
        ("C3_persist_now_preboot", "Y", "pre-boot", c3_face),
    ]
    print(
        f"{'config':<26} {'persist':<8} {'alert':<10} "
        f"{'reported':<9} {'drop_win':<9} {'drop_file':<10} silent_healthy"
    )
    print("-" * 90)
    for name, persist, when, face in rows:
        print(
            f"{name:<26} {persist:<8} {when:<10} "
            f"{face['reported_n']:<9} {face['dropped_window_n']:<9} "
            f"{face['dropped_file_n']:<10} {face['silent_healthy']}"
        )
    print()
    for k, v in claims.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print()
    print(f"all_pass={payload['all_pass']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
