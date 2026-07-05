<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  The Red Line Principle: when to stop an agent loop
  ─────────────────────────────────────────────────────────────────
-->

---
title: "The Red Line Principle: evidence from a controlled experiment on agent loop convergence"
published: false
description: "Same code task, two signal types: compile+test pass vs. LLM self-judgment. Red line adds +78% convergence rate. Key finding: self-judge fails from false negatives, not false positives."
tags: ai, llm, agents, testing
canonical_url: ""
---

How do you make an agent loop converge reliably in production?

I ran 3 core experiments that directly compare convergence with and without a red line, plus 8 auxiliary experiments (lexical overlap, temperature-0, phase gates, embedding separation, multi-model tradeoffs, SPC anomaly detection, cold-start drift, classification accuracy) covering adjacent dimensions. All scripts are open in the appendix.

## Core experiment: same code task, with red line vs. without

Previous versions of this comparison had a confound: "with red line" used a code task while "without red line" used a copywriting task. Different task types prevent causal attribution to the red line. This version corrects that.

**Unified task:** generate a Python function. Verification runs the test and matches the expected output.

**Condition A (with red line):** compilation + test pass = stop. Objective signal: the code ran and the output is correct.
**Condition B (without red line):** LLM self-judgment says "done" = stop. Same code, same test — the background verification still runs to record actual correctness.

Three tasks, 3 trials each, 8-step limit:

| Task | Condition | Convergence rate | Avg steps | Margin |
|------|-----------|----------------|-----------|--------|
| simple | With red line | **3/3 (100%)** | 1.0 | |
| simple | Self-judge only | 1/3 (33%) | 8.0 | **+67%** |
| medium | With red line | **3/3 (100%)** | 3.3 | |
| medium | Self-judge only | 1/3 (33%) | 8.0 | **+67%** |
| complex | With red line | **3/3 (100%)** | 1.0 | |
| complex | Self-judge only | 0/3 (0%) | 8.0 | **+100%** |
| **Total** | **With red line** | **9/9 (100%)** | **1.8** | |
| | **Self-judge only** | **2/9 (22%)** | **8.0** | **+78%** |

**Key finding:** the self-judge failure mode is not false positives (says YES when code is wrong). It's **false negatives** (writes correct code but says NO). The model doesn't trust itself, keeps iterating, and either degrades its own working code or hits the step limit. The red line (compile + test pass) eliminates this: code is correct + signal fires = immediate convergence.

**Marginal contribution of the red line: +78% convergence rate.** Same task, signal type is the only variable — this difference is the causal effect of an objective stop signal.

### On what "compile pass" actually verifies

The red line in these experiments isn't "syntax is valid." It's "the test output matches the expected result" — demand-level verification. Function `is_even(4)` must return `True` and `is_even(3)` must return `False`. This is fundamentally different from a phase gate checking "file exists." The former verifies correctness; the latter verifies occurrence.

For open-ended semantic tasks (write an analysis report), no equivalent objective verification exists. This isn't a "better red line design" problem — it's a task-type limitation.

### Three types of red lines

The experiments exposed a missing conceptual distinction. What we call a "red line" spans three categories with fundamentally different verification power and engineering cost.

**Format red line** — lowest cost, lowest verification power.
Checks file existence, exit 0, syntax parse, JSON Schema compliance.
It verifies "the output is well-formed," not "the output is correct." Phase gates and SPC belong here.

**Demand red line** — moderate cost, moderate verification power.
Checks compilation pass, test output matches expected, business assertion pass.
It verifies "the output satisfies the requirement." The V2 experiment uses this tier. It requires writing tests and assertions — cost is determined by the task's verifiability, not by system design.

**Semantic-layer red line** — does not exist.
No code, assertion, or schema can verify "this analysis report is logically coherent" or "this copy's emotional tone is appropriate."
**This is an open problem.** Under the current stack, no automatic mechanism can reliably judge task completion for open-ended semantic tasks.

| Red line type | Example | What it verifies | Cost | Usable as convergence signal? |
|-------------|---------|-----------------|------|------------------------------|
| Format red line | exit 0 / file exists / syntax pass | Well-formed output | Trivial | No (Phase Gate: 50% false positives) |
| Demand red line | compile + test pass / assertion pass | Output matches requirement | Medium | Yes (V2: 100% convergence) |
| Semantic-layer red line | — | Logical coherence / quality | — | **Does not exist** (open problem) |

The V2 experiment used a demand red line, not a format red line. The +78% convergence contribution was measured at this tier. A format red line (syntax check only) would not produce the same convergence rate — code can compile and still be wrong.

The rules below are based on this distinction. Only demand red lines can serve as convergence signals. Format red lines are insufficient. Semantic-layer red lines do not exist.

## The Red Line Principle

**Rule 1: tasks with an objective convergence signal → auto-converge, enter the production pipeline.**
Code compilation, schema validation, test output matching expectations — these have verifiable outputs. The loop runs, the signal fires, the system stops.

**Rule 2: tasks without an objective convergence signal → must have a hard cutoff.**
Open-ended semantic tasks — writing copy, drafting analysis, writing reports — have no objective "complete" signal. Do not rely on LLM self-judgment to stop the loop. The output at cutoff cannot auto-enter the production flow.

**Rule 3: output at cutoff → mark "unverified," route to human queue.**

The cutoff fired because budget ran out, not because the task was judged complete. "Route to human" isn't a complete engineering solution — it's operational fallback. Below is a design draft for a production-grade human handoff protocol.

#### Backpressure

Human review queue throughput is a hard constraint. When agent production rate persistently exceeds review rate, the system is unsustainable — the simulation confirmed this (5 items/min vs 3 items/min: 34% queue overflow). Backpressure mechanism:

- **Watermark:** queue depth > 80% of capacity triggers degradation. New tasks skip the fix loop entirely — output raw result, tag as "draft mode."
- **Limit:** queue depth hits capacity → drop lowest-priority items (log to circuit-breaker log), prioritize high-value tasks.
- **Recovery:** queue depth < 30% of capacity → resume normal flow.

Core observation: queue design doesn't dominate system stability — **the ratio of agent production rate to human review rate is the decisive factor.** If production exceeds review, any queue fills. Either slow down (cap agent concurrency), speed up (better review tools), or accept overflow (absorb the business cost).

#### Context preprocessing

Raw cutoff output may contain multi-step execution traces and thinking-token leakage (as observed in Experiment C). Showing this directly to a reviewer slows decisions.

Preprocessing rules:

- Extract three fields from the execution trace: final output, last error message, attempt count. Do not send the full trace.
- Reviewer UI displays only: task description → final output (highlighted) → cutoff reason (step limit / self-judge false negative / format anomaly).
- After verdict, collect: approve/reject + reason label (code error / logic error / format issue / hallucination / unclear). Sort labels by frequency — types appearing >3 times should trigger automatic filter rules.

#### Feedback tuning

Human verdicts shouldn't be consumed once and discarded. A feedback loop adapts cutoff parameters based on review results:

- **Sliding window:** approve rate over the last 10 human verdicts.
- **Rate > 80%:** cutoff too tight (too many correct tasks sent to review). Increase the step limit or loosen trigger conditions.
- **Rate < 40%:** cutoff too loose (too many incorrect outputs slip through). Decrease the step limit or tighten trigger conditions.
- **40%–80%:** maintain — cutoff is in the right zone; human review catches edge cases rather than bulk.

Simulation (2 hours, 4 configurations) showed: under baseline conditions (production rate ≤ review rate), the feedback loop converges the cutoff threshold to a stable value within 30–60 minutes. "Route to human" now has measurable behavior metrics — wait time, overflow rate, approval rate — each dimension can be SLO'd.

**Honest risk note:** the feedback tuning structure is isomorphic to the closed-loop calibration criticized in my earlier work (human verdicts → data pool → scheduled tuning). The same failure modes apply: distribution shift nullifies historical patterns, and whack-a-mole effects are possible. The difference is that here we tune a scalar (step limit, bounded [3,15]) rather than LLM few-shot examples (high-dimensional, uncontrolled). The failure domain is narrower, but not zero.

## The boundary of loops — an untested hypothesis

The data raises a question it cannot answer: **does the loop's repair capability have a boundary?**

With the red line, the medium task averaged 3.3 steps while the complex task averaged 1.0 steps. This difference might mean that FizzBuzz's boundary conditions (3→Fizz, 5→Buzz, 15→FizzBuzz) fall in the model's "near-miss zone" — it understood the requirement but made a syntax or edge-case error, which is fixable through iteration. The complex task (data structure manipulation) was written correctly on the first try.

**But this is a post-hoc interpretation.** N=3 cannot exclude random variation. A more fundamental question: if the error is conceptual (the agent completely misunderstood the requirement), can the fix loop still recover? Current experiments don't answer this, because all tasks were within the model's capability range — tasks beyond capability were not included in the design.

A worthwhile independent direction: construct two task classes (syntax errors vs. logic errors) and compare fix-loop success rates — the former expected to be high, the latter low and non-improving with iteration.

## The deeper claim

The Red Line Principle isn't about "how to make agents do more." It's about defining when not to let the agent continue.

The prerequisite for a production-grade agent isn't that it can do more. It's that what it cannot do is clearly marked in advance, and it stops reliably at the boundary.

| Task type | Convergence signal | Red line |
|-----------|-------------------|----------|
| Code / verifiable output | Compile + test pass (demand-level) | Generous step limit (1-3 normally) |
| Open-ended semantic | **None exists** | Cutoff + human (no auto-fix) |

*Note: structured editing (diff to zero) was not tested in the experiments presented here and is omitted from this table.*

---

All experiment scripts: `github.com/zxpmail/blog` → `agent-determinism-illusions/scripts`

Includes the V2 red line comparison (`redline-v2-experiment.py`). Run with your own data.

*The conclusion is "a red line improves convergence rate by +78%," not "the red line solves everything." The former has experimental support. The latter doesn't.*
