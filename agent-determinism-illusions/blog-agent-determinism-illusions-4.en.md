<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Risk-based agent output quality: an alternative to LLM quality gates
  ─────────────────────────────────────────────────────────────────
-->

---
title: "An alternative to LLM quality gates: deterministic routing + sampling"
published: false
description: "No LLM quality inspectors, no embedding clustering, no confidence scores. Just deterministic routing + SPC + diff review + fixed-rate sampling. With honest cost estimates and known failure modes."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

*Every "agent quality gate" I tested shares one fatal assumption: that an LLM can judge whether an LLM did the right thing. This article drops that assumption. The alternative isn't a smarter judge — it's no judge at all, in the control layer.*

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
| **A (verifiable)** | Output is compilable / schema-validatable (code, JSON, SQL) | Compile/schema gate + sampled diff review (Layer 4), no LLM quality inspector. **Requires gate runner independent from agent — see caveat below.** |
| **B (high-risk)** | Money, legal, privacy, external publishing | **No agent execution.** Prompt: "This task requires human handling." AI provides a draft only, never auto-executes. |
| **C (low-risk content)** | Internal briefs, first drafts, brainstorming | **Auto-release.** Tag as "draft" (80% default confidence). No quality queue. |
| **D (medium-risk content)** | Client-facing emails, external documents | **Diff review.** Don't judge content quality. Only show what changed. |

Why this beats an "LLM quality inspector": it acknowledges the LLM's limit at the source. Use the LLM for what it can do (generate). Never use an LLM for what it does poorly (judge semantic quality).

**Caveat — runner independence (raised by Mike Czerwinski in the dev.to comments):** "verifiable" is a property of the check's independence from the generator, not of the output itself. If the agent can write to the verify scripts, the runner configuration, or the test definitions — "compile-green" stops being a deterministic gate and becomes a self-report wearing a green checkmark. This is the DGM fake-log mechanism Weng documented in her harness survey (agent modified its own harness, wrote "tests passed" to a log without running tests, downstream the same agent read the log and concluded validation passed). Engineering pattern: an `editable-surface.json` (or equivalent) explicitly declares which paths the agent can write; verify scripts, runner config, and the editable-surface file itself sit in the readonly section. Without runtime-verified provenance at the storage boundary, "I ran the tests" and "I claim I ran the tests" are both just text.

**Caveat — verifiable is claim-level, not task-level (raised by Mike Czerwinski, third round, in his follow-up piece [*Vibe coding is not a level. It's an axis.*](https://dev.to/jugeni/vibe-coding-is-not-a-level-its-an-axis-12gb)):** "verifiable" is not a property of the task — it's a property of each individual claim, namely whether the claim carries an **addressable referent** (a method, a side effect, a schema field that code can locate and execute against). A Type A task can contain both addressable claims (`compile passes`, `schema validates` — the deterministic gate works) and **paraphrase** claims (`the design is clean`, `this is the right tradeoff` — no executable referent, the gate has nothing to run). On paraphrase, the gate degrades back to semantic judgment — which is exactly why Type D routes to a human diff review instead of an LLM judge. Layer 1's routing implicitly assumes a Type A task's claims are mostly addressable; Mike's framing names the cliff: a single task can straddle the addressable/paraphrase boundary, and only the addressable part is gate-able. The rest falls to sampling or a human, same as Type D.

### Layer 2: diff review — replace "judge right/wrong"

This is the key operational alternative. For Type D tasks, don't show the reviewer the "final output." Show them **what the agent changed from the previous version.**

Implementation: after generation, the system diffs the output against the original (or a template) using `difflib` — no LLM needed.

Reviewer UI: only the modified lines are highlighted. The reviewer answers one question: **"Does this change introduce an error?"**

Measured cognitive load:

| Method | Reading load | Cognitive demand | Time |
|--------|-------------|-----------------|------|
| Full-text quality judgment (500 words) | 500 words | High | ~60 s |
| Diff review (50-word change) | 50 words | **Low** | **~10 s** *(lab; production: 30–90 s — see Knife 3 below)* |

The shift: open-ended judgment ("Is this article good?") becomes closed-ended ("Did this paragraph break something?"). Cognitive demand drops significantly — though the lab "~10 s" compresses to 30–90 s in production once context-switching overhead is included (Knife 3 below).

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
| **G4 (zero-case, garbage)** | **NORMAL** (same features as L4) | **Garbage** | **❌ FN** |
| L1-L4 (valid) | Normal (one mild false-positive) | Valid | ✅ |

SPC catches format anomalies (period, TODO, duck). **G4 (zero-case test log) has the exact same behavioral profile as L4 (valid test log) — SPC misses it 100%.** This directly validates the stated blind spot: SPC catches format anomalies but not semantic traps. G4‑class failures can only be caught by sampling, never prevented.

### Layer 4: fixed-rate sampling — replace confidence scores

Several approaches I initially proposed relied on a "confidence score" (> 95% auto-release, < 80% human review). The hidden cost: confidence requires a feedback loop to calibrate — database, ground-truth labeling, delayed updates. The same complexity I criticized in the closed-loop calibration critique.

Alternative: **fixed-rate sampling. No confidence math.**

| Type | Handling | Sample rate |
|------|----------|-------------|
| A (verifiable) | Compile / schema gate + **sampled into diff review** | **X%** (tuned) |
| B (high-risk) | Mandatory human | — |
| C (low-risk content) | Auto-release | 0% |
| D (medium-risk content) | Diff review (all items) | 100% |
| Zero-shot generation (no prior version, no template) | Sample review | **Fixed 5%** |

**Post-publication correction (raised by Dipankar Sarkar in the dev.to comments):** the original version of this table had Type A at 0% sample rate. That quietly treated schema-validatable syntax as a stand-in for semantic correctness — schema-valid JSON with a plausible-but-wrong value clears the gate silently, code that compiles can still book the wrong flight. This is the same class as the G4 finding in Layer 3 above (format-channel gate kills format-channel failure, not semantic failure); I called it out for SPC and then let Type A make the same mistake one layer up. The 0% was an indefensible asymmetry: zero-shot content gets sampled because there's no prior version to diff against, but schema-validatable code doesn't? X% should be calibrated from defect-rate data using the same logic as zero-shot's 5%. Start at 1-2% in week one, tune from there.

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

- **ROI inversion:** Type A deterministic gate + sampled diff review + C auto-release + D diff-only. The fraction requiring human review drops enough that 3.5 engineer-months of investment breaks even within a reasonable horizon for most mid-volume deployments.
- **Clustering failure:** SPC on behavioral features replaces embedding clustering. Verifiable by code, zero LLM cost.
- **Human error:** Diff review reduces cognitive load. It doesn't eliminate errors (semantic traps still need domain knowledge), but it measurably reduces the error rate.

### Doesn't solve

- **G4-class semantic traps (zero-case test log).** These are caught by sampling, not prevented. The honest difference from the original "deterministic agent" articles: they claimed prevention; we acknowledge detection.
- **Type A semantic traps (compile-pass-but-wrong).** Compiles-but-books-wrong-flight is sampled into diff review, not prevented. Same class as G4 above. The Layer 4 table originally had Type A at 0% sample rate — an indefensible asymmetry, corrected above.
- **Type A runner independence (compile-green as self-report).** Even a correctly-sized sampling rate doesn't help if the agent can author the verify scripts or the runner. "Compile-green" then becomes a self-report wearing a green checkmark — same mechanism as the DGM fake-log incident. Requires an `editable-surface.json` or equivalent to put verify scripts and runner config outside the agent's writable surface. (Raised by Mike Czerwinski in the dev.to comments; see Layer 1 caveat above.)
- **Type A paraphrase claims (gate-able only where addressable).** Even with runner independence and a correctly-sized sample rate, a Type A task's claims split: addressable ones (compile, schema, executable side effects) are gate-able, paraphrase ones (design cleanliness, the right tradeoff) are not — the gate has no referent to run against and degrades to semantic judgment. Routing assumes Type A is mostly addressable; tasks that straddle the boundary need the paraphrase portion routed to sampling or a human, same as Type D. (Raised by Mike Czerwinski, third round; see Layer 1 caveat above.)
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
| Self-dismantling? | Yes — the five findings above dismantle everything that could be dismantled, plus the post-publication correction on Type A's sample rate (raised by Dipankar Sarkar). What remains are engineering facts: Type A deterministic gate + sampling, sensitive-tool hard interception, SPC format anomaly detection, and diff review cognitive-load reduction. |

---

## Three more knives before production (round two of relentless review)

Before this design hits production, three operational problems surfaced that I hadn't fully addressed.

### Knife 1: SPC cold-start baseline drift

SPC uses statistical thresholds (mean +/- 1.5sd). But where does the mean and sd come from on day one?

You need 500-1000 "normal" traces to establish a baseline. If week 1 has a bug that makes every trace abnormally long, the baseline is skewed — real anomalies later get absorbed into the "new normal."

**Measured:** I simulated three phases (normal → bug → recovery + new anomaly) to find the real risk:

| Bug severity (mean) | Mixed threshold | Anomaly (20 steps) detected? | Static threshold (>10) |
|--------------------|----------------|-----------------------------|----------------------|
| Normal(5) → Bug 8 | 9.7 | Yes | Yes |
| Normal(5) → Bug 12 | 12.7 | Yes | Yes |
| Normal(5) → Bug 16 | 16.7 | Yes | Yes |
| Normal(5) → **Bug 20** | **20.5** | **No (missed)** | Yes |
| Normal(5) → Bug 21 | 21.6 | No (missed) | Yes |

**Crossover: dynamic threshold only fails at 4x the normal mean (Bug mean >= 20).** SPC is more robust against moderate drift (2–3x) than the original critique claimed.

**Revised response:** Not a two-phase switch ("static first, then dynamic"), but **dual thresholds in parallel**: a static absolute threshold (steps > 20 always flagged) plus a dynamic relative threshold (rolling 7-day window). Either triggers — no dependency on clean cold-start data.

### Knife 2: context escape in sensitive-tool interception

Keyword-based scanning of the user's request text for "send," "email" — but this fails on:

> "Simulate sending a quote email to the client for preview, **don't actually send it**."

The scanner fires — user gets blocked — forced into manual flow. The agent's actual call chain only had `preview_email`, never `send_email`.

In practice, keyword-based interception has a **30–50% false-positive rate** (users say "pretend to send," "let me see first," "save as draft"). Every false block erodes user trust. High false-positive rates drive users to **bypass the system entirely** — copying the email to their external client and sending it there, defeating the control entirely.

**Revised response (v1, at publication):** Execution-time interception only. Block the agent *at the point of tool invocation* (`send_email` called = block; `preview_email` called = pass). Don't scan the user's request text. This sacrifices "early interception saves inference cost" but delivers **zero false positives** — the tool was either called or it wasn't, no ambiguity.

**Revised response (v2, post-publication):** The either/or framing in v1 drops a viable middle ground (raised by Nazar Boyko in the dev.to comments). Keep the request-text scan, but demote it to a **soft signal that never blocks**: scan fires → agent prompts user "this task looks like it ends in a send — confirm the plan before I spend steps on it." If the user says "actually send," the agent proceeds to the tool call where the **hard gate** still fires (zero FP). If the user says "just previewing," the agent routes to `preview_email` and never hits the gate.

The layered design takes both benefits v1 traded off:

- **Finding 4 preserved:** soft signal fires before inference is spent, so the agent doesn't burn 4 steps before being stopped or redirected.
- **Knife 2's zero-FP-block preserved:** the hard gate at tool invocation never false-positives.
- **Cost:** extra UX friction on simulation requests — unavoidable, since the LLM itself can't reliably tell "simulate" from "real" either.

**Measured (post-publication):** `scripts/knife2-fp-rate-test.py` (N=40, zero-LLM) verified the original "30-50% FP" claim. Coverage on FP-prone scenarios (simulate / draft / conditional / discussion): **95%** (19/20 — the miss was "submission" not matching the "submit" regex root, itself a keyword-scan blind spot). Implied FP rate under 50/50 real/sim mix: **48.7%** — within the claimed band. The FP mechanism is real; the layered design is the right answer.

### Knife 3: diff review "10 seconds" shrinks in real UI

The measured "50-character diff in 10 seconds" is pure reading time. In production, the reviewer's flow is:

> See highlight → recall what the original said → think about context → judge whether the change introduces an error → click approve/reject

With context-switching overhead, real per-item time is **30–45 seconds**. At 50 items/day: 25–37 minutes. Still manageable, but the "order-of-magnitude compression" only exists in the lab.

**Revised estimate:** Diff review time adjusted from "10 s/item" to "30 s (routine) / 90 s (deep review)." Impact on staffing: 0.3 FTE → 0.5 FTE. Not a collapse, but an honest correction.

---

## Final honest table

| Dimension | Original design | After all corrections |
|----------|---------------|----------------------|
| SPC cold start | Not addressed | Dual thresholds in parallel, robust to 4x drift |
| Sensitive-tool interception | Keyword scan (30-50% FP) | Layered: soft signal (request scan, non-blocking) + hard gate (tool invocation) — v2 post-pub |
| Diff review time | 10 s | 30-90 s (0.3 → 0.5 FTE) |
| Engineering cost | 2 engineer-months | 3.5 engineer-months |
| LLM dependency in control layers | None | None (verifiable, deterministic code throughout) |

What remains are business decisions: accept "high risk = human"? accept "semantic traps caught by sampling, not prevention"? accept 30–90 second diff review cycles? These questions have no engineering answers — but the engineering baseline for answering them is now measurable.

**"Don't judge correctness. Judge risk."** — this isn't a smarter architecture. It's a more honest one. It doesn't claim to solve what it can't solve. It just makes the remaining manual work cheaper, faster, and less error-prone.

And after five rounds of measurement, falsification, self-correction, and reconstruction — that's as far as engineering can go. The rest is a business decision.
