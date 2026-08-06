# Reply draft — Max Quimby (Part 8 / escalation stack)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne  

Thesis (enterprise): layer-by-layer intercept → combined policies → humans last and rare → no silver bullet.

Knives (support, not the thesis):
1. `escalate-threshold-calibration-test.py` — yield-adaptive ≈ finds average rate
2. `high-risk-direct-human-test.py` — labeled expensive class first
3. `residual-strategy-4to6-test.py` — T2 / Alex / dual-line @ hard budget K

@ 15% budget: dual-line best overall miss; hr_first best HR; T2/dual best rev-class.

---

## English (paste to DEV.to)

```text
Agreed on the DPI cut — and on the probe. Filesystem is another surface the same agent can write; once a check is load-bearing it is a Goodhart target. Named-evasion is a ratchet, not a closure. The interesting failures stay unenumerated.

In enterprise use the shape is not “pick the clever threshold.” It is layer-by-layer intercept, and the policies have to run as a *combination*: deterministic gates on what you can name, then tripwires / signal rank / dual-line on the residual packet, and only then humans. Humans are the most expensive layer — they sit at the end, in as few places as possible. There is no silver bullet. Stability, accuracy, and efficiency come from that stack discipline, not from one channel or one adaptive rule pretending to finish the job.

Your escalation question is exactly the last opening. I treated it as a hard human budget (who gets the K slots), not a magic number:

- Yield-adaptive vs fixed 10%: helps a naive fixed line when the residual is dirty; vs the same average spend, the extra gain collapses. It mostly discovers the right average rate — it does not close unenumerated miss.
- High-risk direct-to-human at matched budget: HR miss collapses (~0.83 → ~0.15). If budget ≈ HR share, ordinary residual starves — the honest cost of not auto-passing the expensive class.
- Same K: T2-first, Alex signal-rank, dual-line rank all beat uniform. At 15% budget dual-line is best overall (~0.52 vs 0.87); T2/dual best on reversal-class miss; hr_first still best when the expensive class is labeled; Alex is the dirt rank when you lack that label.

So: combine the gates; spend the scarce human queue on the packet you have already measured as expensive; do not ask calibration to replace the human layer. No silver bullet — that is the production answer.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/escalate-threshold-calibration-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/high-risk-direct-human-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/residual-strategy-4to6-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/residual-strategy-4to6.json
```

---

## 中文对照（立场，可贴或不贴）

```text
企业里不是找一道聪明阈值，而是一道一道拦截，而且必须组合：能点名的进确定性闸门，残差再用绊索/信号/双线排序，人工只放最后、尽量少。人工最贵。没有银弹——稳、准、省来自这套栈纪律，不是某一个信道或某一种自适应假装收官。

你问的升级线，就是最后那个开口。我按硬预算（K 个名额给谁看）量了三刀：yield 自适应多半是在找平均抽检率；高风险整类进人在同预算下猛压贵洞；T2 / Alex / 双线在同一 K 下都赢均匀抽检，各盯不同的漏。组合闸门，把稀缺人工砸在已量过的贵包上；别让「校准」代替人工层。没有银弹——这就是生产答案。
```
