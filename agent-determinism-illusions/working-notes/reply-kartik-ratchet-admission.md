# Reply draft — Kartik N V J K (Part 8 / ratchet admission)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne

Kartik (~4h):
- René stuck: temp-0 hides variance, does not make judgment a fact
- Prefers routing unenumerated residual to human over auto-pass
- Open: how decide which named evasions → deterministic catches vs UNCLEAR?

## 策略
- 前半同意（文里已有）；后半用新实验答准入规则
- 不说「日志门未使用」（过卖）；人在最后、KB 只缩可二元已见图
- 挂脚本 + JSON；数字用整数百分比，与跑数一致

---

## English (paste to DEV.to)

```text
Yes on René — temperature-0 hides the variance; it does not turn a semantic call into a fact. And yes on the routing: silent pass is the failure mode the metrics never show, so unenumerated residual goes to human, not green.

The question you asked is the one Part 8 left open. The article has the ratchet shape ("named evasion → permanent catch; unenumerated → UNCLEAR") and a type split (numerical/format → C1, negation-sensitive → C2), but not an admission rule for *which* human-seen misses are worth encoding. I ran that as a small deterministic sim — 18 cases, three classes (binary / semantic-negation / DPI-silent), three policies after each human review of a miss:

| policy | miss | FP | KB | human | enumerable residual |
|---|---:|---:|---:|---:|---:|
| never encode | 100% | 0% | 0 | 12 | 5 |
| encode every miss | 67% | 33% | 6 | 8 | 0 |
| encode binary only | 83% | 0% | 3 | 10 | 2 |

Binary miss falls under encode-binary (100% → 60%) with FP still zero. Encode-all shrinks the residual further, but semantic FP hits 100% on the compliant negation cases — you paid for the extra catches with permanent false rejects. DPI miss stays 100% under every policy: if the deviation never surfaces in the evidence, no pattern the human writes into C1 can see it.

So the rule I trust: human last; after review, promote into the KB only what is binary-nameable. That is the knowledge-base loop — each admitted catch shrinks the *seen enumerable* set. It does not close the unenumerated gap, and it must not pretend semantic or silent deviations became facts because someone typed a regex.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/ratchet-admission-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/ratchet-admission.json
```

---

## 中文对照（不发）

```text
René 那刀同意——temp-0 只是藏方差，不把语义判断变成事实。路由也同意：静默放行是指标永远看不见的失效，未穷举残差给人，不给绿灯。

你问的正是 Part 8 留下的口。文里有 ratchet 形状和类型切分，没有「人审后哪些值得编码」的准入规则。我跑了个小确定性仿真——18 案、三类、三种策略（见上表）。

规则：人在最后；审完只把可二元点名的写进 KB。这是知识库环——每收一条缩「已见可穷举」。它关不上未穷举缺口，也不能假装语义/静默偏差因为写了条正则就变成了事实。
```

---

## 检查
- [ ] 发英文；挂 2 链接（脚本需已在 main/可访问的分支）
- [ ] 不说未发布 Part；不提「日志门未使用」
- [ ] 数字与 `ratchet-admission.json` 一致
