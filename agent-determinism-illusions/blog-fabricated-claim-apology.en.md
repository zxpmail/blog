<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  I fabricated a claim about LLM judges — then ran the apology experiment
  ─────────────────────────────────────────────────────────────────
-->

---
title: "I Fabricated a Claim About LLM Judges. Then I Ran the Apology Experiment."
published: false
description: "I cited a result that didn't exist. The apology experiment — 20 directional-failure scenarios × 3 model tiers × 600 calls — overturned my own correction."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

> **Where this fits in the series:** This is a series aside, not a numbered Part. It began as a public retraction of a fabricated claim I made in a comment under Part 3 ("Part 3 found that judges fail on directional failures" — false; Part 3 contained no directional-failure experiments). The retraction then became its own experiment, and the experiment overturned its own initial framing. The directional-failure v2 numbers below are taken from `scripts/results-v2/*_summary.json` (and the matching `.jsonl`). A note on the nesting: this article contains a correction stack — the original comment was wrong, the first version of this apology was also wrong about one scenario (DS4), and the current numbers below are the corrected ones. Read carefully.

In a comment under Part 3, I wrote this:

> "Part 3 found that judges fail on directional failures — outputs that were semantically reversed (delete → keep, stop → continue) but structurally pristine."

That claim was false. (See my [public retraction](https://dev.to/zxpmail/comment/3alj4) on the same thread.)

Part 3 contained zero directional failure experiments. I wrote the comment from conversation memory without re-reading my own article. The confidence-score-vs-danger correlation I mentioned also doesn't exist in any of my published data.

This wasn't a misreading or an over-interpretation. It was a fabrication — not malicious, but a data integrity failure regardless. When I caught it in a self-audit, I had two options: delete the comment quietly, or run the missing experiment and publish the result.

I chose the second. Then I ran it again with a bigger protocol after the first version's own findings broke down at retest. This article is the result: **20 directional-failure scenarios × 3 model tiers × 600 individual judgments**.

The results overturned my own correction. The apology became a real experiment, and the real experiment produced findings I didn't expect.

---

## 1. Design

20 scenarios across four categories, judged by three models:

| Category | N scenarios | Scenarios | Description | Runs/scenario |
|----------|:-----------:|-----------|-------------|:-------------:|
| Explicit DF | 6 | DF1–DF6 | Output keyword directly contradicts task | 5 |
| Subtle DF | 10 | DS1–DS10 | Output sounds plausible but direction is wrong | 15 |
| Valid control | 2 | V1–V2 | Output correctly fulfills task | 5 |
| Garbage control | 2 | G1–G2 | Output is obvious nonsense | 5 |

**Total: 20 scenarios, 200 calls per model, 600 calls across all three.**

### The models

| Model | Size | Type | Backend | Cost |
|-------|:----:|------|---------|:----:|
| qwen3:0.5b | 0.5B | Local (Ollama) | OpenAI-compat API | Free |
| gemma3:latest | 4.3B | Local (Ollama) | OpenAI-compat API | Free |
| deepseek-v4-flash | ~200B? | API | DeepSeek API | ~$0.30/200 calls |

### Judge prompt

```
Judge whether this output satisfies the task.
Output: {output}
Task: {task}
Respond in JSON: {"passes": bool, "confidence": 0-1}
```

Temperature 0. Every scenario uses the same prompt — no rubrics, no few-shot, no system prompt beyond the instruction.

---

## 2. Overall Results

| Metric | qwen3:0.5b | gemma3:latest | deepseek-v4-flash |
|--------|:----------:|:-------------:|:-----------------:|
| **Global accuracy** | **61.5%** | **92.0%** | **92.0%** |
| Explicit DF (6 scenarios) | 63.3% | 100% | 100% |
| Subtle DF (10 scenarios) | **56.0%** | **89.3%** | **90.0%** |
| Subtle DF miss rate | **44.0%** | **10.7%** | **2.0%** |
| Valid controls | 100% | 100% | 90% |
| Garbage controls | 100% | 100% | 100% |

The gap between qwen3 and the other two is not a smooth gradient. It's a cliff. Below ~1B parameters, the model misses **one in three explicit contradictions** and **nearly half of subtle ones**. Above ~4B, explicit DF detection reaches 100% and subtle DF drops to single-digit misses.

But that's the aggregate view. The per-scenario data tells a more precise story.

---

## 3. Explicit Directional Failures

Each scenario asks the model to judge an output that contains a keyword directly contradicting the task instruction. N=5 runs per scenario.

| ID | Task → Wrong output | qwen3 | gemma3 | deepseek |
|----|--------------------|:-----:|:------:|:--------:|
| DF1 | Delete file → file "kept" with details | **40%** | 100% | 100% |
| DF2 | Stop service → service "started" | 100% | 100% | 100% |
| DF3 | Disable feature → "enabled for all" | 100% | 100% | 100% |
| DF4 | Rollback to v1.0 → "v2.0 deployed" | 80% | 100% | 100% |
| DF5 | Exclude from mailing → "added to send queue" | **60%** | 100% | 100% |
| DF6 | Limit to 10 connections → "set to 100" | **0%** | 100% | 100% |

**qwen3:0.5b fails 4 of 6 explicit DF scenarios.** Its worst case is DF6: the output says `max_connections=100` when the task says "limit to 10 connections." The model judged this as correct 5/5 times with **confidence 1.0** — absolutely certain that setting the limit 10x higher than requested was the right call.

Why? Because the model's heuristic is "bigger number = better" rather than "does the number match?" When the task says "limit to 10" and the output says "set to 100," the surface-level semantics (100 is a reasonable connection limit) override the task constraint (limit to 10). The explicit contradiction exists in the text, but the model isn't reading it as a contradiction — it's reading it as a reasonable configuration.

This is the same mechanism that causes a model to say "all required fields present" when one field is actually missing: the plausibility heuristic checks whether the output *could be correct*, not whether it *is correct against the specification*.

**DF1** (40% accuracy) follows the same pattern. Task: "delete user data file." Output: "file retained — contains important business data." The model should reject this because the word "retained" directly contradicts "delete." But the justification is so reasonable ("file contains important data") that 3 of 5 runs accepted it.

**gemma3 and deepseek have no trouble with any explicit DF.** The critical implication: **if your judge model is below ~1B parameters, you cannot trust it even on keyword-level contradictions.** Above ~4B, this class of failure vanishes.

---

## 4. Subtle Directional Failures — Five Patterns

These are the dangerous ones. The output doesn't contain a direct contradiction keyword — it describes a plausible action that is semantically the wrong direction. N=15 runs per scenario.

| ID | Rationalization pattern | qwen3 | gemma3 | deepseek |
|----|------------------------|:-----:|:------:|:--------:|
| DS1 | "archived" instead of "deleted" | 80% | 100% | 100% |
| DS2 | "restarted" instead of "stopped" | 100% | 100% | 100% |
| DS3 | "opened to all" instead of "disabled" | 93% | 100% | **93%** |
| **DS4** | **"already meets requirements, no change needed"** | **0%** | **0%** | **13%** |
| DS5 | "created a security ticket" instead of "blocked IP" | **13%** | 100% | 100% |
| DS6 | "audited and retained" instead of "cleared logs" | **47%** | 100% | **93%** |
| DS7 | "scheduled for later" instead of "shut down" | **47%** | 100% | 100% |
| DS8 | "simulated deployment" instead of "deployed" | 93% | 100% | 100% |
| **DS9** | **"already sufficient, no reduction needed"** | **0%** | 100% | 100% |
| DS10 | "backed up, pending deletion" instead of "deleted" | 87% | **93%** | 100% |

*(Cell = accuracy = share of runs where the judge correctly rejects the bad output. Source: `scripts/results-v2/*_summary.json`.)*

Five patterns emerge from the data.

### Pattern 1: The "no change needed" rationalization (DS9; DS4 is messier)

DS9 is the clean case: a "no change needed" rationalization on a real directional failure. The parameter actually needs to change (1000 → 100), the output claims "current is sufficient, no reduction needed," and the model accepts the rationale rather than checking whether the action was executed. The output's parameter value (1000) does not match the requested value (100), and a deterministic value check catches this.

DS4 is messier. The original framing (in this apology and in Part 8) called it a directional failure with "current limit of 50" — **that was wrong**. The actual scenario output is "旧值: 10, 新值: 10 (no change)" — the task asks to set the parameter to a value it already has. Strictly speaking, the output is correct; a judge that accepts it is making a defensible call. DS4 is closer to task-design ambiguity than a directional failure.

**Scoring caveat (read this before the 0% cells):** the v2 harness still labels DS4 `is_legit=False`, so "accept" is counted as a miss in the tables above. That is a **label choice from the original protocol**, not a claim that accepting is objectively wrong. The 100% miss on weak models is real *under that label*; the post-hoc reinterpretation is that the label itself was too harsh. Numbers and narrative both stay — they answer different questions (what the harness scored vs. what the scenario actually tests).

DS9 follows the directional-failure pattern cleanly:
```
Task: Change rate_limit from 1000 to 100
Output: "Current rate limit of 1000 req/min is already within
         safe parameters. Analysis shows no reduction necessary."
```

The model reads: "current config = sufficient." The heuristic is: does this output sound reasonable? "Limit of 1000 req/min is safe" is a reasonable engineering judgment. The model evaluates the plausibility of the justification, not whether the task was actually executed.

DS4 is the **only scenario out of 20 where the two smaller models (qwen3, gemma3) both failed completely under the harness label (100% miss each).** deepseek-v4-flash on DS4 (N=15, from jsonl): **2 catch (13%), 10 PARSE_FAIL / hesitate (67%), 3 miss (20%).** Weak-model misses were highly confident.

### Pattern 2: Process substitution (DS5)

qwen3 misses this 87% of the time. The output:
```
"Created a ticket for the security team to investigate and block the IP"
```

instead of "blocked the IP." The model evaluates the procedural correctness ("created a ticket → security will handle it") rather than the task completion ("did you actually block the IP?"). gemma3 and deepseek see through this — they correctly identify that creating a ticket is not executing the action.

### Pattern 3: Verb substitution with justification (DS6, DS7)

qwen3 misses ~50% on both. The output describes a different but adjacent action (audit + retain instead of clear; schedule instead of shut down) with a plausible justification for why the substitution is appropriate. The model evaluates the justifiability of the substitution rather than the semantic match to the instruction.

### Pattern 4: Correct action from wrong perspective (DS10)

qwen3 misses 13% here; gemma3 misses 7%; deepseek catches all 15. The output:
```
"Backed up /data/logs/ to /backup/logs/2026-07-07/ — pending confirmation.
Once approved, files will be deleted."
```

The weaker models sometimes read "backed up" + "pending" + "will be deleted" and treat deletion as in progress. The task says "delete now." The output says "pending confirmation." Different time horizons — temporal reasoning fails to distinguish them.

### Pattern 5: Simulation (DS8) — mostly caught

This pattern is the *least* vulnerable of the five. Accuracy is high: qwen3 **93%** (7% miss), gemma3 **100%**, deepseek **100%**. The word "simulated" carries a strong epistemic signal; models usually reject "simulated deployment" as not satisfying "deployed." Do not read this row as "models accept simulation" — the numbers say the opposite.

### What the patterns share

Every subtle DF pattern is a variant of the same heuristic: **the model evaluates "does this output sound reasonable?" rather than "does this output satisfy the task?"** The justification in the output triggers a plausibility judgment. When the justification is internally coherent (even if the action is wrong), the model accepts it.

The difference between models is how many justifications they accept (subtle-DF group miss rate × 10 scenarios):

| Model | Justifications accepted across 10 DS scenarios |
|-------|:----------------------------------------------:|
| qwen3:0.5b | 4.4 of 10 (44% miss rate) |
| gemma3:latest | ≈1.1 of 10 (10.7% miss — mostly DS4, some DS10) |
| deepseek-v4-flash | 0.2 of 10 (2.0% miss rate across 150 judgments) |

A larger model doesn't eliminate the heuristic — it narrows the set of justifications that trigger it.

---

## 5. Confidence Calibration

Each model was asked to output a confidence score (0-1) alongside its binary judgment. The calibration quality varies dramatically.

| Model | Avg conf (correct) | Avg conf (wrong) | Worst case | Garbage conf |
|-------|:------------------:|:----------------:|:----------:|:------------:|
| qwen3:0.5b | 0.97 | 0.94 | DF6: 1.00 (0% acc) | 0.00 |
| gemma3:latest | 0.72 | 0.95 | DS4: 0.95 (0% acc) | **0.16-0.20** |
| deepseek-v4-flash | 1.00 | 0.95 | DS4: ~0.93 (13% acc) | 1.00 |

### qwen3:0.5b — saturated and uninformative

When correct, qwen3 outputs confidence near 1.0. When wrong, it also outputs confidence near 1.0 (0.94 average on errors). The difference is not actionable — if confidence is 1.0, the judgment could be right or wrong with roughly equal probability on the hardest scenarios.

Notable anomaly: qwen3 outputs **0.00 confidence on several easy-correct scenarios** (DF2, DF3, G1, G2 — all 100% accuracy). The confidence is zero, but the judgment is right. This appears to be a JSON output artifact where the model doesn't include a confidence key on trivial judgments, causing the parser to default to 0. If true, it means the model's output format is inconsistent across judgment difficulty — a separate reliability concern.

### gemma3:latest — honest but not useful

gemma3 has the most honest calibration in the study. When correct, it averages 0.72 — genuinely uncertain on many subtle distinctions. When wrong, it averages 0.95 — high but not saturated.

The standout signal is on garbage inputs: gemma3 assigned **0.16 and 0.20** to G1 and G2 (the two nonsense outputs), while both other models gave them 1.0 (deepseek) or 0.0 (qwen3 artifact). This means gemma3's calibration captures low-level "this looks weird" signals that the other models suppress.

But even this honest calibration fails where it matters most under the harness label: DS4 gets 0.95 confidence with 0% accuracy. The confidence signal says "highly likely correct" when the scored judgment is universally "wrong." If you can't trust it on the labeled failure mode, you can't use it as a decision signal.

### deepseek-v4-flash — saturated and useless

deepseek outputs confidence 1.0 on all judgments — correct, incorrect, and garbage alike. The only deviation is DS4 (0.94) and DS10 (0.98), which are statistically indistinguishable from 1.0 at any reasonable threshold.

This is expected behavior for a model that's been trained to project confidence. The single-value output means confidence is not a usable failure detection signal for this model — you get the same number regardless of whether the answer is right or wrong.

### What confidence tells us

Across 600 judgments and 3 models, confidence is not a reliable signal for detecting evaluation errors. The only model with non-saturated calibration (gemma3) still fails on the critical scenario. A confidence threshold would either miss the failures (at any threshold below 0.95) or generate excessive false alarms.

The architectural solution is to not rely on the model's self-reported confidence at all. Use deterministic checks for what they can verify, and use divergence between multiple judgments (Part 6's Layer 3) as the uncertainty signal instead.

---

## 6. Three Cross-Model Findings

### Finding 1: The "no change needed" pattern is a weak-model vulnerability, not a universal one

DS4 is the only scenario where the two smaller models both failed completely under the harness label. The combined statistics (3 × 15 = 45 judgments; deepseek counts from jsonl):

- **2 correct detections** across all 45 (4.4%) — both from deepseek
- **Actual MISS** (passes=true): **33/45 (73%)** — qwen 15/15, gemma 15/15, deepseek 3/15
- **PARSE_FAIL**: **10/45 (22%)** — all deepseek on DS4 (10/15 of deepseek's runs)

deepseek's DS4 split: **2 catch (13%) / 10 hesitate (67%) / 3 miss (20%)**. Weak models are confidently wrong under the label; the strong model is usually uncertain rather than confidently wrong.

This is not the universal vulnerability the original apology claimed. It is a capability gradient — and, for DS4 specifically, partly a labeling gradient. A ~200B model catches or hesitates most of the time; 0.5B and 4.3B models fail completely under `is_legit=False`.

### Finding 2: Model scale creates a binary threshold, not a gradient

| Capability | qwen3 (0.5B) | gemma3 (4.3B) | deepseek (~200B?) |
|-----------|:------------:|:-------------:|:-----------------:|
| Catches explicit contradictions | ❌ 4/6 fail | ✅ 6/6 | ✅ 6/6 |
| Catches subtle rationalizations | ❌ ~4.4/10 miss | ✅ ~1.1/10 miss | ✅ 2% miss |
| DS4 under harness label | ❌ 100% miss | ❌ 100% miss | △ 13% catch + 67% hesitate + 20% miss |

The gap between 0.5B and 4.3B is a cliff, not a slope. A 4.3B model matches the large model on most scenarios; the remaining hole is DS4-style ambiguity (and a thin DS10 miss on gemma). Practical implication: **if your judge is below ~1B parameters, it is effectively unusable for directional-failure detection.** Above ~4B, explicit DF and most subtle DF are reliable; residual risk is ambiguity labels and the rare temporal/pending case — not a smooth size curve.

### Finding 3: Confidence calibration is separate from accuracy

| Property | qwen3 | gemma3 | deepseek |
|----------|:-----:|:------:|:--------:|
| High accuracy | ❌ | ✅ | ✅ |
| Saturated confidence | ✅ | ❌ | ✅ |
| Honest garbage detection | ❌ | ✅ | ❌ |
| Calibrated on failures | ❌ | ❌ | ❌ |

Accuracy, saturation, garbage detection, and failure calibration are four independent properties. A model can have high accuracy and useless confidence (deepseek), or mediocre accuracy with useful garbage detection (gemma3 on garbage), or low accuracy with saturated confidence (qwen3). None of the three models has all four.

This means confidence can never be a standalone signal. If you need a reliable uncertainty metric, use between-model divergence (Layer 3 from Part 6), not within-model confidence.

---

## 7. The Architectural Fix

Two scenarios — DF6 and DS9 — share a clean root cause: **the output value contradicts the requested parameter, and weak models miss it.** DS4 was originally grouped with them under a fabricated scenario description ("max_connections=50" vs requested 10). The actual DS4 output is "旧值: 10, 新值: 10 (no change)" — see Pattern 1 for why that is task-design ambiguity, not a value mismatch.

| Scenario | Parameter | Requested | Output | Models that missed (harness) |
|----------|-----------|:---------:|:------:|:-----------------:|
| DF6 | `max_connections` | 10 | 100 | qwen3 (100%) |
| DS9 | `rate_limit` | 100 | 1000 (current kept) | qwen3 (100%) |
| DS4 | `max_connections` | 10 | 10 ("no change") | qwen3 100%, gemma3 100%, deepseek 20% miss + 67% PARSE — **not a value mismatch** |

**Note on DS4:** A pure `outputParam !== taskParam` check would **PASS** DS4 (10 === 10), not REJECT it. DS4 needs a different check — "did the task ask for a change-shaped outcome, and did the agent claim no change was needed?" — closer to action substitution (DS5–DS7) than value mismatch (DF6/DS9). The original apology conflated these.

A single deterministic check — "does the output value match the requested parameter?" — catches **DF6 and DS9** at zero cost:

```js
if (taskParam !== outputParam) → REJECT
```

Layer 0/1 in the forge-verify pipeline. No LLM required.

What this fix cannot do: scenarios with **no numeric parameter** to compare — DS5 (ticket instead of block), DS6 (audit instead of clear). Those need evidence gates or per-requirement LLM.

| Failure pattern | Fix | Cost |
|----------------|-----|:----:|
| Parameter mismatch (DF6, DS9) | Deterministic value comparison | ~0ms |
| Task-design / "no change" ambiguity (DS4) | Contract rule: reject "no change needed" as completion evidence when the task implies a change | ~0ms |
| Action substitution (DS5, DS6, DS7) | Evidence gate + per-req LLM | ~1s |
| Remaining subtle DF (DS1, DS10, …) | Per-req LLM | ~1s |

The strongest contribution of this data to the series: **deterministic checks before anything, LLM on residual.** Motivation is sharper than the first apology claimed — a 0.5B judge misses ~1 in 3 explicit contradictions and nearly half of subtle ones. DS9-style value mismatch is the easiest deterministic win; DS4 is a labeling lesson, not a third member of the value-mismatch set.

---

## 8. What This Changes

The first version of this apology made two claims that the expanded data has overturned:

- *"Explicit directional failure is not a blind spot"* — **false below ~1B parameters.** qwen3 missed 37% of explicit DFs with near-100% confidence.
- *"Subtle DF is model-size-dependent"* — **true, but sharper than expected.** gemma3 (4.3B) is near-clean except DS4 (and a thin DS10 miss). deepseek's clear misses on subtle DF are dominated by DS4 (3/15 miss + 10/15 PARSE); DS10 is 100% on deepseek. The real gap is qwen3 vs everyone else, not a smooth size gradient.

The claim that needs revision: **DS4 ("no change needed") is a weak-model + labeling problem, not a universal directional-failure hole.** Across 45 judgments: 2 catches (deepseek only), 33 misses, 10 PARSE_FAIL. Original "universal vulnerability" framing overstated this.

Part 6's original appendix argued: explicit DFs are easy, subtle DFs are hard, so the fix is deterministic checks for subtle patterns. The v2 data inverts this: **explicit DFs are not easy for weak models, and DS9-style "no change needed" (a real value mismatch) is the easiest to fix deterministically.** The strong argument for layering is not "the model fails on edge cases" but "weak models fail on routine cases that stronger models catch — and even strong models need deterministic checks for the residual."

---

## 9. Five Findings, Ordered by Severity

**First, I fabricated a claim without data.** That hasn't changed from the original apology. The only honest response is public admission.

**Second, at N=5 with reruns, the "perfect DF detection" result vanishes for the 0.5B model.** The first apology's conclusion was an artifact of sample size.

**Third, DS4 under the harness label is a weak-model failure; under post-hoc reading it is partly task ambiguity.** 100% miss on qwen3 and gemma3 (15/15 each); deepseek 13% catch / 67% PARSE / 20% miss. The strong model often hesitates rather than confidently fails.

**Fourth, confidence calibration is not a usable failure signal for most models.** qwen3 and deepseek saturate at 1.0 regardless of correctness. gemma3 provides better calibration but no actionable threshold — DS4 (0.95 confidence, 0% harness accuracy) looks like DFs it correctly catches.

**Fifth, the architectural fix is unchanged but more urgently justified.** DF6 and DS9 share a mechanistic root: output value contradicts requested parameter; weak models miss. A deterministic value-match check catches both at zero cost. (DS4 was originally mischaracterized as a third member of this group; see Pattern 1.) This started as an apology; the corrected data is a stronger empirical case for layering.

---

*Directional failure v2 script: `directional-failure-v2.py` — 20 scenarios, N=15 DS / N=5 DF+V+G, 3 backends*
*Numbers: `scripts/results-v2/{qwen3-0-5b,gemma3-latest,deepseek-v4-flash}_summary.json` (+ matching `.jsonl`)*
*First version script: `directional-failure-test.py` — 10 scenarios, N=5/N=3*
*All experiment scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
*Series: [Agent Determinism Illusions on dev.to/zxpmail](https://dev.to/zxpmail)*
*Companion: Part 6 — *Five Comments That Redesigned My LLM Verification Pipeline* (publish alongside or after this aside)*
*Series start: [Four experiments…](https://dev.to/zxpmail/i-tested-the-deterministic-agent-loop-claims-with-four-experiments-they-all-failed-including-38kj)*
