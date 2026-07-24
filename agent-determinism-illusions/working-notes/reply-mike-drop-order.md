# Reply draft — Mike Czerwinski (drop order / mix stress-test)

Source: Part 6 DEV.to thread follow-up (2026-07-23)
Prior: `reply-mike-unique-catch.md` (published unique column)
Evidence: `scripts/results-v2/unique-catch-mix-sweep.json`
Command: unique-catch only, 3×3 (dist × quality), trials=400/cell

Mike's cut: unique/solo share ranks the prune; drop `input_unusual` first, not CD; stress another burst/medium mix before locking.

---

## English (paste to DEV.to)

```text
Agreed — the ordering is the actionable cut, and solo vs unique really are different questions.

Stress-tested the same coupled-Uniform unique-catch definition across a 3×3 (error dist ∈ {uniform, burst, mixed} × signal quality ∈ {low, medium, high}, 400 trials/cell, 10% floor). Unique-CR rank was identical in every cell:

classifier_disagree > barely_passed > route_changed > input_unusual

So if the four-signal set shrinks: input_unusual first, CD last. CD's unique/solo share stays ~2.5–3.0× input_unusual's (published burst/medium was 23% vs 9% ≈ 2.6×). On this fixture family the extremes agree with solo CR; the load-bearing column is still unique catch — the arm that looked weak vs P6 alone is the one you'd keep.

Your co-occurrence caveat still blocks a hard lock: this sweep varies burst clustering and TP/FP levels, not induced co-fire correlation between signals. A correlated-defect fixture could reorder the middle (route vs barely). Not treating the prune as locked until that arm exists — or a production trace replaces the sim.
```

---

## 中文备忘（不发）

- Mike：unique share 定裁剪顺序；先砍 input；换 mix 再锁
- 3×3 全稳：CD 顶、input 底；CD/IU share ≈ 2.5–3.0×
- 诚实边界：独立点火模型未测共现相关；中段可能翻，两端先不锁死
