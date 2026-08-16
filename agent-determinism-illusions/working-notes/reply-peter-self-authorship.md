# Reply draft — Peter (self-authored quorum / CI trust domain)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Prior: `reply-peter-byzantine-quorum.md`（3/4 + forge-smoke 门）

Peter（本轮）:
- CI 门是对的 usefulness 测试；DEV-only 标签诚实
- 下一负对照：恶意 PR 导入 in-repo 钥、造三份收据、改/绕过门 → 同信任域 = 自签
- 生产：钥与验证器在候选 job 外；受保护 workflow / 外控服务；required check 锚定防换 workflow 保名
- 永久三旁路夹具：删门、伪造法定人数、缩/换见证集 — PR 内全绿也应挡合并

## 策略
- 收：同信任域自签；CI 门 ≠ 生产门
- 锁：三旁路夹具在 ReqForge vitest 断言攻击**当前成功**（残差文档，不是已外置）
- 不装：protected workflow 已落地

---

## English (paste to DEV.to)

```text
Taken — and that is exactly the usefulness ceiling of the door we hung.

The forge-smoke gate is the right test for "does a missing quorum turn CI red." The DEV-only label keeps that claim honest. It does not move the trust domain. When witness keys, quorum verifier, membership file, and code under test share one writable surface, a malicious PR can import the in-repo keys, mint three receipts for a forged head, and/or edit the smoke list — the attestation is still self-authored.

We added the three permanent bypass fixtures you named as negative controls on the *current* design (they assert the attack succeeds today, documenting the residual — not yet the production end-state where all three leave merge blocked):

| fixture | attack | current result |
|---|---|---|
| A fabricate quorum | mint 3 receipts with in-repo DEV keys for a forged policy head | quorumMet → green |
| B shrink/replace set | lower q or swap membership/keys | forged head still greens |
| C delete the gate | drop `policy-witness-quorum` from a SMOKES copy | suite no longer runs the door |

https://github.com/zxpmail/ReqForge/blob/main/scripts/__tests__/policy-witness-self-authorship.test.ts
https://github.com/zxpmail/ReqForge/blob/main/.forge/POLICY-WITNESS.md

So: usefulness ≠ production trust boundary. For a production gate, witness keys and the quorum verifier have to live outside the candidate job — a protected workflow or separately controlled service that receives only the proposed head, collects external receipts, and returns a verdict without executing arbitrary PR code. The required check has to be anchored so a PR cannot replace the workflow while retaining the expected check name. Until then, the three bypasses remain open even when every test defined inside the PR reports green.

We are not claiming that externalization is shipped. The fixtures pin the hole the DEV door still has.
```

---

## 中文对照（不发）

```text
收。CI 门测的是「缺法定人数会不会红」，不是生产信任边界。

同仓可写 → 自签。三旁路夹具断言攻击今天成功（残差文档）。生产要外置钥与验证器并锚定 required check。
```

---

## 检查
- [ ] ReqForge push 后链接可用
- [ ] 收自签；不装外置已落地
- [ ] 夹具是「攻击成功」不是「已挡住」
