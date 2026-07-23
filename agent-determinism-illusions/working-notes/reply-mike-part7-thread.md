# Reply drafts — Mike Czerwinski (Part 7 thread)

Post on: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f  
After Part 7 is live on DEV.to, replace “Part 7 §5” with the live URL.

---

## On the inverted trigger / two arms

```text
Agreed — two arms, not one fix. T1/T2 are the recurrence arm (cheap, history-built). The unnamed population is confidently-wrong-and-never-caught-before; that needs a source that doesn't share the judge's priors. Ablation already showed classifier_disagree alone is not that arm (25.1% < P6 28.4% on the sampling fixture). Wrote the fork into Part 7 §5 Update; Part 13 is the closest existing thread on out-of-channel checks.
```

---

## On the checksum test

```text
Pinning that before building is right. Out-of-channel ≠ differently primed LLM. The test is: can you state the probe's failure criterion without referring to the claim's reasoning — checksum-style. If evaluating the probe only means comparing it to the original story, it's still in-channel, just later. That also explains why the novelty arm stays open while recurrence is shippable today: real independence is scarce and usually domain-specific. Wrote the criterion into Part 7 §5 (2026-07-23 Update).
```

---

## On structural vs causal independence

```text
Yes — and the agreement-vs-correctness cut is the one I needed. Checksum framing is the right bar because it is falsifiable without the story; a probe you can only score against the original reasoning is grading agreement, not correctness. The case you name is now explicit in Part 7: “other data” that is structurally different but still downstream of the same collection pipeline can clear the same-channel test and still share a common cause upstream. Structural independence ≠ causal independence. “Recurrence buildable today” is T1/T2 on burned classes — no independence required. The hold-out probe checked the structural half only; it did not certify a common-cause shield.
```
