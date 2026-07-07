# After Six Experiments, This Is the Most Honest Conclusion I Can Give

## We didn't find a silver bullet. We drew a better map.

**Agent Determinism Illusions (Part 8, Series Finale)**

## The Full Experiment Log

This series started with four claims from a 7000-line article — temperature 0 guarantees determinism, lexical overlap thresholds detect task switches, Phase Gate verifies task completion, adversarial verification fixes Phase Gate's blind spots.

Six experiments, two iterations, 200+ API calls, 30 test scenarios.

| Experiment | Question | Key Data |
|-----------|----------|----------|
| P0 | Is temp=0 output consistent? | Structured listing: 20/20 different → inconsistent |
| P1 | Can a single Agent B reduce FP? | FP 50%→0%, but FN 75% |
| P2 | Is the 75% FN stable? | N=10 per scenario, 100% unanimous |
| P3 | Does multi-perspective voting help? | Split is a useful signal, but majority vote FN still 75% |
| P3b | Can prompt calibration balance precision-recall? | v3 "fair" F1=100% on 8 scenarios |
| **P4** | **Does prompt calibration hold on a larger test set?** | **30 scenarios: v2=v3, gap disappears** |

## The Farthest We Got Was Back to the Start

P3b said "just calibrate your prompt" — on 8 scenarios, v3 (balanced) achieved 100% accuracy while v2 (strict) had FN=3. The answer seemed to be in the prompt wording.

P4 expanded the test set to 30 scenarios — and v2 and v3 were **100% consistent on valid calls** (21/21 scenarios, identical verdicts from both prompts).

| Labeling scheme | v2 strict ACC | v3 balanced ACC |
|----------------|-------------|----------------|
| Excluding edge cases | 88.2% [66-97%] | 88.2% [66-97%] |
| Edge marked as correct | 66.7% [47-82%] | 73.9% [54-87%] |
| Edge marked as garbage | 87.5% [69-96%] | 82.6% [63-93%] |

All confidence intervals overlap. The two prompts are statistically indistinguishable.

The "calibration improvement" observed in P3b was **test set composition bias** — on the original 8 scenarios, v3 happened to judge L1/L2 differently from v2. When the sample covered more task types (code, translation, email, tables), the surface-level difference vanished.

The model's review behavior is primarily determined by **task structure and output format**, not by prompt wording. "Search strictly" and "judge fairly" produce the same decision rule in the model's inference.

## What We Actually Know Now

After six experiments, here's what we can say with confidence.

**The precision-recall tradeoff is real.** In review tasks, reducing false positives necessarily increases false negatives. This constraint doesn't go away with a different model or prompt. P1 found it. P4 confirmed it at larger scale.

**Structured judgment consistency is high.** P2 demonstrated 100% unanimous verdicts at N=10. P4 showed 100% agreement between two different prompts across 21/21 scenarios on a diverse test set. This doesn't contradict P0 (free-text inconsistency at temp=0) — it shows that structured output formats effectively constrain the model's decision space.

**JSON format stability is a real engineering cost.** Across all experiments, 15-20% of calls failed due to malformed JSON (unterminated strings, markdown code block parsing failures, empty responses). An automated pipeline relying on LLM JSON output needs retry mechanisms and fallback handling.

**Ground truth labeling is itself contested.** Roughly 1/3 of the 30 scenarios fall into an "edge" category — directionally correct but insufficient quality, correct format but thin content, or cases where the labeler could argue either direction. Switching between labeling schemes changes accuracy by 5-10 percentage points.

**All confidence intervals are wide.** At 30 samples, the interval width is roughly 15-25 percentage points. The direction of the data is trustworthy. The exact percentages are not.

## Why This Problem Is Hard

The difficulty of adversarial verification isn't "designing a clever review scheme" — it's "defining what 'correct' means."

Phase Gate tried to substitute formal checks (file exists, exit code 0) for semantic evaluation. Its problem: form doesn't equal content.

Adversarial verification tried to use an LLM for semantic evaluation. Its problem: the LLM's judgment standard doesn't align with human annotation — and the misalignment is systematic, not random.

Prompt calibration tried to narrow this misalignment. It appeared to work on a small test set, but the larger test set showed limited effect — because the core issue isn't prompt wording, it's that the model has its own stable recognition standard for "complete output" vs. "excerpt-style output," and this standard is stricter than human annotation.

These three approaches didn't fail because we weren't smart enough. They failed because "quality review" is fundamentally a problem of drawing a boundary in semantic space — and that boundary is inherently fuzzy.

## What to Take Away

Not "calibrate your prompt." Not "multi-model voting works." Not "adversarial verification is bad."

This order:

1. **Cover obvious garbage with simple rules first** — length checks, keyword matching, format validation. G1-G4 can all be caught by rules. Don't call an LLM for problems that don't need one.

2. **Use a calibrated prompt as the second layer** — test 2-3 strictness variants on your own test set. Accept that this layer won't be perfect. The goal is to reduce error rates to an acceptable range, not to zero.

3. **Use divergence as an uncertainty signal, not majority vote** — if you run multi-perspective review, a split means this scenario genuinely needs human judgment. Don't force a majority verdict.

4. **Set a tolerance for remaining errors** — the precision-recall tradeoff is real. You must choose which side to tolerate: more false positives or more false negatives. Accepting this is more practical than trying to invent a mechanism that bypasses the tradeoff.

## The Series' Real Subject

The series is called "Agent Determinism Illusions." Over six experiments, the meaning shifted four times:

First, it referred to the illusion of LLM output determinism — people thought temp=0 guaranteed consistency.

Then, it referred to the illusion of review standards — people thought formal checks could guarantee content quality.

Next, it referred to the illusion of solution complexity — people thought they needed complex architecture for what seemed like a prompt engineering problem.

Finally, it referred to the illusion of **a definitive answer** — people thought enough experiments would produce a clean solution.

A clean solution doesn't exist. Quality determination is not a technological innovation problem — it's a semantic boundary problem, and semantic boundaries are inherently fuzzy. Any attempt to fully eliminate semantic uncertainty with technical means is trying to solve an essentially uncertain problem with a deterministic method.

This isn't a pessimistic conclusion. It's a realistic starting point.

---

*All experiment scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
*Series start: [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](blog-agent-determinism-illusions.en.md)*
