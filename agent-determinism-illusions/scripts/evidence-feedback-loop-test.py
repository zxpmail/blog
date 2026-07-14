#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evidence-Feedback-Loop Experiment — Evidence Locker pattern, tested.

CONCEPT (Pascal Cescato's "Evidence Locker"):
  No upfront gate is correct on the first attempt. The honest path is:
  run → collect runtime evidence → challenge the model → refine the
  contract → repeat. The feedback loop, not the upfront gate, does
  the load-bearing work.

EXPERIMENT:
  Multi-round simulation with TWO stages per round:
    1. C3 verify — checks only the current contract scope keys
    2. Post-audit — snapshots ALL keys before/after write, identifies
       keys that changed state but WEREN'T in the contract scope

  The post-audit is the key: it finds "unexpected state changes"
  (keys that moved but the contract didn't ask about), which become
  evidence to broaden the contract.

  Two scenarios per round:
    A. Implementation with TARGETED invalidation (only written key)
       → under-invalidation: user:456 NOT invalidated, but post-audit
          can only see "it didn't change" — NOT a signal.
       → Honest boundary: under-invalidation invisible to automated audit.
    B. Implementation with FLUSH (all keys cleared)
       → over-invalidation: user:456 AND admin:123 both cleared.
         post-audit detects: admin:123 changed but wasn't in scope.
       → Converges: evidence of over-invalidation broadens scope.

  8 rounds total. Measures convergence rate.

  Pure deterministic — zero API cost.

USAGE:
  python evidence-feedback-loop-test.py          # run
  python evidence-feedback-loop-test.py --save   # + JSON
"""

import sys, io, json, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"


ALL_KEYS = ["user:123", "user:456", "admin:123"]
TRUE_SCOPE = ["user:123", "user:456"]  # All user:* keys on user write


# ── Two cache implementations ──────────────────────────────────────────

class TargetedCache:
    """write(k) removes only k. Under-invalidation: user:456 survives."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        if k in self.data:
            del self.data[k]
    def has(self, k):
        return k in self.data


class FlushCache:
    """write(k) removes EVERYTHING. Over-invalidation: admin:123 also cleared."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        self.data.clear()
    def has(self, k):
        return k in self.data


# ── Helpers ─────────────────────────────────────────────────────────────

def snapshot(cache):
    """Capture cache state before write."""
    return {k: cache.has(k) for k in ALL_KEYS}

def c3_verify(cache_cls, scope_keys):
    """C3: write user:123, assert all scope_keys are invalidated. Return list."""
    c = cache_cls()
    before = snapshot(c)
    c.write("user:123")
    after = snapshot(c)
    results = []
    for k in scope_keys:
        gone = not c.has(k)
        results.append({"key": k, "pass": gone, "present_after": c.has(k)})
    return results, before, after, c

def post_audit(before, after, scope_keys):
    """After C3, check ALL keys for unexpected state changes.
    'Unexpected' = key changed state but wasn't in the verify scope.
    Also detects: key didn't change state but is in scope (under-invalidation)."""
    evidence = []
    scope_set = set(scope_keys)

    for k in ALL_KEYS:
        changed = before[k] != after[k]
        in_scope = k in scope_set

        if changed and not in_scope:
            evidence.append({
                "key": k, "type": "unexpected_change",
                "detail": f"{k} changed state but wasn't in verify scope"
            })
        if not changed and in_scope:
            evidence.append({
                "key": k, "type": "expected_change_missing",
                "detail": f"{k} was in scope but did NOT change state"
            })
        if changed and in_scope:
            evidence.append({
                "key": k, "type": "expected_change_confirmed",
                "detail": f"{k} changed as expected"
            })

    return evidence


def broaden_from_evidence(current_scope, evidence):
    """Given evidence, produce broader scope for next round."""
    new_scope = set(current_scope)
    for e in evidence:
        if e["type"] == "unexpected_change":
            # A key we didn't check was affected — add it
            new_scope.add(e["key"])
        if e["type"] == "expected_change_missing":
            # A key we expected to change didn't — this is a REAL gap
            # We can't fix the impl, but we flag it for human review
            pass  # scope doesn't change, but gap is recorded
    return sorted(new_scope, key=ALL_KEYS.index)


# ── Main ────────────────────────────────────────────────────────────────

def run():
    parser = argparse.ArgumentParser(description="Evidence feedback loop experiment")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    print("─" * 72)
    print("Evidence-Feedback-Loop Experiment")
    print("Evidence Locker pattern: runtime evidence → contract refinement")
    print("─" * 72)
    print()
    print(f"True scope (user write → invalidate ALL user:*): {TRUE_SCOPE}")
    print()

    for name, CacheCls, impl_desc in [
        ("A", TargetedCache, "TARGETED — user:456 NOT invalidated (under-invalidation)"),
        ("B", FlushCache,   "FLUSH — admin:123 ALSO deleted (over-invalidation)"),
    ]:
        print(f"=== Scenario {name}: {impl_desc} ===")
        print()

        current_scope = ["user:123"]
        round_log = []

        for rnd in range(1, 9):
            # C3 verify
            results, before, after, _ = c3_verify(CacheCls, current_scope)
            evidence = post_audit(before, after, current_scope)

            passes = sum(1 for r in results if r["pass"])
            fails = sum(1 for r in results if not r["pass"])

            # Coverage vs true scope
            covered = [k for k in current_scope if k in TRUE_SCOPE]
            coverage = len(covered) / len(TRUE_SCOPE) * 100

            # Evidence signals
            unexpected = [e for e in evidence if e["type"] == "unexpected_change"]
            missing = [e for e in evidence if e["type"] == "expected_change_missing"]
            confirmed = [e for e in evidence if e["type"] == "expected_change_confirmed"]

            print(f"  Round {rnd}: scope={current_scope}, PASS={passes}/{len(results)}, "
                  f"coverage={coverage:.0f}%")
            for e in evidence[:3]:  # show first few evidence items
                print(f"    evidence: {e['key']} → {e['type']}")

            round_log.append({
                "round": rnd, "scope": list(current_scope),
                "pass": passes, "fail": fails,
                "coverage_pct": round(coverage, 1),
                "evidence_count": len(evidence),
                "unexpected_changes": [e["key"] for e in unexpected],
                "missing_expected": [e["key"] for e in missing],
            })

            # Feedback loop: broaden from evidence
            new_scope = broaden_from_evidence(current_scope, evidence)
            if new_scope != current_scope:
                added = [k for k in new_scope if k not in current_scope]
                print(f"    ↳ EViDENCE FEEDBACK: broadened by {added}")
            else:
                # Check if converged
                if coverage >= 100 and not missing:
                    print(f"    ✅ CONVERGED (full scope covered, no gaps)")
                elif coverage < 100:
                    print(f"    ⏸ Stalled: scope={coverage:.0f}%, under-inv invisible to audit")

            current_scope = new_scope
            print()

        # Summary
        final_r = round_log[-1]
        converged = final_r["coverage_pct"] >= 100 and not final_r["missing_expected"]
        print(f"  → {'✅ CONVERGED' if converged else '❌ STALLED'}")
        print()

        # Save per-scenario
        if args.save:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            path = RESULTS_DIR / f"evidence-feedback-loop-{name}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "scenario": name, "impl": impl_desc,
                    "rounds": round_log,
                    "true_scope": TRUE_SCOPE,
                    "converged": converged,
                    "design": {
                        "claim": "Evidence feedback loop converges when over-invalidation is detectable",
                        "honest_boundary": "Under-invalidation (scope too narrow, impl correct-but-incomplete) is invisible to automated audit. The loop can only detect scope gaps that produce unexpected state changes.",
                    }
                }, f, indent=2, ensure_ascii=False)
            print(f"Saved: path")

    # ── Final comparison ──
    print("─" * 72)
    print("  HONEST BOUNDARY OF THE FEEDBACK LOOP")
    print("─" * 72)
    print()
    print("  Scenario A (targeted, under-invalidation):")
    print("    C3 verifies user:123 → PASS (correct)")
    print("    Post-audit: user:456 unchanged → no evidence signal")
    print("    Scope stalls at 50% — under-inv invisible to audit")
    print()
    print("  Scenario B (flush, over-invalidation):")
    print("    C3 verifies user:123 → PASS (correct)")
    print("    Post-audit: admin:123 CHANGED → evidence signal")
    print("    Scope broadened by feedback → converges")
    print()
    print("  Conclusion: The feedback loop converges only when")
    print("  the implementation produces OVER-invalidation that an")
    print("  automated audit can detect. UNDER-invalidation (the")
    print("  original S1 gap from the referent-mismatch test) is")
    print("  invisible to this loop — it requires human review to")
    print("  close the gap between 'what the contract covers' and")
    print("  'what the requirement should cover.'")
    print("─" * 72)


if __name__ == "__main__":
    run()
