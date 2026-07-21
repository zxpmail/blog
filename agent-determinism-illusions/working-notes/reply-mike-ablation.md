# Reply draft — Mike Czerwinski follow-up (ablation + 95.8% concentration)

Source: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f  
Date: 2026-07-22  
Evidence:
- `scripts/results-v2/external-signal-ablation.json`
- `scripts/results-v2/confidence-vs-miss-concentration.json`
- Commands: `python external-signal-sampling-test.py --ablation-only`  
  `python confidence-vs-miss-concentration.py`

---

## English (paste to DEV.to)

You're right on both — and the numbers cut against the cleaner story.

**On the ablation.** Same long-tail-burst / medium fixture as the published 28.5% → 48.8% comparison (`external-signal-sampling-test.py --ablation-only`, 1000 trials). Singles and pairs, 10% floor kept:

| Arm | Catch |
|-----|-------|
| P6 (cross-prompt) | 28.4% |
| `classifier_disagree` alone | **24.9%** |
| `barely_passed` alone | 20.5% |
| `route_changed` alone | 17.5% |
| `input_unusual` alone | 16.0% |
| best pair **without** CD | `route+barely` **28.0%** (≈ P6) |
| best pair **with** CD | `CD+barely_passed` **35.5%** (1.25× P6) |
| Full four | 48.7% |

So: CD alone does **not** get most of the way from 28.5 to 48.8 — it doesn't even clear P6. It *is* the best single signal, and every pair that beats P6 includes it; drop CD and the best remaining pair collapses back to ~P6. The partner doing real work next to it is `barely_passed` (a margin/threshold signal, cheaper than L0/L1-vs-L2). Cross-layer earns a seat; it does not earn solo credit for the 1.7×. The bundled result stands; the causal story in §4 needs that caveat. I'll put the ablation table on-page rather than leave it in a script.

**On the 95.8%.** Not a balanced 3×20 panel. Of 96 MISS runs: **qwen3-0.5b = 77 (80.2%)**, gemma = 16 (16.7%), deepseek = 3 (3.1%). Top scenario DS4 alone is 34.4%. So the headline fraction is partly "qwen misses a lot, and when it misses it's confident."

What *does* hold as a shape, conditional on miss: qwen 75/77 (97.4%) and gemma 16/16 (100%) at conf ≥ 0.9. deepseek barely misses (1/3 high-conf). I shouldn't design an escalation trigger as if 95.8% were a stable property of "models in general" on this set — it's a property of the miss-mass we actually have, which is qwen-heavy. Script dump: `confidence-vs-miss-concentration.json`.

Net: publish the ablation and the concentration caveat the same way as the 5.6× correction — on-page, not off-page. Done in Part 6 §4 Update (2026-07-22): ablation table + qwen-heavy caveat; the "isolation queued" line is closed. Thanks for forcing both.

---

## 中文备忘（不发）

- 消融结论：CD 单独 24.9% < P6 28.4%；必与 barely_passed 搭档才到 35.5%；四信号捆到 48.7%。跨层有必要、无独占功劳。
- 95.8%：80% MISS 来自 qwen；形态（高置信）在 qwen/gemma 条件成立；不能当三模型通用律。
