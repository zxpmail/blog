<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  The Red Line Principle: when to stop an agent loop
  ─────────────────────────────────────────────────────────────────
-->

---
title: "The Red Line Principle: objective stop signals outperform LLM self-judgment in verifiable tasks"
published: false
description: "Same code task, two signal types: compile+test pass vs. LLM self-judgment. Directional evidence that objective signals improve convergence. Scope: verifiable tasks only (code, structured output). Not applicable to open-ended semantic tasks."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

> **Where this fits in the series:** This article sits between Part 5 (the layered verification pipeline L0→L1→L2→L3) and the later parts that expand the experiments. It asks the upstream question: *how does an agent loop know when to stop?* The "demand red line vs. format red line" distinction below maps onto the L1 (contract regex) vs. L0 (evidence gate) split formalized in the main series. The "no semantic-layer red line exists" claim is the same boundary later named the DPI bound.

*The scope of this article is limited to tasks with objectively verifiable acceptance criteria (code, structured output, assertable results). For open-ended semantic tasks (writing copy, drafting analysis), the Red Line Principle does not apply.*

> **Scope restated:** The conclusions in this article hold only under the following conditions — the task has an objective verification standard, and that standard can be predefined by a human (code output matching expectations, schema validation passing, all tests green). For open-ended semantic tasks (writing copy, drafting analysis, generating creative content), no known automatic convergence signal exists within the scope of these experiments; refer to Rules 3 and 4. All data below is within this scope.

How do you make an agent loop converge reliably in production?

I ran 3 core experiments that directly compare convergence with and without a red line, plus 8 auxiliary experiments (lexical overlap, temperature-0, phase gates, embedding separation, multi-model tradeoffs, SPC anomaly detection, cold-start drift, classification accuracy) covering adjacent dimensions. All scripts are open in the appendix.

## Core experiment: same code task, with red line vs. without

**Warning: N=3, directional results, not statistically significant.**

Previous versions of this comparison had a confound: "with red line" used a code task while "without red line" used a copywriting task. Different task types prevent causal attribution to the red line. This version corrects that.

**Unified task:** generate a Python function. Verification runs the test and matches the expected output.

**Test cases:** human-written, covering normal input, boundary values, and edge cases. Injected into the agent context alongside the task definition. Test suite published at `scripts/test_cases/`.

**Condition A (with red line):** compilation + test pass = stop. Objective signal: the code ran and the output is correct.
**Condition B (without red line):** LLM self-judgment says "done" = stop. Same code, same test — the background verification still runs to record actual correctness.

Three tasks, 3 trials each, 8-step limit. N=3, showing distribution not effect size:

| Task | Condition | Convergence (individual) | Avg steps |
|------|-----------|------------------------|-----------|
| simple | With red line | [1,1,1] | 1.0 |
| simple | Self-judge only | [X,OK,X] | 8.0 |
| medium | With red line | [1,4,5] | 3.3 |
| medium | Self-judge only | [X,X,OK] | 8.0 |
| complex | With red line | [1,1,1] | 1.0 |
| complex | Self-judge only | [X,X,X] | 8.0 |

**Direction:** 9/9 converged with the red line; 2/9 actually converged with self-judge (both ran to the 8-step hard limit before self-triggering). The directional difference is stable, but N=3 cannot exclude random variation.

**Self-judge failure mode:** 0 false positives (says YES when code is wrong) and at least 4 false negatives (code correct but self-judge says NO or never triggers). The model wrote correct code but didn't trust itself, kept iterating, and either degraded its own working code or hit the step limit.

**Prompt bias note:** the self-judge prompt ("are you done?") is biased toward "not yet." A different prompt format (e.g., "output FINISH if code passes all tests") would likely change the self-judge convergence rate. This comparison describes "a specific self-judge prompt vs. a compilation signal," not a general "red line vs. no red line."

### On what "compile pass" actually verifies

The red line in these experiments isn't "syntax is valid." It's "the test output matches the expected result" — demand-level verification. Function `is_even(4)` must return `True` and `is_even(3)` must return `False`. This is fundamentally different from a phase gate checking "file exists." The former verifies correctness; the latter verifies occurrence.

For open-ended semantic tasks (write an analysis report), no equivalent objective verification exists. This isn't a "better red line design" problem — it's a task-type limitation.

### Three types of red lines

The experiments exposed a missing conceptual distinction. What we call a "red line" spans three categories with fundamentally different verification power and engineering cost.

**Honest note on the demand red line:** the demand red line used in these experiments (compile + test output matches expectation) depends on human-written test assertions. The system does not automatically know whether a task is complete — a human pre-defines the verifiable boundary, and the agent operates within it.

"Demand red line works" is equivalent to saying: "if a human writes a complete acceptance test upfront, the agent can satisfy it in 1-3 steps." This is labor shifting — moving verification cost from runtime to design time. For tasks where a complete, pre-writable verification set does not exist (most open-ended semantic tasks), the demand red line is inapplicable. It is a task classification, not a universal mechanism.

**Format red line** — lowest cost, lowest verification power.
Checks file existence, exit 0, syntax parse, JSON Schema compliance.
It verifies "the output is well-formed," not "the output is correct." Phase gates and SPC belong here.

**Demand red line** — moderate cost, moderate verification power.
Checks compilation pass, test output matches expected, business assertion pass.
It verifies "the output satisfies the requirement." The V2 experiment uses this tier. It requires writing tests and assertions — cost is determined by the task's verifiability, not by system design.

**Semantic-layer red line** — no known reliable method found within the scope of these experiments.
Existing approaches (LLM-as-judge, multi-round debate, consistency checks) show high false-positive rates or irreproducibility in limited testing.
**This is an open problem.** Not in-principle unsolvable — but no known engineering mechanism can reliably judge completion for open-ended semantic tasks under the current stack.

| Red line type | Example | What it verifies | Cost | Usable as convergence signal? |
|-------------|---------|-----------------|------|------------------------------|
| Format red line | exit 0 / file exists / syntax pass | Well-formed output | Trivial | No (Phase Gate: 50% false positives) |
| Demand red line | compile + test pass / assertion pass | Output matches requirement | Medium | Yes (V2: directional evidence) |
| Semantic-layer red line | — | Logical coherence / quality | — | **No known reliable method** (open problem) |

The V2 experiment used a demand red line, not a format red line. A format red line (syntax check only) would not produce the same convergence rate — code can compile and still be wrong.

The rules below are based on this distinction. Only demand red lines can serve as convergence signals. Format red lines are insufficient. Semantic-layer red lines do not exist.

## The Red Line Principle

**Rule 1: tasks with an objective convergence signal → auto-converge, enter the production pipeline.**
Code compilation, schema validation, test output matching expectations — these have verifiable outputs. The loop runs, the signal fires, the system stops.

**Rule 2: tasks with incomplete signals → auto-converge + human sampling.**
Many real tasks fall in the grey zone — 80% test coverage, schema-valid but business-unverified, diff-zeroed but semantically unchecked. Rules 1 and 4 are composable, not mutually exclusive: a task can auto-converge via its demand red line, then layer Rule 4's human sampling to cover the blind spots.

**Rule 3: tasks with no convergence signal → must have a hard cutoff; label "unverified," route to human queue.**
Open-ended semantic tasks — writing copy, drafting analysis, writing reports — have no objective "complete" signal. Do not rely on LLM self-judgment to stop the loop. The output at cutoff cannot auto-enter the production flow.

**Rule 4: output at cutoff → mark "unverified," route to human queue.**

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

Simulation (same 4 configurations as the backpressure table) showed: under A (production ≤ review), feedback tuning converged the step limit to max (5→15) in approximately 30 minutes, driven by the 40-80% approve rate zone keeping tuning in maintain. Under B/D (production > review), backpressure fires before tuning — the binding constraint is throughput, not convergence parameters.

| Config | Production (/min) | Review (/min) | Queue cap | 2h overflow |
|--------|-----------------|--------------|-----------|-------------|
| A (baseline) | 2 | 3 | 50 | **0%** |
| B (overload) | 5 | 3 | 50 | **34%** |
| C (burst) | 2 (burst ×3) | 3 | 50 | **0%** |
| D (slow review) | 2 | 1 | 50 | **30%** |

**This is a parameter estimation example, not production data.** Core observation: when production/review ratio ≤ 1, the system is stable; when ratio ≥ 2, it is unsustainable — queue design doesn't dominate, throughput ratio does. Actual deployment requires calibration against your own data.

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

The core experiment (`redline-v2-experiment.py`) supports `--task-file` for custom task definitions (JSON format, see `test_cases/README.md`). Run the red line comparison on your own tasks.

*The conclusion is "a red line leads to higher and more stable convergence rates," not "the red line solves everything." The former has experimental support. The latter doesn't.*
