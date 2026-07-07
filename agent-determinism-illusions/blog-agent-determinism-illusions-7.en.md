# The Reviewer's Stability — A Consistency Test

**Agent Determinism Illusions (Part 7)**

## Background

P1 ([Part 6](blog-agent-determinism-illusions-6.en.md)) found that using deepseek-v4-flash as an adversarial reviewer (Agent B) on 8 Phase Gate scenarios reduced the false positive rate from 50% to 0%, but the false negative rate reached 75%.

An immediate question: how stable is this 75%? If you run the same scenario 10 times, do you get the same verdict each time?

This question matters for downstream experiments. If the 75% is random noise (the same input sometimes passes, sometimes gets rejected), you can reduce the false negative rate by sampling multiple times and taking majority vote. If it's systematic bias (the same "wrong" verdict every time), you need a different strategy.

P2 answers this.

## Experiment Design

5 scenarios selected from P1's 8, covering different "certainty levels":

| Scenario | Content | P1 Verdict | Expected Difficulty |
|----------|---------|-----------|-------------------|
| L4 | 42 passed, 0 failed | 3/3 pass | Easy (clearly correct) |
| G1 | "I am a little duck, quack quack" | 3/3 reject | Easy (clearly garbage) |
| L1 | Loop engine research brief (excerpt) | 0/3 pass | Hard (correct but excerpt style) |
| L2 | 2000-word draft (summary annotation) | 0/3 pass | Hard (correct but summary style) |
| G4 | 0 passed in 0.00s | 3/3 reject | Medium (exit 0 but no tests) |

Method: each scenario repeated N=10 times, temperature=0, JSON `{"pass": bool}` judgment per call.

## Results

| Scenario | Valid Calls | PASS | REJ | Consistency | Confidence |
|----------|------------|------|-----|-------------|-----------|
| L4 (42 passed) | 8 | 8 | 0 | 100% | Sufficient |
| G1 (duck) | 10 | 0 | 10 | 100% | Sufficient |
| L2 (summary) | 10 | 0 | 10 | 100% | Sufficient |
| G4 (0 collected) | 7 | 0 | 7 | 100% | Sufficient |
| L1 (excerpt) | 2 | 0 | 2 | 100% | **Insufficient** |

*Some calls failed due to malformed JSON output — excluded from statistics.*

The four scenarios with sufficient data (L4, G1, L2, G4) were unanimous. L1 has insufficient data (2/10 valid), noted for reference only.

No scenario exhibited a split vote. L4 passed every time, G1 and L2 rejected every time. The model's binary judgment on identical input is stable.

## Analysis: Why So Consistent?

P0 (temperature 0 determinism test, Part 1) and P2 test consistency on different task types:

- **P0 tested free-text generation** (taglines, adjective lists) — large output space, temperature alone can't constrain semantic variance
- **P2 tested structured binary judgment** (`{"pass": true/false}`) — output space constrained by JSON schema and task framing

When output is compressed to a binary choice, the model only picks a boolean value. Small output space, naturally higher consistency. The reason field still varies, but the binary verdict is fixed.

Looking at the reason variations:

```
L4 #1: "the assistant executed the test script and reported that all..."
L4 #2: "the AI assistant ran the test script and reported that all 42..."
L4 #3: "the output shows the test script was executed with all 42 te..."
L4 #4: "the assistant executed the test script and confirmed all 42..."
L4 #5: "the output shows the test script was executed successfully w..."
```

Different phrasing each time, but pass=true every time. The model's semantic understanding varies (sometimes emphasizing "executed", sometimes "all 42 passed"), but the binary judgment is fixed.

This reinforces a thread running through the series: **LLM uncertainty lives primarily in semantic space, not in structured decision space.** The more structured the task (JSON schema, binary decision, clear rubric), the more deterministic the output. But "deterministic" ≠ "correct" — Agent B was deterministically wrong on 3/4 correct scenarios.

## A Side Finding: JSON Format Stability

P2 also revealed an engineering issue: roughly 15% of calls returned malformed JSON (unterminated strings, empty responses, markdown code blocks that failed to parse).

| Scenario | Valid | Failed |
|----------|-------|--------|
| L4 | 8 | 2 |
| L1 | 2 | 8 |
| G4 | 7 | 3 |

L1 had the highest failure rate (8/10) — possibly because its mixed Chinese/English content made JSON escaping more error-prone for the model. This is a practical concern: if you rely on LLM JSON output to drive automated workflows, roughly 10-15% of calls will need retries or fallbacks due to format issues.

## Tying Back to the Series

Connecting P0-P2:

- **P0 (temperature 0)**: Free-text output at temp=0 is inconsistent (20 different versions on structured listing)
- **P1 (adversarial verification)**: Single Agent B review, 0% FP / 75% FN
- **P2 (consistency test)**: Structured binary judgment at temp=0 is consistent; the 75% FN is systematic, not random

This means the precision-recall tradeoff is not something you can "run more samples" to avoid. You can't fix Agent B's false negatives by majority voting — it makes the same judgment every time.

Random bias and systematic bias require different strategies:
- Random bias can be reduced through repeated sampling and confidence thresholds
- Systematic bias requires calibration (adjusting prompt, changing the model, adding code-level check items) or accepting it as a fixed cost

A relevant reference point: human reviewers also have systematic bias — typically larger and less stable than this. Two engineers reviewing the same code produce consistent verdicts far less than 100% of the time. From an engineering standpoint, a **stable but strict** reviewer is easier to work with than an **unstable** one, because its behavior is predictable.

## Next Steps

P2 confirms a foundational assumption of adversarial verification: the reviewer's judgment on identical input is stable. This assumption holds.

The next question: if a single model's systematic bias is known and stable, can introducing multiple models — each with its own bias profile — produce a more reliable signal through **disagreement**? P3 will test multi-model voting: when three models unanimously agree vs. when they split, what are the respective accuracy rates?

---

*Experiment code: `agent-determinism-illusions/scripts/consistency-test-p2.py`*
