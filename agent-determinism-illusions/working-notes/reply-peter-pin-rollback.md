# Reply draft — Peter (pin rollback / authorization history)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — The Third Predicate / argument-space  
Prior reply: `reply-peter-reporting-authority.md`（外钉 digest 收报告权）

Peter（本轮）:
- 外钉 digest 证明「曾批准」，不证明「仍是允许的最新」
- CI 可选旧但仍匹配的 pin → 不改 artifact 即可复活已知假绿 verifier
- 绑单调 harness/policy 版本或 append-only 透明日志检查点
- 拒低于仓库 recorded minimum 的版本
- 轮换须独立授权的 forward transition，不能只换 expected digest
- 外钉从 trusted reference → authorization history with rollback resistance

## 策略
- 收：完整性 ≠ 新鲜度；选型回滚 ≠ 改写 pin（正交于 R2）
- 锁：密封 minimum 关掉选型；minimum 若 CI 可写则同一通道再开（对应他的 independently authorized forward transition）
- 不装透明日志已实现；一句「checkpoint / 独立授权跃迁」收他的处方方向
- 实验四格全 SUPPORT；不报现场发生率
- 分支链接至 merge 前：`cursor/xiao-man-epistemic-distance-reply`
- 不提铁律包；不装 Part 已发

Branch links:
`cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Taken — and that edge sits past the digest pin, not under it.

An external digest proves the verifier was approved. It does not prove it is the newest acceptable one. If CI may pick any still-matching digest from an approval set, it can resurrect an older verifier with a known false-green channel without rewriting that artifact — only by selecting which pin to use. That is orthogonal to the writable-pin swap we already cut: rewrite changes bytes; rollback keeps bytes and changes which approved history entry is live.

We ran that shape offline on a failing observation (cache not invalidated). Two executable harnesses in the approval history: v1 always PASSes (false-green channel); v2 REJECTs on the failing obs. Repo minimum already at 2.

Digest-only allowlist: selecting v1 admits and adjudicates PASS — CI green on a failing obs. Selecting v2 admits and adjudicates REJECT. Same failing world; only the pin choice flips the green.

Digest + sealed minimum (≥2): selecting v1 is refused at admission (harness never runs). Selecting v2 admits and stays REJECT.

Negative control for "selection ≠ rewrite": mutate v1's bytes → digest leaves the approval set → REJECT. Unmodified v1 under digest-only still admits. Resurrection does not require touching the pinned artifact.

One residual that matches your forward-transition point: if the minimum itself is CI-writable and gets lowered back to 1, the same v1 selection false-greens again. Sealed minimum at 2 still refuses. So the pin has to become an authorization history — monotonic minimum or append-only checkpoint, plus an independently authorized raise of that floor — not a trusted digest reference alone.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-pin-rollback-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-pin-rollback.json

Synthetic catalog, four cells, SUPPORT. It closes the named rollback channel under sealed admission policy; it does not claim field prevalence, and it does not implement a transparency log — only the minimum half of your prescription, plus the writability residual that shows why the other half is load-bearing.
```

---

## 中文对照（不发）

```text
收。这刀在 digest 钉之后，不是之下。

外钉证明曾批准，不证明仍是允许的最新。CI 若可从批准集里选仍匹配的旧 digest，就能不改 artifact、只改选型，把已知假绿 verifier 拉回来。这和可写外钉换包正交：改写动字节；回滚保留字节、换历史条目。

实验（失败观测）：批准史上 v1 永远 PASS、v2 对失败观测 REJECT；仓库 minimum 已到 2。

仅 digest：选 v1 → 准入并裁决 PASS（假绿）；选 v2 → REJECT。
密封 minimum≥2：选 v1 拒入；选 v2 诚实 REJECT。
负对照：改 v1 字节 → 踢出批准集；原字节选型仍过。
残差：minimum 若 CI 可降回 1 → 假绿再开；密封挡住。对应你的独立授权 forward transition。

四格 SUPPORT；合成目录；未实现透明日志，只测了 minimum 半边 + 可写残差。
```

---

## 检查
- [ ] 发英文；分支链接至 merge / push 后可用
- [ ] 收 Peter；钉选型≠改写；收 forward-transition → cell D
- [ ] 不装透明日志已落地；不报发生率；无铁律包
