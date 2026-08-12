# Reply draft — Tom Jones (instrumentation rung / empty-denominator collapse)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Commenter: Tom Jones  
Prior contact: runtime-channel-collapse reply (Aug 10, Channel Gap thread) — same predicate, structural form

What Tom is reporting:
- Theorem 2 measured in production: verifier read producer's text, returned `verified:true` for wrong answers on 5/8 caller-supplied shapes. Same channel → fabrication left no trace.
- Then they moved to cross-model (a genuinely different channel). Witness is selected by **BACKEND**, model is whatever that backend serves. Under 429, the rate limiter advances the selection loop, so the second opinion can be the drafter's own model answering twice. Cross-model silently degrades to self-agreement at request time — no error, no exception, no metric.
- Then they built a sampler measuring P(wrong | agreement) at 100% sampling. Collected zero rows for four days while serving 113–209 req/day. Cause: empty denominator. Nothing counted the events reaching the gate, so starving and broken looked identical from outside.
- Tom's proposed rung: instrumentation. Two request-time questions — "is the evaluator still the one you configured?" and "would anything on the box tell you the moment it stopped being that?"

Map to the article:
- 5/8 = Theorem 2 (§5) field version. Same shape, measured instead of argued.
- Runtime collapse under 429 = the predicate the prior runtime-channel-collapse reply named (`witness_fingerprint ≠ drafter_fingerprint`, refuse on mismatch). Tom now has the production trace.
- Empty-denominator = the new contribution. Same DPI shape one layer up: sampler reports green when the failure signal never reached it. "Zero rows read as healthy" is the monitoring equivalent of "agreement true" on a self-grade.
- Tom's two questions decompose cleanly: Q1 = per-request identity assertion (refuse). Q2 = per-window reachability alarm. Either alone collapses.

No new experiment — field confirmation + structural extension, not a challenged empirical claim.

---

## English (paste to DEV.to)

```text
The 5/8 lands as the measured version of the bound — same shape Theorem 2 predicts. Field data on caller-supplied shapes is the version of the argument I had only structural; useful.

The runtime collapse is the second-channel failure in production form: witness selected by backend slot, 429 advances the loop, self-grade reads as cross-grade. The move is the per-request predicate from the structural version — bind PASS to `witness_fingerprint ∈ configured set`, refuse on mismatch. You've got the production trace now; the predicate is what the trace shows was missing. The 429-advance detail is the part that stays invisible without it — agreement arithmetically true, metric green, no exception.

The empty-denominator rung is the genuinely new one, and the reason is that the same shape repeats one layer up. The sampler reading P(wrong | agreement) reports green when the failure signal never reached it — structurally identical to the verifier reporting green when the fabrication never reached the channel. "Zero rows read as healthy" is the monitoring equivalent of "agreement true" on a self-grade. The bound does not stop at the verifier; the same shape appears in the instrumentation above it.

So the rung is two predicates, one refused and one alarmed. Per-request identity: witness fingerprint ∈ configured set, refuse on mismatch. Per-window reachability: count gate-reachable events separately from sampled events, and alarm on `reachable > 0 && sampled == 0` (sampler drift) and on `reachable == 0` over the window (starvation reading as health). Your two questions are these exactly — the first is the assertion, the second is the alarm. Either alone collapses: assertion without alarm is a tree in an empty forest (sampler reads 0 rows and calls it healthy); alarm without assertion is a heartbeat (the box is fed, but the witness may already be the drafter).

One thing I'd be curious about from your case: when the reachability alarm fires, who is the channel to? The next collapse I'd expect is the alarm landing in a queue nobody reads, or being auto-resolved by a noise filter — the assertion works, the alarm works, green stays green because the alarm channel itself went dark. If you've seen that in practice, it would be the field version of the third collapse.

Tested the underlying invariant offline — writer-permission is the load-bearing axis, not the mechanism. Five configs, only the writer/key-holder varied: producer-written evidence PASSes fabrication (C1, DPI face); runner-written rejects (C2); HMAC-attested with producer lacking the key rejects (C3); **same HMAC mechanism with producer holding the key PASSes** (C4 control — isolates key secrecy from HMAC presence); post-sign tamper caught (C5). The per-request identity predicate above is the same invariant at the API layer — the witness fingerprint is the key the producer cannot forge.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/writer-permission-collapse-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/writer-permission-collapse.json
```

---

## 中文备忘（不贴帖）

- 5/8 = Theorem 2 实测版（结构 → 数据）；不重复论证
- runtime collapse：429 advance loop → self-grade as cross-grade；解 = 每请求见证指纹断言 + 失配拒绝（与 8/10 那条同谓词，Tom 这回给了生产侧轨迹）
- empty-denominator 是真新增：sampler 是 Channel A 读 Channel B；"0 rows 健康读" = 自评错题上 "agreement true"；DPI 不在 verifier 停步，向上一层同形复现
- 两谓词合一：每请求 identity 拒绝；每窗口 reachability 告警（reachable>0 && sampled==0 = sampler 漂移；reachable==0 = 饥饿伪装健康）。Tom 两问 = 这两谓词
- 反问：告警通道本身塌缩（队列无人读 / 噪音过滤器自动 resolve）—— 第三层 collapse 的现场版
- 实验：`writer-permission-collapse-test.py` 五刀全 PASS；C4 对照（producer 持 key）翻回 PASS——密钥占有关系承重，HMC 机制本身不承重
- 不引用未发表章节；不动已发文章
