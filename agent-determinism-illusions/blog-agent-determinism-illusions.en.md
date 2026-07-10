<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS — submit a Story, paste the GitHub URL of THIS file,
  and use one of these as the title (HN rewards dry/honest; punishes hype):

  Recommended:
    Lexical overlap, temperature 0, phase gates: tested and failed

  Alternatives:
    I tested the 'deterministic agent loop' claims (lexical overlap, temp-0, phase gates). All failed.
    "Deterministic" agent loops are only formally deterministic — 4 experiments, data inside
  ─────────────────────────────────────────────────────────────────
-->

---
title: "I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix."
published: false
description: "Lexical-overlap thresholds, temperature-0 evaluators, phase gates — and an embedding 'upgrade' I thought would save them. The data says no."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

A certain genre of "production-grade AI agent" article has been making the rounds. You know the shape: it argues that ReAct loops break in production, so you have to stack *deterministic* constraints on top of the LLM's uncertainty — a pre-AL gate, an LLM-as-Judge at temperature 0, a phase gate, a decision state machine. The one I have in mind claims 7000+ lines of production Rust.

The **direction is right**. Agent loops do need engineering guardrails; you can't let the LLM declare victory on its own. Pulling "self-contained agents" out of academic fantasy and toward engineering reality is a valuable move.

The problem is the repeated use of words like *deterministic*, *objective fact*, *code vetoes the LLM* to manufacture confidence. Do those claims actually hold up?

I didn't argue. I ran four experiments. Conclusion: **each of the three core mechanisms it uses to establish "determinism" is only formally deterministic — all of them fail at the semantic layer. And the "upgrade" I prepared to fix them failed too.**

Here's the data.

## Fair credit first

The most valuable thing in this genre is the problem awareness. Three real defects of bare ReAct loops: no termination condition, no interrupt handling, no idle-loop protection. The proposed direction — wrap the LLM's uncertainty in deterministic constraints — is correct.

The problem isn't the direction. It's the landing. These articles treat three specific mechanisms as solved answers, and their actual behavior doesn't survive measurement.

I tested exactly these three:

1. **Lexical-overlap thresholds** — deciding whether a user interjection is a new task or an addendum
2. **Temperature-0 evaluators** — deciding whether the agent is done
3. **Phase gates** — deciding whether task completion is an "objective fact"

Three experiments, all using the methods and parameters the articles themselves describe, falsifying the articles' own claims.

## Illusion 1: lexical overlap = semantics?

Mid-loop on turn 5 the user interjects: "actually, change it to X." Is this an addendum to the old task, or a brand-new task?

The proposed fix: compute a "lexical overlap" score with two fixed thresholds — **≥0.24 means same task, ≤0.08 means new task**, with the middle sent to the LLM. The claim is "80% decided by code, instantly."

Sounds engineering-grade. But lexical overlap reads characters, not meaning. I built 30 labeled pairs, applied its thresholds, ran three tokenizers.

**Result: 50% hard misclassification.**

The worst cases:

> Current task: "continue writing the loop-engine article"
> User interjects: "**delete** the loop-engine article"
> Overlap **0.615 → judged same task**

The user said delete; the engine decides "same as writing," and **keeps writing**. A reverse operation is treated as a continuation. This is incident-grade.

> Current task: "fix the checkout bug"
> User interjects: "the payment page is throwing, can you look"
> Overlap **0.000 → judged new task**

Any human sees one task. Jaccard gives 0. Paraphrase fails entirely — 6/6 wrong. Cross-lingual is worse: 6 same-task EN/ZH pairs all score 0.000, all judged new. In any bilingual shop this mechanism **collapses on contact**.

A defender might say: "code makes a call in 90% of cases, above the 80% we promised."

That's a bait-and-switch. The implicit promise of "80% decided by code" is "80% decided **correctly**." The reality: code issues a verdict in 27 cases and gets 12 right — **44% accuracy**.

Treating "decided" as "decided correctly" is the most dangerous rhetorical move in the whole design.

The thresholds only work on easy samples (high-overlap same-task, low-overlap new-task): 12/12 correct. The three "common but hard" categories — paraphrase, cross-lingual, antonym — go 0/16. **Strongly suggests the thresholds were tuned on the easy set.** Any non-trivial sample distribution breaks them immediately.

## Illusion 2: temperature 0 = determinism?

The article sets the evaluator to temperature 0.0, "output almost entirely determined," because "for the same input, the evaluation should be as consistent as possible."

This is testable in one sentence: same prompt, temperature 0, run it 20 times, check consistency.

I ran three prompt categories on GLM-5.2, 20 runs each.

**Result: open-ended output is only 70% consistent; 30% diverges.**

| Prompt type | Exact-match rate | Distinct versions |
|------------|------------------|-------------------|
| Math (most stable) | 100% | 1 |
| Structured listing | 95% | 2 |
| Open-ended creative | **70%** | **5** |

The open-ended row is the killer — same prompt, temperature 0, 20 runs, 5 different versions, lowest pairwise similarity **0.198**:

> "Always head Northbound for your daily cup of exceptional coffee."
> "Premium coffee for the journey ahead."

Almost no shared characters. **And the LLM-as-Judge evaluator outputs exactly this kind of open text** — `done` / `phase_done` / `reason` / `evidence`.

The article says "the evaluator isn't creative writing, it's judgment, so temperature must be 0." But the evaluator's `reason` and `evidence` fields are inherently open; measured divergence is on the same order as creative prompts.

Even "structured listing" is unstable: five adjectives in a different order. If `evidence` is a list and the order changes, downstream JSON changes, the decision changes.

The only 100%-deterministic case is "17×23=391." Which proves the rule: **temperature-0 determinism holds only when the answer space is razor-thin.** The moment the output has any openness, determinism breaks. Treating a narrow special case as a universal property is overgeneralization.

Evaluator reproducibility is the foundation of the entire loop engine. Unstable evaluation → unstable `done` signal to the phase gate → unstable decision state machine. The foundation shakes, and ten layers of "deterministic constraints" stacked on top are standing on a shaking base.

(Only tested one provider, GLM-5.2. But the article's claim is universal, so single-provider falsification suffices. OpenAI's temp-0 non-determinism is documented and independently confirmed; more providers would only strengthen this.)

## Illusion 3: phase gate = task completion?

The most confident line in the genre: **"task completion, transformed from an LLM's self-claim into a verifiable objective fact."**

The phase gate checks four things: did the script exit 0, does the file exist, is the file count met, is there a user-confirmation record. All in code, all checking "objective facts."

The problem — **these checks verify that an action happened, not that the result is correct.**

I implemented the phase gate per the article's description and built 8 scenarios: 4 with correct content, 4 with garbage content that still satisfies the gate.

**Result: 100% gate pass rate, 50% content correctness, 50% false-positive rate.**

The four false positives, in their own words:

| Task | Actual output | Gate verdict |
|------|--------------|--------------|
| Write a research brief | "I am a little duck, quack quack." | ✅ pass → "complete" |
| Draft covering ≥3 mechanisms | "." (a single period) | ✅ pass → "complete" |
| Generate 3 chapter files | 3 files containing "TODO" | ✅ pass → "complete" |
| Run the tests | `0 passed (no tests collected)`, exit 0 | ✅ pass → "complete" |

A duck, a period, TODO, zero test cases — the phase gate waves all of them through. It has zero discrimination on content correctness.

This isn't an implementation bug. The four checks it describes **don't read content by construction**; any faithful implementation has the same blind spot. Exit 0 means the process didn't crash, not that the result is right. File-exists means the path is there, not that the content meets the requirement.

Packaging "file exists / script ran" as "task complete" is an over-extension of the claim. The truth: the phase gate turns **"an action happened"** into an objective fact. It does **not** turn **"the task is done"** into an objective fact. Between those two lies a semantic gap it cannot cross.

That gap is called **content quality** — which is exactly what production users care most about.

## Three pillars, all cracked

The genre's thesis sentence: "stack deterministic constraints on top of the LLM's uncertainty."

Now all three "determinisms" are punched through by measurement:

| Pillar | Article claim | Measured | Status |
|--------|--------------|----------|--------|
| Lexical overlap = semantics | "80% decided by code" | 50% misclassified, 44% accuracy | ❌ |
| Temperature 0 = determinism | "almost entirely determined" | Open output 70% consistent | ❌ |
| Phase gate = task completion | "verifiable objective fact" | 50% false positives | ❌ |

All three foundation layers leak. The ten layers of constraints above stand on a leaking base.

The 7000 lines of Rust are probably real. But they guard the **symbolic layer** — string matching, file paths, exit codes. The semantic layer (intent, content, quality) is still running naked.

## Why this genre goes viral

It lands precisely on the anxiety of readers who've built a demo but never hit production. To someone who hasn't run an LLM system in production, the mechanism pile feels heavyweight and authoritative — they haven't seen these practices, and don't know they fail at the semantic layer.

Anyone who *has* run production reads it and thinks "the names are nicer than the contents": Pre-AL gate is prompt-injected state, temperature-0 LLM-as-Judge is evaluator hygiene, "determinism-first" is try/catch plus string matching, phase gate is validation logic, ten priority levels are an if-else chain. Every mechanism is correct and worth doing — but naming each one with a proprietary term to manufacture the impression of "an original framework" is **rebranding, not innovation**.

The harder wound: these articles open with "not pseudocode, not a concept diagram," then deliver zero lines of real code — only function names, constants, parameter values. Those are identifiers, not code. The promise isn't kept.

And the thing repeatedly cited as evidence of "production-grade" — "7000+ lines" — appears three times. Line count is the worst proxy for quality. A system that actually runs in production should produce SLO data, postmortems, load-test curves — not line counts.

## Fourth cut: I lied too

The first three cuts target the genre's three pillars of "determinism." Data speaks; all three break.

But I have to be honest here: I had a "constructive upgrade" ready behind those three cuts — embedding to upgrade lexical overlap, multi-vote to patch temperature 0, a second LLM to backstop the phase gate. I thought it would lift the article from "criticism" to "construction."

**I was wrong. That proposal has the same disease as the articles it criticizes: using complicated engineering to fake a semantic solution.**

I ran an experiment to convince myself. Not on the target — on my own proposal. I used Qwen3-embedding:0.6b (a real neural embedding model, 1024 dimensions) on the exact same synonymy-vs-antonymy separation test.

Result:

| Category | Mean | Min | Max |
|----------|------|-----|-----|
| **Synonyms** (should be high) | **0.766** | 0.490 | 0.977 |
| **Antonyms** (should be mid-low) | **0.739** | 0.582 | 0.881 |
| **Unrelated** (should be low) | **0.326** | 0.237 | 0.404 |

Synonyms (0.766) and antonyms (0.739) **differ by 0.026 — too close to separate.**

"optimize code performance" vs "don't optimize code performance" — cosine **0.881**, higher than 10 of the 12 synonym pairs.

"build a login-registration feature" vs "add the account-auth piece" (these are synonyms) — cosine **0.490**, lower than nearly every antonym pair.

**The only separation a neural embedding can do is "related vs unrelated" — synonyms/antonyms both sit around 0.75, unrelated drops to 0.326. But the moment the topic is the same and the direction is opposite, embedding fails exactly like Jaccard.**

So the entire separation chain — characters to statistics to neural vectors — fails by measurement:

- **Jaccard (Exp 1):** 50% misclassified. Cannot separate.
- **TF-IDF char 2-gram:** synonyms 0.072, antonyms **0.222** — direction reversed. Fails.
- **Qwen3-embedding (Exp 4):** synonyms 0.766, antonyms 0.739, diff 0.026. Fails.

My "embedding upgrade" doesn't survive this data. I'm deleting it and replacing it with the honest version.

## Honest conclusion: under the current stack, this problem has no engineering solution

The genre's three "determinism" pillars all collapse. My attempt to patch them with embedding, multi-vote, and a second LLM also fails:

- **Embedding cannot separate synonymy from antonymy** — same topic, opposite direction produces near-identical vectors.
- **A second LLM doesn't fix the first one's unreliability** — the inspector itself hallucinates; it just shifts the problem up one layer.

**So: when a user interjects something directionally ambiguous (new task or addendum? same direction or opposite?) into the current topic, engineering should not let an algorithm decide unilaterally. Detect topic overlap, then ask the human. Don't auto-adjudicate.**

This isn't cowardice. It's an honest choice of objective function: **correctness outranks autonomy.** If you want an unattended autonomous agent — neither the genre's design nor mine gets you there today. If you must guarantee no misclassification — human confirmation is the only known strategy.

**"LLM does symbolic-layer work; humans override on semantic judgment" isn't sexy. But it doesn't lie.**

## The question to ask before implementing

If you read one of these articles and are about to build a similar system, ask yourself first:

**Can your task's output be objectively verified for *correctness* — not just *existence*?**

If "no" (most content-generation, analysis, and conversational tasks are no), most of the genre's design doesn't apply to you. You need strong human review, cross-model verification, and user-feedback loops — not file-existence checks.

If "yes," still re-tune the parameters yourself, redesign the acceptance criteria, and reserve plenty of human-fallback channels.

Don't copy 0.24/0.08. Don't trust temperature 0 to give you determinism. Don't assume a passed phase gate means the task is done. **Don't assume swapping in an embedding model buys you semantics.**

Each of those four "don'ts" has measured data behind it.

## Reproducible scripts

All four scripts are public, one-click runnable, no cherry-picking. Swap in your own business data and rerun.

Repo: `github.com/zxpmail/blog` → `agent-determinism-illusions/scripts`:

- **Exp 1** (local, no API): `lexical-overlap-test.py` — 30 labeled pairs against the 0.24/0.08 thresholds
- **Exp 2** (needs API): `temp0-determinism-test.py` — same prompt × 20 runs, temperature 0
- **Exp 3** (local, no API): `phasegate-formalism-test.py` — duck / period / TODO / zero-tests false positives
- **Exp 4** (needs Ollama + Qwen3): `embedding-semantic-test.py` — synonymy/antonymy separation

If your business data produces a materially lower error rate than mine, tell me — it means the mechanism holds in some domain, and I'll update the conclusion.

---

The original target was a viral tech article. But the same standard turns back on me: **does my critique survive the three criteria — constraint, data, reproducibility?** All four scripts are public; anyone can swap samples and rerun. Being measurable by the ruler you hand out is the honesty technical criticism deserves.
