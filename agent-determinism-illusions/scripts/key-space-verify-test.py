#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Key-Space C3 Experiment — Bloom filter analogy, tested.

CONCEPT:
  Current C3 verifies: write(k), observe cache[k]. If the agent resolved
  to a wrong k (Mike's attack), C3 passes on the wrong target.

  Key-space C3 verifies: declare a key space (e.g. "user:*"), write the
  trigger, then check ALL keys in that space. If any key in the declared
  space survives, FAIL. This is analogous to a Bloom filter upstream of
  a cache membership test — it checks the space, not a single key.

EXPERIMENT:
  6 scenarios from write-time-resolution-test.py × 2 C3 modes:

  - Single-key C3: write(k), assert cache[k] gone (original, Mike's target)
  - Key-space C3: write(k), assert ALL keys matching space pattern gone

  Two cache implementations:
  - LiveCache: write(k) removes only k (targeted, under-inv by default)
  - BulkCache: write(k) removes ALL keys matching k's prefix (can satisfy spaces)

  For each scenario × C3-mode × cache-impl, measure:
  - C3 pass/fail
  - Whether it catches wrong resolution
  - Whether it false-positive on correct resolution

  Also test: can the key space ALWAYS be declared? Edge cases where the
  intent is explicitly open-ended but the key space is the honest hint.

USAGE:
  python key-space-verify-test.py                # run all
  python key-space-verify-test.py --save          # + JSON

PURE DETERMINISTIC — zero API cost.
"""

import sys, io, json, argparse, re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"

# ============================================================
# Key space
# ============================================================

ALL_KEYS = [
    "user:123", "user:456",
    "session:abc", "session:xyz",
    "profile:123", "token:789",
    "admin:123",
]

def keys_in_space(space_pattern: str) -> List[str]:
    """Resolve a key space pattern to concrete keys.
    Patterns: 'user:*', 'session:*', 'profile:*', 'token:*', 'admin:*',
    or a single key like 'user:123'.
    '*' matches any suffix after the colon (prefix match)."""
    if space_pattern == "*":
        return list(ALL_KEYS)
    if space_pattern.endswith(":*"):
        prefix = space_pattern[:-1]
        return [k for k in ALL_KEYS if k.startswith(prefix)]
    return [space_pattern]  # single key, treated as a space of 1

def space_description(space_pattern: str) -> str:
    """Human-readable description of what a key space covers."""
    keys = keys_in_space(space_pattern)
    if not keys:
        return f"{space_pattern} → (empty)"
    return f"{space_pattern} → {keys}"

# ============================================================
# Cache implementations
# ============================================================

class LiveCache:
    """write(k) removes only k. Doesn't invalidate anything else."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        if k in self.data:
            del self.data[k]
    def has(self, k):
        return k in self.data
    def keys_matching(self, pattern: str) -> List[str]:
        return [k for k in self.data if
                (pattern.endswith(":*") and k.startswith(pattern[:-1]))
                or k == pattern]

class BulkCache:
    """write(k) removes ALL keys matching k's prefix (e.g. write 'user:123'
    clears 'user:123' AND 'user:456'). Designed to satisfy key-space verify."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        prefix = k.split(":")[0] + ":"
        self.data = {k2: v for k2, v in self.data.items() if not k2.startswith(prefix)}
    def has(self, k):
        return k in self.data
    def keys_matching(self, pattern: str) -> List[str]:
        return [k for k in self.data if
                (pattern.endswith(":*") and k.startswith(pattern[:-1]))
                or k == pattern]

class FlushCache:
    """write(k) removes EVERYTHING. Extreme over-inv."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        self.data.clear()
    def has(self, k):
        return k in self.data
    def keys_matching(self, pattern: str) -> List[str]:
        return [k for k in self.data if
                (pattern.endswith(":*") and k.startswith(pattern[:-1]))
                or k == pattern]


# ============================================================
# C3 modes
# ============================================================

def single_key_c3(cache, trigger_key, verify_key: str) -> Tuple[bool, str]:
    """Original C3: write trigger, check single verify_key."""
    before = cache.has(verify_key)
    cache.write(trigger_key)
    after = cache.has(verify_key)
    passed = not after
    detail = f"check '{verify_key}': before={'present' if before else 'gone'}, after={'present' if after else 'gone'}"
    return passed, detail

def key_space_c3(cache, trigger_key, space_pattern: str) -> Tuple[bool, str, List[Dict]]:
    """New C3: write trigger, check ALL keys in the declared space.
    Returns (passed, summary, per_key_results)."""
    keys_before = {}
    for k in keys_in_space(space_pattern):
        keys_before[k] = cache.has(k)

    cache.write(trigger_key)

    per_key = []
    failures = []
    for k in keys_in_space(space_pattern):
        after = cache.has(k)
        passed = not after
        if not passed:
            failures.append(k)
        per_key.append({
            "key": k,
            "present_before": keys_before[k],
            "present_after": after,
            "passed": passed,
        })

    all_passed = len(failures) == 0
    coverage = len(keys_in_space(space_pattern))
    found = coverage - len(failures)
    detail = f"space '{space_pattern}' ({coverage} keys): {found} invalidated, {len(failures)} survived → {'PASS' if all_passed else 'FAIL'}"
    return all_passed, detail, per_key


# ============================================================
# Scenarios
# ============================================================

@dataclass
class Scenario:
    id: str
    requirement: str
    trigger_key: str
    single_key_to_check: str           # what single-key C3 would check (agent's chosen k)
    true_keyspace: str                 # the REAL key space that should be invalidated
    true_intent: str
    notes: str

SCENARIOS = [
    Scenario(
        id="S1",
        requirement="invalidate the relevant cache entry when user data changes",
        trigger_key="user:123",
        single_key_to_check="user:123",
        true_keyspace="user:*",
        true_intent="invalidate ALL user:*",
        notes="Mike's original attack: single-key C3 checks user:123 → PASS, but user:456 never checked",
    ),
    Scenario(
        id="S2",
        requirement="clear stale cache entries before writing new data",
        trigger_key="user:123",
        single_key_to_check="user:123",
        true_keyspace="user:123",  # intentionally narrow — only the write key itself
        true_intent="invalidate ONLY the specific write key",
        notes="space of 1 = single-key C3 is sufficient",
    ),
    Scenario(
        id="S3",
        requirement="invalidate cache if write affects the user's active session",
        trigger_key="user:123",
        single_key_to_check="user:123",
        true_keyspace="session:*",
        true_intent="invalidate session:abc, not user:123 itself",
        notes="wrong-referent: agent checks user:123, should check session:*",
    ),
    Scenario(
        id="S4",
        requirement="when updating a user profile, invalidate all related entries",
        trigger_key="user:123",
        single_key_to_check="user:123",  # narrow resolution
        true_keyspace="user:*,profile:*",
        true_intent="invalidate user:123 AND profile:123",
        notes="compound key space: two prefixes",
    ),
    Scenario(
        id="S5",
        requirement="on password change, invalidate the user's security token",
        trigger_key="user:123",
        single_key_to_check="user:123",
        true_keyspace="token:*",
        true_intent="invalidate token:789, not user:123 itself",
        notes="wrong-referent: agent checks user:123, should check token:*",
    ),
    Scenario(
        id="S6",
        requirement="when permissions change, invalidate all sessions for this user",
        trigger_key="user:123",
        single_key_to_check="user:123",
        true_keyspace="session:*",
        true_intent="invalidate ALL session:* for this user across nodes",
        notes="wrong-referent: checks user:123, should check all sessions",
    ),
]


# ============================================================
# Compound key space support
# ============================================================

def check_compound_space(cache, trigger_key, space_spec: str) -> Tuple[bool, str, List[Dict]]:
    """Handle compound spaces like 'user:*,profile:*' by checking each sub-space."""
    patterns = [s.strip() for s in space_spec.split(",")]
    all_per_key = []
    all_passed = True
    failures = []

    for pattern in patterns:
        passed, detail, per_key = key_space_c3(cache, trigger_key, pattern)
        all_per_key.extend(per_key)
        if not passed:
            all_passed = False
            failing = [r["key"] for r in per_key if not r["passed"]]
            failures.extend(failing)

    coverage = len(all_per_key)
    found = coverage - len(failures)
    detail = f"compound space '{space_spec}' ({coverage} keys): {found} invalidated, {len(failures)} survived → {'PASS' if all_passed else 'FAIL'}"
    return all_passed, detail, all_per_key


# ============================================================
# Main
# ============================================================

CACHE_IMPLS = [
    ("LiveCache", LiveCache, "single-key delete — under-inv by default"),
    ("BulkCache", BulkCache, "prefix-based delete — can satisfy key spaces"),
    ("FlushCache", FlushCache, "flush all — over-inv extreme"),
]

C3_MODES = [
    ("single-key", "check the single key the agent resolved to (Mike's target)"),
    ("key-space", "check ALL keys in the declared key space (Bloom filter)"),
]


def run():
    parser = argparse.ArgumentParser(description="Key-space C3 verification experiment")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("Key-Space C3 Experiment — Bloom filter analogy")
    print("=" * 72)
    print()
    print(f"{'Cache':<12} {'Mode':<12} {'Sc':<4} {'Result':<8} Detail")
    print("-" * 72)

    results = []
    summary_rows = []

    for cache_name, CacheCls, cache_desc in CACHE_IMPLS:
        for mode_name, mode_desc in C3_MODES:
            for sc in SCENARIOS:
                cache = CacheCls()

                if mode_name == "single-key":
                    passed, detail = single_key_c3(cache, sc.trigger_key, sc.single_key_to_check)
                    per_key = None
                else:
                    if "," in sc.true_keyspace:
                        # HACK: compound spaces only work with BulkCache for correct test
                        # LiveCache can only satisfy single-key spaces
                        # For the experiment, we still run it to show the failure
                        if cache_name == "LiveCache" and sc.true_keyspace != sc.single_key_to_check:
                            passed, detail, per_key = check_compound_space(cache, sc.trigger_key, sc.true_keyspace)
                        elif cache_name == "LiveCache":
                            passed, detail, per_key = key_space_c3(cache, sc.trigger_key, sc.true_keyspace)
                        else:
                            passed, detail, per_key = check_compound_space(cache, sc.trigger_key, sc.true_keyspace)
                    else:
                        passed, detail, per_key = key_space_c3(cache, sc.trigger_key, sc.true_keyspace)

                # Classify
                resolution_ok = sc.true_keyspace == sc.single_key_to_check or (
                    sc.true_keyspace.endswith(":*") and sc.single_key_to_check.startswith(
                        sc.true_keyspace[:-1]
                    )
                )
                # A wrong resolution passes single-key C3 when the trigger key happens to match
                single_key_blind = (
                    not resolution_ok
                    and cache_name == "LiveCache"
                    and sc.single_key_to_check == sc.trigger_key
                )
                key_space_catches = (
                    not resolution_ok
                    and mode_name == "key-space"
                    and cache_name == "LiveCache"
                    and not passed
                )

                result = {
                    "scenario": sc.id,
                    "cache": cache_name,
                    "mode": mode_name,
                    "requirement": sc.requirement,
                    "trigger_key": sc.trigger_key,
                    "single_key_to_check": sc.single_key_to_check,
                    "true_keyspace": sc.true_keyspace,
                    "passed": passed,
                    "detail": detail,
                    "resolution_ok": resolution_ok,
                    "single_key_blind": single_key_blind,
                    "key_space_catches": key_space_catches,
                }

                if per_key:
                    result["per_key"] = per_key

                results.append(result)

                status = "PASS" if passed else "FAIL"
                print(f"{cache_name:<12} {mode_name:<12} {sc.id:<4} {status:<8} {detail}")
                if mode_name == "key-space" and per_key:
                    for pk in per_key[:3]:  # show first 3 per-key results
                        pk_status = "PASS" if pk["passed"] else "SURVIVED"
                        print(f"  {'':<24} {pk['key']:<20} {pk_status}")
                    if len(per_key) > 3:
                        print(f"  {'':<24} ... {len(per_key) - 3} more keys")
                print()

    # === Analysis ===
    print("=" * 72)
    print("ANALYSIS")
    print("=" * 72)
    print()

    # Wrong-referent cases where single-key C3 is blind vs key-space C3 catches
    wrong_ref_scenarios = [s for s in SCENARIOS if s.true_keyspace != s.single_key_to_check]
    print(f"Wrong-referent scenarios (Mike's attack): {len(wrong_ref_scenarios)} "
          f"({', '.join(s.id for s in wrong_ref_scenarios)})")
    print()

    for sc in wrong_ref_scenarios:
        blind = [r for r in results
                 if r["scenario"] == sc.id and r["mode"] == "single-key"
                 and r["cache"] == "LiveCache" and r["single_key_blind"]]
        caught_key_space = [r for r in results
                            if r["scenario"] == sc.id and r["mode"] == "key-space"
                            and r["cache"] == "LiveCache" and r["key_space_catches"]]
        caught_bulk = [r for r in results
                       if r["scenario"] == sc.id and r["mode"] == "key-space"
                       and r["cache"] == "BulkCache" and not r["passed"]]

        print(f"  {sc.id}: single-key C3 blind = {len(blind) > 0}, "
              f"key-space C3 catches (Live) = {len(caught_key_space) > 0}, "
              f"key-space C3 catches (Bulk) = {len(caught_bulk) > 0}")

    print()

    # Summary table: catch rate by mode
    print("── Catch rate on wrong-referent scenarios ──")
    print(f"{'Mode':<15} {'Cache':<12} {'Caught':<8} {'Out of':<8} {'Rate':<8}")
    print("-" * 45)

    for mode_name in ["single-key", "key-space"]:
        for cache_name in ["LiveCache", "BulkCache"]:
            wrong = [r for r in results
                     if r["scenario"] in [s.id for s in wrong_ref_scenarios]
                     and r["mode"] == mode_name and r["cache"] == cache_name]
            caught = [r for r in wrong if not r["passed"]]
            total = len(wrong)
            rate = f"{len(caught)}/{total}" if total else "0/0"
            print(f"{mode_name:<15} {cache_name:<12} {len(caught):<8} {total:<8} {rate}")

    # Key-space C3 coverage by scenario
    print()
    print("── Key-space C3: per-scenario performance ──")
    print(f"{'Sc':<4} {'Space':<20} {'Cache':<12} {'Result':<8} Detail")
    print("-" * 65)
    for sc in SCENARIOS:
        for cache_name in ["LiveCache", "BulkCache"]:
            entry = next((r for r in results
                          if r["scenario"] == sc.id and r["mode"] == "key-space"
                          and r["cache"] == cache_name), None)
            if entry:
                status = "PASS" if entry["passed"] else "FAIL"
                # Summarize survivors
                if not entry["passed"] and entry.get("per_key"):
                    survivors = [pk["key"] for pk in entry["per_key"] if not pk["passed"]]
                    detail = f"survivors: {survivors}"
                else:
                    detail = "all invalidated"
                print(f"{sc.id:<4} {sc.true_keyspace:<20} {cache_name:<12} {status:<8} {detail}")

    # Honest boundary
    print()
    print("=" * 72)
    print("HONEST BOUNDARY")
    print("=" * 72)
    print()
    print("  Key-space C3 catches wrong-referent cases that single-key C3 misses —")
    print("  provided the key space CAN be declared. Prefix patterns ('user:*', 'session:*')")
    print("  always work. Traced relations ('sessions by userId') resolve to parameterized")
    print("  queries — still a space, just not a flat prefix.")
    print()
    print("  The remaining honest boundary: open-ended relevance ('invalidate related")
    print("  entries') without a dependency trace. If 'related' can't be resolved to a")
    print("  declarable space, key-space C3 has nothing to iterate over and falls back")
    print("  to the same point as single-key C3 — but with an explicit admission that")
    print("  the space was undeclarable, which is itself actionable evidence.")
    print()
    print("  The Bloom filter analogy holds: a membership test against a declared space")
    print("  is stronger than a single-key lookup. But declaring the space is itself")
    print("  a semantic step — the honest question is whether that step can be")
    print("  automated or requires human judgment.")

    # Save
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / "key-space-verify.json"
        # Compile summary
        summary = {
            "experiment": "key-space-verify-test",
            "design": {
                "claim": "Key-space C3 catches wrong-referent cases single-key C3 misses, "
                         "analogous to a Bloom filter before cache lookup",
                "method": f"{len(SCENARIOS)} scenarios × {len(C3_MODES)} C3 modes × {len(CACHE_IMPLS)} cache impls",
                "wrong_referent_scenarios": [s.id for s in wrong_ref_scenarios],
            },
            "results": results,
            "catch_rates": {}
        }
        for mode_name in ["single-key", "key-space"]:
            for cache_name in ["LiveCache", "BulkCache"]:
                wrong = [r for r in results
                         if r["scenario"] in [s.id for s in wrong_ref_scenarios]
                         and r["mode"] == mode_name and r["cache"] == cache_name]
                caught = sum(1 for r in wrong if not r["passed"])
                total = len(wrong)
                summary["catch_rates"][f"{mode_name}_{cache_name}"] = {
                    "caught": caught, "total": total,
                    "rate": caught / total if total else 0,
                }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Saved: {path}")


if __name__ == "__main__":
    run()
