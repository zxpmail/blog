# Reply draft — Alexey Spinov on Part 6

Post on: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f

```text
You're right — and the tell was already in the 95.8% / 0.969 MISS concentration.

Divergence→human measures ambiguity. On qwen3:0.5b with real Strict/Balanced/Lenient over the DF set, 4/6 dangerous accepts were unanimous_pass — exactly the population that auto-passes under the Part 6 diagram. Divergence-only would have caught 2/6. Class tripwire ∪ inverse-unanimous (D+T2) caught 6/6.

Wrote it up as Part 13 of the series (not a silent rewrite of this post). Part 6 only gets a pointer Update. Thanks for naming the population mismatch so cleanly.
```

After Part 13 is published on DEV.to, replace “Part 13 of the series” with the live URL.
