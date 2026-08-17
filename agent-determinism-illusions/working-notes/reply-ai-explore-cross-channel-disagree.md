# Reply draft — AI Explore (Part 8 / cross-channel disagreement signal)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne

AI Explore (~4h):
- Negation example (write.?invalidat × "not write-invalidation") keeps him up
- 42.9% → 100% from free-text → per-req: frame > model
- Add: track A vs B disagreement rate as its own signal; diverge = flag for
  evasion / broken check; agreement boring; spend review minutes on diverge

## 策略
- 前半同意（文里已有）；后半用轻实验答运维规则
- 锁 SUPPORT + 范围：双绿仍有 SC10，agreement 不全 boring
- 挂脚本 + JSON；不引未发布 Part

---

## English (paste to DEV.to)

```text
Yes on both — the negation cell is the regex-level DPI, and the frame jump is the one I want locked: same model, same evidence, per-requirement vs free-text, and the wall moves.

Your add is the ops rule Part 8 left implicit. The article maps where A and B diverge and combines with A∨B reject; it does not say "treat disagreement rate as the budget signal." I ran that on the Phase 1 dump (no re-sim):

| cell | n | P(non-compliant) |
|---|---:|---:|
| disagree (A⊕B) | 3 | 1.00 |
| agree_pass (both green) | 4 | 0.25 |
| agree_reject (both red) | 5 | 1.00 |

All three complementary catches (fabricated, stale, review-only) sit in disagree — precision 1.0 on this fixture. Density vs dual-green is 1.00 > 0.25, so review minutes spent on diverge beat minutes spent on agree_pass. Agree_reject is already caught by both channels; it does not need a conflict signal.

One scope lock, because "agreement is boring" is too strong for dual-green: SC10 (semantic gap) is agree_pass — both channels green, shared miss. Disagreement is high-yield for *complementary* failure; it does not replace the DPI / shared-miss tripwire. Spend on diverge; do not read dual-green as done.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/cross-channel-disagree-signal-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/cross-channel-disagree-signal.json
```

---

## 中文对照（不发）

```text
前两刀都同意——否定格是正则层的 DPI；帧跳跃也要锁：同一模型、同一证据，逐条 vs 自由文本，墙会动。

你加的是 Part 8 没写成运维规则的那句。文里画了 A/B 分歧并用 A∨B，没说「分歧率 = 人审预算信号」。我在 Phase 1 落盘上跑了（不重测）：分歧格精度 1.0、密度高于双绿；三个互补抓全在分歧里。双拒两边都已抓住，不靠冲突信号。

范围：双绿不无聊——SC10 语义缺口就在 agree_pass。分歧高产的是互补失效；替不了 DPI/共享漏绊索。分钟砸分歧；别把双绿读成办完了。
```

---

## 检查
- [ ] 发英文；挂 2 链接（push 后 main/分支可访问）
- [ ] 收 SUPPORT + SC10 范围
- [ ] 不重跑 channel-comparison
