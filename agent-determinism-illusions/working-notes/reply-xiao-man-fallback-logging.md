# Reply draft — Xiao Man (fallback-with-logging / survival retirement)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  
Prior: `reply-xiao-man-anchor-relocation.md` (path-pass leak + survival matrix; open Q on narrow↔wide)

Xiao Man (≈ Jul 30–31):
- v1→v2 + inner `timeout_ms` leak = QED for boundary-leak audit; path-passing is a discipline
- "no anchor 8/8" is the production-relevant cell
- Resolve via **fallback-with-logging**, not voting: primary + parallel secondary, log disagreements, retire on unreal perturbations
- Checksum / cross-field identity: different cost profile; commit fixtures want cheap & mostly-right
- Let the survival matrix / logged data pick

Re-ran after pull (n=40, seed=7): path-passing claims PASS; survival counts unchanged 7/8 · 7/8 · 6/8 · 7/8.

Status: English paste below is the tightened landing (death-cell tiebreak + pipeline close). Ready to post.

---

## English (paste to DEV.to)

```text
The death-cell tiebreaker is the cleanest decision rule this open question lands on.

Rate alone can't break the 7/8 three-way tie — that's a real result. synonym_list as primary because it dies only on out-of-declaration rename (exactly the failure the declaration review catches anyway): the gap in the anchor maps to the place where a human check already exists. Not choosing the "best" anchor — choosing the one whose blind spot is cheapest to cover.

Secondary reinforces that. structural dies on shape-clone, a different and more expensive failure mode, so it earns the parallel-probe seat. cross_field at 7/8 with the P7 inner-rename death is real but too costly for always-on — keep it in the suite, off the commit gate.

On fallback-with-logging over voting: agreed. Voting reopens the disagreement-routing problem this thread started with. Logging disagreements while keeping one gate in charge turns the secondary into telemetry without diluting accountability.

Pipeline: declare → path-pass every renamed key (outer and inner) → primary + secondary with disagreement logs → retire against real traffic. That last step is the one most people skip. Anchors that look essential in the mutation suite may never fire in production; anchors that fire constantly may only be catching perturbations the codebase never generates.

Data picks; philosophy doesn't.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/declaration-anchor-survival-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/declaration-anchor-survival.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/working-notes/boundary-leak-detector-rule.md
```

---

## 中文备忘（不发）

- 死亡格破 7/8 三平局；主锚 synonym_list，次锚 structural；cross_field 留套件
- 注意：矩阵里 cross_field 是 7/8（不是 6/8）；cardinality 才是 6/8——原稿「6/8」已改
- fallback+日志，不投票；retire against real traffic 是收束
- 挂 survival 脚本 + JSON + boundary-leak note；不挂未发布 Part 17
