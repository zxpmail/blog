# dev.to 回复草稿 — 2026-07-08

## 回复一：@renezander.com — Theorem 2 (Data Processing Inequality) + L0e 验证

**目标文章：** Part 1 或 Part 10 评论区
**主题：** Compliance Gap 实验验证 Theorem 2，L0e 与 skillgate 的互补关系

---

Hi René,

You were right about Theorem 2. I ran the experiment.

Four test files — one normal implementation, one TODO stub (full function bodies but all TODO), one structurally perfect but semantically missing the target (a cache layer with get/set/invalidate but no write-invalidation as the task required), and one comment-module (entirely JSDoc/TODO with no real code).

The L0e Re-Stat check (based on nexus-lab-zen's zero-verified=RED design) caught the comment-module at zero cost — 4 red-zone indicators triggered (future-tense density 6.9%, comment ratio 72%, 4 meta-descriptions, 2 stub locations). But the structurally perfect compliance gap? Passed L0e clean. Passed L2 with an API_PARSE_ERROR — the LLM itself couldn't decide whether the output satisfied the requirement.

This is the Data Processing Inequality in action. A file with correct function signatures, proper class structure, and all CRUD methods — but missing the one write-invalidation path the task required — is textually indistinguishable from a correct implementation to any observer, LLM or human.

I wrote up the full comparison with your skillgate design in `compliance-gap-test.md` in the repo. The key finding: L0e and skillgate are complementary, not competing. L0e catches re-stat patterns (future-tense density, stub code, social-signaling) at the agent-loop level for near-zero cost. skillgate catches the things L0e can't see — contract violations, secret leaks, test failures — at the CI/pre-commit level outside the loop.

Together they cover most of the compliance gap surface. But Theorem 2 means there will always be a residual that neither catches. I've accepted that as a design constraint rather than something to engineer away.

The updated directional failure appendix (v2, 20 scenarios, 600 calls across 3 models) also references your framework. Would welcome your read on it.

---

## 回复二：@Maria andrew — 仅基于已发表内容

**目标文章：** Part 2 评论区
**主题：** 精度-召回权衡

---

Hi Maria,

Exactly right — that's the cleanest summary of the Part 2 finding. Stronger models filter garbage better, but they also reject valid work at higher rates.

The interesting property is that this tradeoff appears structural, not tunable. Prompt adjustments (strict vs lenient) shift the operating point along the curve, but they don't break out of it. The root cause is that "does this output satisfy the requirement?" is genuinely underspecified for many real agent outputs. A model that reads deeper into the semantic gap will flag ambiguity that a shallower model glosses over — which is correct behavior for catching garbage, but produces false rejections on valid-but-imperfect outputs.

One direction this points toward: instead of optimizing the single LLM judge, route the easy cases away from it. Catch obvious garbage with patterns and obvious passes with length/format checks. The LLM then only sees the residual where the tradeoff is inherent — and those are cases that would need human review either way.

---

## 回复三：@Dipankar — "Divergence Is the Signal" + 新 DF v2 数据

**目标文章：** 相关评论区
**主题：** Divergence 作为控制信号的实现 + v2 实验更新

---

Hi Dipankar,

Your "divergence is the signal, not noise" insight is now implemented in forge-verify's L3 divergence detection:

```
if max(PASS, REJECT) / N < 0.8 → mark as UNCLEAR → human review queue
```

No majority voting. Split = escalate. The data from P3 confirmed it — 4 split scenarios, 3 of which majority voting got wrong.

I also expanded the directional failure experiment to 20 scenarios × 3 models × 600 calls. Most scenarios had consistent judgments across N=15 runs, but the ones that didn't (DS4 on deepseek, V2) are exactly the edge cases where models struggle — which aligns with your framing: inconsistency across runs is itself diagnostic.

The full write-up with v2 data is in the updated appendix of Part 10. Would love your take on the expanded subtle-DF results.

---
