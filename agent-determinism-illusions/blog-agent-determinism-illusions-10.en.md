<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Five commenters redesigned my LLM verification pipeline
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Five Comments That Redesigned My LLM Verification Pipeline"
published: false
description: "After six experiments produced no clean answer, five dev.to commenters reshaped my entire verification pipeline. Each insight paired with new experimental validation."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

Six experiments, 260+ API calls, 15 scripts. The series concluded with an honest answer: **there's no clean solution** to LLM output verification.

But after publishing, commenters saw something I didn't — not gaps in the data, but an architecture I'd failed to draw from my own results. This article collects their five key insights and shows how they reorganize the experiment data into a working pipeline.

Each insight is paired with experimental validation from a new prototype (Experiment F, 38 scenarios across two test sets).

---

## 1. Alexey Spinov & Manuel Bruña: Layer Before You Judge

[Alexey's comment](https://dev.to/alex_spinov/comment/3ai7e) identified the most fundamental design flaw in my experiments:

> "G4 ('0 passed, no tests collected') is a fact that can be verified with code in one shot. There is no need to wait for an LLM."

[Manuel](https://dev.to/tecnomanu/comment/3aj7c) added the constructive direction:

> "Run deterministic checks first. Then let the LLM handle only the truly ambiguous residual."

I went back to my own 8-scenario P1 test set. Four garbage scenarios (G1-G4) and four legitimate ones (L1-L4):

| ID | Output | Type | Could code catch it? |
|----|--------|------|---------------------|
| G1 | "I am a little duck, quack quack" | nonsense | ✅ very short + no keywords |
| G2 | "。" (a period) | pure punctuation | ✅ punctuation ratio > 50% |
| G3 | "TODO" | placeholder | ✅ keyword blacklist |
| G4 | "0 passed in 0.00s (no tests collected)" | zero-test pass | ✅ regex `0 passed` + `no tests` |

**All four garbage scenarios can be caught deterministically, at zero cost, before any LLM call.**

Why didn't I do this? Because I defaulted to treating "verification" as "ask the LLM." My experiment design was: Phase Gate (form check) → LLM (content check). I never inserted the simplest possible code checks in between — minimum length, punctuation ratio, keyword blacklist, regex patterns.

This omission rippled through the entire series:

- **P1's 75% false negative rate** — the LLM was asked to judge everything, including garbage it never should have seen
- **P3's "majority voting doesn't fix systematic bias"** — on legitimate scenarios (L1-L3), the LLM's judgment is genuinely ambiguous and needs multi-perspective voting. For garbage (G1-G4), there was never any ambiguity to begin with
- **P4's "calibration effect disappears at larger test set"** — many of the new edge scenarios were "passes format checks, fails content quality" — exactly what Layer 0/1 handles

### The architecture they helped me draw

```
         ┌─────────────────┐
 input → │  Layer 0         │  shape/existence
         │  (code)          │  empty? punctuation? placeholder? zero tests?
         └──────┬──────────┘
                │ pass         ┌─────────────────┐
                ├─────────────→│  Layer 1          │  contract match
                │              │  (code)          │  minLen, keywords, blacklist
                │              └──────┬──────────┘
                │ pass               │ pass
                │                    ├─────────────→┌─────────────────┐
                │                    │              │  Layer 2          │  semantic sufficiency
                │                    │              │  (LLM, thin)     │  residual only
                │                    │              └──────┬──────────┘
                │                    │  divergence         │ unanimous
                │                    ├──────────────────→┌─────────────────┐
                │                    │                   │  Layer 3          │  human review
                │                    │                   └─────────────────┘
                ↓                    ↓
             REJECT              REJECT              AUTO-PASS
```

Each layer can early-exit. If Layer 0 catches it, the LLM never sees it.

### Experiment F validation

I implemented this pipeline as a Python prototype and ran it on both the P1 (8-scenario) and P4 (30-sample) test sets. The results:

**P1 test set:**

| Metric | Original P1 (LLM only) | Layered (Experiment F) |
|--------|----------------------|----------------------|
| LLM calls needed | 8 (100%) | **4 (50%)** |
| Garbage caught by L0/L1 | 0 | **4/4 (100%)** |
| False positives | 0 | 0 |
| False negatives | 3 (75%) | 0 |

**P4 test set:**

| Category | Samples | Caught by L0 | Caught by L1 | Reaches L2 | Zero-cost catch rate |
|----------|---------|-------------|-------------|-----------|---------------------|
| correct | 10 | 0 | 0 | 10 | 0% (should all go to LLM) |
| garbage | 10 | **3** | **5** | 2 | **80%** |
| edge | 10 | 0 | 2 | 8 | 20% |

**Overall: LLM calls reduced 33% (30→20). Zero false positives from deterministic layers.**

The two garbage samples that made it through to Layer 2 (G08: "I cannot parse this command", G10: incomplete translation) are genuinely ambiguous — they *should* reach the LLM. That's correct behavior, not a leak.

---

## 2. Alexey Spinov: Cost Asymmetry

[Alexey's second comment](https://dev.to/alex_spinov/comment/3ai7e) pointed out a measurement problem:

> "A false accept ships once. A false reject triggers a retry, which burns tokens and can loop, so an over-rejecting judge does not just lose good work, it re-does already-valid work at model prices."

All experiments P1-P4 used symmetric precision-recall metrics. F1 gives FP and FN equal weight. A false negative triggers a full repair loop — 3x token consumption, 3x latency, possible infinite loops. A false positive is one-shot contamination.

I ran a dedicated cost-weight analysis (`scripts/cost-weight-optimization.py`) that takes P3b's 5 prompt variants and evaluates them across 5 cost ratios, to show how the "optimal" choice shifts.

### 5 prompts × 5 cost ratios

| Prompt | FP | FN | F1 | WCost(1:1) | WCost(3:1) | WCost(5:1) | WCost(10:1) |
|--------|----|----|----|-----------|-----------|-----------|------------|
| v1 extreme strict | 0 | 4 | 0 | 4 | **12** | **20** | **40** |
| v2 strict (P1 baseline) | 0 | 3 | 0 | 3 | **9** | **15** | **30** |
| v3 balanced | 0 | 0 | 100 | **0** | **0** | **0** | **0** |
| v4 lenient | 0 | 0 | 100 | **0** | **0** | **0** | **0** |
| v5 extreme lenient | 1 | 0 | 86 | **1** | **1** | **1** | **1** |

Under symmetric F1, v3 (100) and v5 (86) are far apart. Under weighted cost at 3:1, v5 (cost=1) beats v2 (cost=9) — v5 let one piece of garbage through, but because it never rejected valid work, its total cost is lower.

### What the combined data shows

| Strategy | WCost(1:1) | WCost(3:1) | WCost(10:1) | LLM calls |
|----------|-----------|-----------|------------|-----------|
| P3b v2 (unlayered) | 3 | **9** | **30** | 24 |
| P3b v3 (unlayered) | 0 | **0** | **0** | 24 |
| P1 layered + v3 | 0 | **0** | **0** | **12 (-50%)** |
| P4 unlayered (estimate) | 4 | **8** | **22** | 90 |
| P4 layered (Experiment F) | 1 | **3** | **10** | **60 (-33%)** |

Layering doesn't change that v3's cost is 0 (it already has FP=FN=0 on the 8-scenario set). But it changes two things that the raw cost number doesn't capture:

1. **4/4 garbage caught by L0/L1 at zero cost** — even if the LLM misjudges every remaining sample, the absolute cost is halved
2. **33-50% fewer LLM calls** — not by changing the model, by giving it fewer samples to judge

For v2 (the strict prompt from P1), the effect is more instructive. v2 has FN=3. Layering saves 4 LLM calls but doesn't reduce FN:
- **Layering + switching prompt** (v2→v3): FN drops from 3 to 0
- **Layering only**: saves tokens, but FN stays at 3

This exposes the boundary of layering: it reduces the LLM's *workload*, not its *bias*. To reduce FN, you need prompt calibration alongside layering.

### Sensitivity scan: when does the optimum shift?

I ran a continuous scan from costFN:costFP = 1:1 to 15:1. v3 dominates at every ratio on the P3b set — because it has FP=FN=0, any cost weight gives it zero cost. This reflects the 8-scenario data limitation (P4 already showed this perfection doesn't generalize).

The more informative finding is the cost asymmetry itself: at 1:1, F1 says v3 is 16% better than v5. At 3:1, weighted cost says they're equivalent. At 10:1, any prompt with FN>0 collapses — the only safe choice is to drive FN to zero through calibration + layering + cost-weighted selection.

### Five findings

1. **Symmetric metrics hide the real ranking.** F1 says v3 >> v5. Weighted cost at 3:1 says they're close.

2. **The "optimal" found at 1:1 is not optimal at 3:1.** Selecting a prompt by F1 picks balance, not thrift.

3. **v3/v4 dominate all ratios on the 8-scenario set** — because the set is small and v3 happened to score zero errors on it. P4 already showed this advantage disappears at 30 samples.

4. **Layering doesn't reduce bias, but it shrinks the bias's blast radius.** After L0/L1 filters the garbage, any LLM mistake costs half as much.

5. **Above cost ratio 5:1, any strategy with FN>0 is unsustainable.** The only reliable approach is FN→0: calibrated prompt + layered fallback + cost-weighted selection. When choosing a prompt, look at the absolute FN count, not F1.

---

## 3. Dipankar Sarkar: Divergence Is the Signal, Not Noise

P3's multi-perspective voting experiment found a pattern I described but misinterpreted. My original framing:

> "In split-vote scenarios, the majority was always wrong. Majority voting can't correct for systematic bias."

[Dipankar](https://dev.to/dipankar_sarkar/comment/3aiii) flipped the interpretation:

> "Vote disagreement itself is the most valuable signal. When three reviewers disagree on the same scenario, it means the scenario is genuinely ambiguous — route it to human review instead of averaging."

Re-examining P3's data through this lens:

| Scenario | Strict | Balanced | Lenient | Majority | Correct? |
|----------|--------|----------|---------|----------|----------|
| L1 (excerpt) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L2 (summary) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L3 (one chapter) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| G3 (TODO) | REJ | REJ | PASS | REJ (2-1) | ✓ |

Majority voting was wrong on 3 of 4 split scenarios. But if I use divergence as the control signal:

- **Unanimous (4/8):** auto-execute → 100% accuracy
- **Split (4/8):** escalate to human → no false majority decisions

Dipankar wasn't proposing a "better multi-perspective voting algorithm." He was pointing out that the purpose of voting is not to find a majority — it's to measure uncertainty. I missed this distinction when writing P3.

Operational rule (now implemented in forge-verify's layer 3):

```
if max(PASS, REJECT) / N < threshold (default 0.8)
    → mark as UNCLEAR, write to human review queue
    → do NOT majority-vote
```

---

## 4. Mike Czerwinski & xm_dev_2026: Fixed Sampling Misses Long Tails

[Mike Czerwinski](https://dev.to/jugeni/comment/3ahff) named the architectural limit I'd been circling without stating:

> "Stacking more symbolic checks on top doesn't grow that reach, it just adds more places for the same blind spot to hide... 'Ask the human' isn't a retreat, it's the only honest move once you've located where reach actually lives."

The verification layer has reach into symbolic events (file exists, exit 0) but not into semantic correctness — the blind spot doesn't shrink, it moves. P4 reported 83.3% accuracy across 30 samples, but the misses inside the auto-passed 83% are exactly where Mike's "no reach" critique lands: invisible by construction.

[xm_dev_2026](https://dev.to/xm_dev_2026/comment/3ajod) showed where this bites hardest in production — fixed-percentage audits:

> "Fixed-percentage audits feel 'fair' but they miss exactly the kind of long-tail directional failures you're describing. The model is most confident when it's wrong in a structured way."

My original mitigation had been "5-10% random audit." This isn't a parameter-tuning problem — it's a design principle problem. Fixed sampling assumes errors are uniformly distributed. Real production errors are long-tailed.

I ran a simulation (`scripts/adaptive-sampling-sim.py`) that generates synthetic verification streams with controlled error distributions, then compares fixed-rate sampling against adaptive sampling (200-trial averages).

The adaptive formula:

```
audit_rate = base_rate × risk_weight / confidence^1.5
```

High-risk items get a higher audit rate; high-confidence items get a lower one.

### Results

**Uniform (errors spread evenly):**

| Strategy | Audit rate | Catch rate | Efficiency |
|----------|-----------|-----------|------------|
| Fixed 10% | 10.0% | 12% | 0.111 |
| Adaptive(combined) | 7.8% | 18% | **0.247** |

No significant gap — without a long-tail structure, random sampling is adequate.

**Long-tail burst (90% of errors in 10% of the stream — xm_dev_2026's scenario):**

| Strategy | Audit rate | **Long-tail catch rate** | Efficiency |
|----------|-----------|------------------------|------------|
| Fixed 5% | 5.0% | **5%** | 0.120 |
| Fixed 10% | 10.0% | **10%** | 0.119 |
| Fixed 20% | 20.0% | **20%** | 0.118 |
| Adaptive(confidence) | 8.7% | **24%** | 0.321 |
| Adaptive(risk) | 6.0% | **15%** | 0.264 |
| **Adaptive(combined)** | **12.8%** | **65%** | **0.543** |

At the same audit budget as Fixed 10%, adaptive catches **65% of long-tail errors** — a 6x improvement.

**Distribution drift (Mike's "input shift erases visibility"):**

| Strategy | Audit rate | Catch rate |
|----------|-----------|------------|
| Fixed 10% | 10.0% (flat) | 11% (constant) |
| Adaptive(combined) | 21.5% (ramps up) | **48%** |

Fixed sampling's catch rate stays flat as the error rate drifts upward. Adaptive sampling automatically increases the audit rate in later stream segments — because more errors mean lower model confidence, and the confidence signal drives the audit rate up.

**Mixed (uniform noise + periodic long-tail bursts — most realistic, 200-trial average):**

| Strategy | Audit rate | **Long-tail catch rate** | Efficiency |
|----------|-----------|------------------------|------------|
| Fixed 5% | 5.0% | **5%** | 0.095 |
| **Fixed 10%** | **10.0%** | **10%** | 0.094 |
| Fixed 20% | 20.0% | **20%** | 0.094 |
| Adaptive(confidence) | 7.8% | **19%** | 0.230 |
| Adaptive(risk) | 6.0% | **15%** | 0.148 |
| **Adaptive(combined)** | **10.1%** | **56%** | **0.324** |

Key row: **Fixed 10% and Adaptive(combined) have nearly identical audit rates (10.0% vs 10.1%), but long-tail catch rate goes from 10% to 56% — a 5.6x improvement at the same cost.**

### Why it works (cross-validated against my existing experiments)

P2's consistency test showed that binary LLM judgments on identical input are highly stable (N=10, 0 divergence). So the "confidence" signal doesn't come from within-model variance — it comes from P3's multi-perspective divergence:

- Unanimous → high confidence → low audit rate (<5%)
- Split (2-1) → low confidence → high audit rate (>30%)

P2 and P3 were independent experiments, but their outputs combine into a coherent adaptive sampling strategy. This isn't parameter tweaking — it's a design principle difference. Fixed sampling pursues "uniform global coverage." Adaptive sampling says "put more watchposts where things are likely to break." The latter uses audit budget **3-4x more efficiently**.

---

## 5. Manuel Bruña & Alexey Spinov: Evidence, Not Narrative

Throughout P1-P4, all LLM review experiments output free-text "reason" fields. [Manuel](https://dev.to/tecnomanu/comment/3aj7c) identified the structural problem and the fix in one sentence:

> "Treat the LLM inspector as an evidence-producing reviewer, not the final binary gate. Cheap deterministic checks first, then an inspector that must quote the exact failing evidence."

[Alexey](https://dev.to/alex_spinov/comment/3ai7e) sharpened the architectural split:

> "Deterministic assertions own everything mechanically checkable (tests collected greater than zero, schema conformance, non-emptiness thresholds), and the LLM only judges the irreducibly fuzzy residue."

My experiments had this blind spot:

```
P1, scenario L1 (model REJECT):
"The research brief should cover the core mechanisms of the loop engine,
but the file only has a short excerpt..."

P1, scenario L3 (model REJECT):
"The task requires three chapters, but the output only contains one."
```

These are impression judgments. You can't code-verify whether "a short excerpt" is enough.

The proposed output format:

```
Assertion 1: "File line count = 3, expected > 20"        → code-verifiable
Assertion 2: "File contains 1/3 required keywords"        → code-verifiable
Assertion 3: "Content structure completeness < threshold" → semantic judgment
```

Assertions 1-2 are deterministic — code can confirm whether the model's claim is true. Assertion 3 is the actual semantic judgment, preserve for Layer 2.

This creates a cascade: when a deterministic assertion is code-verified and found inconsistent with the actual file → explicit hallucination signal → mark as UNCLEAR → escalate. No human judgment required in the loop — the code flow triggers automatically.

---

## Synthesis: What the Five Comments Build Together

| Comment | My blind spot | Replacement |
|---------|-------------|-------------|
| Alexey + Manuel | Fed everything to the same LLM reviewer | L0/L1 filter deterministically; LLM handles residual |
| Alexey (2nd) | Symmetric FP/FN metrics | Weighted cost (FN×3) shifts optimal operating point |
| Dipankar | Split votes averaged by majority | Divergence = UNCLEAR → human, no majority |
| Mike + xm_dev_2026 | Fixed 5-10% audit rate | Adaptive sampling by confidence × risk |
| Manuel + Alexey (2nd) | Narrative "reason" field | Evidence-quoted reviewer + deterministic assertions |

Combined, these form a complete verification system: L0/L1 handle deterministic filtering (Alexey+Manuel), L2 LLM quotes exact failing evidence (Manuel+Alexey), divergence escalates to L3 human review (Dipankar), audit rate adapts by confidence (Mike+xm_dev_2026), and system thresholds are selected by weighted cost (Alexey 2nd).

This article doesn't claim to have solved anything. It just puts the design decisions I made and the corrections the community provided side by side.

### Implementation

The full pipeline has been implemented in forge-verify's `content-verify.mjs`. File-by-file results now show which layer stopped each sample:

```
  📄 src/api/register.ts
  ❌ REJECT @ L3: REJECT (3/3 votes)
    └ L0: PASS
    └ L1: UNCLEAR — contains blacklisted keyword: FIXME
    └ L2: [REJECT/REJECT/REJECT] PASS=0 REJ=3
    └ L3: REJECT — REJECT (3/3 votes)
```

Layer 0/1 checks are zero-cost code. Layer 2 only runs on the residual. Layer 3 divergence detection prevents false majority decisions.

---

## A Side Note: An Apology Experiment

An earlier version of this article had a long appendix — an apology for a fabricated claim I'd made in a dev.to comment about "directional failure" experiments. The apology included the actual experiment I should have run (20 scenarios × 3 model tiers × 600 calls).

That appendix grew into a real finding in its own right, though the framing has since been revised after re-checking the data: **DS4 ("no change needed") defeats weak text-channel judges (qwen3:0.5b 100% miss, gemma3:latest 100%), but strong models partially recover (deepseek-v4-flash 13% miss, 53% PARSE_FAIL/hesitation).** The directional failure is real but uneven — strongest empirical case for L0/L1 layering on weak models, with the strong-model residual still justifying deterministic checks.

That deserves its own article now.

**→ [I Fabricated a Claim About LLM Judges. Then I Ran the Apology Experiment.](blog-fabricated-claim-apology.en.md)**

---

**Series navigation (Agent Determinism Illusions):**
1. *I tested the 'deterministic agent loop' claims with four experiments — they all failed, including my own fix.*
2. *I tested 3 models as AI agent quality inspectors — the stronger the model, the more valid work it rejects.*
3. *I designed a Harness to fix my agent's quality problem — then found 6 flaws in my own design.*
4. *Five commenters redesigned my LLM verification pipeline (this article).*
- *Side note: [I Fabricated a Claim About LLM Judges. Then I Ran the Apology Experiment.](blog-fabricated-claim-apology.en.md)*

All four parts are on [dev.to/zxpmail](https://dev.to/zxpmail). All experiment scripts are in [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts).

*Experiment F prototype: `forge-verify-layered-prototype.py` (Python, runnable with or without API)*
*forge-verify implementation: `ReqForge/scripts/forge-verify/content-verify.mjs` (Node.js, production)*

---

**Which comment did I miss?** If you've hit a verification failure mode that the L0/L1/L2/L3 pipeline doesn't catch, drop it in the comments — I'll run it through Experiment F and report what each layer does with it.
