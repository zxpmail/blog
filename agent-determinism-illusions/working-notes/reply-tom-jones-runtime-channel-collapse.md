# Reply draft — Tom Jones (runtime channel collapse / FS per-request assert)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne  
Parent: Channel Gap / miscompile thread

Tom's fourth class:
- Cross-model Channel A by design; witness by **backend slot**, not model name
- Failover → same model as drafter; agreement true; metric green; design doc still says two
- Independence is runtime → assert per request; they log collapse, still serve — he wants refuse
- Open Q: FS equivalent? Wanted "agent could not have produced this" — he sees no cheap check

Correction vs prior draft:
- Do **not** say "no cheap check / no fingerprint." Fingerprints exist.
- Model side: response model id / endpoint **is** the fingerprint; missing piece is refuse-on-mismatch.
- FS side: cheap assert is runner-attested fingerprint (HMAC/sign under a key the agent lacks), not "impossible to write the bytes."

No new experiment — field case + fingerprint assert is the cut.

---

## English (paste to DEV.to)

```text
Taken — and this is worse than named evasion or the miscompile for the reason you name: the check keeps working. Two channels in the design doc; one channel at runtime; agreement arithmetically true; metric green. The gate did not lie. The independence DPI needs was never a property of the wiring diagram — only of the request that ran.

Selecting the witness by backend slot instead of by model identity is a design-time label standing in for a runtime fact. Rate-limit advances the loop, slot 3 is the drafter's model, and you count a cross-family agreement on a self-grade. Logging the collapse is necessary. Serving on a collapsed pair is the bug. Refuse.

On fingerprints: they are already there. The API response's model id / endpoint *is* the per-request fingerprint of the witness. Your audit log records whether that fingerprint was a separate endpoint. The missing move is not a new sensor — it is binding PASS to `witness_fingerprint ≠ drafter_fingerprint`. If that predicate fails, the independent channel did not run; green is invalid.

The filesystem equivalent is the same shape, not the stronger claim "the agent could not have produced these bytes." Ordinary FS bytes have no author. What is cheap per request is a **runner-attested fingerprint**: content hash (and path) signed or HMAC'd under a key that lives with the readonly runner, not with the agent. Before PASS, assert the signature verifies under that key for *this* request. The agent can forge a plausible `test-output.txt`; it cannot forge a valid fingerprint without the runner key. Same rule as your slot check: assert producer identity per request; on failure, refuse — do not inherit "two channels" from the architecture diagram.

So the property to assert is not impossibility of authorship. It is: the witness fingerprint for this request belongs to the declared second-channel identity. Independence is that predicate, checked live, or it is not independence.
```

---

## 中文备忘（不贴帖）

- 第四类：runtime channel collapse；塌缩应拒
- 改口：有指纹；模型侧 = 返回的 model id/endpoint；缺的是按指纹拒绝
- FS 侧：runner 密钥下的 HMAC/签名指纹，不是「agent 写不出字节」
- 谓词：本请求见证指纹 ∈ 声明的第二通道身份；失败则拒
- 不新开实验
