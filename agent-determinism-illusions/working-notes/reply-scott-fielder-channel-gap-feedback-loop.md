# Reply draft — Scott Fielder (Part 8 / human queue as feedback loop)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne

Scott (~5h):
- Channel gap 像 eval 问题，实为 routing 问题（同意文义）
- 未穷举案例不随机、会聚类；跑几周 hybrid 后 human queue 呈现模式（新 evasion family、确定性检查没预料的 edge case）
- queue 是下一轮迭代的训练信号，不是 safety net；很多人把 human review 当 last-resort fallback
- 实操：resolution time 给每个 human-review case 打 reason code（哪怕粗糙）

## 策略
- 同意 + 用 `defect-class-concentration-histogram.json` 给聚类直觉量化（96 MISS，top-2 家族=恰好 50%，单档=80%）
- reason code = ratchet 的准入机制；但 `ratchet-admission.json` 给出准入规则的边界：只编码 binary-nameable（encode-all → FP 33%，semantic 类 100% FP）
- 诚实边界：queue 是有偏样本（只含路由到 human 的）；`evidence-feedback-loop-A/B` 显示 under-inv 无信号永不收敛——DPI-silent 类进不了 queue、打不上 code
- 不发未发布 Part（feedback-loop 实验挂脚本+JSON，不挂 Part 14）

---

## English (paste to DEV.to)

```text
Good framing — the routing point is the article's whole escalation argument, and "they cluster" is the load-bearing half, because clustering is what makes a feedback loop turn fast. I can put numbers on both halves now.

They cluster — confirmed. In the DF v2 directional-failure set (96 misses across 3 model tiers), the misses are the opposite of uniform: DS4 + DS9 account for exactly half the total (34.4% + 15.6%), DS4 alone is a third of the whole tail, and 80% of all misses came from one model tier. For your reason-code idea this is the good news: the top two families cover half your queue. You don't need to enumerate the tail to start mining it — you need two codes to be halfway there.

Reason codes are the ratchet's admission rule — with one refinement. The article's C1 is a ratchet: each named evasion becomes a permanent catch, so your resolution-time reason code is exactly how a human-seen miss becomes a named evasion. But *which* codes get promoted into the KB matters, and I ran that as a small deterministic sim — 18 cases, three classes (binary / semantic / DPI-silent), three admission policies:

| policy | miss | FP | KB | human reviews |
|---|---:|---:|---:|---:|
| never encode | 100% | 0% | 0 | 12 |
| encode every miss | 67% | 33% | 6 | 8 |
| encode binary only | 83% | 0% | 3 | 10 |

Take your instinct to its literal end — tag and encode everything — and you pay 33% FP overall, and 100% FP on the compliant semantic cases: you've traded silent acceptance for permanent rejection of valid work. The refinement the data forces: tag every case at resolution time (that's how you find the families), but promote only binary-nameable codes into C1. Semantic codes stay in the C2/human layer — a human's word-space label shouldn't harden into a regex that rejects valid output forever.

The boundary you can't mine your way past. The queue is a biased sample — it only contains what routed to human. The failures that don't surface never flag, so they never get a reason code. A feedback loop I ran makes this concrete: over-invalidation (the agent changed more than asked — a detectable state change) converges in 2 rounds — the loop learns the correct scope because there's a signal to mine. Under-invalidation (the agent didn't touch what it should have — no state change at all) runs 8 rounds stuck at 50% coverage and never converges. Absence leaves no evidence, so no resolution-time tag will ever see it. That's the DPI class again: your queue is the ratchet's fuel, and the ratchet closes the *seen* gap by design. The silent tail is exactly why the third prescription — a deterministic check on what is actually binary, or a receipt/argument-space channel that observes the side effect — has to live outside the queue, sampling the green path rather than waiting to appear in the red one.

So: the reason-code discipline is the right motor for the loop, and your clustering read is what makes it efficient. Just don't let the queue showing you patterns lull you into thinking it shows you all of them.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/defect-class-concentration-histogram.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/ratchet-admission.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/evidence-feedback-loop-A.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/evidence-feedback-loop-B.json
```

---

## 中文对照（不发）

```text
同意——routing 点是全文升级论证的核心，"会聚类"才是承重的一半，因为聚类决定反馈环转得有多快。现在能给你量化：

聚类——属实。DF v2 集 96 个 MISS（三档模型）完全不均匀：DS4+DS9 恰好占一半（34.4%+15.6%），DS4 单独就占整条尾巴三分之一，单档模型占 80%。对 reason-code 是好消息：前两个家族就覆盖半个队列，不需要枚举尾巴就能开始挖。

reason code = ratchet 的准入机制，但要加一条修正。C1 是 ratchet——每条点名变永久拦截，你的 resolution-time code 正是"人审过的 miss 变成点名"的机制。但哪些 code 进 KB 有讲究（18 案、三类、三种准入策略见上表）。把直觉推到极端——全部编码——付 33% FP，semantic 类 100% FP：拿静默放行换对合法工作的永久误拒。数据逼出的修正：resolution 时全打 code（那是找家族的方式），但只把 binary-nameable 的写进 C1。语义 code 留在 C2/人工层——人打的词空间标签不该硬成一条永久误拒合法输出的正则。

挖不过去的边界。queue 是有偏样本——只含路由到 human 的。不 surface 的失效从不触发，永远打不上 code。反馈环实验把这点说死：over-inv（改了比要求多的，有可检测状态变化）2 轮收敛；under-inv（该动的没动，无任何状态变化）8 轮卡在 50% 永不收敛。absence 无证据，任何 resolution-time tag 都看不见它。这就是 DPI 类：queue 是 ratchet 的燃料，而 ratchet 只关"已见"缺口。静默尾巴正是第三条处方（确定性检查可二元点名的、或 receipt/argument-space 观察副作用）必须活在 queue 外、去抽样绿道而不是等它出现在红道上的原因。

reason-code 纪律是对的马达，聚类读法让它高效。只是别让"queue 给你看模式"骗你觉得它给你看了全部。
```

---

## 检查
- [ ] 发英文；挂 4 链接（defect-class / ratchet-admission / evidence-feedback-loop-A / -B）
- [ ] 数字核对：96 MISS、DS4 33(34.4%)、DS4+DS9 48(50%)、qwen 77(80.2%)；ratchet 三策略表；feedback-loop A 8轮50%不收敛 / B 2轮收敛
- [ ] 不提未发布 Part 14；feedback-loop 只挂脚本/JSON
