# Reply draft — Ofri Peretz (YAML = prompt? / same-representation)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne  
Commenter: Ofri Peretz

Thesis they bring:
1. DPI ↔ static analysis linting the AST the compiler already accepted
2. René → "same representation": judge sees artifact only
3. skillgate ↔ out-of-band witness
4. Open: enough gate types → rebuild semantic judgment in YAML?

Answer (measured, Part 8 Update 2026-08-10):
- Yes if YAML encodes sufficiency / domain coverage
- Design cut: **necessity in YAML, not sufficiency** (red ⇒ not done; green ⇏ done)
- Numbers: sufficiency YAML miss 83.3% vs necessity 0%; stop-policy A 60% vs B 0%; CODE binding shrinks escalate load

---

## English (paste to DEV.to)

```text
"Same representation" is the right name for René's cut — and the static-analysis analogy lands cleanly. Linting the AST the compiler already accepted is DPI one layer down: the checker only sees what survived the transform. An LLM judge reading the model's own text has the same bound — artifact only, no channel to intention or side-effects. Skillgate is the security-audit move: stop trusting the process's self-report, go look at what it actually touched.

Your open question is the load-bearing one. I measured it.

Short rule: put necessity in the YAML, not sufficiency. Gate-red means not done. Gate-green does not mean done. If you enumerate gate types until the file "covers the task domain," you are rebuilding the semantic judgment at authoring time — René's deterministic wrapper again, just earlier and harder to see.

Three cuts on the same thread (Part 8 Update, 2026-08-10):

1. Sufficiency YAML vs necessity YAML, both with green→PASS: soft patterns ("complete" / "production ready" / "adequate") missed 83.3% (5/6) of non-compliant packs; necessity atoms (test names, coverage ≥85%, lint 0) missed 0%. That is the rebuild — a prompt wearing YAML syntax.
2. Same contract gate, stop policy: green→PASS missed 60% (6/10); green→C2 residual missed 0%. The gap is exactly the gate-green false-pass set.
3. Binding a code-level REQ to review vs to test output: same final miss/FR on this run, but CODE cut gate-green false passes and residual calls by 2 — review binding is how sufficiency sneaks back into the residual.

So: YAML instead of a prompt wins only while it stays a falsification checklist. The moment it becomes a second encoding of "sufficient," you've moved the judgment, not escaped it. The interesting failures stay unenumerated on purpose.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/sufficiency-vs-necessity-yaml-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/necessity-vs-sufficiency-stop-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/evidence-binding-fr-test.py
```

---

## 中文备忘（不贴帖）

- 接住 same representation / 静态分析 / out-of-band witness
- 规则：YAML 放必要性，不放充分性；红=未完成，绿≠已完成
- 数：充分性 YAML 漏检 83.3% vs 必要性 0%；停机 A 60% vs B 0%；CODE 绑定少 2 次升级
- 链 Part 8 Update + 三个脚本
