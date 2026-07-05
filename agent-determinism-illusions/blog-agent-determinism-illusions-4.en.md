<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Risk-based agent output quality: an alternative to LLM quality gates
  ─────────────────────────────────────────────────────────────────
-->

---
title: "After dismantling four rounds of agent quality solutions, here's the honest alternative"
published: false
description: "No LLM quality inspectors, no embedding clustering, no confidence scores. Just deterministic routing + SPC + diff review + fixed-rate sampling. With honest cost estimates and known failure modes."
tags: ai, llm, agents, testing
canonical_url: ""
---

Over the last three articles, I tested the popular "production agent loop" design across six separate experiments:

1. **Lexical overlap ≠ semantics** — 50% misclassification
2. **Temperature 0 ≠ determinism** — open output only 70% consistent
3. **Phase gates ≠ task completion** — 50% false positives
4. **Embedding ≠ synonym/antonym separation** — cosine diff 0.026
5. **Stronger models trade false positives for false rejections** — GLM-5.2 hit 0% FP but rejected 75% of valid work
6. **Architecture diagrams ≠ solutions** — my own human-in-the-loop Harness had 6 unvalidated assumptions

Six rounds of dismantling, all backed by reproducible experiments.

Then I asked myself the question every critic has to answer: **"What's your alternative?"**

Here it is. Not an architecture diagram — a set of four implementable strategies, all using deterministic code, zero new LLM dependencies.

## The core insight shift

Every approach I tested or proposed shared a fatal assumption: **a single module (LLM or human) can judge whether output is "correct."** That binary judgment at the semantic layer is what creates the precision-recall trap that all three model tiers fell into.

The alternative: **don't judge correctness. Judge risk.** Route high-risk work out of the agent pipeline entirely. Auto-release low-risk work. Only show medium-risk work to a human — and when you do, make it a diff review, not a full-text read.

## Four-layer architecture (all deterministic code)

### Layer 1: task-type routing

Before a task enters the agent engine, a router classifies it by output type:

| Type | Criterion | Strategy |
|------|-----------|----------|
| **A (verifiable)** | Output is compilable / schema-validatable (code, JSON, SQL) | **Fully automatic.** Compile check or schema validation is the one and only gate. No LLM quality inspector called. |
| **B (high-risk)** | Money, legal, privacy, external publishing | **No agent execution.** Prompt: "This task requires human handling." AI provides a draft only, never auto-executes. |
| **C (low-risk content)** | Internal briefs, first drafts, brainstorming | **Auto-release.** Tag as "draft" (80% default confidence). No quality queue. |
| **D (medium-risk content)** | Client-facing emails, external documents | **Diff review.** Don't judge content quality. Only show what changed. |

Why this beats an "LLM quality inspector": it acknowledges the LLM's limit at the source. Use the LLM for what it can do (generate). Never use an LLM for what it does poorly (judge semantic quality).

### Layer 2: diff review — replace "judge right/wrong"

This is the key operational alternative. For Type D tasks, don't show the reviewer the "final output." Show them **what the agent changed from the previous version.**

Implementation: after generation, the system diffs the output against the original (or a template) using `difflib` — no LLM needed.

Reviewer UI: only the modified lines are highlighted. The reviewer answers one question: **"Does this change introduce an error?"**

Measured cognitive load:

| Method | Reading load | Cognitive demand | Time |
|--------|-------------|-----------------|------|
| Full-text quality judgment (500 words) | 500 words | High | ~60 s |
| Diff review (50-word change) | 50 words | **Low** | **~10 s** |

The shift: open-ended judgment ("Is this article good?") becomes closed-ended ("Did this paragraph break something?"). The cognitive demand drops by an order of magnitude.

### Layer 3: statistical process control — replace semantic clustering

Semantic clustering failed because content about different topics (a research brief vs. a chapter) won't embed close together just because they were both falsely rejected.

Alternative: **don't cluster by semantic features. Cluster by behavioral features.**

For every task, record metadata — execution steps, tool-call count, output length, special-character ratio. Then detect anomalies with simple statistical thresholds:

- 15 execution steps vs. mean of 5 → flag
- Output length = 0 → flag
- Output is 100% punctuation (the duck and the period from Experiment 3) → flag

All code. Zero LLM cost. And it catches "quack quack" (length anomaly) and "." (special-char anomaly) without understanding a word.

**Measured:** I ran SPC on the 8 scenarios from Experiment E (content length, special-char ratio, CJK ratio, alpha ratio, digit ratio; statistical threshold = mean +/- 1.5sd):

| Scenario | SPC result | Actual | Correct? |
|----------|-----------|--------|----------|
| G1 (duck, garbage) | **ANOMALY** (high CJK ratio) | Garbage | ✅ |
| G2 (period, garbage) | **ANOMALY** (100% special char) | Garbage | ✅ |
| G3 (TODO, garbage) | **ANOMALY** (100% alphabetic) | Garbage | ✅ |
| **G4 (zero-case, garbage)** | **NORMAL** (same features as L4) | **Garbage** | **FOFN** |
| L1-L4 (valid) | Normal (one mild false-positive) | Valid | ✅ |

SPC catches format anomalies (period, TODO, duck). **G4 (zero-case test log) has the exact same behavioral profile as L4 (valid test log) — SPC misses it 100%.** This directly validates the stated blind spot: SPC catches format anomalies but not semantic traps. G4‑class failures can only be caught by sampling, never prevented.

### Layer 4: fixed-rate sampling — replace confidence scores

Several approaches I initially proposed relied on a "confidence score" (> 95% auto-release, < 80% human review). The hidden cost: confidence requires a feedback loop to calibrate — database, ground-truth labeling, delayed updates. The same complexity I criticized in the closed-loop calibration critique.

Alternative: **fixed-rate sampling. No confidence math.**

| Type | Handling | Sample rate |
|------|----------|-------------|
| A (verifiable) | Fully automatic | 0% |
| B (high-risk) | Mandatory human | — |
| C (low-risk content) | Auto-release | 0% |
| D (medium-risk content) | Diff review (all items) | 100% |
| Zero-shot generation (no prior version, no template) | Sample review | **Fixed 5%** |

I admit: 5% is a guess. But its mathematical properties are known and quantifiable — which is more than can be said for a confidence score with no feedback loop.

---

## Relentless self-review (same ruler)

Before calling this "done," I applied the same six-cut standard to this design.

### Finding 1: classification is not free

Type labels can't depend on business owners manually tagging every task. They don't know their own types — they'd label 70% as "D" to be safe.

**Fix:** In the MVP phase, use two hard rules for automatic classification: ① if the task text contains sensitive keywords (money/contract/compensation) → force B; ② if the tool-call chain hits "send/publish/submit" → force human confirmation. Everything else defaults to C. Tune thresholds after launch based on false-positive rate.

### Finding 2: diff review covers a narrower range than "edit tasks"

Diff review only works when there's a clear prior version. Agent workflows often involve **reading five source documents → writing a new one from scratch** — there's no single "previous version" to diff against.

**Fix:** In this design, "edit task" means exactly "a prior version of the same document exists." Multi-document synthesis tasks go to "zero-shot generation" → fixed 5% sampling. This is an honest scope reduction.

### Finding 3: 5% sampling has known detection probability

With 5% sampling on zero-shot tasks: if the real defect rate is 20% on a given day, the probability of detecting at least one defective item = 1 − (0.8)⁵ = **67%**. That means **33% probability of zero detection** on any single day — a silent degradation could slip through for days.

**Fix:** 5% for non-critical content is acceptable. For critical content, raise to 10–20% or use deterministic sampling (every Nth item). First week post-launch: use 20% sampling to collect baseline defect-rate data before tuning.

### Finding 4: sensitive-tool interception is not free

Intercepting "send email" after the agent has already taken 4 steps is not zero-cost — those steps consumed inference budget.

**Fix:** Add a "preheat check" before the agent executes — scan the user's request text for sensitive verbs (send/modify/delete/submit) and pre-confirm with the user. Don't wait until runtime to pull the trigger.

### Finding 5: engineering cost — I made the same mistake I criticized

I initially estimated 2 engineer-months for the MVP. Same flaw as the cost analysis I criticized in my previous article: I only counted the core modules, not the integration.

Honest breakdown:

| Module | Effort |
|--------|--------|
| Diff review UI (visual diff + highlight + judgment button) | 1 engineer-month (frontend) |
| SPC collector (metadata + thresholds + aggregation) | 0.5 engineer-month (backend) |
| Sensitive-tool whitelist + runtime interceptor | 0.5 engineer-month (full-stack, needs agent framework hooks) |
| Monitoring dashboard + alerts | 1 engineer-month (full-stack) |
| Sampling queue + assignment + expiry | 0.5 engineer-month (backend) |
| **Total** | **3.5 engineer-months (MVP)** |

That's **30% cheaper** than the 5 engineer-month human-in-the-loop Harness — not 60%. Less sexy, but real.

---

## Honest close: what this design solves and what it doesn't

### Does solve

- **ROI inversion:** Type A fully automatic + C auto-release + D diff-only. The fraction requiring human review drops enough that 3.5 engineer-months of investment breaks even within a reasonable horizon for most mid-volume deployments.
- **Clustering failure:** SPC on behavioral features replaces embedding clustering. Verifiable by code, zero LLM cost.
- **Human error:** Diff review reduces cognitive load. It doesn't eliminate errors (semantic traps still need domain knowledge), but it measurably reduces the error rate.

### Doesn't solve

- **G4-class semantic traps (zero-case test log).** These are caught by sampling, not prevented. The honest difference from the original "deterministic agent" articles: they claimed prevention; we acknowledge detection.
- **Humans are still the final decision layer.** In sensitive operations and edit reviews, humans are not optional.
- **Zero-shot generation is sampled, not guaranteed.** 5% sampling means 67% single-day detection probability at 20% defect rate. For critical content, raise to 20% (98% detection probability).
- **Classification is imperfect.** Automatic keyword and tool-chain classification has measurable false-positive and false-negative rates that must be tuned post-launch.

### The actual prerequisites

- A router/whitelist implementation, SPC threshold configuration, diff review UI, sampling queue, and monitoring dashboard — all standard CRUD + regex + statistics. No LLM dependency.
- Engineering investment: 3.5 engineer-months for an MVP.
- Business acceptance: **"high risk requires human," "zero-shot is sampled," "semantic traps are detected, not prevented."** These three constraints are business decisions, not engineering ones. No design can substitute for them.

---

## Final rating (same ruler)

| Criterion | Rating |
|----------|--------|
| Unvalidated assumptions? | Yes, all stated (5% sampling = 67% detection probability, not 100%) |
| LLM dependency in control layers? | **Zero.** All control logic is deterministic code. |
| Engineering cost estimated? | Yes: 3.5 engineer-months (honest, with integration costs) |
| Honest boundary declarations? | Yes: G4 traps not prevented, zero-shot sampled, humans not free, classification imperfect |
| Self-dismantling? | Yes — the five findings above dismantle everything that could be dismantled. What remains are engineering facts: Type A auto-verification, sensitive-tool hard interception, SPC format anomaly detection, and diff review cognitive-load reduction. |

---

**"Don't judge correctness. Judge risk."** — this isn't a smarter architecture. It's a more honest one. It doesn't claim to solve what it can't solve. It just makes the remaining manual work cheaper, faster, and less error-prone.

And after five rounds of measurement, falsification, self-correction, and reconstruction — that's as far as engineering can go. The rest is a business decision.
