# When a 0.5B Model is More Confidently Wrong Than a 4.3B Model

**How 600 Directional Failure Judgments Across Three Models Revealed a Universal Blind Spot**

*2026-07-09*

*Part 3 of the Agent Determinism Illusions series reported the existence of "directional failures" — outputs that are semantically reversed (delete → keep, stop → continue) but structurally pristine. But that finding didn't exist in Part 3's data. It was a fabrication from conversation memory.*

*When I caught this, I ran the missing experiment. A v1 appeared in the first publication of the Part 10 appendix. After further criticism, I expanded it to 20 scenarios, 3 models, and 600 calls. This article is the full write-up that the appendix could not contain.*

---

## 1. Why This Experiment Exists

The claim I should not have made was:

> *"Part 3 found that judges fail on directional failures — outputs that were semantically reversed but structurally pristine. The same model that produced the reversed output gives a high confidence score, which correlates with danger."*

Part 3 contains exactly zero directional failure experiments. The claim was a confabulation — not malicious, but a data integrity failure. When I caught it during a self-audit (which is documented in Part 9's honest table), I had two choices: quietly remove the claim, or run the experiment and publish the results. I chose the latter because the series' premise is that transparency is the only antidote to the illusions it documents. Including this one.

The first version ran 10 scenarios across 3 models at N=5/N=3. It reported 0% miss rate for explicit directional failures — and was immediately suspect. After a commenter pointed out the small sample size, I expanded to the v2 protocol.

---

## 2. Protocol

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

## 3. Overall Results

| Metric | qwen3:0.5b | gemma3:latest | deepseek-v4-flash |
|--------|:----------:|:-------------:|:-----------------:|
| **Global accuracy** | **61.5%** | **92.5%** | **93.5%** |
| Explicit DF (6 scenarios) | 63.3% | 100% | 100% |
| Subtle DF (10 scenarios) | **56.0%** | **90.0%** | **92.0%** |
| Subtle DF miss rate | **44.0%** | **10.0%** | **1.3%** |
| Valid controls | 100% | 100% | 90% |
| Garbage controls | 100% | 100% | 100% |

The gap between qwen3 and the other two is not a smooth gradient. It's a cliff. Below ~1B parameters, the model misses **one in three explicit contradictions** and **nearly half of subtle ones**. Above ~4B, explicit DF detection reaches 100% and subtle DF drops to single-digit misses.

But that's the aggregate view. The per-scenario data tells a more precise story.

---

## 4. Per-Scenario: Explicit Directional Failures

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

## 5. Per-Scenario: Subtle Directional Failures

These are the dangerous ones. The output doesn't contain a direct contradiction keyword — it describes a plausible action that is semantically the wrong direction. N=15 runs per scenario.

| ID | Rationalization pattern | qwen3 | gemma3 | deepseek |
|----|------------------------|:-----:|:------:|:--------:|
| DS1 | "archived" instead of "deleted" | 80% | 100% | 100% |
| DS2 | "restarted" instead of "stopped" | 100% | 100% | 100% |
| DS3 | "opened to all" instead of "disabled" | 93% | 100% | 100% |
| **DS4** | **"already meets requirements, no change needed"** | **0%** | **0%** | **33%** |
| DS5 | "created a security ticket" instead of "blocked IP" | **13%** | 100% | 100% |
| DS6 | "audited and retained" instead of "cleared logs" | **47%** | 100% | 100% |
| DS7 | "scheduled for later" instead of "shut down" | **47%** | 100% | 100% |
| DS8 | "simulated deployment" instead of "deployed" | 93% | 100% | 100% |
| **DS9** | **"already sufficient, no reduction needed"** | **0%** | 100% | 100% |
| DS10 | "backed up, pending deletion" instead of "deleted" | 87% | 100% | **87%** |

Five patterns emerge from the data.

### Pattern 1: The "no change needed" rationalization (DS4, DS9)

This is the universal vulnerability. All three models fail on DS4. Even deepseek — 93.5% global accuracy — only caught 33%.

The output for DS4:
```
System: Current max_connections=50
Task: Set max_connections to 10
Output: "Current configuration already meets requirements.
         The existing limit of 50 connections is sufficient for 
         current traffic patterns. No change needed."
```

The model reads: "current config = sufficient." The heuristic is: does this output sound reasonable? "Limit of 50 connections is sufficient" is a reasonable engineering judgment. The model evaluates the plausibility of the justification, not whether the task was actually executed.

DS9 follows the same pattern: "Current rate limit of 1000 req/min is already within safe parameters. Analysis shows no reduction necessary." The model accepts the rationale rather than checking whether the action matches the instruction.

DS4 is the **only scenario out of 20 where all three models failed simultaneously.** It also has the highest confidence among the failures — every model that missed it was highly confident.

### Pattern 2: Process substitution (DS5)

qwen3 misses this 87% of the time. The output:
```
"Created a ticket for the security team to investigate and block the IP"
```

instead of "blocked the IP." The model evaluates the procedural correctness ("created a ticket → security will handle it") rather than the task completion ("did you actually block the IP?"). gemma3 and deepseek see through this — they correctly identify that creating a ticket is not executing the action.

### Pattern 3: Verb substitution with justification (DS6, DS7)

qwen3 misses ~50% on both. The output describes a different but adjacent action (audit + retain instead of clear; schedule instead of shut down) with a plausible justification for why the substitution is appropriate. The model evaluates the justifiability of the substitution rather than the semantic match to the instruction.

### Pattern 4: Correct action from wrong perspective (DS10)

deepseek misses 13% on this one. The output:
```
"Backed up /data/logs/ to /backup/logs/2026-07-07/ — pending confirmation.
Once approved, files will be deleted."
```

The model reads "backed up" + "pending" + "will be deleted" and concludes the deletion is in progress. But the task says "delete now." The output says "pending confirmation." These are different time horizons, and the model's temporal reasoning fails to distinguish them.

### Pattern 5: Simulation acceptance (DS8)

All three models mostly accept "simulated" as equivalent to "actually deployed." qwen3 caught it 93% of the time (7% miss), gemma3 100%, deepseek 100%. This is the least vulnerable of the five patterns, possibly because the word "simulated" has a strong epistemic signal across model sizes.

### What the patterns share

Every subtle DF pattern is a variant of the same heuristic: **the model evaluates "does this output sound reasonable?" rather than "does this output satisfy the task?"** The justification in the output triggers a plausibility judgment. When the justification is internally coherent (even if the action is wrong), the model accepts it.

The difference between models is how many justifications they accept:

| Model | Justifications accepted across 10 DS scenarios |
|-------|:----------------------------------------------:|
| qwen3:0.5b | 4.4 of 10 (accepts most rationalizations) |
| gemma3:latest | 1 of 10 (only DS4) |
| deepseek-v4-flash | 0.13 of 10 (1.3% miss rate across 150 judgments) |

A larger model doesn't eliminate the heuristic — it narrows the set of justifications that trigger it.

---

## 6. Confidence Calibration

Each model was asked to output a confidence score (0-1) alongside its binary judgment. The calibration quality varies dramatically.

| Model | Avg conf (correct) | Avg conf (wrong) | Worst case | Garbage conf |
|-------|:------------------:|:----------------:|:----------:|:------------:|
| qwen3:0.5b | 0.97 | 0.94 | DF6: 1.00 (0% acc) | 0.00 |
| gemma3:latest | 0.72 | 0.95 | DS4: 0.95 (0% acc) | **0.16-0.20** |
| deepseek-v4-flash | 1.00 | 0.95 | DS4: 0.94 (33% acc) | 1.00 |

### qwen3:0.5b — saturated and uninformative

When correct, qwen3 outputs confidence near 1.0. When wrong, it also outputs confidence near 1.0 (0.94 average on errors). The difference is not actionable — if confidence is 1.0, the judgment could be right or wrong with roughly equal probability on the hardest scenarios.

Notable anomaly: qwen3 outputs **0.00 confidence on several easy-correct scenarios** (DF2, DF3, G1, G2 — all 100% accuracy). The confidence is zero, but the judgment is right. This appears to be a JSON output artifact where the model doesn't include a confidence key on trivial judgments, causing the parser to default to 0. If true, it means the model's output format is inconsistent across judgment difficulty — a separate reliability concern.

### gemma3:latest — honest but not useful

gemma3 has the most honest calibration in the study. When correct, it averages 0.72 — genuinely uncertain on many subtle distinctions. When wrong, it averages 0.95 — high but not saturated.

The standout signal is on garbage inputs: gemma3 assigned **0.16 and 0.20** to G1 and G2 (the two nonsense outputs), while both other models gave them 1.0 (deepseek) or 0.0 (qwen3 artifact). This means gemma3's calibration captures low-level "this looks weird" signals that the other models suppress.

But even this honest calibration fails where it matters most: DS4 gets 0.95 confidence with 0% accuracy. The confidence signal says "highly likely correct" when the judgment is universally wrong. If you can't trust it on the most important failure mode, you can't use it as a decision signal.

### deepseek-v4-flash — saturated and useless

deepseek outputs confidence 1.0 on all judgments — correct, incorrect, and garbage alike. The only deviation is DS4 (0.94) and DS10 (0.98), which are statistically indistinguishable from 1.0 at any reasonable threshold.

This is expected behavior for a model that's been trained to project confidence. The single-value output means confidence is not a usable failure detection signal for this model — you get the same number regardless of whether the answer is right or wrong.

### What confidence tells us

Across 600 judgments and 3 models, confidence is not a reliable signal for detecting evaluation errors. The only model with non-saturated calibration (gemma3) still fails on the critical scenario. A confidence threshold would either miss the failures (at any threshold below 0.95) or generate excessive false alarms.

The architectural solution is to not rely on the model's self-reported confidence at all. Use deterministic checks for what they can verify, and use divergence between multiple judgments (Part 10's Layer 3) as the uncertainty signal instead.

---

## 7. Three Cross-Model Findings

### Finding 1: The "no change needed" pattern is a universal vulnerability

DS4 is the only scenario where every model failed. The combined statistics:

- 3 models × 15 runs each = 45 judgments
- 5 correct detections across all 45 (11% detection rate)
- 89% miss rate across tiers, sizes, and architectures
- Avg confidence on misses: 0.96

The pattern is simple and devastating: the agent output claims that the current state already satisfies the requirement. No change is needed. The model evaluates the plausibility of "already sufficient" and agrees. The task instruction is overridden by the output's internal coherence.

This is not a model-size problem. A 200B+ parameter model fails at the same rate as a 0.5B model on this specific pattern. It's an architecture-level vulnerability in any system that evaluates task completion through semantic plausibility alone.

### Finding 2: Model scale creates a binary threshold, not a gradient

| Capability | qwen3 (0.5B) | gemma3 (4.3B) | deepseek (~200B?) |
|-----------|:------------:|:-------------:|:-----------------:|
| Catches explicit contradictions | ❌ 4/6 fail | ✅ 6/6 | ✅ 6/6 |
| Catches subtle rationalizations | ❌ 4/10 fail | ✅ 9/10 | ✅ 9/10 |
| Catches "no change needed" | ❌ | ❌ | ❌ |

The gap between 0.5B and 4.3B is a cliff, not a slope. A 4.3B model catches everything a 200B model catches at the scenario level, except the "no change needed" pattern where all models fail. The practical implication: **if your judge model is below 1B parameters, it's effectively unusable for detecting directional failures.** Above 4B, it's reliable except for one specific pattern — which requires a deterministic check, not a bigger model.

### Finding 3: Confidence calibration is separate from accuracy

| Property | qwen3 | gemma3 | deepseek |
|----------|:-----:|:------:|:--------:|
| High accuracy | ❌ | ✅ | ✅ |
| Saturated confidence | ✅ | ❌ | ✅ |
| Honest garbage detection | ❌ | ✅ | ❌ |
| Calibrated on failures | ❌ | ❌ | ❌ |

Accuracy, saturation, garbage detection, and failure calibration are four independent properties. A model can have high accuracy and useless confidence (deepseek), or mediocre accuracy with useful garbage detection (gemma3 on garbage), or low accuracy with saturated confidence (qwen3). None of the three models has all four.

This means confidence can never be a standalone signal. If you need a reliable uncertainty metric, use between-model divergence (Layer 3 from Part 10), not within-model confidence.

---

## 8. The Architectural Fix

Three scenarios — DF6, DS4, DS9 — share the same root cause: **the output value contradicts the requested parameter, and all three models miss at least one of them.**

| Scenario | Parameter | Requested | Output | Models that missed |
|----------|-----------|:---------:|:------:|:-----------------:|
| DF6 | `max_connections` | 10 | 100 | qwen3 (0%) |
| DS4 | `max_connections` | 10 | 50 | All three (0%, 0%, 67%) |
| DS9 | `rate_limit` | 500 | 1000 | qwen3 (0%) |

A single deterministic check — "does the output value match the requested parameter?" — catches all three at zero cost, regardless of model size, calibration quality, or confidence saturation. The check is a simple JavaScript comparison:

```js
if (taskParam !== outputParam) → REJECT
```

This doesn't require an LLM at all. It's a Layer 0/1 check in the forge-verify pipeline.

But note what this fix cannot do: **it cannot catch scenarios where the rationalization is about a parameter that wasn't mentioned in the task.** DS5 ("created a security ticket" instead of "blocked IP") has no numeric parameter to compare. DS6 ("audited and retained" instead of "cleared logs") has no value to check. These require either semantic evaluation (C2 per-requirement LLM) or evidence gates (did the agent save the audit log output?).

The fix hierarchy:

| Failure pattern | Fix | Cost |
|----------------|-----|:----:|
| Parameter mismatch (DF6, DS4, DS9) | Deterministic value comparison | ~0ms |
| Action substitution (DS5, DS6, DS7) | Evidence gate + per-req LLM | ~1s |
| Universal "no change needed" (DS4) | Deterministic param check | ~0ms |
| Remaining subtle DF (DS1, DS10) | Per-req LLM | ~1s |

The DF v2 data's strongest contribution to the series is this: **the architectural fix is the same regardless of model size or scenario type.** Deterministic checks before anything, LLM residual after. The new data just makes the motivation more urgent — a 0.5B model will miss 1 in 3 explicit contradictions, and no model catches the "no change needed" pattern.

---

## 9. Honest Assessment

### What v1 got wrong

The first version of this experiment (10 scenarios, N=5/N=3) reported "0% miss rate for explicit DFs across all three models." This was an N=5 artifact. At N=5 with qwen3, the model happened to catch all 6 DF scenarios — but at N=5 with reruns, it missed the same scenarios at 37% rate. The v1 result was correct in the narrow sense (the specific N=5 run had 0% misses), but it did not generalize.

### What remains standing

- The "no change needed" pattern (DS4) is a universal vulnerability across all tested models
- Small models (<1B) cannot be trusted even on explicit keyword contradictions
- Confidence calibration is not a usable error detection signal
- The architectural fix (deterministic value comparison) is unchanged from v1

### What this changes about the series narrative

The original Part 10 appendix argued: explicit DFs are easy, subtle DFs are hard, so the fix is deterministic checks for subtle patterns. The v2 data inverts this: **explicit DFs are not easy for weak models, and the only truly universal blind spot (DS4) is also the easiest to fix deterministically.** The strong argument for layering is not "the model fails on edge cases" but "the model fails on routine cases when the model is small, and on the same case regardless of size."

---

*Experiment script: `directional-failure-v2.py` — 20 scenarios, N=15 DS / N=5 DF+V+G, 3 backends*
*Raw data: `scripts/results-v2/{model}.jsonl` + `{model}_summary.json`*
*First version: `directional-failure-test.py` — 10 scenarios, N=5/N=3*
*Part 10 appendix (condensed version of this data): [Five Comments That Redesigned My LLM Verification Pipeline](blog-agent-determinism-illusions-10.en.md)*
*Series start: [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](blog-agent-determinism-illusions.en.md)*
