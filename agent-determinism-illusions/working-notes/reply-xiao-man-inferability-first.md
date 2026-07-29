# Reply draft — Xiao Man (inferability-first: stability test before depth inference)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513
Prior: `reply-xiao-man-probe-routing.md` (cheap pre-check + artifact-shape forks)

Xiao Man's push (2026-07-29):
- The cascade's depth-from-keys rule (budget→P4, services[]→P3) is schema-
  deterministic and cheap, but the determinism is on surface shape — exactly
  what an adversarial artifact can rewrite.
- Move the stable-referent test one level up: instead of "does this case have
  a stable referent?" ask "is the depth signal stable under minor shape
  changes?" If yes → schema rule. If no → don't infer depth; route to fixed
  mid-depth probe as baseline, then escalate.
- Otherwise the geometry just moved one level up.

Data now covers three shape-perturbation cells, two failure axes:
- cue_erase (strip budget cue, wrong fingerprint): routing sends 80/80 to
  T3/P3 instead of T4/P4. Catch 82.5% (7 cross-fingerprint misses). CATCH axis.
- decoy_nest (decorative services[] in T2): routing sends 80/80 to T3/P3
  instead of T2/P2. Catch 0% (40/40 missed). CATCH axis.
- rename_keys (services→components on T3, schema-synonym rename): routing
  sends 80/80 to T1/P1 instead of T3/P3. Catch 100% (P1 over-rejects), but
  false_reject 100% in BOTH arms — fixed_matched ALSO breaks, because the
  probe implementation hardcodes `art.get("services")`. Routing AND probe
  layers are key-coupled. FALSE_REJECT axis (and worse than expected).

All three perturbations flip routing classification entirely. Depth signal
not stable on either axis. Xiao Man's design implication follows: don't
infer depth from shape; use fixed mid-depth probe as baseline; escalate on
cross-field signal.

Bonus finding from rename_keys: the probe layer is also key-coupled, so
"fixed mid-depth probe as baseline" needs key-anchored probes (structural
half of the checksum fixture), not just any P3 probe.

My prior reply said P-level is "fixed by schema depth, or a non-writable
shape proxy for it." Xiao Man's sharpening makes the "non-writable"
assumption explicit and testable. The perturbation data already broke it.

New experiment: `probe-shape-routing-rename-keys-test.py` — third cell only,
reuses existing infrastructure. Result: `results-v2/probe-shape-routing-rename-keys.json`.

---

## English (paste to DEV.to)

```text
The "geometry moved one level up" read is right. budget→P4 and services[]→P3 are schema-deterministic and cheap, but the determinism is on surface shape — exactly what an adversarial artifact rewrites. Ran three perturbation cells against the same router; all three flip routing classification entirely.

cue_erase (strip budget cue, force wrong fingerprint residual): artifact-shape routing sends 80/80 to T3/P3 instead of T4/P4. Catch drops to 82.5% — 7 cross-fingerprint misses. Right probe at wrong depth.

decoy_nest (inject decorative services[] into T2): routes 80/80 to T3/P3 instead of T2/P2. Catch drops to 0% — 40/40 missed. Wrong probe, wrong depth.

rename_keys (services→components on T3, schema-synonym rename, semantic-preserving): routes 80/80 to T1/P1 instead of T3/P3. Catch 100% — but P1 over-rejects everything because T3 has no top-level max_connections. False_reject 100%. New failure axis: cue_erase and decoy_nest broke catch; rename_keys breaks specificity.

Worse: in the rename_keys cell, fixed_matched ALSO false-rejects 100%, because the probe implementation itself hardcodes `art.get("services")`. So the key-coupling isn't just at the routing layer — the probe layer has it too. "Fixed mid-depth probe as baseline" only works if the probe is anchored to structural invariants, not to key names.

So "is the depth signal stable under minor shape changes?" — no, on three perturbations and two axes. Your design cut is the right one: don't infer depth from shape; route to a fixed mid-depth probe as baseline; escalate when the probe signals cross-field. Fast path stays fast on honest artifacts; unstable cases fail over to fixed-depth rather than right-probe-wrong-depth. Add: anchor the baseline probe to structural invariants (checksum fixture), not key names.

My prior reply said P-level is "fixed by schema depth, or a non-writable shape proxy for it." Your sharpening makes the non-writable assumption explicit and testable. The three perturbation cells already broke it; I should have drawn the design implication instead of stopping at "shape can set P-level only as an honest schema proxy."

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/probe-shape-routing-rename-keys-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/probe-shape-routing-rename-keys.json
```

---

## 中文备忘（不发）

- Xiao Man 的"几何搬一层"判断准确——shape-based routing 把攻击面从 depth 搬到 key shape
- 三个扰动 cell，两条 failure axis：
  - cue_erase (删 key): catch 82.5%（catch 轴）
  - decoy_nest (加 key): catch 0%（catch 轴）
  - rename_keys (换名): routing 100% 翻盘 + probe 也 key-coupled → false_reject 100%（specificity 轴）
- **rename_keys 这个 cell 比预期更狠**：不只破 routing，连 fixed_matched 也破——probe 函数硬编码 `art.get("services")`
- 设计含义：不推 depth；固定中深度 probe 作 baseline；baseline 必须 key-anchored（structural invariant），不能 key-named
- 我上一条说"non-writable shape proxy"——Xiao Man 把这个隐含假设显式化、可测；三个扰动 cell 已证伪
- 挂 2 个新链接：rename-keys 脚本 + 结果 JSON
