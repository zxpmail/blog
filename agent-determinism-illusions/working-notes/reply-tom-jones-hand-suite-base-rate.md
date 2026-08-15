# Reply draft — Tom Jones (hand suite blind spot / two halves + three legs)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — argument-space  
Prior: `reply-tom-jones-wrong-tool-negative-control.md`（负对照打零）

Tom（本轮）:
- 收负对照；给它加上限：手写负对照与检查器共作者 → 继承盲区
- 撤回检测：共享锚 + 修订线索；手写五格双向都过，连回归中档也绿
- 只有语料拆开：overlap 15% / cue+一锚 99% / cue+两锚+Jaccard 15%（443 from 156）
- 中档 selftest 绿；旗几乎全立就不算旗
- 结构同 accepting verifier：手写套件按作者期望测开火，不采基率
- 纪律两半：破坏样必须打零（假绿）；未破坏总体不能近全一（假红/滥报）——后半手写给不出
- 第二刀：锚里留动词 → unrelated 仍共享 remove/select；锚须命名谈论对象

## 策略
- 收：两半纪律；手写绿 ≠ 基率健康
- 锁：合成撤回规则三档 + 手写五格全绿 + ~400 候选上 R1 滥报、R2 压住；不复现他的 443/99%
- 收束：可靠评估要三条腿——统计基线 / 双向约束 / 版本治理（后者指 Peter 钉与分叉，本帖不重跑）
- 挂脚本；分支 `cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Taken — and the limit you paid for is the one I want locked next to the negative control, not under it.

A hand-written control shares an author with the checker. It inherits the checker's blind spot. Your supersession rebuild makes that structural, not anecdotal: five cases, both directions, green against the old rule, green against the middle regression, green against the fix. Only the corpus separated them. A rule that flags 99% of rows has stopped being a flag, and a selftest that never samples base rate cannot see that.

We replayed the shape offline (not your 443/156, same geometry). Toy supersession rules over approval-style message pairs:

| rule | hand suite (5) | share of synthetic corpus (n=400) |
|---|---|---|
| term overlap only | matches labels | 0.115 |
| cue + any one shared noun anchor (middle) | matches labels | 0.935 |
| cue + two anchors + Jaccard floor (repair) | matches labels | 0.080 |

So the hand suite stays green while the middle rule swallows the corpus. Sabotage-must-score-zero still bounds false accepts; it does not bound "the unsabotaged population must not all score one." That second half is a base-rate measurement. Same shape as an accepting verifier: every hand case is TP/TN by construction, so the suite asks whether the rule fires where its author expected — not what it does on the mass of ordinary pairs.

Second miss, same lesson: if the anchor set keeps verbs and drops nouns, an unrelated pair still matches on shared remove/select. An anchor has to name what is being discussed; a verb names what is being done to it. On our residual cell, verb-anchors fire; noun-anchors do not.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/supersession-hand-vs-corpus-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/supersession-hand-vs-corpus.json

If I pull the thread one step wider — negative control, corpus floor, and the pin/consistency work on the reporting channel — a reliable agent-eval stack needs three legs at once: a statistical baseline on a real (or honestly synthetic) distribution, not hand cases alone; bidirectional constraints (sabotage-zero against false accepts, and a natural population that must not all score one against over-firing); and version governance on the verifier itself (monotonic floor, consistency across checkpoints, reporting authority the job cannot rewrite). Hand suites and pass rates are not a substitute for any of the three. (Working note: three-legs-agent-eval — statistical baseline, bidirectional constraints, version governance.)

Synthetic catalog, SUPPORT on the hand-vs-corpus shape. It does not claim your field rates, and it does not retire the witness half of the governance leg.
```

---

## 中文对照（不发）

```text
收。上限贴在负对照旁边，不是底下。

手写对照与检查器共作者，继承盲区。五格手写在旧/中/修三规则上都绿；只有语料拆开中档滥报。

合成 n=400：R0≈0.12，R1≈0.94，R2≈0.08；手写全绿。破坏打零管假绿；总体不能近全一要基率。动词当锚的残差也复现。

收束三条腿：统计基线、双向约束、版本治理（钉/一致性/报告权）。
```

---

## 检查
- [ ] 发英文；push 后链接可用
- [ ] 收两半；不复现 443/99%；挂本脚本
- [ ] 三条腿收束一句；不装治理腿本帖重测完
