# Reply draft — Xiao Man on P-level fixed vs dynamic / cheap pre-check (Part 7)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  
证据：Part 7 Update (2026-07-27)  
+ `scripts/probe-cascade-routing-test.py` → `results-v2/probe-cascade-routing.json`  
+ `scripts/probe-artifact-shape-routing-test.py` → `results-v2/probe-artifact-shape-routing.json`

**状态：** 正文已写入 `blog-agent-determinism-illusions-7.{en,zh}.md`；下面可直接贴 DEV.to 评论。若 DEV.to 上的 Part 7 尚未同步本 Update，先改帖再回，或回复里带脚本/结果路径。

---

Xiao Man — yes on the phase-transition read, and thanks for the routing question. I ran both forks on the same checksum fixture.

**Fail-signal / cheap pre-check:** P1 PASS → accept; P1 FAIL → jump to matched Pi. On T4 that drops catch to **23%** (same floor as under-spec P1) with **22/31** cross-field misses — budget / port-unique / fingerprint breaks often *pass* the shallow probe, so the cascade never fires. It also looks cheaper (~7 vs ~30 ops). That is the trap that pairs with “over-spec = waste”: under-spec saves cycles on the blind spot. Cascading on PASS up to schema-matched depth recovers catch, but that ceiling *is* fixed matched depth — not a savings policy.

**Artifact characteristics:** infer depth from keys (`budget` → P4, `services[]` → P3, …). On honest artifacts, catch matches fixed task-type routing (100% T1–T4). Strip the depth cue or inject a decoy nest and it breaks: cue-erase → **82%** (P4-only fingerprint misses); T2+decoy services → **0%** catch at ~5× the ops. So shape can set P-level only as an *honest schema proxy* — still matched-depth routing, not “deepen when P1/P2 signal.”

**Direct answer:** in this setup P-level is fixed by schema depth (task type, or a non-writable shape proxy for it). A cheap P1/P2 pre-check that routes deeper only on fail does **not** catch the cross-field population — those are exactly the failures the pre-check does not signal.

Wrote both runs into Part 7 Update (2026-07-27). Same caveats as the dual-axis: fixture, structural half, instrumented ops.

Scripts / results:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/probe-cascade-routing-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/probe-cascade-routing.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/probe-artifact-shape-routing-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/probe-artifact-shape-routing.json

Part 7 (local body; sync DEV.to Update if the live post is behind):
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-7.en.md
Thread:
https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513

---

中文备忘（一般贴英文评论即可）：
- 失败才加深：T4 捕获 23%，跨字段漏 22/31，还更便宜 → 陷阱
- 按产物形状：诚实线索 ≈ 固定匹配；删线索 / 诱饵嵌套会欠规格或误路由
- 结论：P 跟 schema 深度；不是跟浅层失败信号
- 已写入 Part 7 Update 2026-07-27；回复末尾带 GitHub 链接
