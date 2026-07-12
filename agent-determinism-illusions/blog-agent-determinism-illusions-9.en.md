---
title: "My \"Just Calibrate Your Prompt\" Only Held for 8 Samples"
published: false
description: "Prompt calibration sweep across 5 strictness levels. v3 'balanced' aced 8 Phase Gate scenarios at 100% but collapsed on 30 — the calibration effect disappeared. With Wilson CIs."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# My "Just Calibrate Your Prompt" Only Held for 8 Samples

## At 30 samples, the calibration effect disappeared

**Agent Determinism Illusions (Part 9)**

## Context

[The previous article](blog-agent-determinism-illusions-8.en.md) reported an optimistic finding: on 8 Phase Gate scenarios, the "balanced" prompt (v3) achieved 100% accuracy, reducing the "strict" prompt's (v2, the P1 baseline) false negative rate from 75% to 0%. The conclusion was that "adversarial verification doesn't need a stronger model or multi-model voting — it needs a calibrated prompt."

This article is a correction of that conclusion. To be fair, the previous article already stated in its "Limitations" section that "conclusions are indicative, not conclusive" and previewed the expanded testing described below. This article is the follow-up validation that was promised, not a retraction of an unconditional claim.

## Experiment P4: Expanded Test Set

I expanded the test set from 8 to 30 scenarios, covering more task types (code generation, translation, email writing, command parsing, execution confirmation), and added an "edge" category — directionally correct but insufficient quality, correct format but thin content. Then I ran both v2 (strict) and v3 (balanced) prompts on all 30 scenarios.

30 scenarios × 2 prompts = 60 API calls.

### Results

| Labeling scheme | v2 strict ACC | v3 balanced ACC |
|----------------|-------------|----------------|
| Excluding edge (20 samples) | 88.2% [66-97%] | 88.2% [66-97%] |
| All, edge as correct | 66.7% [47-82%] | 73.9% [54-87%] |
| All, edge as garbage | 87.5% [69-96%] | 82.6% [63-93%] |

All confidence intervals overlap. The two prompts are statistically indistinguishable.

More directly: **v2 and v3 were 100% consistent on valid calls** — on all 21 scenarios where both returned valid results, the verdicts were identical.

The "calibration improvement" from P3b did not replicate.

### What happened

P3b's 8 scenarios were mostly Phase Gate types (research briefs, drafts, chapter files) — v3 was slightly more lenient on these excerpt-style outputs. But when the test set expanded to cover code, translation, email, parsing, and tables, the difference disappeared.

The reason: **the model's review behavior is primarily determined by task structure and output format, not by prompt wording.** "Search strictly" and "judge fairly" produced the same decision boundary in the model's inference. C02-C03 (summary-style outputs for "write a full file" tasks) were consistently rejected by both prompts.

This explains why P3b's finding didn't generalize — it measured test set composition bias, not prompt engineering leverage.

## How Far the Series Actually Got

P0 to P4, six experiments, six paths that didn't lead to a definitive solution:

- **Temperature 0 doesn't guarantee consistency.** Free-text output at temp=0 diverges. But this turned out not to be the main constraint — structured binary judgments are highly stable.
- **Adversarial verification eliminates false positives.** At the cost of 75% false negatives. The precision-recall tradeoff is a structural constraint.
- **Systematic bias can't be sampled away.** The reviewer makes the same judgment every time — voting doesn't help.
- **Multi-perspective divergence is a useful signal.** A split indicates genuine uncertainty. But majority voting can't correct bias direction.
- **Prompt calibration worked on a small test set.** But at 30 samples the effect disappeared — the model's decision boundary is more stable than expected and not meaningfully shifted by wording.
- **JSON format failure rate is 15-20%.** This is a real engineering threshold for any pipeline that depends on structured LLM output.

The common thread: **every time we thought we found a solution, it didn't hold up under a larger test set or a more rigorous check.**

## What We Actually Learned

I don't think these six experiments had no output. They produced three usable maps.

**Map 1: Where the precision-recall tradeoff lives.**

Across ~260 API calls and multiple task types, false positives are easy to control (garbage scenarios have clear signals), but false negative rates vary widely by scenario type (complete files pass easily, excerpt-style outputs are consistently rejected). Error is not uniformly distributed — it's **scenario-dependent.** Knowing which scenario types fail is more useful than knowing an average accuracy rate.

**Map 2: The reviewer's consistency boundary.**

P2 (N=10 unanimous) and P4 (v2/v3 100% consistent) point to the same conclusion: **structured review judgments are highly deterministic.** The model does not randomly fluctuate on binary verdicts for identical input. This is both good news (predictable behavior) and bad news (systematic bias won't self-correct).

**Map 3: Ground truth ambiguity limits test set quality.**

Roughly 1/3 of the 30 scenarios fall into an "edge" category — directionally correct but insufficient quality, or cases where the labeler could argue either direction. Switching between labeling schemes changes accuracy by 5-10 percentage points. This means the quality ceiling of a test set is bounded by labeling consistency, not model capability.

## If This Is Really the End

The series is called "Agent Determinism Illusions." Over six experiments, the meaning shifted four times:

First, it referred to the illusion of LLM output determinism — people thought temp=0 guaranteed consistency.

Then, it referred to the illusion of review standards — people thought formal checks could guarantee content quality.

Next, it referred to the illusion of solution complexity — people thought they needed complex architecture for what looked like a prompt engineering problem.

Finally, it referred to the illusion of **a definitive answer** — people thought enough experiments would produce a clean solution.

There is no clean solution. The precision-recall tradeoff is a structural constraint on review tasks. Prompt calibration helps at the margins but doesn't remove the constraint. Multi-perspective voting provides additional signal but can't replace fundamental calibration. Larger test sets produce more robust conclusions but reveal more edge cases.

These aren't failures — they're the process of turning "what we don't know" into "what we know we don't know."

If you take only one thing:

**The effectiveness of adversarial verification doesn't depend on which model you use, and it doesn't depend on how you write your prompt. It depends on whether you accept that no perfect solution exists.** The precision-recall tradeoff isn't something you bypass — it's the constraint within which you choose an acceptable ratio of false positives to false negatives.

Once you accept this premise, the choices are clear: cover obvious garbage with simple rules, use a calibrated LLM as the second layer, escalate split-vote scenarios to human review, and accept residual error instead of trying to eliminate it.

---

*All experiment scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
*Series start: [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](https://dev.to/zxpmail/i-tested-the-deterministic-agent-loop-claims-with-four-experiments-they-all-failed-including-38kj)*
