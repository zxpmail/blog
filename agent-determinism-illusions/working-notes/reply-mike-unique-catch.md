# Reply draft — Mike Czerwinski (unique catch / fixture retention)

Source: Part 6 DEV.to follow-up (2026-07-22)
Evidence: `scripts/results-v2/external-signal-ablation.json` → `unique_catch`
Command: `python external-signal-sampling-test.py --ablation-only`

---

## English (paste to DEV.to)

You're right — and that was the missing column.

Same burst / medium / 10% floor fixture. Coupled Uniform draw across the four solo arms: **unique catch** = defective caught by arm *i* that none of the other three would have caught alone.

| Signal | Solo CR | Unique CR | Unique / solo |
|--------|---------|-----------|---------------|
| `classifier_disagree` | 25.0% | **5.8%** | **23%** |
| `barely_passed` | 20.4% | 3.2% | 16% |
| `route_changed` | 17.4% | 1.9% | 11% |
| `input_unusual` | 16.0% | 1.4% | 9% |

So the story that looked like "CD is the weak link vs P6 (24.9 vs 28.4)" flips on the quantity that actually predicts stacking: CD is the largest unique catcher (~3× route, ~4× input). Solo CR undersells it; a fixture that drops by solo performance would cut the load-bearing arm. Unique fire tells the same shape (CD 19.6% vs route 6.5% / input 4.9%).

Publishing unique catch next to the solos and combos now — on-page in the ablation Update. Thanks for naming the metric; the table without it was half the argument.

---

## 中文备忘（不发）

- Mike：solo 看不出边际；要发 unique catch
- 结果：CD 独有 5.8% 最高；solo 弱、组合承重、独有也承重——三者一致留 CD
