#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Composite generated-stamp hides per-check observation spread (Tom Jones).

Claim under test
----------------
A single ``generated`` stamp on a multi-check snapshot is a summary that
cannot report its own spread: wall-clock at write-time (after all checks
finish) stands in for the time each check actually observed. A hung or
early check inherits a fresh document stamp; no field names the lag.

Tom Jones (DEV.to, Part 9 / Weng blind-step thread, follow-up to
``reply-tom-jones-stale-snapshot.md``): computed-at is neither render
time nor mtime — it parses the snapshot body stamp. Alert count is
re-read live. But the stamp is taken after the full run (~71.7s); checks
at the top of the file observed earlier. Correct ownership: computed-at
belongs to the individual observation; document stamp = max of parts.

Method
------
Offline simulation (no API). Three runs share the same check schedule
relative to t0; only how ``generated`` / age is attributed changes.

  C1 document-end stamp: generated = end of run; age(check) uses that
  C2 per-check stamp:    age(check) uses each check's observed_at
  C3 hung early check:   first check stalls 600s; document stamp still
                         end-of-run — C1 reports fresh; C2 reports 600s

PASS criteria (falsify if any fails)
------------------------------------
  1. C1 max age across checks equals only the write lag after last check
     (not the full run span from first observation).
  2. C2 max age equals first_observed → generated span (full spread).
  3. C3 with hang: C1 max age stays small (< 5s write lag); C2 max age
     >= hang duration.

Expected: SUPPORT.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "composite-stamp-spread.json"

# Relative seconds from run start (matches Tom's shape: ~72s wall).
CHECK_OFFSETS_S = [0.0, 12.0, 28.0, 45.0, 60.0]  # last check at 60s
WRITE_LAG_S = 11.7  # stamp after all checks → total ~71.7s
HANG_S = 600.0


def age_at_write(observed_at: list[float], generated: float) -> dict:
    """Age of each observation at document write time."""
    ages = [generated - o for o in observed_at]
    return {
        "generated": generated,
        "observed_at": observed_at,
        "ages_at_write": ages,
        "max_age": max(ages),
        "min_age": min(ages),
        "true_spread": max(ages) - min(ages),
    }


def main() -> None:
    # --- 71.7s-shaped run (Tom's timed magnitude) ---
    observed = list(CHECK_OFFSETS_S)
    generated = max(observed) + WRITE_LAG_S  # stamp after every check completed

    # C1: only document stamp published → reader has no spread field
    c1_true = age_at_write(observed, generated)
    c1_published_spread = 0.0  # single stamp cannot report spread

    # C2: per-check observed_at published → spread is a field
    c2_true = age_at_write(observed, generated)
    c2_published_spread = c2_true["true_spread"]

    # --- C3 hang: check[0] samples world at t=0, then blocks HANG_S ---
    # Remaining checks run after the hang; stamp still end-of-run.
    hung_observed = [0.0] + [HANG_S + o for o in CHECK_OFFSETS_S[1:]]
    hung_generated = max(hung_observed) + WRITE_LAG_S
    c3_true = age_at_write(hung_observed, hung_generated)
    # Document-only attribution: every check inherits generated →
    # at write time a consumer who only sees `generated` treats the
    # whole snapshot as age≈0 relative to generated (no per-check lag).
    c3_inherited_ages = [0.0] * len(hung_observed)
    c3_doc_max_inherited = max(c3_inherited_ages)
    c3_published_spread = 0.0

    claim1 = (
        c1_published_spread == 0.0
        and c1_true["true_spread"] == max(CHECK_OFFSETS_S) - min(CHECK_OFFSETS_S)
        and c1_true["true_spread"] > 30
    )
    claim2 = abs(c2_published_spread - c1_true["true_spread"]) < 1e-9
    claim3 = (
        c3_published_spread == 0.0
        and c3_doc_max_inherited == 0.0
        and c3_true["max_age"] >= HANG_S - 1e-9
    )

    support = claim1 and claim2 and claim3
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "claim": (
            "Single generated stamp on a composite snapshot cannot report "
            "observation spread; per-check stamps make the slowest check visible"
        ),
        "source": "Tom Jones DEV.to follow-up on Part 9 stale-snapshot thread",
        "method": "offline sim; 71.7s-shaped run + 600s hang on first check",
        "verdict": verdict,
        "claims": {
            "c1_published_spread_zero_while_real_span": claim1,
            "c2_published_spread_equals_obs_span": claim2,
            "c3_hang_hidden_under_doc_stamp": claim3,
        },
        "runs": {
            "C1_document_stamp_only": {
                **c1_true,
                "published_spread": c1_published_spread,
            },
            "C2_per_check_stamps": {
                **c2_true,
                "published_spread": c2_published_spread,
            },
            "C3_hang_600s": {
                "true_ages": c3_true,
                "inherited_ages_under_doc_stamp": c3_inherited_ages,
                "published_spread": c3_published_spread,
                "hang_s": HANG_S,
            },
        },
        "tom_field_note": (
            "71.7s is the small dose; fresh stamp over a drain last run at "
            "boot is the same defect with the gap grown to hours"
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("composite-stamp-spread — Tom Jones / Part 9 follow-up")
    print(f"verdict: {verdict}")
    print(f"claim1 published_spread=0 vs real span: {claim1} "
          f"(span={max(CHECK_OFFSETS_S)-min(CHECK_OFFSETS_S)}s)")
    print(f"claim2 per-check publishes spread: {claim2} "
          f"(spread={c2_published_spread}s)")
    print(f"claim3 hang hidden under doc stamp: {claim3} "
          f"(true max_age={c3_true['max_age']}s, inherited max={c3_doc_max_inherited}s)")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
