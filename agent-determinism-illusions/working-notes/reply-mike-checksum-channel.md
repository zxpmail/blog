# Reply draft — Mike on checksum / out-of-channel

Post: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f  
Evidence: Part 7 §5 Update (2026-07-23)

---

## English (paste)

Pinning that before building is right.

Out-of-channel ≠ a differently primed LLM. A second text read of the same evidence — even one asked to disagree — is still same-channel. The property that buys independence is re-deriving the fact on a path the original claim never touched (other data, structural invariant, re-computation).

Operational test: can you state what it means for the probe to be wrong **without referring to the claim's reasoning** — checksum-style? If the only way to score the probe is to compare it to the original story, it's still in-channel, just later in the pipeline.

That also explains the asymmetry you name: recurrence (T1/T2) is buildable today; novelty stays open because real independence is scarce and usually domain-specific — not because we haven't added a fifth prompt. Wrote the criterion into Part 7 §5 (2026-07-23 Update). Part 13 remains the closest existing thread on runner-not-reader probes.

---

## 中文备忘

- 出信道 = 可独立于主张说理的证伪准则（checksum 检验）
- 换 priming 的 LLM ≠ 出信道
- 复发臂可建；新奇臂开着是因为真独立稀缺，不是缺 prompt
