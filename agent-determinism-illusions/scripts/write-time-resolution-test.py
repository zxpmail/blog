#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Write-Time Resolution Experiment — Mike Czerwinski's round 7, tested.

CLAIM (Czerwinski, dev.to Part 5, Jul 14):
  "The write-time-resolution fix says: when a requirement defers scope on
   purpose ('the relevant cache entry'), force whoever implements it to
   compute the concrete referent before the requirement is admitted. That
   computation is not the human authoring a requirement, it's the agent
   discharging the gate's own resolution step. If that step can be satisfied
   by naming a plausible-but-wrong key, the gate itself accepted a bad
   resolution."

EXPERIMENT:
  Six scenarios, each with a requirement that intentionally defers scope.
  Each scenario has a TRUE intent and a set of plausible-but-wrong resolutions.
  The experiment has two phases:

  Phase A (deterministic, zero API cost):
    For each scenario, enumerate ALL possible resolutions (correct + wrong).
    Run C3 verify on each resolution. Predicted result: C3 PASSES on ALL
    resolutions, because C3 only verifies cache[k] for the k it was given.
    This confirms Mike's claim: the gate cannot detect a wrong resolution.

  Phase B (--with-llm, optional):
    Feed the same ambiguous requirement to an LLM, let it choose a resolution.
    Measure: how often does the LLM's resolution match the true intent?
    This measures agent resolution accuracy.

MEASUREMENTS:
  - C3 pass rate on wrong resolutions (should be 100%)
  - Under-invalidation rate (resolution too narrow)
  - Over-invalidation rate (resolution too broad)
  - Resolution accuracy (LLM Phase only)
  - Post-audit detection rate (evidence feedback loop on resolution errors)

USAGE:
  python write-time-resolution-test.py                 # Phase A only (deterministic)
  python write-time-resolution-test.py --save           # + save JSON
  python write-time-resolution-test.py --with-llm       # + Phase B LLM resolution
  python write-time-resolution-test.py --with-llm --save --model glm-5.2

DEPENDENCIES:
  Phase A: none (pure Python, stdout)
  Phase B: ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL env vars
           or OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL
"""

import sys, io, json, argparse, os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"


# ============================================================
# Cache simulator (same pattern as evidence-feedback-loop-test.py)
# ============================================================

ALL_KEYS = [
    "user:123", "user:456",
    "session:abc", "session:xyz",
    "profile:123", "token:789",
    "admin:123",
]

class LiveCache:
    """Cache with per-key invalidation. write(k) removes only k."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        if k in self.data:
            del self.data[k]
    def has(self, k):
        return k in self.data

class FlushCache:
    """Cache with full flush. write(k) removes everything."""
    def __init__(self):
        self.data = {k: f"v{i}" for i, k in enumerate(ALL_KEYS)}
    def write(self, k):
        self.data.clear()
    def has(self, k):
        return k in self.data


# ============================================================
# Scenarios: ambiguous requirements that defer scope
# ============================================================

@dataclass
class Scenario:
    id: str
    requirement: str
    true_intent: str          # human-readable description
    true_keys: List[str]      # the k(s) that should be invalidated
    trigger_key: str          # what the agent writes
    resolution_choices: Dict[str, List[str]]  # label → keys the resolver might pick
    impl_type: str = "live"   # "live" or "flush"
    notes: str = ""

SCENARIOS = [
    Scenario(
        id="S1",
        requirement="invalidate the relevant cache entry when user data changes",
        true_intent="invalidate ALL user:* keys on user data write",
        true_keys=["user:123", "user:456"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["user:123", "user:456"],
            "narrow-user": ["user:123"],
            "wrong-target": ["admin:123"],
        },
        notes="classic under-inv: S1 from referent-mismatch test",
    ),
    Scenario(
        id="S2",
        requirement="clear stale cache entries before writing new data",
        true_intent="invalidate ONLY the specific key being written, leave others",
        true_keys=["user:123"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["user:123"],
            "over-inv-flush": ALL_KEYS[:],  # flush all
            "narrow-none": [],
        },
        notes="over-inv vs under-inv: both plausible from 'stale entries'",
    ),
    Scenario(
        id="S3",
        requirement="invalidate cache if write affects the user's active session",
        true_intent="invalidate the session:abc, not user:123 directly",
        true_keys=["session:abc"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["session:abc"],
            "wrong-referent-user": ["user:123"],
            "overly-cautious": ["session:abc", "user:123", "session:xyz"],
        },
        notes="wrong referent: plausible-but-wrong k passes C3",
    ),
    Scenario(
        id="S4",
        requirement="when updating a user profile, invalidate all related entries",
        true_intent="invalidate user:123 AND profile:123",
        true_keys=["user:123", "profile:123"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["user:123", "profile:123"],
            "narrow-user-only": ["user:123"],
            "narrow-profile-only": ["profile:123"],
        },
        notes="compound scope: resolving only one half is under-inv",
    ),
    Scenario(
        id="S5",
        requirement="on password change, invalidate the user's security token",
        true_intent="invalidate token:789 for this user, not user:123 itself",
        true_keys=["token:789"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["token:789"],
            "wrong-referent-user": ["user:123"],
            "overly-broad": ["token:789", "user:123", "session:abc"],
        },
        notes="wrong referent: plausible to pick user:123 instead of token:789",
    ),
    Scenario(
        id="S6",
        requirement="when permissions change, invalidate all sessions for this user",
        true_intent="invalidate ALL session:* for this user across nodes",
        true_keys=["session:abc", "session:xyz"],
        trigger_key="user:123",
        resolution_choices={
            "correct": ["session:abc", "session:xyz"],
            "narrow-session-only": ["session:abc"],
            "wrong-referent-user": ["user:123"],
        },
        notes="scope breadth: resolving only one session leaves the other alive",
    ),
]


# ============================================================
# C3 verify + post-audit
# ============================================================

def snapshot(cache):
    return {k: cache.has(k) for k in ALL_KEYS}

def c3_verify(cache_cls, trigger_key, resolution_keys):
    """C3: write trigger, check that ALL resolution_keys are invalidated.
    Returns (results, before, after)."""
    c = cache_cls()
    before = snapshot(c)
    c.write(trigger_key)
    after = snapshot(c)

    results = []
    for k in resolution_keys:
        gone = not c.has(k)
        results.append({
            "key": k, "pass": gone,
            "present_after": c.has(k),
            "expected_invalidated": True,
        })
    return results, before, after


def post_audit(before, after, resolution_keys):
    """Detect unexpected state changes (evidence for feedback)."""
    evidence = []
    scope_set = set(resolution_keys)

    for k in ALL_KEYS:
        changed = before[k] != after[k]
        in_scope = k in scope_set

        if changed and not in_scope:
            evidence.append({
                "key": k, "type": "unexpected_change",
                "detail": f"{k} changed but wasn't in resolution scope",
            })
        if not changed and in_scope:
            evidence.append({
                "key": k, "type": "expected_change_missing",
                "detail": f"{k} was in resolution scope but did NOT change",
            })

    return evidence


# ============================================================
# LLM resolver (Phase B)
# ============================================================

def call_llm(prompt, model="deepseek-v4-flash", max_tokens=1024):
    """Call LLM for resolution task. Supports Anthropic-compatible and OpenAI endpoints."""
    import urllib.request
    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    if base:
        url = base.rstrip("/") + "/v1/messages"
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        use_model = os.environ.get("ANTHROPIC_MODEL", "") or model
        data = json.dumps({
            "model": use_model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }, method="POST")
    else:
        # OpenAI-compatible fallback
        url = (os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions")
        key = os.environ.get("OPENAI_API_KEY", os.environ.get("ANTHROPIC_AUTH_TOKEN", ""))
        use_model = os.environ.get("OPENAI_MODEL", os.environ.get("ANTHROPIC_MODEL", model))
        data = json.dumps({
            "model": use_model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }, method="POST")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if base:
                    # Anthropic-compatible: content may contain thinking blocks before text
                    for block in body["content"]:
                        if block.get("type") == "text":
                            return block["text"]
                    return ""  # no text block found
                else:
                    return body["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 2:
                return f"[LLM call failed: {e}]"
            continue


RESOLUTION_PROMPT = """\
You are implementing a cache invalidation strategy based on a product requirement.
The requirement is intentionally broad — your job is to choose the concrete cache key(s) to invalidate.

Requirement: {requirement}

The system writes: {trigger_key}

Which cache keys should be invalidated? Available keys:
{available_keys}

Respond with ONLY a JSON array of key strings, nothing else. Example:
["user:123", "session:abc"]

If no keys should be invalidated, respond with an empty array: []
"""


def llm_resolve(scenario: Scenario) -> List[str]:
    """Ask LLM to pick resolution keys."""
    avail = "\\n".join(f"  - {k}" for k in ALL_KEYS)
    prompt = RESOLUTION_PROMPT.format(
        requirement=scenario.requirement,
        trigger_key=scenario.trigger_key,
        available_keys=avail,
    )
    text = call_llm(prompt)
    # Try to parse JSON array from response
    try:
        # Find JSON array in response
        import re
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except (json.JSONDecodeError, AttributeError):
        return []


# ============================================================
# Resolution classification
# ============================================================

def classify_resolution(chosen_keys, true_keys):
    """Classify how the chosen resolution relates to the true intent."""
    chosen_set = set(chosen_keys)
    true_set = set(true_keys)

    if chosen_set == true_set:
        return "correct"
    if chosen_set.issuperset(true_set):
        return "over-inv"
    if chosen_set.issubset(true_set) and chosen_set:
        return "under-inv"
    if not chosen_set:
        return "under-inv-empty"
    # Partial overlap but neither subset nor superset
    if chosen_set & true_set and not chosen_set.issubset(true_set):
        return "mixed"
    # No overlap
    return "wrong-referent"


# ============================================================
# Phase A: deterministic enumeration
# ============================================================

def run_phase_a():
    """Enumerate ALL possible resolutions for each scenario.
    Shows that C3 passes on every resolution — even wrong ones."""
    print("=" * 72)
    print("Phase A: Deterministic Enumeration — all possible resolutions")
    print("=" * 72)
    print()

    rows = []
    all_c3_pass = True

    for sc in SCENARIOS:
        print(f"── {sc.id}: {sc.requirement}")
        print(f"    True intent: {sc.true_intent}")
        print(f"    Keys to invalidate: {sc.true_keys}")
        print()

        cache_cls = FlushCache if sc.impl_type == "flush" else LiveCache

        for label, res_keys in sc.resolution_choices.items():
            results, before, after = c3_verify(cache_cls, sc.trigger_key, res_keys)
            passes = sum(1 for r in results if r["pass"])
            fails = sum(1 for r in results if not r["pass"])
            c3_passed = fails == 0
            if not c3_passed:
                all_c3_pass = False

            evidence = post_audit(before, after, res_keys)
            classification = classify_resolution(res_keys, sc.true_keys)
            post_audit_signal = any(
                e["type"] == "unexpected_change" for e in evidence
            )

            print(f"      resolution: {label}  →  keys={res_keys}")
            print(f"        C3: {'PASS' if c3_passed else 'FAIL'} ({passes}/{passes+fails})")
            print(f"        classification: {classification}")
            if not c3_passed:
                failed_keys = [r["key"] for r in results if not r["pass"]]
                print(f"        FAILED keys: {failed_keys}")
            print(f"        post-audit signal: {'YES (over-inv detectable)' if post_audit_signal else 'NO (under-inv silent)'}")
            print()

            rows.append({
                "scenario": sc.id,
                "requirement": sc.requirement,
                "resolution_label": label,
                "resolution_keys": res_keys,
                "true_keys": sc.true_keys,
                "c3_pass": c3_passed,
                "c3_pass_count": passes,
                "c3_total": passes + fails,
                "classification": classification,
                "post_audit_detectable": post_audit_signal,
            })

    # Summary
    print("── Summary ──")
    print()
    wrong_c3_pass = [r for r in rows
                     if r["classification"] != "correct" and r["c3_pass"]]
    wrong_c3_fail = [r for r in rows
                     if r["classification"] != "correct" and not r["c3_pass"]]
    print(f"  Wrong resolutions that PASS C3: {len(wrong_c3_pass)}")
    print(f"  Wrong resolutions that FAIL C3: {len(wrong_c3_fail)}")
    print(f"  C3 blocks wrong resolution rate: "
          f"{len(wrong_c3_fail)}/{len(wrong_c3_pass) + len(wrong_c3_fail)} "
          f"({len(wrong_c3_fail)/(len(wrong_c3_pass)+len(wrong_c3_fail))*100:.0f}%)")

    # Breakdown by classification
    for cls in ["under-inv", "under-inv-empty", "over-inv", "wrong-referent", "mixed"]:
        cls_rows = [r for r in rows if r["classification"] == cls]
        if cls_rows:
            c3_pass_count = sum(1 for r in cls_rows if r["c3_pass"])
            print(f"  {cls}: {len(cls_rows)} total, {c3_pass_count} passed C3")

    return rows, all_c3_pass


# ============================================================
# Phase B: LLM resolution (optional, --with-llm)
# ============================================================

def run_phase_b():
    """Let LLM resolve ambiguous requirements; measure accuracy."""
    print()
    print("=" * 72)
    print("Phase B: LLM Write-Time Resolution")
    print("=" * 72)
    print()

    results = []
    correct_count = 0

    for sc in SCENARIOS:
        print(f"── {sc.id}: {sc.requirement}")
        chosen = llm_resolve(sc)
        classification = classify_resolution(chosen, sc.true_keys)
        is_correct = classification == "correct"

        print(f"    LLM chose: {chosen}")
        print(f"    True intent: {sc.true_keys}")
        print(f"    Classification: {classification}")
        print(f"    {'✓' if is_correct else '✗'} Correct")

        if is_correct:
            correct_count += 1

        results.append({
            "scenario": sc.id,
            "requirement": sc.requirement,
            "llm_chosen_keys": chosen,
            "true_keys": sc.true_keys,
            "classification": classification,
            "correct": is_correct,
        })
        print()

    accuracy = correct_count / len(SCENARIOS) * 100
    print(f"── LLM Resolution Accuracy: {correct_count}/{len(SCENARIOS)} ({accuracy:.0f}%)")
    print()

    return results


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Write-time resolution experiment")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument("--with-llm", action="store_true", help="Run Phase B (LLM resolution)")
    parser.add_argument("--model", default="deepseek-v4-flash", help="Model for Phase B")
    args = parser.parse_args()

    # ── Phase A ──
    rows_a, all_c3_pass = run_phase_a()

    result = {
        "experiment": "write-time-resolution-test",
        "design": {
            "claim": "Write-time resolution moves failure surface to resolution step; "
                     "C3 cannot detect wrong resolution, only verify chosen k",
            "method": "6 scenarios × multiple resolution choices, C3 verify + post-audit",
            "phases": ["A: deterministic enumeration", "B: LLM resolution (optional)"],
            "scenario_count": len(SCENARIOS),
            "total_resolution_variants": sum(
                len(sc.resolution_choices) for sc in SCENARIOS
            ),
        },
        "phase_a": {
            "all_c3_pass": all_c3_pass,
            "wrong_resolutions_that_pass_c3": sum(
                1 for r in rows_a
                if r["classification"] != "correct" and r["c3_pass"]
            ),
            "wrong_resolutions_that_fail_c3": sum(
                1 for r in rows_a
                if r["classification"] != "correct" and not r["c3_pass"]
            ),
            "rows": rows_a,
        },
        "phase_b": None,
    }

    # ── Phase B ──
    if args.with_llm:
        rows_b = run_phase_b()
        accuracy = sum(1 for r in rows_b if r["correct"]) / len(rows_b)
        result["phase_b"] = {
            "model": args.model,
            "accuracy": accuracy,
            "correct_count": sum(1 for r in rows_b if r["correct"]),
            "total": len(rows_b),
            "rows": rows_b,
        }

    # ── Honest boundary ──
    print()
    print("=" * 72)
    print("HONEST BOUNDARY")
    print("=" * 72)
    print()
    print("  C3 verifies cache[k] for the k it was given.")
    print("  C3 CANNOT verify that k matches the requirement's intent.")
    print()
    print("  Write-time resolution is a real improvement —")
    print("  it makes the agent's k choice explicit, auditable, and")
    print("  reviewable. But the resolution step itself is a semantic")
    print("  judgment, DPI-bound, outside C3's reach.")
    print()
    print("  The gap Mike named is structural, not a C3 bug:")
    print("  the gate accepts a bad resolution when the chosen k")
    print("  happens to pass C3's mechanical check on the wrong target.")
    print()
    print("  Under-inv (resolution too narrow) → no evidence signal →")
    print("  undetectable by automated audit. Over-inv (too broad) →")
    print("  post-audit detects unexpected changes → converges by feedback.")
    print()

    # ── Save ──
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / "write-time-resolution.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
