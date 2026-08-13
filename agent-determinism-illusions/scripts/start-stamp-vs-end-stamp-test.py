#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start-of-run stamp vs end-of-run stamp (simple freshness cure).

Claim under test
----------------
A minimal fix for composite-stamp lying "fresh": set the document
``generated`` (or computed-at) at run **start** ``t0``, not after every
check finishes. Published age then cannot be fresher than the oldest
observation window; an early hang inflates the document age instead of
inheriting a just-written stamp.

Does **not** publish per-check spread — only flips the error direction
from dangerous (looks too new) to conservative (looks too old).

Method
------
Offline simulation (no API). Same schedule as Tom's ~71.7s shape and a
600s early hang. Two attribution policies:

  END:   generated = write_time (current composite habit)
  START: generated = t0 (simple cure)

Published document age at write = write_time - generated.
True oldest age at write = write_time - min(observed_at).

PASS criteria (falsify if any fails)
------------------------------------
  1. Hang + END: published_age < 5s while true_oldest >= hang.
  2. Hang + START: published_age >= hang (and >= true_oldest).
  3. Normal 71.7s + START: published_age >= run_wall (not ~0).
  4. Normal 71.7s + END: published_age < 5s (hides the 60s span).

Expected: SUPPORT for "START is the safe simple fix; END is the lie."

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "start-stamp-vs-end-stamp.json"

CHECK_OFFSETS_S = [0.0, 12.0, 28.0, 45.0, 60.0]
WRITE_LAG_S = 11.7
HANG_S = 600.0
FRESH_LIE_MAX_S = 5.0


def summarize(label: str, observed: list[float], generated: float, write_time: float) -> dict:
    """Compare published document age to true oldest observation age."""
    published_age = write_time - generated
    true_oldest = write_time - min(observed)
    true_newest = write_time - max(observed)
    return {
        "label": label,
        "generated": generated,
        "write_time": write_time,
        "observed_at": observed,
        "published_age": published_age,
        "true_oldest_age": true_oldest,
        "true_newest_age": true_newest,
        "looks_fresher_than_oldest": published_age + 1e-9 < true_oldest,
    }


def main() -> None:
    # --- Normal ~71.7s run ---
    observed_n = list(CHECK_OFFSETS_S)
    write_n = max(observed_n) + WRITE_LAG_S
    end_n = summarize("normal_END", observed_n, generated=write_n, write_time=write_n)
    start_n = summarize("normal_START", observed_n, generated=0.0, write_time=write_n)

    # --- Early hang: sample at 0, stall HANG_S, then remaining checks ---
    # After hang, other checks keep relative gaps from the hung finish.
    hung_finish = HANG_S
    observed_h = [0.0] + [hung_finish + o for o in CHECK_OFFSETS_S[1:]]
    write_h = max(observed_h) + WRITE_LAG_S
    end_h = summarize("hang_END", observed_h, generated=write_h, write_time=write_h)
    start_h = summarize("hang_START", observed_h, generated=0.0, write_time=write_h)

    claim1 = end_h["published_age"] < FRESH_LIE_MAX_S and end_h["true_oldest_age"] >= HANG_S
    claim2 = (
        start_h["published_age"] >= HANG_S
        and start_h["published_age"] + 1e-9 >= start_h["true_oldest_age"]
    )
    claim3 = start_n["published_age"] >= write_n - 1e-9
    claim4 = end_n["published_age"] < FRESH_LIE_MAX_S

    support = claim1 and claim2 and claim3 and claim4
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "claims": {
            "hang_END_lies_fresh": claim1,
            "hang_START_safe": claim2,
            "normal_START_not_zero": claim3,
            "normal_END_hides_span": claim4,
        },
        "normal_71_7s": {"END": end_n, "START": start_n},
        "hang_600s": {"END": end_h, "START": start_h},
        "simple_cure": (
            "generated = t0 (run start), never write_time; "
            "error direction: too old, not too new"
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("start-stamp-vs-end-stamp — simple cure check")
    print(f"verdict: {verdict}")
    print(
        f"hang END published={end_h['published_age']:.1f}s "
        f"true_oldest={end_h['true_oldest_age']:.1f}s lie={claim1}"
    )
    print(
        f"hang START published={start_h['published_age']:.1f}s "
        f"true_oldest={start_h['true_oldest_age']:.1f}s safe={claim2}"
    )
    print(
        f"normal END published={end_n['published_age']:.1f}s | "
        f"START published={start_n['published_age']:.1f}s"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
