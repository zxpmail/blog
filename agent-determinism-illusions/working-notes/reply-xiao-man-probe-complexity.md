# Reply draft — Xiao Man on probe catch vs complexity (Part 7)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  
证据：Part 7 §5 Update (2026-07-24) + `scripts/probe-complexity-dual-axis.py` → `results-v2/probe-complexity-dual-axis.json`

**状态：** 正文已写入 `blog-agent-determinism-illusions-7.{en,zh}.md`；下面可直接贴 DEV.to 评论。若 Part 7 已在 DEV.to 发表，发帖后把正文 Update 同步上去，再回评论。

---

Xiao Man — sharp framing. I ran it as two axes, not one: task/artifact depth (T1–T4) × probe depth (P1–P4), checksum-style only (pass/fail from schema+artifact, never from judge rationale).

**Catch, when matched:** 100% across T1–T4. On this fixture, out-of-channel catch *is* stable with task complexity — *if* probe depth tracks the schema.

**Catch, when under-specified:** collapses. Same T4 artifacts: P1 23% → P2 30% → P3 70% → P4 100%. Misses are exactly the nested/cross-field rules the shallow probe never looks at. Having “a checksum” is not enough; the invariant set has to cover the failure surface.

**Relative cost:** under an instrumented execution-ops model, matched cost_ratio stayed **below 1** all the way (≈0.23 / 0.14 / 0.20 / 0.19). No threshold where the probe became as expensive as the task representation. Deeper probes cost more; over-spec keeps catch while raising cost — waste, not safety. An *authoring*-cost model would cross earlier.

Wrote the matrices into Part 7 §5 Update (2026-07-24). Same caveats as the hold-out: fixture + structural half of the novelty bar, not production wall-clock, not causal independence. Thanks for forcing the dual-axis cut.

---

中文备忘（一般贴英文评论即可）：
- 匹配：T1–T4 捕获 100%
- 欠规格：T4 上 23→30→70→100
- 执行成本比未跨 1；写不变量的成本模型会更早跨
- 已写入 Part 7 Update 2026-07-24
