#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutation poisoning: probe must go red on killed behavior (P hardening).

Claim under test
----------------
A probe is never proven correct — but a **mutation** of the claimed side
effect must flip it to REJECT. If the probe still PASSes after the
behavior is poisoned, the probe is watching the wrong thing (silent
spec/probe error).

  M0 baseline honest impl (invalidates on write) → probe PASS
  M1 poison: remove invalidation → correct probe REJECT
  M2 poison: invalidate a *different* key only → correct probe REJECT;
     wrong-key probe may still PASS (exposes mis-aimed probe)
  M3 always-green probe on M1 → PASS (mutation test FAILED → probe suspect)

PASS criteria (falsify if any fails)
------------------------------------
  1. M0 + correct probe → PASS
  2. M1 + correct probe → REJECT (mutation killed, gate red)
  3. M2 + correct probe → REJECT; M2 + wrong-key probe → PASS
  4. M1 + always-green probe → PASS and ``mutation_test_failed`` True

Expected: SUPPORT — mutations that matter must redden a live probe.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "probe-mutation-poison.json"


def write_honest(cache: dict, key: str) -> None:
    cache[key] = "value"
    cache.pop(key, None)  # invalidate = delete entry


def write_no_invalidate(cache: dict, key: str) -> None:
    cache[key] = "value"  # mutation: keep entry


def write_wrong_key_only(cache: dict, key: str) -> None:
    cache[key] = "value"
    other = f"{key}__other"
    cache[other] = "tmp"
    cache.pop(other, None)  # mutates a different referent


def run_scenario(write_fn, key: str = "k") -> dict:
    cache = {"seed": 1}
    write_fn(cache, key)
    return cache


def probe_correct(cache: dict, key: str = "k") -> str:
    """Claim: after write(key), key must be absent (invalidated)."""
    return "REJECT" if key in cache else "PASS"


def probe_wrong_key(cache: dict, key: str = "k") -> str:
    """Mis-aimed: watches key__other absence, not the claim's key."""
    other = f"{key}__other"
    return "REJECT" if other in cache else "PASS"


def probe_always_pass(_cache: dict, _key: str = "k") -> str:
    return "PASS"


def mutation_ok(baseline_pass: bool, after_verdict: str) -> bool:
    """Mutation test passes only if baseline was green and mutant is red."""
    return baseline_pass and after_verdict == "REJECT"


def main() -> None:
    key = "k"
    m0 = run_scenario(write_honest, key)
    m1 = run_scenario(write_no_invalidate, key)
    m2 = run_scenario(write_wrong_key_only, key)

    m0_correct = probe_correct(m0, key)
    m1_correct = probe_correct(m1, key)
    m2_correct = probe_correct(m2, key)
    m2_wrong = probe_wrong_key(m2, key)
    m1_always = probe_always_pass(m1, key)

    baseline_ok = m0_correct == "PASS"
    mut1_ok = mutation_ok(baseline_ok, m1_correct)
    mut2_correct_ok = mutation_ok(baseline_ok, m2_correct)
    # Wrong probe: baseline on M0 — other key absent → PASS; after M2 still PASS
    m0_wrong = probe_wrong_key(m0, key)
    mut2_wrong_failed = m0_wrong == "PASS" and m2_wrong == "PASS"
    always_failed = m1_always == "PASS"  # did not redden

    claim1 = m0_correct == "PASS"
    claim2 = m1_correct == "REJECT" and mut1_ok
    claim3 = m2_correct == "REJECT" and m2_wrong == "PASS" and mut2_wrong_failed
    claim4 = always_failed is True

    support = claim1 and claim2 and claim3 and claim4
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Poisoning the claimed side effect must redden the probe; "
            "a probe that stays green is mis-aimed or vacuous"
        ),
        "claims": {
            "M0_honest_PASS": claim1,
            "M1_no_invalidate_REJECTs_correct_probe": claim2,
            "M2_wrong_referent_exposes_misaimed_probe": claim3,
            "M3_always_green_fails_mutation_test": claim4,
        },
        "caches": {"M0": m0, "M1": m1, "M2": m2},
        "verdicts": {
            "M0_correct": m0_correct,
            "M1_correct": m1_correct,
            "M2_correct": m2_correct,
            "M2_wrong_key_probe": m2_wrong,
            "M1_always_pass_probe": m1_always,
        },
        "mutation_tests": {
            "M1_vs_correct": {"passed": mut1_ok},
            "M2_vs_correct": {"passed": mut2_correct_ok},
            "M2_vs_wrong_key_probe": {
                "passed": not mut2_wrong_failed,
                "stayed_green": mut2_wrong_failed,
            },
            "M1_vs_always_pass": {
                "passed": False,
                "mutation_test_failed": always_failed,
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("probe-mutation-poison — kill side effect, probe must redden")
    print(f"verdict: {verdict}")
    print(f"M0 honest → {m0_correct}")
    print(f"M1 no-invalidate → correct {m1_correct} (mut_ok={mut1_ok})")
    print(
        f"M2 other-key-only → correct {m2_correct}, "
        f"wrong-probe {m2_wrong} (misaimed stayed_green={mut2_wrong_failed})"
    )
    print(f"M1 always-pass probe → {m1_always} (mutation_test_failed={always_failed})")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
