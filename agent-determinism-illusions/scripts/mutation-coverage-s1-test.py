#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutation-Coverage Probe — Tom Jones's mutation proposal on Part 11's S1, tested.

CLAIM (Jones, on Part 11):
  Mutation moves the under-invalidation boundary. Instead of asking whether
  user:456 changed, delete the code that would have invalidated user:456 and
  re-run the verify. A surviving mutant is itself the observation — it shows
  the verify's scope is narrower than the implementation's. L3 then reads
  only the mutants that lived.

TEST:
  Apply a fixed set of mutation operators to the invalidation behavior of
  Part 11's S1 fixture, re-run the S1 verify (check user:123 gone) on each,
  and report killed vs surviving.

  Two implementation surfaces:
    A — the literal S1 implementation (targeted key-level delete), which
        ALREADY under-delivers: user:456 is never invalidated.
    B — the true-intent implementation (invalidate ALL user:*), which
        satisfies the intent the S1 requirement missed.

  The question is which surface yields a surviving mutant that points at the
  S1 failure (user:456 not invalidated) rather than at over-delivery.

  A contrast verify written from the TRUE INTENT (all user:* gone) runs
  alongside, to show the fix is contract-definition, not mechanical.

PURE DETERMINISTIC — zero API cost.

SCENARIOS:
  S1  targeted key-level: req=user:123, intent=user:*, verify=check user:123 gone

EXPECTED:
  A  literal S1 impl: survivors are OVER-DELIVERY mutants (also delete
     user:456, clear all). There is no "code that would have invalidated
     user:456" to delete, so the S1 failure stays an absence — mutation does
     NOT flag it.
  B  true-intent impl: a regression mutant (stop invalidating user:456)
     SURVIVES the narrow verify — the real signal mutation can give.
  Contrast  the intent verify kills that regression mutant → the fix is
     contract-definition, which mutation can point at but not derive.

FALSIFY:
  Falsified if any mutation of the LITERAL S1 implementation yields a
  surviving mutant whose presence directly flags "user:456 was never
  invalidated" — rather than flagging a behavior the narrow verify happens
  not to check.

USAGE:
  python mutation-coverage-s1-test.py          # no API
  python mutation-coverage-s1-test.py --save   # + results JSON
"""

import sys, io, json, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"

INITIAL = {"user:123": "v1", "user:456": "v2"}


# ── Implementation surfaces (Part 11 S1 fixture) ───────────────────────

def s1_write(s, k):
    """Literal S1 impl — targeted key-level delete: invalidates only k."""
    del s[k]

def wide_write(s, k):
    """True-intent impl — invalidate ALL user:* entries."""
    for key in list(s):
        if key.startswith("user:"):
            del s[key]


# ── Mutation operators (replacements of the invalidation behavior) ─────

MUTANTS = {
    "M_noop":        lambda s, k: None,
    "M_wrongkey":    lambda s, k: s.pop("user:456", None),
    "M_broaden":     lambda s, k: (s.pop("user:123", None), s.pop("user:456", None)),
    "M_clear":       lambda s, k: s.clear(),
    "M_regress":     lambda s, k: s.pop("user:123", None),
}

DESC = {
    "M_noop":     "invalidation removed entirely",
    "M_wrongkey": "deletes a different key (user:456 only)",
    "M_broaden":  "deletes user:123 AND user:456 (over-delivery)",
    "M_clear":    "clears everything (over-delivery)",
    "M_regress":  "deletes ONLY user:123 — regression from the wide surface",
}


# ── Verifies ───────────────────────────────────────────────────────────

def verify_s1(s):
    """Verify written from the NARROW requirement: check user:123 gone."""
    return "user:123" not in s

def verify_intent(s):
    """Verify written from the TRUE INTENT: all user:* gone."""
    return not any(k.startswith("user:") for k in s)


def run_verify(write_fn, check_fn, key="user:123"):
    s = dict(INITIAL)
    write_fn(s, key)
    return check_fn(s)


VERDICT = lambda passed: "SURVIVE" if passed is True else ("killed" if passed is False else str(passed))


SURFACES = [
    {
        "name": "A — literal S1 impl (targeted delete; user:456 never invalidated)",
        "write": s1_write,
        "mutants": ["M_noop", "M_wrongkey", "M_broaden", "M_clear"],
    },
    {
        "name": "B — true-intent impl (invalidate ALL user:*)",
        "write": wide_write,
        "mutants": ["M_noop", "M_wrongkey", "M_regress"],
    },
]


def run():
    parser = argparse.ArgumentParser(description="Mutation-coverage probe on Part 11 S1")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    W = 76
    print("─" * W)
    print("Mutation-Coverage Probe — Tom Jones's proposal on Part 11's S1")
    print("─" * W)
    print("  Base verify (narrow):  check user:123 gone")
    print("  Contrast verify (intent): all user:* gone")
    print()

    check_fns = {"verify_narrow": verify_s1, "verify_intent": verify_intent}
    all_rows = []

    for surf in SURFACES:
        print("┌─ " + surf["name"])
        # base behavior (no mutation), for reference
        base_narrow = run_verify(surf["write"], verify_s1)
        base_intent = run_verify(surf["write"], verify_intent)
        print(f"│   base behavior → verify_narrow: {VERDICT(base_narrow)}   verify_intent: {VERDICT(base_intent)}")
        print(f"│   {'mutant':<12}{'desc':<42}{'verify_narrow':<16}{'verify_intent'}")
        for mid in surf["mutants"]:
            mfn = MUTANTS[mid]
            row = {
                "surface": surf["name"].split(" — ")[0],
                "mutant": mid,
                "desc": DESC[mid],
            }
            for fname, fn in check_fns.items():
                try:
                    res = run_verify(mfn, fn)
                except Exception as e:
                    res = f"ERR:{e}"
                row[fname] = VERDICT(res)
            print(f"│   {mid:<12}{DESC[mid]:<42}{row['verify_narrow']:<16}{row['verify_intent']}")
            all_rows.append(row)
        print("└─")
        print()

    # ── Verdict ──
    print("─" * W)
    print("VERDICT")
    print("─" * W)
    print("  1. On the literal S1 impl (surface A) the under-invalidation is NOT flagged.")
    print("     Survivors are OVER-DELIVERY mutants (M_broaden, M_clear): there is no")
    print("     'code that would have invalidated user:456' to delete, so the S1 failure")
    print("     (user:456 alive) stays an absence. Reading those survivors requires the")
    print("     same contract judgment L3 already owes — 'should user:456 be invalidated?'")
    print()
    print("  2. Mutation fires cleanly one step over (surface B): a correct implementation")
    print("     under a narrow verify. M_regress (stop invalidating user:456) SURVIVES the")
    print("     narrow verify and is KILLED by the intent verify. There the audit is silent")
    print("     (no unexpected state change — the impl is correct), so mutation genuinely")
    print("     adds detection: it guards the true-intent behavior against future regressions.")
    print()
    print("  3. The fix is contract-definition: the intent verify kills the regression mutant.")
    print("     Mutation points at the gap; it cannot derive the right scope. The survivor")
    print("     queue is smaller than the whole contract, but each item still needs the")
    print("     contract judgment — matching Jones's honest limit.")
    print("─" * W)

    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / "mutation-coverage-s1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "scenario": "S1 (referent mismatch, Part 11)",
                "base_verify": "check user:123 gone",
                "intent_verify": "all user:* gone",
                "surfaces": [
                    {"name": s["name"], "write": s["write"].__name__,
                     "base_narrow": VERDICT(run_verify(s["write"], verify_s1)),
                     "base_intent": VERDICT(run_verify(s["write"], verify_intent)),
                     "mutants": [m for m in s["mutants"]]}
                    for s in SURFACES
                ],
                "rows": all_rows,
                "verdict": (
                    "On the literal S1 impl, mutation does not flag the under-invalidation: "
                    "survivors are over-delivery mutants, and reading them needs the same "
                    "contract judgment L3 already owns. Mutation fires cleanly as a regression "
                    "guard on a correct implementation (surface B): a regression mutant survives "
                    "the narrow verify and is killed by the intent verify, where the audit is "
                    "silent. The fix is contract-definition, not mechanical."
                ),
            }, f, indent=2, ensure_ascii=False)
        print(f"Saved: {path}")

    return all_rows


if __name__ == "__main__":
    run()
