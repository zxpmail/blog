# Reply draft — Mike Czerwinski (induced co-fire / co-occurrence labels / dose)

Source: Part 6 DEV.to thread follow-up (after 3×3 mix-sweep reply)
Prior: `reply-mike-drop-order.md`
Evidence:
- `scripts/results-v2/unique-catch-cofire.json` (+ `-pairs.json`)
- `scripts/results-v2/unique-catch-cooccur-labels.json`
- `scripts/results-v2/unique-catch-cooccur-dose.json`

Mike's cut: nine independent cells leave independence untested — force route∧CD co-fire; see if barely vs route reorders.

Arc run: (1) his named pair-force (2) all C(4,2) pairs (3) label→signature co-occurrence (4) dose-response π*.

---

## English (paste to DEV.to)

```text
Agreed — nine cells under independence was the wrong thing to call a lock. Ran the fixture you named, then pushed past it.

1) Forced pair (your cut). Same coupled-Uniform unique-catch, burst/medium, 400 trials/ρ. After the independent draw, force route_changed ∧ classifier_disagree = 1 on fraction ρ of *defectives* (shared defect class, injected directly). Joint among defectives 0.13 → 0.82 as ρ goes 0→0.8. Unique-CR rank every ρ: CD > barely > route > input. Middle never swapped; extremes held. Unique *mass* collapses (shared fires eat unique catch) — order does not. Also swept all C(4,2)=6 forced pairs the same way: none reordered.
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/unique-catch-cofire.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/unique-catch-cofire-pairs.json

2) That still wasn't co-occurrence *labels*. Replaced pair-force with a generative stand-in: each defective draws a latent class label → signature set fires at p_sig=0.90. Under mike_half (π_route_cd=0.5), middle *does* flip: route > barely (tiny but stable at N=2000: 0.0166 vs 0.0164). Extremes still held. So pair-force alone was the wrong attack surface — label mass on your named class unlocks the middle.
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/unique-catch-cooccur-labels.json

3) Dose-response on that class: sweep π_route_cd ∈ {0, 0.05, …, 1}. π* ≈ 0.50 (anti-flicker). barely_route and cd_barely never flip middle on the same grid. At π_route_cd=1 extremes also break (route overtakes CD) — only under that extreme.
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/unique-catch-cooccur-dose.json

So: ends (drop input first / keep CD last) survive these sims; middle (barely vs route) is *not* locked once co-occurrence labels concentrate on route∧CD. On-page Update (repo; sync to DEV.to next):
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-6.en.md#update-2026-07-27-co-occurrence-unlocks-the-middle-ends-still-hold
Still not a production lock — π here is invented; a real trace's label mass is the next cut.
```

---

## 中文备忘（不发）

- Mike 点名的单对强制共火：不翻序；六对全扫也不翻
- 换成共现标签生成式：mike_half 翻中段（微小但稳）
- 剂量：π*(route_cd)≈0.5；另外两类单标签不翻中段
- 两端大体稳；π=1 时 route 可顶掉 CD
- 中段不能锁；要真实 π
- 回复已挂 GitHub 结果 JSON + Part 6 Update 锚点（DEV 同步前用仓库链）
