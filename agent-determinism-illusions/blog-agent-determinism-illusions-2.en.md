<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  3 model tiers as agent quality inspectors — the false-positive / false-rejection tradeoff
  ─────────────────────────────────────────────────────────────────
-->

---
title: "I tested 3 models as AI agent quality inspectors: the stronger the model, the more valid work it rejects"
published: false
description: "qwen3:0.5b, gemma3:4.3b, and GLM-5.2 as agent output quality gates. The tradeoff: every garbage catch comes at the cost of false-rejecting real work. With data."
tags: ai, llm, agents, testing
canonical_url: ""
---

In my previous article (part 1 of this series), I tested the three "determinism" pillars that popular production-agent articles claim:

- **Lexical overlap** as a proxy for semantic continuity — 50% misclassification.
- **Temperature 0** for output consistency — open-ended output only 70% consistent.
- **Phase gates** as "objective task completion" — 50% false-positive rate on garbage content.

And I ended with a fourth experiment for humility: my proposed "upgrade" — swapping out the lexical-overlap threshold for an embedding model — also failed. Qwen3-embedding couldn't separate synonymy from antonymy (cosine diff: 0.026).

The honest conclusion I landed on: **under the current stack, this problem has no clean engineering fix.**

But the most common pushback I got was: "You used qwen3:0.5b — a 0.5B parameter model. Of course it fails. Try a real model."

Fair. I tried three tiers of model as the quality inspector, same 8 scenarios, same prompt template.

What I found made the conclusion **more nuanced, not less**. The data reveals a tradeoff that "just use a stronger model" doesn't solve.

## Experiment design

Same 8 scenarios from Experiment 3 (the phase-gate test):

- **4 valid outputs** — research brief, first draft, chapter files, test log (42 passed)
- **4 garbage outputs** — "I am a little duck, quack quack", a period, "TODO", "0 passed (no tests collected), exit 0"

The phase gate (string-level checks) waves all 8 through — **50% false-positive rate on garbage, by design.**

The question: can you add an LLM quality inspector on top to catch the garbage? And what does it cost?

I ran each scenario 3 times per model (majority vote) to smooth out the temp-0 sampling noise documented in Experiment 2.

## Three model tiers, measured

| Inspector | False-positive rate | False rejection of valid work | Vote instability |
|-----------|-------------------|------------------------------|------------------|
| (None, phase gate only) | **50%** | 0% | — |
| qwen3:0.5b (local, 0.5B) | **25%** | 50% | 2/8 |
| gemma3:latest (local, 4.3B) | **25%** | 50% | 0/8 |
| GLM-5.2 (API, ~hundreds of B) | **0%** | **75%** | 0/8 |

### Finding 1: false-positive rate drops monotonically with model size

qwen3 and gemma3 both hit the same ceiling: 25%. They both fail on the same case — **G4** (this is the chat model qwen3:0.5b, not the embedding model qwen3-embedding from Experiment 4):

> **Task:** Run the test script, ensure the tests actually pass
> **Output:** `exit 0, 0 passed (no tests collected)`

Both smaller models see "exit 0" + "passed" and let it through. GLM-5.2 understands the semantics: *"No tests collected" means no tests actually ran.*

This is a genuine model-size discontinuity. The weak models are fooled by a surface-level "passed" signal; the strong model reads the actual meaning.

### Finding 2: the cost is a surge in false rejections

GLM-5.2 drops the false-positive rate to 0%. Sounds like a solution.

**But it rejected 3 out of 4 perfectly valid outputs.**

- Research brief (valid, has content) → rejected
- First draft (valid, ~2000 words) → rejected
- Chapter files (valid, contains content) → rejected
- Test log (valid, "42 passed") → passed

Only the test log with explicit pass counts gets through. Everything else is flagged as "insufficient."

This isn't a bug. The strong model is simply *following instructions strictly* — the output has to clearly demonstrate it meets the task requirement. Anything that reads as a sketch or fragment gets killed.

## What's really happening: a precision-recall tradeoff

Put the two columns together and the pattern is clear:

- **Weak model:** lets garbage through (high false positives), but doesn't over-reject legitimate work
- **Strong model:** catches all garbage (zero false positives), but rejects most legitimate work too

This is a **precision-recall tradeoff**, not a solution. The model isn't "solving" the semantic problem; it's *choosing a position on the curve.* A quality gate that catches everything can trivially achieve 0% false positives — by rejecting everything.

## The "0% false positive" mirage

This also explains something I wrote earlier. I previously had a note that "DeepSeek achieved 0% false positive rate on this test" and concluded the problem was solved.

**I was looking at the wrong metric.**

0% false positive looks great. But without looking at the false-rejection rate alongside it, it's the exact mirror of the original articles' error: they treated "file exists" as "task complete"; I was treating "no garbage slipped through" as "quality gate works."

**A quality gate's job isn't just to keep garbage out — it's to keep good work in.** The "0%" number masked the fact that the strong model was rejecting 75% of valid outputs.

## Honest revision of the conclusion

My previous article said: *the quality inspector just shifts the problem up one layer.*

That was too harsh. The data shows the inspector **does** reduce false positives — from 50% to 0% with a strong model. But it's not a fix — it's a **cost transfer.** Every garbage catch costs one false rejection.

A more precise model of how this works:

> **Phase gate (free, leaks 50%) → LLM quality gate (reduces false positives, but introduces false rejections) → Human review (catches the false rejections)**

No single layer "solves" the problem. Each layer transfers the remaining uncertainty to the next. The honest design is a **chain of risk transfer**, not a stack of deterministic guarantees.

And the practical implication: if you add an LLM quality gate, you must budget for the human time to review false rejections. The stronger the model, the more you'll pay in flags that turn out to be false alarms.

## What this means for production

If you're building an agent loop with output verification:

1. **Phase gates catch nothing on content.** They're cheap, but they buy you zero quality signal. Expect 50%+ garbage pass-through.

2. **A small-model quality gate (≤4B)** catches some obvious garbage but misses subtle cases. Your false-positive rate drops from 50% to ~25%, but you'll false-reject ~50% of real work.

3. **A strong-model quality gate (API-grade)** catches everything — including edge cases small models miss. Your false-positive rate hits 0%. **But you'll false-reject ~75% of real work.** Budget human review accordingly.

4. **The metric that matters is the full confusion matrix**, not a single column. Anyone advertising "0% false positives" without showing false-rejection rates is selling the same oversimplification they claim to fix.

## Reproducible script

The experiment script is **parameterized** for multi-model comparison:

Repo: `github.com/zxpmail/blog` → `agent-determinism-illusions/scripts` → `harness-verify-test.py`

Set environment variables to switch models:
- `VERIFY_MODEL=qwen3:0.5b` (local Ollama, default)
- `VERIFY_MODEL=gemma3:latest` (local Ollama)
- `VERIFY_MODEL=glm-5.2` with `VERIFY_BASE_URL` and `VERIFY_API_KEY` (API)

Each model runs the same 8 scenarios × N iterations (default 3, majority vote). Swap in your own valid and garbage samples.

---

I wrote the first article to measure a popular genre's determinism claims. The second to catch myself proposing the same kind of oversimplified fix. This third piece corrects both: the truth isn't "no solution" or "just use a bigger model" — it's "there's a tradeoff, and you have to pick where to hurt."

Same ruler, one more measurement.
