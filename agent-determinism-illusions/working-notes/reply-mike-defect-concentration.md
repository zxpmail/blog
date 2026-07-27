# Reply draft — Mike Czerwinski (π as class concentration / histogram gate)

Source: Part 6 DEV.to thread (co-occur / dose follow-up)
Prior: `reply-mike-cofire.md`
Evidence:
- `scripts/results-v2/unique-catch-cooccur-dose.json` (π*)
- `scripts/results-v2/defect-class-concentration-histogram.json` (cheap gate)

Mike's cut: pair-force vs generative labels are different manipulations; π_route_cd = fraction of defects in one same-cause class; fragile only at high concentration; cheaper next step = histogram actual class concentration.

---

## English (paste to DEV.to)

```text
Agreed — the hair-flip locating the mechanism is the useful result. Pair-force still leaves each defective independently labeled, so from CD's seat a co-forced row looks like any other catch. The generative version changes *what the defective is* (a class whose signature is route∧CD), not just how signals respond — same surface co-occurrence, different manipulation.

That also makes π_route_cd a real-world question: what fraction of the defect population is one class where route and CD are both diagnostic of the same cause, versus each catching an unrelated slice. π*≈0.50 flips middle; π=1 breaks ends — fragile in a *narrow high-concentration* regime, not everywhere.

Cheaper step you named, on the taxonomy this repo already has (DF v2 MISS runs — not route_cd labels on the sampling sim, caveat load-bearing):

scenario_id histogram (N=96): max share = DS4 at 34.4%, HHI=0.18 — *below* the π*=0.50 fragile band.
model|scenario max = 15.6%.
(model axis max = qwen 80% — different axis, already on-page; not π_route_cd.)

So on this available miss taxonomy, concentration alone does not put you in the dose flip regime. Middle prune still isn't locked for a real external-signal trace — that needs a histogram where the class *is* "route and CD same cause." But the gate is cheap and it's clear: histogram first; only rerun the fixture if a dominant class sits near ~0.5+.

On-page Update:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-6.en.md#defect-class-concentration-mike
Dump: https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/defect-class-concentration-histogram.json
Script: https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/defect-class-concentration-histogram.py
```

---

## 中文备忘（不发）

- 承认机制：pair-force ≠ 生成式标签
- π = 同因类浓度；脆弱带在高浓度
- 便宜一步：DF MISS 按 scenario 直方图，max=34.4% < 0.50
- 仍非生产 route_cd 锁；但门禁清楚
