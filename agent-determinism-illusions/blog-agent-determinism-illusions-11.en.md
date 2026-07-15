---
title: "Key-space C3: the Bloom filter that closes referent gameability — tested"
published: false
description: "Two experiments on Mike Czerwinski's round 7: write-time-resolution passes 50% of wrong referents and LLM accuracy is 17%. Solution: declare key space instead of single key — key-space C3 catches 5/5 wrong-referent cases."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Key-space C3: the Bloom filter that closes referent gameability — tested

**Agent Determinism Illusions (Part 11)**

*2026-07-15*

Part 10 identified a structural gap in C3: when a write-time-resolution produces a plausible-but-wrong key ("user:123" instead of "session:abc"), C3 verifies the chosen key and passes — the gate accepts a bad resolution because it verifies mechanically on the wrong target.

Mike Czerwinski argued this failure belongs to the gate, not upstream of it. The resolution step is the gate's own mechanism, and if the gate accepts a plausible-but-wrong key, the failure happened within the architecture's boundary.

This article tests that claim with two experiments, then adds the fix.

---

## 1. Experiment I: Write-time resolution, tested

### Design

Six requirements that intentionally defer scope. Each has a true intent (what should happen) and multiple possible resolutions (what an agent could plausibly choose). C3 verifies whatever key the agent picks.

**Phase A (deterministic):** enumerate all possible resolutions, run C3 on each.

| Scenario | Requirement | True intent | Wrong resolution that passes C3 |
|----------|------------|-------------|--------------------------------|
| S1 | "invalidate the relevant cache entry when user data changes" | all user:* | user:123 only → PASS (under-inv) |
| S2 | "clear stale cache entries before writing" | only user:123 | (none — over-inv caught) |
| S3 | "invalidate cache if write affects the user's session" | session:abc | user:123 → PASS (wrong-referent) |
| S4 | "invalidate all related entries on profile update" | user:123 + profile:123 | user:123 only → PASS (under-inv) |
| S5 | "on password change, invalidate security token" | token:789 | user:123 → PASS (wrong-referent) |
| S6 | "on permissions change, invalidate all sessions" | all session:* | user:123 → PASS (wrong-referent) |

### Results

**C3 blocks wrong resolutions at 6/12 (50%).** But the distribution matters:

| Error type | Total | Pass C3 | Blocked by C3 |
|-----------|-------|---------|---------------|
| wrong-referent | 4 | **3** | 1 |
| under-inv | 4 | 2 | 2 |
| over-inv | 3 | 0 | 3 |
| under-inv-empty | 1 | 1 | 0 |

*Note: 6 "correct" resolutions (1 per scenario) are excluded — C3 verifies them correctly and they are not failure cases. The 6/12 denominator counts only the wrong resolutions.*

**Mike's claim confirmed: 3 of 4 wrong-referent resolutions pass C3.** S1, S3, S5: the agent chose a key that happens to be the trigger key, C3 verifies it, passes. The gate accepted a bad resolution because the mechanically checked key happened to align with the write operation, not with the requirement's intent.

The over-inv pattern is the mirror: when the resolution claims *more* keys than the implementation actually touched, C3 correctly FAILs. Over-inv produces detectable evidence (surviving keys the resolution claimed should be gone). Under-inv and wrong-referent don't.

**Phase B (LLM performs the resolution, deepseek-v4-flash):** Let the model read each ambiguous requirement and produce the concrete key list.

| Scenario | Model chose | Correct? |
|----------|------------|----------|
| S1 | user:123 + profile:123 + admin:123 | ❌ mixed |
| S2 | user:123 + profile:123 + admin:123 | ❌ over-inv |
| S3 | [] | ❌ empty refusal |
| **S4** | **user:123 + profile:123** | **✅** |
| S5 | [] | ❌ empty refusal |
| S6 | [] | ❌ empty refusal |

**LLM resolution accuracy: 1/6 (17%).** The model either over-invalidates (adds unrelated keys) or under-invalidates (returns empty — cautious refusal). Only S4 was correctly resolved.

This adds a hard number to Mike's concern: an agent doing write-time resolution is wrong 83% of the time on this test set. The gate passes 50% of those errors silently.

---

## 2. The Bloom filter idea

The structural pattern is a **membership test** problem. Single-key C3 asks "is cache[k] gone?" — a point check that passes on any k the agent names, regardless of whether k was the right one.

The fix: declare the **key space** instead of the single key. "user:*" instead of "user:123". C3 checks ALL keys in that space after the write operation. This is analogous to a Bloom filter upstream of a cache: you don't ask "is this specific key present?" — you ask "is ANY key in the declared space present?"

The contract field becomes:

```json
{
  "id": "REQ-3",
  "desc": "write-invalidation on cache writes",
  "verify_command": "node .forge/verify/write-invalidation.js",
  "verify_keyspace": "user:*",
  "type": "argument-space"
}
```

C3 iterates `keys_in_space("user:*")` → `["user:123", "user:456"]` → verifies both are gone after the write.

---

## 3. Experiment II: Key-space C3

### Design

Same 6 scenarios. Each has a declared key space. Two C3 modes:

| Mode | Question it answers |
|------|-------------------|
| Single-key C3 | "Is cache[k] gone after write(k)?" |
| Key-space C3 | "Is EVERY key in space S gone after write(k)?" |

Three cache implementations:
- **LiveCache:** write(k) removes only k (targeted, under-inv by default)
- **BulkCache:** write(k) removes ALL keys matching k's prefix (prefix-based)
- **FlushCache:** write(k) removes everything (over-inv extreme)

### Results

| Mode | Cache | Wrong-ref caught | Rate |
|------|-------|-----------------|------|
| single-key | any | 0/5 | **0%** |
| **key-space** | **LiveCache** | **5/5** | **100%** |
| **key-space** | **BulkCache** | **4/5** | **80%** |
| key-space | FlushCache | 5/5 | 100% |

**Key-space C3 catches 5/5 wrong-referent cases with LiveCache.** Every scenario where single-key C3 was blind to a wrong resolution is caught when C3 checks the declared space.

The one BulkCache "miss" (S1: space `user:*`, trigger `user:123`) is the *desired* behavior: the trigger's prefix matches the space, BulkCache correctly invalidates all user:* keys, and the gate passes. The resolution was correct, the implementation handled the space, and the gate confirmed it.

**How it works in each scenario:**

| Scenario | Agent resolves to | Declared space | Key-space C3 checks | Result |
|----------|-----------------|----------------|-------------------|--------|
| S1 | user:123 | user:* | user:123 ✅ user:456 ❌ (survived) | FAIL |
| S3 | user:123 | session:* | session:abc ❌ session:xyz ❌ (not invalidated) | FAIL |
| S4 | user:123 | user:*,profile:* | user:123 ✅ user:456 ❌ profile:123 ❌ | FAIL |
| S5 | user:123 | token:* | token:789 ❌ (not invalidated) | FAIL |
| S6 | user:123 | session:* | session:abc ❌ session:xyz ❌ (not invalidated) | FAIL |

In every case, the agent's wrong resolution is caught because the declared space contains keys that the write operation didn't touch.

---

## 4. The remaining boundary — measured

Key-space C3 requires the key space to be **declarable**. The boundary question is: how large is the undeclarable class in real requirements?

I ran a corpus classification experiment: 35 requirements from cache invalidation, authorization, and write-path domains. Each classified by human ground truth (can a key space be declared?) and by an automated classifier (deterministic rules).

### Human ground truth

| Class | Count | Rate |
|-------|-------|------|
| Declarable | 20 | 57% |
| Partial (needs human resolution) | 7 | 20% |
| Undeclarable | 5 | 14% |
| Out-of-scope (UX/ops/freshness) | 3 | 9% |

### The undeclarable class — what is it?

The 8 undeclarable + out-of-scope cases are not cache write-path requirements. They are:

- **Freshness/timing properties** (3): "eventually consistent", "latest state", "latest hierarchy"
- **UX/robustness claims** (2): "gracefully handle cache misses", "feel responsive"
- **Non-write-path mechanisms** (2): TTL-based expiry, data integrity consistency
- **Distribution property** (1): "synchronize across all nodes"

**Zero of these belong in C3's domain.** They are not write-path cache invalidation requirements — they were misclassified at the routing step.

### The partial class — resolvable?

| Subtype | Count | Resolution |
|---------|-------|-----------|
| Needs dependency trace | 3 | `SELECT session_id FROM sessions WHERE user_id = ?` — architecturally resolvable |
| Needs intent inference | 4 | "relevant", "related", "stale" — requires human judgment |

### Automated classifier

The classifier (deterministic pattern rules) achieves 66% exact agreement with human ground truth — not high enough to run unattended. It tends to be conservative (says "partial" for 8 cases the human called "declarable"), which slows things down without reopening the gap. The critical direction: **zero false undeclarables** — the classifier never said "can't declare" when a human said "can declare." There is 1 false-declarable in the other direction, so the classifier is a conservative first-pass that needs review before accepting a "declarable" verdict.

### What this means

The undeclarable-space class that would reopen Part 10's under-inv gap is **small and bounded for requirements legitimately in C3's domain**. Of the 35-requirement corpus, 5 (14%) are genuinely undeclarable even by a human — freshness, timing, and distribution properties that no key-space expression can capture. Another 3 (9%) are out-of-scope (UX/ops/data-integrity) and shouldn't have entered the C3 pipeline at all.

The honest boundary shifts from "undeclarable space size" to **"routing accuracy into C3"** — a classification problem upstream of the gate. That's a different problem, addressable by the same sampling layer, but not a structural gap in key-space C3 itself.

---

## 5. What this means for the architecture

| Mechanism | Gap it addresses | Catch rate | Remaining boundary |
|-----------|-----------------|------------|-------------------|
| Single-key C3 | DPI-bound fabrications | 5/5 (Part 9) | Referent gameability (0/5) |
| **Key-space C3** | **Referent gameability** | **5/5** | **Routing into C3 (not space size)** |
| Evidence feedback loop | Over-invalidation | Converges 2 rounds | Under-inv invisible |
| Sampling | All residual gaps | — | Fixed cost, no adaptive signal |

The move from single-key to key-space C3 is a structural improvement: it changes the question from "did this one key change?" to "is the declared space covered?" and in doing so closes the wrong-referent gap that Mike identified.

The three mechanisms from Part 10 (C3, evidence feedback, L3 human review) now have a fourth: **key-space declaration**. It's not a new mechanism — it's a more precise contract field that constrains what C3 iterates over. The Bloom filter analogy holds: a membership test against a declared space is stronger than a point lookup, and declaring the space (rather than implying it) makes the contract's scope explicit.

The honest claim: **wrong-referent gameability is structurally closed for declarable spaces.** The 35-requirement corpus puts a number on the residual: 14% are genuinely undeclarable by a human, 9% are misrouted, and the remaining 77% are either declarable now (57%) or resolvable via dependency tracing (20%). The boundary is not space size but routing accuracy into the gated pipeline.

---

*Experiment scripts:*
- [`write-time-resolution-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 6 scenarios × resolution enumeration + LLM phase
- [`key-space-verify-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 6 scenarios × 2 C3 modes × 3 cache impls
- [`space-declarability-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 35-requirement corpus × human × automated classifier

*Results: `results-v2/write-time-resolution.json`, `results-v2/key-space-verify.json`, `results-v2/space-declarability.json`*

*Previous: [The honest boundary of argument-space verification](blog-agent-determinism-illusions-10.en.md)*
*Series: [Agent Determinism Illusions on dev.to/zxpmail](https://dev.to/zxpmail)*
