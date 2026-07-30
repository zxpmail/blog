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

---

## English (paste to DEV.to)

```text
Agreed on both reads — path-passing as discipline, and "no anchor 8/8" as the production cell. Re-ran after sync: v1 rename false_reject 100% → v2 0%; survival still 7/8 · 7/8 · 6/8 · 7/8. Same envelopes.

Fallback-with-logging lands cleaner than voting. Voting reopens the disagreement-routing problem this thread started with; logging disagreements keeps one gate in charge and turns the secondary into a telemetry arm. That matches the matrix better than a quorum.

One sharpening on "pick the highest survival rate as primary": three anchors tie at 7/8 (synonym_list / structural / cross_field). Rate alone does not break the tie — the death cells do. For a per-commit fixture (cheap, mostly-right), I'd take synonym_list as primary: dies only on out-of-declaration rename, which is exactly the failure you want the declaration review to catch. Parallel secondary: structural (dies on shape-clone). Log when they disagree. Retire whichever dies on perturbations the codebase never generates. cross_field stays in the suite as a third probe, not a commit-gate — its P7 death (inner rename) is real but expensive to keep as the always-on path.

Checksum / semantic-identity path: same cost read as yours. Brittle under structural churn; fine as an audit arm, wrong as the default gate.

So: declare → path-pass every renamed key (outer and inner) → primary+secondary with disagreement logs → retire from the matrix against real traffic. Data picks; philosophy doesn't.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/declaration-anchor-survival-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/declaration-anchor-survival.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/working-notes/boundary-leak-detector-rule.md
```

---

## 中文备忘（不发）

- 同意：path-passing 是纪律；无锚 8/8 是生产题；fallback+日志，不投票
- 点明 7/8 三平局：用死亡格破平，不用「最高生存率」口号
- 生产默认：主锚 synonym_list，并行次锚 structural；cross_field 留套件不当 commit 门
- checksum / 语义身份：同意成本画像，不当默认门
- 不挂 Part 17；挂 survival 脚本 + JSON + boundary-leak note
- 未新开实验；若他追问再做「主+次并行记分歧」小探针
