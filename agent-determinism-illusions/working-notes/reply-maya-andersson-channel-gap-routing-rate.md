# Reply draft — Maya Andersson (Part 8 / routing rate + per-class agreement)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne

Maya (~9h):
- Routing divergence → human 是正确默认；DPI 让它成立（同意文义）
- **路由率本身是测量**：稳定 = 点名追得上 agent；攀升 = 未穷举残差在涨、确定性层掉队；要学的是趋势线不是事故
- **两信道一致率按失败类拆，不 pooled**：几乎总一致的检查 ≈ 一个检查加延迟，价值全在分歧；pooled 一致率可以平着，而你在乎的类悄悄归零

## 策略
- 不重复 AI Explore 线程（分歧=高精度升级信号 + SC10 范围锁已在 `reply-ai-explore-cross-channel-disagree.md`）；只接 Maya 的新点
- 点 2 用 escalation-population-mismatch（路由率是策略函数：D→1.6%/漏 97.9% 自动放行，T1→76%/全抓）+ confidence-vs-miss-concentration（92/96 高置信=分歧路由为什么瞎）+ ratchet（每条点名移除一类→路由率是竞速不是水位）+ rank-inside-stream（D 流 miss-starved）
- 点 3 用 cross-channel-disagree-signal 现成数据直接演示 pooled 掩盖（pooled 75% vs 按格拆）；再泛化到 defect-class-concentration（80% 单档 / 50% 双家族）
- 诚实：没有 routing-rate 时间序列实验，竞速 framing 是 ratchet 机制推出的概念贡献，不冒充纵向实验

---

## English (paste to DEV.to)

```text
Yes on both — routing divergence to human over auto-pass is the load-bearing default (Part 7 exists precisely because the earlier trigger auto-passed the confidently-wrong set, the failure mode no metric shows), and the DPI cut is why judge quality can't close it. Two additions from the data, one for each number you named.

On the routing rate as a measurement — yes, but it's a race, and it's policy-dependent before it's a signal. The rate is the difference between two other rates: how fast new unenumerated evasions appear, and how fast you name them into the KB. Each named evasion removes a class from the queue (ratchet admission: never-encode leaves 12 cases for human review, encoding drops that to 8–10). So a flat routing rate against a growing KB is not equilibrium — it's a moving frontier; you're naming at the same speed the agent generates. And the measurement has a precondition the escalation data exposes: the routing rate is a function of your policy before it's a function of the agent. Same data, three rates — route on divergence (policy D) and you send 1.6% to human and auto-pass 97.9% of the misses; route on reversal-class (T1) and you send 76% and catch 100%. A stable D-rate trend line reads as "the deterministic layer is keeping pace" while the miss population never enters the queue at all — and 92 of the 96 misses are high-confidence, which is exactly what divergence-based routing is blind to. So the trend line is only worth anything if the routing policy is frozen *and* the routed stream actually carries misses; on my fixtures the divergence stream is miss-starved (2 misses in 30 routed, vs 6 in the class stream). Track the rate — first verify the pipe carries the miss class.

On agreement rate by class — the pooled rate already fails in the Phase 1 data. Pooled agreement across 12 scenarios is 75% (9/12 both channels agree). Break it by cell:

| cell | n | non-compliant |
|---|---:|---:|
| disagree (A⊕B) | 3 | 100% |
| agree_reject (both red) | 5 | 100% |
| agree_pass (both green) | 4 | 25% |

The pooled number is doing exactly the hiding you predicted. The disagree cell — the class you'd mine for the pair's value — is 100% non-compliant (all three complementary catches: fabricated, stale, review-only). And your "two checks that agree almost always are one check with extra latency" holds for agree_reject (both channels redundant, 5/5), but the 25% of agree_pass is the one case the pair exists for: SC10, the semantic gap, both channels green on a violation. The shared miss lives inside the agreeing cell — invisible to any agreement-rate figure. Two channels that agree are one check with extra latency *except when they're both wrong*, and that exception is precisely the class pooled rates bury.

Which widens your last line: break out by class, but also by tier and evasion family. The miss data pools the same way — 96 misses look like one number, but 80% come from a single tier and two evasion families (DS4+DS9) are exactly half. Every pooled rate in this pipeline has a class hiding inside it that you can't see unless you slice.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/escalation-population-mismatch.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/cross-channel-disagree-signal.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/ratchet-admission.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/defect-class-concentration-histogram.json
```

---

## 中文对照（不发）

```text
前两刀都同意——routing 分歧到人、别自动放行，是承重默认（Part 7 存在正是因为旧触发自动放行了自信错集合——指标永远看不见的失效），DPI 切分说明 judge 质量关不上这口。对你点的两个数各加一个数据。

路由率是测量——对，但它是竞速，而且先是你策略的函数、才是 agent 的函数。率 = 新未穷举逃逸出现的速度 − 你把它点名进 KB 的速度。每点名一条就移除一类（ratchet 准入：不编码留 12 个人审，编码降到 8–10）。所以 KB 在涨而路由率平，不是均衡——是移动的前沿，你命名的速度和 agent 生成的速度持平。测量有个前提是 escalation 数据暴露的：同一份数据三个率——按分歧路由（D）送 1.6% 给人类、97.9% 的漏自动放行；按反转类路由（T1）送 76%、全抓。D 率平的趋势线读作"确定性层跟得上"，而漏群体压根没进队列——96 个漏里 92 个高置信，正是分歧路由瞎的地方。趋势线只在路由策略冻结、且路由流真的装着漏时才有意义；我的 fixture 上分歧流 miss-starved（30 里 2 个漏，class 流 6 个）。盯率，但先验证管道里装的是漏类。

一致率按类拆——pooled 在 Phase 1 数据里已经失败了。12 场景 pooled 一致率 75%（9/12 双通道同判）。按格拆（见上表）：分歧格 100% 非合规（三个互补抓全在这）；agree_reject 100% 但冗余；agree_pass 25%——那一个正是 SC10 语义缺口，双绿违例。共享漏住在同意格里，任何一致率数字都看不见它。两个一致的通道是"一个检查加延迟"，除非它们一起错——而这个例外正是 pooled 埋掉的类。

把你这句放宽：按类拆，也按档位和逃逸家族拆。miss 数据同样 pooling——96 个漏像一个数，但 80% 来自单档、两个家族（DS4+DS9）恰好一半。这条管道里每个 pooled 率里都藏着一个你不切就看不见的类。
```

---

## 检查
- [ ] 发英文；挂 4 链接（escalation-population-mismatch / cross-channel-disagree-signal / ratchet-admission / defect-class-concentration）
- [ ] 数字核对：D→1.6%/97.9% 漏放行、T1→76.4%/100%；92/96 高置信；跨信道 pooled 75%、disagree 3/100%、agree_reject 5/100%、agree_pass 4/25%(SC10)；96 miss 中 qwen 80.2%、DS4+DS9 50%
- [ ] 不重复 AI Explore 回复的分歧精度表；routing-rate 无纵向实验要诚实（竞速是 ratchet 机制推论）
- [ ] 不提未发布 Part
