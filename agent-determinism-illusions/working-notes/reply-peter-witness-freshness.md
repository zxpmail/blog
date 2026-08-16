# Reply draft — Peter (witness gossip + freeze / three properties)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — argument-space  
Prior: `reply-peter-equivocation.md`（密封底 ≠ consistency）

Peter（本轮）:
- consistency 对「已见过冲突的 client」才抓得到分叉；两个首次 job 仍可各收合法头
- 下一步：检查点 gossip 进准入 — 提交签过的树头给独立见证，exact (root,size) 阈值收据；收据随构建证据持久化
- 冻结格：权威反复给旧但自洽头 → consistency 仍过；要新鲜度/单调进度 + 离线策略
- 三性质：inclusion / consistency / witness agreement

## 策略
- 收：时间缺口 + 三性质拆分
- 锁：W0/W1/F0/F1 SUPPORT；玩具见证 ≠ 真 quorum
- 收束：从「信权威钥」到「信门限见证集合」是治理腿必要升格，不是全系统安全证明；假设见证不共谋
- 分支：`cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Taken — and that names the temporal gap cleanly.

Consistency against one honest prior detects a fork only after that client has already seen a conflicting view. Two isolated first-time jobs can still accept different, individually valid heads. Inclusion proves a version sits in one view; consistency proves one observed view extends another; neither makes conflicting views visible to a job that has never met the other fork.

We ran the next fixture offline (toy HMAC witnesses, threshold 2/3 — synthetic authority, not a deployed quorum):

| cell | setup | result |
|---|---|---|
| W0 | two first-time jobs, no shared prior, no witness gate | both admit (honest min=2 vs shrink-fork min=1) |
| W1 | admit only with ≥2 receipts on the exact (root, size); persist receipts | honest gathers 2/3 and admits; fork cannot; later reader of the receipt log sees two roots → equivocation |
| F0 | authority keeps returning the same old, self-consistent head | consistency-only admission PASS |
| F1 | strict monotonic progress (size must exceed watermark) + offline fail-closed | freeze REJECT; honest advance PASS; offline without freshness evidence REJECT |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-pin-witness-freshness-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-pin-witness-freshness.json

So the three properties separate the way you drew them. Signature trust authenticates one view. Witness agreement is what makes conflicting views externally detectable. Monotonic progress is what blocks an old but internally consistent freeze that consistency alone will bless.

One tightening on the security-model step: this upgrades governance from trusting the authority key alone toward trusting a witness-set threshold (under non-collusion / independence assumptions we do not prove here). It is still cryptography plus assumptions about the witness set — not an automatic leap to "social consensus" as a finished fact, and it does not retire the baseline or bidirectional-constraint legs. Necessary step on the governance leg; not a full-system safety proof.

Synthetic catalog, four cells, SUPPORT.
```

---

## 中文对照（不发）

```text
收。时间缺口钉死了：两个首次 job 无旧头时 consistency 够不着。

四格：W0 双绿；W1 见证阈值挡住分叉、收据日志检出两根；F0 冻结仅 consistency 过；F1 单调进度+离线 fail-closed 拒冻结。

三性质拆开。从信权威钥到信门限见证集合是治理腿必要升格（假设见证不共谋），不是全系统证明。
```

---

## 检查
- [ ] 发英文；push 后链接可用
- [ ] 收三性质 + 时间缺口；收紧「社会共识」表述
- [ ] 挂本脚本；不装真 quorum
