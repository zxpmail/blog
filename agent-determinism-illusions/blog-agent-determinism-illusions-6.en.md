# I added an LLM judge to my Phase Gate — false positives hit 0%, false negatives hit 75%

**Agent Determinism Illusions (Part 6)**

## Background

A previous experiment ([Phase Gate formalism test, Part 1](blog-agent-determinism-illusions.en.md)) found that a checkpoint mechanism implemented per the described specification passed all 8 scenarios indiscriminately — including outputs like "I am a little duck, quack quack" and "。". False positive rate: 50%.

A natural follow-up question: can adding an LLM-based review step (Agent B) to Phase Gate reduce the false positive rate?

## Experiment Design

**Review model**: deepseek-v4-flash (via Anthropic-compatible API, temperature=0)

**Scenarios**: Reusing the 8 scenarios from the Phase Gate experiment
- L1-L4: Correct content (research brief, draft document, chapter files, passing tests)
- G1-G4: Garbage content (nonsense text, single punctuation, TODO placeholder, zero collected tests)

**Method**: Each scenario passes the task description and output to the model, asking it to judge whether the output actually satisfies the requirements. Each scenario repeated 3 times, majority vote.

**Judgment format**: JSON `{"pass": true/false, "reason": "..."}`. pass=true means the model considers the output satisfactory.

## Results

| Scenario | Ground Truth | Agent B Verdict (3 runs) | Phase Gate |
|----------|-------------|--------------------------|------------|
| L1 | Correct | Rejected (0/3) | Pass |
| L2 | Correct | Rejected (0/3) | Pass |
| L3 | Correct | Rejected (0/3) | Pass |
| L4 | Correct | Passed (3/3) | Pass |
| G1 | Garbage | Rejected (3/3) | Pass |
| G2 | Garbage | Rejected (3/3) | Pass |
| G3 | Garbage | Rejected (3/3) | Pass |
| G4 | Garbage | Rejected (3/3) | Pass |

### Summary

| Metric | Phase Gate | Agent B |
|--------|-----------|---------|
| False positive (passed garbage) | 50% (4/4) | **0%** (0/4) |
| False negative (rejected correct) | 0% (0/4) | **75%** (3/4) |

Agent B performed perfectly on garbage detection — all 4 garbage scenarios rejected, false positive rate down to 0%. But it performed poorly on correct content — 3 out of 4 correct scenarios rejected (L1-L3), false negative rate 75%. The only scenario that passed all 3 rounds was L4 (test execution: 42 passed, 0 failed).

## Analysis

### Why garbage scenarios were rejected

Agent B's reasons for rejecting G1-G4:

- G1 ("I am a little duck, quack quack") → "Content is completely unrelated to the user's requirements"
- G2 ("。") → "Output is only a single period, no substantive content"
- G3 ("TODO") → "Output is only a placeholder, no actual files or content generated"
- G4 ("0 passed in 0.00s") → "Script ran successfully but no tests were collected"

These 4 scenarios exhibit obvious problem patterns: irrelevant content, minimal content, placeholder text, empty test results. Technically, **none of these require LLM-level semantic understanding** — keyword matching, length checks, regex matching, and stdout parsing would all suffice.

Phase Gate missed them not because they are hard to detect — but because its check items (file exists, exit code 0) are orthogonal to content quality.

### Why correct scenarios were rejected

L1-L3 share a common pattern in their rejection reasons:

- L1 output was a snippet from an article about loop engine internals → model judged "did not generate a complete research brief file"
- L2 output included a title and structural description, annotated as "~2000 words body text" → model judged "only provided title and summary description"
- L3 output showed chapter titles and content previews → model judged "only output one chapter's placeholder content"

A notable detail: L1-L3's outputs were presented as **content excerpts** (simulating "file has been generated"), not complete files. Agent B interpreted this form as "incomplete" rather than "content correct but shown as excerpt."

L4 passed all 3 runs because the test execution result (stdout: "42 passed, 0 failed") is a **self-contained complete signal** — unlike file content excerpts that carry ambiguity about completeness.

### The precision-recall tradeoff

Comparing this result with the earlier experiment (Experiment E, [Part 2](blog-agent-determinism-illusions-2.en.md)):

| Model | False Positive | False Negative |
|-------|---------------|---------------|
| qwen3:0.5b | 25% | 50% |
| gemma3:4.3b | 25% | 50% |
| GLM-5.2 | 0% | 75% |
| **deepseek-v4-flash (this experiment)** | **0%** | **75%** |

deepseek-v4-flash lands at the same point as GLM-5.2: 0% false positive, 75% false negative. This is consistent with the pattern observed in Experiment E — **stronger models in review tasks do not improve across all metrics. Instead, they shift along the precision-recall curve toward the precision end.**

A plausible explanation: more precise semantic understanding gives the model a sharper boundary for what constitutes "satisfying the requirements." The sharper the boundary, the more willing the model is to reject outputs that appear insufficient. The result: fewer false positives (harder for garbage to slip through), but more false negatives (more marginally-correct outputs get rejected).

### Artifact discussion

L1-L3's rejection results are partially affected by how the output was presented — providing complete file content instead of excerpts might have changed the judgment. However, this raises a more general question:

In real Agent workflows, the reviewer (Agent B) also sees Agent A's output — not a human-annotated ground truth. If Agent A's output varies in form and completeness (which is common in auto-generated content), the calibration problem the reviewer faces is real, not just an experimental artifact.

## Summary

P1 experiment data shows:

1. Adversarial verification (single Agent B) reduced Phase Gate's 50% false positive rate to 0%
2. The cost: false negative rate rose from 0% to 75%
3. This result is consistent with the precision-recall tradeoff pattern from earlier experiments — the stronger the model, the higher the precision but the lower the recall
4. The 4 garbage scenarios suggest that code-level content quality checks (length, format, keywords) could cover most of these cases without relying on LLM judgment

Next step (P2) will test Agent B's output stability — whether the 75% false negative rate from this single experiment is reproducible or has significant random variance.

---

*Experiment code: `agent-determinism-illusions/scripts/adversarial-verify-p1.py`*
*Full series: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions)*
