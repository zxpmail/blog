#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Referent-Mismatch Experiment — Mike Czerwinski's round 6 game, tested.

CLAIM (Czerwinski, round 6):
  An author can name a technically-addressable referent (a key, id, path)
  that passes the referent-presence gate while punting the real ambiguity
  one layer down. A gate checking referent PRESENCE has the same shape gap
  as C1's keyword-presence check — elevated one level.

EXPERIMENT:
  Tests the ACTUAL game: a human reads the (wrong/narrow) requirement,
  writes ONE verify command from it, and C3 runs that single command.

  Five scenarios. Each: implementation + wrong requirement + verify command
  written from the wrong referent. Does C3 PASS (game succeeds) or FAIL
  (game caught)?

  Pure deterministic — zero API cost.

SCENARIOS:
  S1  targeted key-level: req=user:123, intent=user:*,  verify=check 123 gone
  S2  flush all:          req=user:123, intent=leave 456, verify=check 456 alive
  S3  prefix:user: req=admin:123, intent=user:123, verify=check admin:* gone
  S4  tiered L1/L2: req=L1, intent=L1+L2, verify=check L2 gone
  S5  cascade: req=user:123, intent=leave 456, verify=check 456 alive

USAGE:
  python referent-mismatch-test.py          # no API
  python referent-mismatch-test.py --save   # + results JSON
"""

import sys, io, json, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"


# ── Cache Implementations ───────────────────────────────────────────────

class TargetedCache:
    """write(k) removes cache[k] only — correct key-level invalidation."""
    def __init__(self):
        self.data = {"user:123": "v1", "user:456": "v2"}
    def write(self, k):
        del self.data[k]
    def has(self, k):
        return k in self.data

class FlushCache:
    """write(k) removes EVERYTHING — over-invalidation."""
    def __init__(self):
        self.data = {"user:123": "v1", "user:456": "v2"}
    def write(self, k):
        self.data.clear()
    def has(self, k):
        return k in self.data

class PrefixCache:
    """write(k) removes only keys matching 'user:*'."""
    def __init__(self):
        self.data = {"user:123": "v1", "user:456": "v2", "admin:123": "v3"}
    def write(self, k):
        for key in list(self.data):
            if key.startswith("user:"):
                del self.data[key]
    def has(self, k):
        return k in self.data

class TieredCache:
    """write(k) removes L1[k] but preserves L2[k]. Partial invalidation."""
    def __init__(self):
        self.l1 = {"user:123": "v1"}
        self.l2 = {"user:123": "persisted-v1"}
    def write(self, k):
        if k in self.l1:
            del self.l1[k]
    def l1_has(self, k):
        return k in self.l1
    def l2_has(self, k):
        return k in self.l2

class CascadeCache:
    """write(k) removes ALL entries — over-invalidation."""
    def __init__(self):
        self.data = {"user:123": "v1", "user:456": "v2"}
    def write(self, k):
        self.data.clear()
    def has(self, k):
        return k in self.data


# ── C3 helper ──────────────────────────────────────────────────────────

def c3_check(Impl, write_key, check_fn):
    """Run C3: create impl, write key, then check. Return True=PASS."""
    c = Impl()
    c.write(write_key)
    return check_fn(c)


# ── Scenarios: single verify command, written from the WRONG referent ──

SCENARIOS = [
    {   # S1 ─ targeted key-level: wrong referent but verify tests the right behavior
        "id": "S1",
        "impl": "targeted (key-level delete)",
        "desc": "Wrong referent hides incomplete scope",
        "wrong_referent": "invalidate user:123",
        "true_intent": "invalidate ALL user:* entries",
        "verify_label": "check user:123 gone (follows req referent)",
        "verify": lambda: c3_check(TargetedCache, "user:123", lambda c: not c.has("user:123")),
        # Expected: PASS — key IS deleted. Game succeeds.
    },
    {   # S2 ─ flush-all: verify written from narrow referent, but impl too broad
        "id": "S2",
        "impl": "flush-all (over-invalidates)",
        "desc": "Broad impl absorbs wrong referent",
        "wrong_referent": "invalidate user:123 only, leave user:456",
        "true_intent": "invalidate user:123 only, preserve user:456",
        "verify_label": "check user:456 alive (req says leave it)",
        "verify": lambda: c3_check(FlushCache, "user:123", lambda c: c.has("user:456")),
        # Expected: FAIL — flush killed user:456. Game caught.
    },
    {   # S3 ─ prefix:user: verify written from wrong referent prefix
        "id": "S3",
        "impl": "prefix:user/* only",
        "desc": "Wrong referent prefix",
        "wrong_referent": "invalidate admin:123",
        "true_intent": "invalidate user:123",
        "verify_label": "check admin:* gone (req says admin)",
        "verify": lambda: c3_check(PrefixCache, "user:123", lambda c: not any(k.startswith("admin:") for k in c.data)),
        # Expected: FAIL — admin:* NOT invalidated. Game caught.
    },
    {   # S4 ─ tiered L1/L2: verify written from narrow scope
        "id": "S4",
        "impl": "tiered L1/L2 (partial invalidation)",
        "desc": "Wrong tier scope",
        "wrong_referent": "invalidate user:123 (L1 only)",
        "true_intent": "invalidate user:123 (L1 AND L2)",
        "verify_label": "check L2 gone (req says L1, we check deeper)",
        "verify": lambda: c3_check(TieredCache, "user:123", lambda c: not c.l2_has("user:123")),
        # Expected: FAIL — L2 preserved. Game caught (verify checks deeper than req).
    },
    {   # S5 ─ cascade: verify written from narrow referent, but impl too broad
        "id": "S5",
        "impl": "cascade (over-invalidates all)",
        "desc": "Broad cascade absorbs wrong referent",
        "wrong_referent": "invalidate user:123, NOT user:456",
        "true_intent": "invalidate user:123 only, preserve user:456",
        "verify_label": "check user:456 alive (req says preserve it)",
        "verify": lambda: c3_check(CascadeCache, "user:123", lambda c: c.has("user:456")),
        # Expected: FAIL — cascade killed user:456 too. Game caught.
    },
]


# ── Main ────────────────────────────────────────────────────────────────

def run():
    parser = argparse.ArgumentParser(description="Referent-mismatch experiment")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    W = 72
    print("─" * W)
    print("Referent-Mismatch Experiment — Czerwinski round 6 game, tested")
    print("─" * W)
    print("  One verify command per scenario, written from the WRONG referent.")
    print("  PASS = game succeeds (C3 approved work against wrong referent)")
    print("  FAIL = game caught (C3 detected the mismatch)")
    print()

    results = []

    for sc in SCENARIOS:
        sid = sc["id"]
        try:
            result = sc["verify"]()
        except Exception as e:
            result = f"ERROR:{e}"

        passed = result is True
        result_str = "PASS" if passed else "FAIL" if isinstance(result, bool) else str(result)

        print(f"  {sid}: {sc['impl']}")
        print(f"    {sc['desc']}")
        print(f"    Wrong req:  {sc['wrong_referent']}")
        print(f"    True intent: {sc['true_intent']}")
        print(f"    Verify: {sc['verify_label']:45s} → {result_str}")
        if passed:
            print(f"    → GAME SUCCEEDS: C3 approved work against wrong referent")
        else:
            print(f"    → GAME CAUGHT: C3 rejected — mismatch detected")
        print()

        results.append({
            "id": sid, "impl": sc["impl"],
            "wrong_referent": sc["wrong_referent"],
            "true_intent": sc["true_intent"],
            "verify_command": sc["verify_label"],
            "c3_result": result_str,
            "game_succeeded": passed,
        })

    # ── Summary ──
    print("─" * W)
    succeeded = sum(1 for r in results if r["game_succeeded"])
    caught = len(results) - succeeded
    print(f"  Game succeeded (PASS):   {succeeded}/5")
    print(f"  Game caught (FAIL):      {caught}/5")
    print()
    for r in results:
        if r["game_succeeded"]:
            print(f"  {r['id']}: ❌ GAME SUCCEEDED — C3 approved work against wrong referent")
        else:
            print(f"  {r['id']}: ✅ GAME CAUGHT — C3 detected mismatch")
    print()
    print("  HONEST BOUNDARY:")
    print("  C3 catches the game when the verify command checks something")
    print("  the implementation DOESN'T do (narrower or different scope).")
    print("  It misses when the verify command checks something the impl")
    print("  happens to satisfy — via over-invalidation (flush, cascade)")
    print("  or correct-by-coincidence key targeting.")
    print("─" * W)

    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / "referent-mismatch.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "scenarios": results,
                "summary": {
                    "game_succeeded": succeeded,
                    "game_caught": caught,
                    "total": len(results),
                    "honest_boundary": (
                        "C3 catches mismatch when verify checks a gap the impl doesn't fill. "
                        "It misses when verify checks something the impl satisfies by accident "
                        "(over-invalidation, correct-by-coincidence). This is contract-definition "
                        "quality — L3 territory."
                    ),
                }
            }, f, indent=2, ensure_ascii=False)
        print(f"Saved: {path}")

    return results

if __name__ == "__main__":
    run()
