# -*- coding: utf-8 -*-
"""Alerting-channel iron-law collapse — Zero-Trust package vs sparse alerts (2026-08-13).

Question:
  Six iron laws (fail-fast on missing watermark, circuit-break on inter-record
  gap > 5, 1s TTL, fsync+heartbeat, backpressure-block at lag 10, silent-cap
  suicide) were proposed as a Zero-Trust upgrade of the watermark-bootstrap
  fix. Do Laws 2, 5, and 1 as stated survive on an *alerting* channel, or do
  they mint new silent damage?

Claims under test:
  C1  Law 2 (circuit-break if consecutive record timestamps differ by > 5):
      a complete sparse log (seq 1 then seq 2, wall-clock gap 100, nothing
      missing) is healthy idle. Law 2 suicides. False kill.
  C2  Law 5 (producer blocks writes when written − consumed > 10): consumer
      dead, lag already 15, a new fire arrives. Backpressure refuses the
      write — alert never lands. Yell-but-still-write (same lag, no block)
      lands the alert and alarms. Isolates backpressure from "producer must
      yell": yelling is load-bearing, blocking the evidence channel is not.
  C3  Law 1 (missing cursor → panic, no fallback): first boot (never
      initialized) and lost cursor share the cell `watermark is None`, so
      panic-any maps both to PANIC — the system cannot be born. Three-state
      (never_initialized → NEED_BOOTSTRAP, lost → PANIC, valid → RUN) splits
      the cell. Same absence≠blindness cut as the rate-card null≡no test.

Falsifiers:
  C1 fail → gap>5 on a complete sparse log does not suicide (Law 2 as stated
            is not an inter-record wall-clock check).
  C2 fail → backpressure still writes the new alert, OR yell-and-write also
            refuses (block and yell are not separable).
  C3 fail → panic-any already distinguishes first-boot from lost, OR
            three-state maps them to the same verdict.

Method (offline sim, no API):
  Integer clock, append-only seq log. Three configs; only the law under
  test varies. Ground truth for C1 is sequence completeness, not wall-clock
  density. Ground truth for C2 is "the fire is on disk". Ground truth for
  C3 is whether first-boot and lost share a verdict.

Run:
  python alerting-iron-law-collapse-test.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "alerting-iron-law-collapse.json"

GAP_MAX = 5    # Law 2 example
LAG_MAX = 10   # Law 5 example


# ── Law 2: inter-record wall-clock gap → suicide ──

def law2_circuit_break(alerts: list[dict[str, int]], gap_max: int = GAP_MAX) -> dict[str, Any]:
    """As stated: compare each record's timestamp to the previous record."""
    suicide = False
    gap = None
    at_seq = None
    for prev, curr in zip(alerts, alerts[1:]):
        g = curr["ts"] - prev["ts"]
        if g > gap_max:
            suicide = True
            gap = g
            at_seq = curr["seq"]
            break
    seqs = [a["seq"] for a in alerts]
    complete = seqs == list(range(seqs[0], seqs[-1] + 1)) if seqs else True
    return {
        "law": "L2_interrecord_gap",
        "suicide": suicide,
        "gap": gap,
        "at_seq": at_seq,
        "seq_complete": complete,
        "n_alerts": len(alerts),
        "healthy_idle": complete and not _seq_missing(alerts),
    }


def _seq_missing(alerts: list[dict[str, int]]) -> bool:
    if not alerts:
        return False
    seqs = [a["seq"] for a in alerts]
    return seqs != list(range(min(seqs), max(seqs) + 1))


# ── Law 5: backpressure-block vs yell-and-write ──

def law5_write(
    log: list[dict[str, int]],
    consumed_upto: int,
    new_alert: dict[str, int],
    *,
    block_on_lag: bool,
    lag_max: int = LAG_MAX,
) -> dict[str, Any]:
    written = max((a["seq"] for a in log), default=0)
    lag = written - consumed_upto
    alarm = lag > lag_max
    if block_on_lag and lag > lag_max:
        return {
            "wrote": False,
            "alarm": alarm,
            "lag": lag,
            "blocked": True,
            "log_seqs": [a["seq"] for a in log],
            "new_seq_on_disk": new_alert["seq"] in {a["seq"] for a in log},
        }
    landed = list(log) + [new_alert]
    return {
        "wrote": True,
        "alarm": alarm,
        "lag": lag,
        "blocked": False,
        "log_seqs": [a["seq"] for a in landed],
        "new_seq_on_disk": new_alert["seq"] in {a["seq"] for a in landed},
    }


# ── Law 1: panic-any vs three-state ──

def law1_panic_any(watermark: int | None) -> str:
    """As stated: missing cursor → panic. No provenance."""
    return "PANIC" if watermark is None else "RUN"


def law1_three_state(watermark: int | None, provenance: str) -> str:
    """never_initialized / lost / valid — absence ≠ blindness."""
    if provenance == "valid":
        assert watermark is not None
        return "RUN"
    if provenance == "never_initialized":
        return "NEED_BOOTSTRAP"
    if provenance == "lost":
        return "PANIC"
    raise ValueError(provenance)


def main() -> None:
    # C1: sparse complete log. Wall-clock gap 100, seq contiguous.
    sparse = [{"seq": 1, "ts": 0}, {"seq": 2, "ts": 100}]
    c1 = law2_circuit_break(sparse)

    # C2: consumer dead, lag 15 > 10, fire seq=21 arrives.
    log = [{"seq": i, "ts": i} for i in range(1, 21)]  # written=20
    consumed_upto = 5
    new_fire = {"seq": 21, "ts": 21}
    refuse = law5_write(log, consumed_upto, new_fire, block_on_lag=True)
    yell = law5_write(log, consumed_upto, new_fire, block_on_lag=False)

    # C3: same raw cell (None), two provenances.
    first_boot = {"watermark": None, "provenance": "never_initialized"}
    lost = {"watermark": None, "provenance": "lost"}
    valid = {"watermark": 20, "provenance": "valid"}
    c3 = {
        "panic_any": {
            "first_boot": law1_panic_any(first_boot["watermark"]),
            "lost": law1_panic_any(lost["watermark"]),
            "valid": law1_panic_any(valid["watermark"]),
        },
        "three_state": {
            "first_boot": law1_three_state(first_boot["watermark"], first_boot["provenance"]),
            "lost": law1_three_state(lost["watermark"], lost["provenance"]),
            "valid": law1_three_state(valid["watermark"], valid["provenance"]),
        },
    }

    claims = {
        "C1_law2_false_kills_healthy_idle": (
            c1["seq_complete"] is True
            and c1["healthy_idle"] is True
            and c1["suicide"] is True
            and c1["gap"] == 100
            and c1["gap"] > GAP_MAX
        ),
        "C2_law5_backpressure_drops_the_fire_yell_keeps_it": (
            refuse["wrote"] is False
            and refuse["new_seq_on_disk"] is False
            and refuse["blocked"] is True
            and refuse["alarm"] is True
            and yell["wrote"] is True
            and yell["new_seq_on_disk"] is True
            and yell["blocked"] is False
            and yell["alarm"] is True
        ),
        "C3_law1_panic_any_conflates_first_boot_with_lost": (
            c3["panic_any"]["first_boot"] == "PANIC"
            and c3["panic_any"]["lost"] == "PANIC"
            and c3["panic_any"]["first_boot"] == c3["panic_any"]["lost"]
            and c3["three_state"]["first_boot"] == "NEED_BOOTSTRAP"
            and c3["three_state"]["lost"] == "PANIC"
            and c3["three_state"]["first_boot"] != c3["three_state"]["lost"]
            and c3["three_state"]["valid"] == "RUN"
            and c3["panic_any"]["valid"] == "RUN"
        ),
    }

    payload = {
        "claim": (
            "Iron laws 2/5/1 as stated mint new damage on an alerting channel: "
            "time-gap suicides healthy idle; backpressure refuses the fire; "
            "panic-any conflates first boot with a lost cursor"
        ),
        "thresholds": {"gap_max": GAP_MAX, "lag_max": LAG_MAX},
        "configs": {
            "C1_law2_sparse_idle": c1,
            "C2_law5_refuse": refuse,
            "C2_law5_yell_and_write": yell,
            "C3_law1_cursor": c3,
        },
        "claims": claims,
        "all_pass": all(claims.values()),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("alerting-channel iron-law collapse — Laws 2 / 5 / 1 as stated")
    print(f"gap_max={GAP_MAX}  lag_max={LAG_MAX}")
    print()
    print(
        f"C1 Law2  seq_complete={c1['seq_complete']}  "
        f"healthy_idle={c1['healthy_idle']}  suicide={c1['suicide']}  gap={c1['gap']}"
    )
    print(
        f"C2 Law5  refuse wrote={refuse['wrote']} on_disk={refuse['new_seq_on_disk']}  "
        f"yell wrote={yell['wrote']} on_disk={yell['new_seq_on_disk']} alarm={yell['alarm']}"
    )
    print(
        f"C3 Law1  panic_any first={c3['panic_any']['first_boot']} "
        f"lost={c3['panic_any']['lost']}  "
        f"three_state first={c3['three_state']['first_boot']} "
        f"lost={c3['three_state']['lost']}"
    )
    print()
    for k, v in claims.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print()
    print(f"all_pass={payload['all_pass']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
