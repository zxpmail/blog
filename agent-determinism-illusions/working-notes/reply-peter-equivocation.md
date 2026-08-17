# Reply draft — Peter (equivocation / consistency across checkpoints)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — The Third Predicate / argument-space  
Prior: `reply-peter-pin-rollback.md`（密封 minimum 关选型回滚）

Peter（本轮）:
- 密封底干净关掉本地回滚
- 透明日志半边不要只测单视图 append-only；加 equivocation
- 持久化 job 写不掉的旧 signed tree head；inclusion + old→new consistency
- 独立见证/法定人数（未测，残差）
- 密封底 = 这次没回退；跨检查点一致性 = 批准史没分叉

## 策略
- 收：两谓词正交
- 锁：CT-lite 六格 SUPPORT — A–C 谓词差；D 同尺寸换根仍抓；E/F 标出「旧头不可写 / 会跨视图对照」假设破了会再开
- 不装：真 CT、发生率、见证已测、穷尽攻击者证明
- 分支：`cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Taken — and that splits the pin into two predicates.

The sealed floor proves this job did not go backwards on the view it was shown. It does not prove the approval history itself is one global append-only log. A compromised authority can hand job A a signed checkpoint whose minimum is 2 and job B a fork whose minimum is still 1; each view can carry a locally valid signature and an inclusion proof while no single history exists.

We ran that shape offline on the same failing observation as the rollback cell. Toy CT-lite (RFC 6962–style Merkle over approval leaves; HMAC-signed tree heads — synthetic authority, not a deployed log). Six cells.

Local sealed floor + inclusion only: job A on the honest history (min=2, select v2) admits and adjudications REJECT; job B on a shrink fork (min=1, select v1) admits and false-greens. Equivocation invisible under per-view checks.

Same views, plus a job-unwritable persisted prior head (honest size-2 / min-2) and old→new consistency: job A PASS; job B REJECT (tree shrank / not a prefix).

Negative control: honest append size-1→2 — inclusion(v2) and consistency both PASS.

Attack-family boundary (still not a security proof): a same-size root-swap fork (size still 2, different root, alternate false-green leaf) is also REJECT under that honest unwritable prior. If the persisted-prior slot is rewritten to a fork-compatible head, consistency PASSes and the fork false-greens again. If each job keeps only a private prior and never cross-checks views, both pipelines go green on mutually inconsistent roots.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-pin-equivocation-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-pin-equivocation.json

Synthetic catalog, six cells, SUPPORT. Sealed floor ≠ consistency across checkpoints; consistency catches the named forks when the prior stays honest and unwritable and someone actually checks it — rewriting that slot, or skipping cross-view compare, re-opens dual-green. No field prevalence, no real transparency log, and the witness/quorum half for minimum-version changes still sits outside this run.
```

---

## 中文对照（不发）

```text
收。钉子拆成两个谓词。

密封底：本视图没回退。≠ 批准史是一条全局日志。权威可给 A min=2、B fork min=1。

六格 CT-lite：A 本地两绿；B 旧头+consistency 抓住缩树；C 诚实 append 过；D 同尺寸换根也抓；E 改写旧头槽再假绿；F 私有旧头不对照 → 双绿。

假设边界，不是安全证明；见证未测。
```

---

## 检查
- [ ] 发英文；分支 push 后链接可用
- [ ] 收两谓词 + D/E/F 假设边界；不装穷尽证明 / 真 CT / 见证
- [ ] 只挂本脚本与 JSON
