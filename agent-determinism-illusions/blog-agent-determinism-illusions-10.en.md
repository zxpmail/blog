---
title: "The honest boundary of argument-space verification — and what the Evidence Locker adds"
published: false
description: "Four experiments establish C3's catch rate at 4/5 against referent mismatch, and show why the remaining 1/5 is a structural boundary, not a fixable gap. Evidence Locker-style feedback loops detect over-invalidation but not under-invalidation."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# The honest boundary of argument-space verification — and what the Evidence Locker adds

**Agent Determinism Illusions (Part 10)**

*2026-07-14*

Part 9 tested C3 (argument-space runner) against five scenarios and three evaluators. The result: C3 scored 5/5, synonym-immune, DPI-bound made concrete — a structural floor on addressable claims.

That floor has a crack. Mike Czerwinski found it in the dev.to comments on Part 4. This article tests the crack, measures its depth, and shows why it can't be closed — only bounded.

Then it adds a second mechanism: an **evidence feedback loop** inspired by Pascal Cescato's "Evidence Locker" concept. The loop catches over-invalidation (the implementation did more than the contract asked for) but stalls on under-invalidation (the implementation did less). The crack and the loop's blind spot are the same structural boundary.

---

## 1. The crack: referent gameability

Part 9's C3 works by running a verify command that tests the actual behavior: write a key, observe whether the cache entry is gone. The verify command doesn't read the requirement text — it runs code.

Mike Czerwinski pointed out a gap in this design. An author who knows the gate checks referent-presence can write:

> "invalidate user:123"

This is technically addressable (names a key, satisfies the referent gate). But the real intent was broader — invalidate ALL user entries, not just user:123. The gate passes on the narrow referent while the actual scope is missed.

The question: can C3 catch this, even when the verify command is written from the wrong referent?

---

## 2. Experiment I: C3 vs referent mismatch

### Design

Five scenarios. In each, a human reads a requirement with a wrong/narrow referent, writes ONE verify command from it, and C3 runs it. If C3 PASSES, the game succeeded — the verify approved work against a wrong referent. If C3 FAILS, the mismatch was caught.

| Scenario | Implementation | Wrong referent (req) | True intent | Verify checks | Result |
|----------|---------------|---------------------|-------------|---------------|--------|
| S1 | targeted key-level delete | invalidate user:123 | invalidate ALL user:* | user:123 gone | **PASS** → game succeeds |
| S2 | flush-all | leave user:456 alive | same | user:456 alive | **FAIL** → caught |
| S3 | prefix:user/* only | invalidate admin:123 | invalidate user:123 | admin:* gone | **FAIL** → caught |
| S4 | tiered L1/L2 | invalidate L1 | invalidate L1+L2 | L2 gone | **FAIL** → caught |
| S5 | cascade over-inv all | leave user:456 alive | same | user:456 alive | **FAIL** → caught |

### Results

**C3 catch rate: 4/5.** The game succeeds only on S1.

S1 succeeds because the verify command happens to check the right mechanical behavior despite following the wrong referent. "Check user:123 gone" → implementation invalidates user:123 → PASS. But user:456 was never checked, because the narrow requirement never mentioned it.

**The honest interpretation:** C3 catches referent mismatch when the wrong referent leads to a verify command that mismatches the implementation's actual scope. It misses when the verify command mechanically checks the right behavior — even though the SCOPE of what should be checked was wrong.

---

## 3. What the 1/5 gap actually is

The S1 gap is not a C3 defect. It's a **contract-definition quality** issue.

Sequence of events:
1. Human writes requirement: "invalidate user:123" (narrow, incomplete)
2. Human reads requirement, writes verify command: check user:123 gone
3. C3 runs verify command → PASS (user:123 IS invalidated)
4. But user:456 was never checked, because no one asked for it

Step 2 is where the gap lives. The human who wrote the verify command was working from a requirement that was already too narrow. The verify command correctly verifies what the requirement says — but the requirement itself was wrong.

**No deterministic gate can fix this.** A gate verifies what it's told to verify. If the instructions are wrong, the gate produces a correct pass on the wrong scope. This is the irreducible L3 (human review) boundary.

---

## 4. The Evidence Locker pattern

While working on this gap, I read Pascal Cescato's concept of an "Evidence Locker" — a structured collection of runtime evidence that challenges the model rather than accepting it by default.

The core insight: no upfront gate is correct on the first attempt. The honest path is **run → collect evidence → challenge the model → refine the contract → repeat.**

This is exactly the feedback loop missing from the current architecture. C3 produces evidence (PASS/FAIL per key). That evidence should feed back into the contract scope, not just into a human review queue.

---

## 5. Experiment II: evidence feedback loop

### Design

Multi-round simulation. Each round:
1. C3 verifies against the current contract scope
2. **Post-audit**: snapshot ALL keys before and after write, detect state changes outside the verify scope
3. Evidence from the post-audit broadens the contract for the next round
4. Repeat until scope converges

Two cache implementations to test what the loop can and cannot detect:

- **Scenario A (targeted, under-invalidation):** write(k) removes only k. user:456 survives. This is the S1 gap from Experiment I.
- **Scenario B (flush, over-invalidation):** write(k) removes EVERYTHING. admin:123 also gets cleared.

### Results

**Scenario A (under-invalidation): STALLED at 50% (8 rounds).**

| Round | Scope | Coverage | Evidence signal |
|-------|-------|----------|----------------|
| 1 | user:123 | 50% | user:123 confirmed → no gap signal |
| 2-8 | user:123 | 50% | Same. user:456 unchanged → invisible |

The loop cannot detect under-invalidation because **no state change = no evidence**. user:456 sits untouched, the post-audit sees no unexpected activity, and the scope never broadens. This is the same honest boundary as Experiment I's S1 gap.

**Scenario B (over-invalidation): CONVERGED in 2 rounds.**

| Round | Scope | Coverage | Evidence signal |
|-------|-------|----------|----------------|
| 1 | user:123 | 50% | **admin:123 changed unexpectedly** |
| 2 | user:123 + user:456 + admin:123 | 100% | all confirmed → converged |

The loop detects over-invalidation because the implementation produces **unexpected state changes** — keys that moved even though the contract didn't ask about them. "admin:123 was deleted even though we only wrote user:123" is a detectable signal.

### Honest boundary

| Signal type | Detectable? | Mechanism | Maps to |
|-------------|------------|-----------|---------|
| Over-invalidation | ✅ | Unexpected state change | flush, cascade |
| Under-invalidation | ❌ | No state change = no evidence | S1 gap, Mike's game |

The feedback loop is a partial answer. It broadens scope when the implementation over-delivers, but it cannot close the under-invalidation gap — because the gap is the ABSENCE of an observable event.

---

## 6. Three mechanisms, three failure modes

| Mechanism | Catches | Misses | Why |
|-----------|---------|--------|-----|
| C3 verify (non-parameterized) | Behavior mismatch, DPI-bound fabrications | Incomplete verify scope (wrong referent) | Runs what it's told |
| C3 verify + broader referent check | Wrong referent that mismatches impl behavior (4/5) | Wrong referent that coincidentally passes (1/5) | Verify tests the referent it was given |
| Evidence feedback loop | Over-invalidation (unexpected state changes) | Under-invalidation (no change = no signal) | Audit detects changes, cannot detect absences |
| L3 human review | All of the above | Attention budget, fatigue, bias | No mechanism replaces human judgment |

The honest claim: these three mechanisms are not a pipeline that converges to 100%. They are three different failure-mode detectors, each with a blind spot, and the blind spots overlap in one place — the under-invalidation gap, which is contract-definition quality and belongs to human review.

---

## 7. What this means for the architecture

The Evidence Locker pattern adds a specific engineering artifact: a **post-audit layer** that runs after every C3 verify, snapshots persistent state, and flags keys that changed outside the verify scope.

In forge-verify terms:
- **C3 verify** runs the human-authored verify_command → PASS/FAIL per requirement
- **Evidence feedback** runs a post-audit that compares pre/post state across ALL known keys → unexpected changes flagged
- **Contract refinement** uses flagged unexpected changes to broaden the verify scope for the next run

The honest benefit: **over-invalidation converges quickly** (flush, cascade, broad-scope implementations all produce detectable signals). The honest limitation: **under-invalidation does not converge** (wrong referent that happens to work remains invisible).

This is not fixable by a smarter audit. It is a structural property of automated verification: you cannot detect the absence of an event without knowing the event should have occurred, and knowing that requires human domain knowledge. The gap is named, bounded, and assigned to L3 — which is the design's honest work, not its failure.

---

*Experiment scripts:*
- [`referent-mismatch-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 5 scenarios, single verify command, C3 catch rate 4/5
- [`evidence-feedback-loop-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 2 scenarios × 8 rounds, over-inv converges in 2, under-inv stalls

*Results: `results-v2/referent-mismatch.json`, `results-v2/evidence-feedback-loop-{A,B}.json`*

*Previous: [The Third Predicate: Argument-Space Verification, Tested](blog-agent-determinism-illusions-9.en.md)*
*Series: [Agent Determinism Illusions on dev.to/zxpmail](https://dev.to/zxpmail)*
