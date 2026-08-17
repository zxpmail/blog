#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canary catches probe/spec error (P); policy-soften detector catches G.

Claim under test
----------------
P and G are not fixed by parent/IPC. Two small mechanisms:

  P — known-wrong canary must REJECT. If the probe watches the wrong
      referent (or a broken probe always PASSes), the canary goes green
      and the gate is invalidated.
  G — a policy-soften detector flags fail-open diffs (timeout→warn,
      digest→warn_only, retry_until_green). Silent softens are caught;
      unchanged fail-closed policy is clean.

PASS criteria (falsify if any fails)
------------------------------------
  1. Correct probe: canary REJECT, honest case PASS.
  2. Wrong-key probe: canary PASS (miss) → gate_invalid True; detector fires.
  3. Always-PASS probe: canary PASS → gate_invalid True.
  4. Soften diff (warn_only / retry_until_green) → detector ALERT.
  5. Unchanged fail-closed policy → detector CLEAN.

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

OUT = Path(__file__).parent / "results-v2" / "pg-canary-governance-test.json"

# Canary: implementation that does NOT invalidate — must never PASS.
CANARY_IMPL = {"k": "stale", "invalidated": False}
HONEST_OK_IMPL = {"k": "gone", "invalidated": True}

SOFTEN_MARKERS = (
    "warn_only",
    "fail_open",
    "retry_until_green",
    "timeout_as_warn",
    "digest_warn",
)


def probe_correct(impl: dict) -> str:
    """Watches the named referent: invalidated flag on key k."""
    return "PASS" if impl.get("invalidated") is True else "REJECT"


def probe_wrong_key(impl: dict) -> str:
    """Spec error: watches unrelated field that happens to look fine."""
    return "PASS" if "k" in impl else "REJECT"


def probe_always_pass(_impl: dict) -> str:
    return "PASS"


def gate_with_canary(probe) -> dict:
    """Run canary first; if canary PASSes, invalidate the whole gate."""
    canary_verdict = probe(CANARY_IMPL)
    gate_invalid = canary_verdict == "PASS"
    honest_verdict = None if gate_invalid else probe(HONEST_OK_IMPL)
    return {
        "canary": canary_verdict,
        "gate_invalid": gate_invalid,
        "honest": honest_verdict,
        "final": "GATE_INVALID" if gate_invalid else honest_verdict,
    }


def detect_policy_soften(before: dict, after: dict) -> dict:
    """Alert if after is softer than before on gate-critical knobs."""
    alerts = []
    if before.get("on_timeout") == "reject" and after.get("on_timeout") != "reject":
        alerts.append("timeout_softened")
    if before.get("on_digest_mismatch") == "reject" and after.get(
        "on_digest_mismatch"
    ) != "reject":
        alerts.append("digest_softened")
    if after.get("retry_until_green") is True and before.get("retry_until_green") is not True:
        alerts.append("retry_until_green_enabled")
    # String-scan stand-in for config sprawl
    blob = json.dumps(after, ensure_ascii=False)
    for m in SOFTEN_MARKERS:
        if m in blob and m not in json.dumps(before, ensure_ascii=False):
            if m not in ("retry_until_green",):  # already covered as key
                alerts.append(f"marker:{m}")
    # dedupe
    alerts = sorted(set(alerts))
    return {"status": "ALERT" if alerts else "CLEAN", "alerts": alerts}


def main() -> None:
    p_correct = gate_with_canary(probe_correct)
    p_wrong = gate_with_canary(probe_wrong_key)
    p_always = gate_with_canary(probe_always_pass)

    policy_strict = {
        "on_timeout": "reject",
        "on_digest_mismatch": "reject",
        "retry_until_green": False,
    }
    policy_soft = {
        "on_timeout": "warn_only",
        "on_digest_mismatch": "digest_warn",
        "retry_until_green": True,
    }
    g_soft = detect_policy_soften(policy_strict, policy_soft)
    g_clean = detect_policy_soften(policy_strict, dict(policy_strict))

    claim1 = (
        p_correct["canary"] == "REJECT"
        and p_correct["gate_invalid"] is False
        and p_correct["honest"] == "PASS"
    )
    claim2 = p_wrong["canary"] == "PASS" and p_wrong["gate_invalid"] is True
    claim3 = p_always["canary"] == "PASS" and p_always["gate_invalid"] is True
    claim4 = g_soft["status"] == "ALERT" and len(g_soft["alerts"]) >= 2
    claim5 = g_clean["status"] == "CLEAN"

    support = all([claim1, claim2, claim3, claim4, claim5])
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "P: known-wrong canary invalidates wrong/always-pass probes; "
            "G: soften detector ALERTs fail-open policy diffs"
        ),
        "claims": {
            "P_correct_probe_canary_reject_honest_pass": claim1,
            "P_wrong_key_canary_invalidates_gate": claim2,
            "P_always_pass_canary_invalidates_gate": claim3,
            "G_soften_diff_alerts": claim4,
            "G_unchanged_clean": claim5,
        },
        "P": {
            "correct_probe": p_correct,
            "wrong_key_probe": p_wrong,
            "always_pass_probe": p_always,
        },
        "G": {"softened": g_soft, "unchanged": g_clean},
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("pg-canary-governance — P canary + G soften detect")
    print(f"verdict: {verdict}")
    print(f"P correct: {p_correct['final']} (canary={p_correct['canary']})")
    print(f"P wrong-key: {p_wrong['final']}")
    print(f"P always-pass: {p_always['final']}")
    print(f"G soften: {g_soft['status']} {g_soft['alerts']}")
    print(f"G clean: {g_clean['status']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
