# Reply draft — Mike Czerwinski (before-the-fact test: adversarial worst case distinguishable from clean pass)

Thread: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f  
Prior: `reply-mike-one-instrument.md`（"Locked — same shape across those three"；ship rule = 别让一个仪表冒充它没在测的主张）

Mike（~3h，Re: Locked）:
- **Before-the-fact 是承重词**：把规则陈述一遍 ≠ 事前可应用；难的是在**失败之前**就知道一个仪器从未在测某物，不是之后
- **测试**：问仪器在对抗性最坏情况上报什么，检查该上报是否与干净通过不可区分
- **判据**：若 forensic-only 在能力坏掉时给不出「与沉默不同」的信号，它就没接上去抓这个失效——**事前可知**，而不是等一块撒谎的绿板事后发现

## 策略
- 无新实验（回帖规则：现场确认）；把 Mike 的测试映射到**本线程已在跑的 ρ-sweep** + **silence 极点负对照**
- 核心格：ρ=0.8 = 对抗性最坏情况（soft-couple 父失配）；forensic-only any=98% ≈ clean 100% **不可区分** → SHIP（撒谎板）；dual live=62% vs clean 99% **可区分** → HOLD
- silence 极点：absence-not-health——死门 catches=0 与 live-clean 同值；破坏样必须打零才能印健康
- 把 ship rule 的 before-the-fact 形式交给 Mike：只放行「对抗最坏上报 ≠ 干净通过上报」的仪表；不能区分 → forensic 可用，不是 health/interrupt 令状
- 链接用 main（shadow-promote + absence-not-health 两对；都已在 main）；不重贴整表
- 末尾反问现场数据（哪一列先动）

---

## English (paste to DEV.to)

```text
That's the applicability test, and it's the one the sweep has been running.

Adversarial worst case is the soft-couple row — parent mismatch, ρ=0.8. On the interrupt monitor, forensic-only (any-alert) reads 98% against 100% on the clean row ρ=1: a forensic-only dashboard ships. The dual column reads live-catch 62% against 99% clean: distinguishable, so it holds. The instrument that was never wired to catch the collapse is the one whose report doesn't move — and the sweep shows that going in, before any outage.

The silence pole is the same test at the other end. A replay gate whose heartbeat is its catch count prints catches=0 when dead and catches=0 when live-and-clean — identical silence. What makes it knowable going in is the negative control: sabotage must score zero before health may print. Three isomorphic cells — the quiet number collides, the planted sabotage separates.

So the before-the-fact form of the rule is yours: ship only instruments whose adversarial-worst-case report separates from their clean-pass report. If it can't separate, it's forensic — fine for reconstructing what happened, never a health or interrupt warrant.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/joint-failure-shadow-promote-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/joint-failure-shadow-promote.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/absence-not-health-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/absence-not-health.json

The sim can't hand you the field: at the first real failure your instruments actually see, which of the two numbers moved first?
```

---

## 中文对照（不发）

```text
这就是可应用性测试，而且就是这条线一直在跑的 ρ-sweep。

对抗性最坏情况是 soft-couple 行——父失配，ρ=0.8。中断监视器上，forensic-only（any-alert）读 98%，干净行 ρ=1 读 100%：forensic-only 的板会 SHIP。双列读 live-catch 62% vs 干净 99%：可区分，所以 HOLD。那个「从未接上去抓崩溃」的仪表，就是上报不动的那一个——而 sweep 让你**事前**（在出任何故障前）就知道。

silence 极点是同一测试的另一端。以 catch 数为心跳的重放门，死时印 catches=0、活着且干净也印 catches=0——与沉默完全相同。让它事前可知的，是负对照：破坏必须打零才能印健康。三个同构格——安静的数碰撞，种下的破坏把它们分开。

所以规则的 before-the-fact 形式就是你说的：只放行「对抗性最坏上报 ≠ 干净通过上报」的仪表。区分不开，它就是 forensic——用来复盘发生了什么可以，永远不是 health/interrupt 令状。

sim 给不了你现场：在你仪器真正看到的第一次真实故障里，两个数哪个先动？
```

---

## 检查
- [ ] 发英文（Part 6 线程，Re: "Locked" 评论）
- [ ] 链接 main（shadow-promote + absence-not-health 两对，已在 main）
- [ ] 无新实验；只引既有；不重贴整表
- [ ] 末尾反问现场数据；不把 SUPPORT 说成生产证明
