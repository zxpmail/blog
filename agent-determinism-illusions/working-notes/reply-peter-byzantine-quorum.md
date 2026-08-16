# Reply draft — Peter (Byzantine double-sign / quorum intersection)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Prior: `reply-peter-witness-freshness.md`（2/3 见证阈值）

Peter（本轮）:
- 分离对，但 2/3 还要对抗格：拜占庭 B 双签两根 → X=A+B、Y=B+C 都满 2/3，交点只有双签者
- 阈值 alone ≠ fork safety；要任意两法定人数交点 > f → q>(n+f)/2；常构 n=3f+1,q=2f+1；f=1 → **3/4**
- 加：双签夹具；见证保留 last head 拒不一致；冲突收据可携；见证集/轮换进治理态（同 anti-rollback）

## 策略
- 收：交点条件；承认上一格 2/3 不够
- 锁：B0/B1/R/E/G SUPPORT；不装 BFT 证明
- 落地：ReqForge `forge-smoke` 挂 3/4 政策收据门（缺则 CI 红）；DEV HMAC 非生产信任
- 分支 blog：`cursor/xiao-man-epistemic-distance-reply`；ReqForge：`main`（需 push）

---

## English (paste to DEV.to)

```text
Taken — and that adversarial cell is the one the last fixture was missing.

Threshold fraction is not fork safety. With A,B,C and Byzantine B double-signing both roots, X collects A+B and Y collects B+C: both hit 2/3 while their only intersection is the equivocating witness. Two isolated jobs can still each see a locally valid quorum.

We ran that shape offline, then the usual intersection repair for f=1:

| cell | setup | result |
|---|---|---|
| B0 | double-signing B; q=2 of n=3 | both roots meet threshold |
| B1 | same attack; q=3 of n=4 (n=3f+1, q=2f+1) | X can meet 3; Y cannot — dual-admit blocked |
| R | witness retains last accepted head | inconsistent second root refused |
| E | persist conflicting signed receipts | later reader sees two roots — portable equivocation evidence |
| G | CI-writable membership shrink back to ABC @ 2/3 | dual-admit reopens |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-pin-byzantine-quorum-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-pin-byzantine-quorum.json

So the separation gains a fourth load-bearing piece next to inclusion / consistency / witness agreement: **quorum intersection** under an explicit f. For f=1, 3-of-4 rather than 2-of-3. Retaining last head is the local hygiene that stops an honest witness from becoming an accidental double-signer; portable conflicting receipts are what later jobs (and auditors) can carry without re-trusting the authority.

And yes — witness-set membership and key rotation are governed state. Cell G is the writability residual: if CI can shrink the set, you are back in B0. They need the same append-only, freshness, and anti-rollback treatment as the minimum-version policy.

One step past the synthetic catalog: we hung the f=1 gate on a real release smoke. ReqForge's `pnpm forge-smoke` now runs `policy-witness-quorum` against `.forge/policy-version.json` and requires 3-of-4 HMAC receipts on that exact head before the suite can go green. Drop a receipt → smoke exits 1. That is the usefulness bar for this leg: a false-legal policy admit fails CI, not only a JSON claim. The keys in-repo are labeled DEV-only for reproducibility — not a production witness set, not a BFT proof, and membership still needs the same anti-rollback treatment as minimum-version.

https://github.com/zxpmail/ReqForge/blob/main/scripts/forge-smoke/policy-witness-quorum.mjs
https://github.com/zxpmail/ReqForge/blob/main/.forge/POLICY-WITNESS.md

Synthetic catalog, five cells, SUPPORT; plus a CI door that actually turns red. The previous 2-of-3 fixture still shows gossip-vs-no-gossip; it does not claim fork safety under one faulty witness.
```

---

## 中文对照（不发）

```text
收。上一格缺的对抗格。

2/3 双签下两根都能满；f=1 要 3/4。实验五格 SUPPORT。

并挂进 ReqForge forge-smoke：政策头缺 3/4 收据则 CI 红。DEV 钥非生产信任；见证集治理仍残差。
```

---

## 检查
- [ ] blog 拜占庭实验 + 本草稿 commit/push
- [ ] ReqForge 门闩 commit/push 后链接才真可用
- [ ] 发英文；收交点；不装 BFT；点明 DEV 钥
