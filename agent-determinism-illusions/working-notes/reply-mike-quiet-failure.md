# Reply draft — Mike Czerwinski (quiet failure: shadow ∈ (0, enforce))

Thread: https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g
Prior: Part 15 dual-line ops (`dual-line-ops-sim.py`)

Mike's three moves (2026-07-29):
1. Stratified-vs-temporal is the actual finding (axis naming, not SHIP calls).
2. Quiet failure gap: shadow=0 is loud and easy; shadow ∈ (0, enforce) is
   hard — vacuous check never fires, dual-line ships compromised rank.
3. Order under budget as the universal — generalizes past escalation triggers.

Verified the gap on real df_proxy data via controlled staleness injection.
Current fallback rule (dual-line-ops-sim.py line 346):
```python
if shadow_c == 0 and oracle > 0:
    return enforce, "fallback_arrival"
return shadow_c, "shadow"
```

Pure-math scan (`partial-stale-shadow-test.py`): 81 cells across (shadow,
enforce) ∈ {0..8}², 28 in quiet-gap regime, mean vacuous-vs-noninferior
loss 3 catches/cell, max 7. Conceptual proof.

Empirical stress (`partial-stale-injection-test.py`): stratified class
stream (n=164, k=8, enforce=8, oracle=8, pure R_hist=8). With prob p per
item, replace R_hist score with prior — simulates partial calibration loss.

| p    | shadow mean | gap fraction | vacuous vs noninferior loss |
|------|-------------|--------------|------------------------------|
| 0.0  | 8.00        | 0%           | 0                            |
| 0.3  | 7.90        | 3%           | 3.00                         |
| 0.5  | 7.17        | 40%          | 2.08                         |
| 0.7  | 4.73        | 93%          | 3.50                         |
| 0.8  | 3.17        | 100%         | 4.83                         |
| 0.9  | 2.70        | 97%          | 5.21                         |

At p=0.8 every draw lands in the gap regime. At p=0.9 vacuous ships a
compromised shadow while enforce would have caught ~5 more per draw.

Fix is one line: change `shadow_c == 0` to `shadow_c < enforce`. Noninferior
rule strictly dominates on gap cells, ties at corners.

Mike's gap is real and quantifiable on this fixture when ranker partially
loses calibration — not just conceptual.

Landing: collected with three other reader-driven revisions (Mike HHI
pair-join, Tom Jones position-adjacency, Xiao Man shape-routing rename_keys)
in Part 16 — `blog-agent-determinism-illusions-16.{en,zh}.md`, `published:false`
on dev.to as of 2026-07-29. Reply paste below uses script links only; add
Part 16 dev.to URL when it goes live.

---

## English (paste to DEV.to)

```text
Three cuts land.

1. Stratified-vs-temporal as the load-bearing axis — agree. Stratified tests "does the table generalize across items from the same distribution"; temporal tests "is the distribution still the one the table was calibrated to." R_hist catching 8/8 on stratified diluted and 0/8 on temporal diluted is the signature you're naming — a gate suite that only shuffles data is structurally blind to staleness no matter how many folds it runs.

2. Quiet failure — named a real gap. Current rule is `shadow==0 ⟹ fallback`. On the existing fixture pure R_hist lands at corners (0 on temporal diluted, 8 on stratified class), so the gap doesn't show natively. To stress the in-between I injected controlled perturbation into R_hist scores on stratified class stream (n=164, k=8, enforce=8, oracle=8, pure shadow=8): with probability p per item, replace its R_hist score with prior — simulates partial loss of calibration.

Results across 30 draws per p:
  p=0.3: shadow mean 7.90, 3% of draws in quiet-gap regime (shadow ∈ (0, enforce))
  p=0.5: shadow 7.17, 40% in gap
  p=0.7: shadow 4.73, 93% in gap
  p=0.8: shadow 3.17, 100% in gap
  p=0.9: shadow 2.70, vacuous loses 5.21 catches/draw vs noninferior rule

So when the ranker partially drifts, the vacuous rule ships a compromised shadow while enforce would have caught more. Fix is one line: change `shadow==0` to `shadow < enforce`. Noninferior rule strictly dominates on the gap cells, ties at the corners. (Pure-math scan over the 81-cell (shadow, enforce) grid confirms the same shape: 28 cells in gap regime, mean vacuous-vs-noninferior loss 3 catches/cell, max 7.)

Your "ranking true misses below distractors" already showed the shape at the loud corner — R_hist 8 → 0 on temporal diluted. The stress test fills in the quiet middle: when R_hist drifts to anywhere in (0, enforce), the current fixture doesn't natively exercise it but production rankers will occupy that cell whenever they partially drift.

3. Order under budget as the universal — agree this generalizes furthest. Named it for DF escalation traffic; same shape applies to any ranked queue under a hard review cap. Budget names who gets seen; ranker-stale-or-not determines whether being seen helps.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/partial-stale-shadow-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/partial-stale-injection-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/partial-stale-injection.json
```

---

## 中文备忘（不发）

- Mike 三个 cut 都准：stratified vs temporal 是 axis 命名，quiet failure 是真 gap，order-under-budget 是 universal
- quiet gap 已 empirical 量化：在 stratified class stream 上注入 R_hist 扰动
  - p=0.3 起进入 gap regime（3% draws）
  - p=0.8 时 100% draws 都在 gap
  - peak: vacuous 比 noninferior 少 catch 5.21/draw（p=0.9）
- Fix 是一行：`shadow_c == 0` → `shadow_c < enforce`
- 现有 fixture 在角落（pure R_hist 全 0 或全 8），需要 stress 才能暴露 gap
- Production rankers 会自然落入 partial-stale 区间（drift 不是 0/1 的）
- 挂 3 个链接：scan 脚本 + injection 脚本 + injection 结果
