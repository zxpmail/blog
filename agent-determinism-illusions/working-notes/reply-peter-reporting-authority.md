# Reply draft — Peter (reporting authority vs behavioral oracle)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — The Third Predicate / argument-space

Peter:
- 5/5 clarifies boundary; reporting channel should terminate outside evaluated process
- Trusted parent + restricted child + narrow IPC; parent decides PASS/REJECT
- Child exit/hang/malformed cannot convert rejection → success; fail closed
- Bind result to digest of harness/fixtures/sandbox policy
- Split: randomized probes strengthen behavioral oracle; external supervisor protects reporting authority

## 策略
- 收：两 claim 拆分正确；报告权外置
- 锁：处方必要但不完备；挂实验
- G 用 policy soften / fail-open drift，不说「运营拆门」
- 权衡树：少自动放行，可疑人审（降假绿，不降真阳）
- 不装 Part 18 已发；可一句「可能收进后续篇」
- 不提铁律包

Branch links (until merge to main):
`cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Agreed on the split — and the 5/5 makes it sharper, not softer. Synonym-immune probes strengthen the behavioral oracle. They do not, by themselves, protect who is allowed to say PASS. Reporting has to terminate outside the evaluated process: trusted parent, narrow IPC, parent-owned verdict, fail-closed on timeout / signal / protocol violation, and a digest over harness + fixtures + sandbox policy so CI cannot quietly swap the verifier. That separates the two claims cleanly.

We ran that shape offline. In-process adversary converts a failing observation into PASS. Same failing observation under a parent that ignores child exit codes and PASS banners stays REJECT; hang and malformed IPC fail closed; digest mismatch rejects; honest child + matching digest passes.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-reporting-authority-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-reporting-authority.json

The prescription is right and incomplete. If the child fills `{"obs":"ok"}`, the parent only notarizes a lie. If the child can rewrite a shared observation file, same. If the expected digest lives in the same mutable tree as the harness, rewriting both is a colocated placebo. Three cuts, all false-green under "parent + IPC" alone; all reject when observation is parent-owned / fixtures sealed / pin is external:

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-oracle-hollow-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-oracle-hollow.json

Two residuals after those hardenings still green: parent `import`s the child and trusts its return value; an "external" pin that CI can still write gets swapped with the backdoor. Out-of-process sealed adjudication and a second-channel attestation pin catch them — until the next channel.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/parent-residual-false-green-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/parent-residual-false-green.json

So I will not quote a single "blocks X%" for the stack. On a synthetic catalog, L3 (parent reporting + parent-owned observation + real external pin + ban import) catches all reporting/oracle/digest rows and none of probe-spec error or policy-soften rows. Word-space fabrications need argument-space (L4/C3). Headline rate is a mixture: reporting-heavy ≈ 75% at L3; word-space-heavy ≈ 20% at L3 on that catalog — coverage of shapes, not field prevalence.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/false-green-interception-rates-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/false-green-interception-rates.json

What parent/IPC cannot eat:

- Probe/spec error: known-wrong canary first — if the canary PASSes, invalidate the gate. Mutation poison on the claimed side effect must redden the probe; a probe that stays green is mis-aimed or vacuous. More diverse failing samples shrink how long a bad probe survives. They do not prove it correct.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/pg-canary-governance-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/probe-mutation-poison-test.py

- Policy soften / fail-open drift (not "ops sabotage"): timeout→warn, digest→warn_only, retry-until-green. Detect the diff; require named change, dual control, expiry. Soften detector ALERTs; unchanged fail-closed stays CLEAN.

On the tradeoff tree: minimize automatic release. High confidence may be machine-judged; ambiguous does not get green — it escalates to human. That buys fewer false greens, not fewer true positives.

Harder bound: open-world gates do not get "fully correct," with or without AI — AI mostly cheapens false-green supply. Finite experiments reduce risk and close named channels; they are not a universal proof. Local claims in a closed catalog can still be shown; "never false-green again" cannot.

Your split stands. I want it locked as: probes for the oracle, parent supervisor for reporting authority, parent-owned observation + sealed fixtures + attested pin to keep the parent from notarizing lies, canary/mutation for probe aim, soften-detection for fail-open drift, and humans on the residual. Likely material for a later part in the series; the comment thread on Part 10 is the right place to pin it first.
```

---

## 中文对照（不发）

```text
同意拆分。5/5 让边界更清：探针加强行为 oracle，不保护谁有权说 PASS。报告须出进程；父裁定；超时/协议 fail-closed；digest 绑 harness/fixtures/policy。

实验：进程内可装绿；父进程挡住 exit/横幅/挂起/坏协议；digest 不匹配拒绝。

处方对且不完备：孩子填 obs、污染夹具、同库改 digest → 父进程公证假绿。硬化后仍有 import 孩子、可写「外钉」。

不报单一拦截率；混合物决定头条。词空间要 C3。探针错靠 canary+变异（多错误样本降存活，不证明正确）。策略软化靠 diff 检出。权衡树：少自动放行，可疑人审。开放世界无完全正确；实验降风险非全称证明。
```

---

## 检查
- [ ] 发英文；分支链接至 merge 前可用
- [ ] 收 Peter；锁不完备；G=策略软化
- [ ] 权衡树句正确；无「降真阳」；无铁律包
