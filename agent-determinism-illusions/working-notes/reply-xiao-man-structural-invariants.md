# Reply draft — Xiao Man (structural invariants / mutation suite)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  
Prior: `reply-xiao-man-inferability-first.md` (three perturbation cells; key-coupling at both layers)

Xiao Man (Jul 29): rename_keys proves key-name coupling at two layers; asks what
counts as a structural invariant (position / type / cardinality); frames the
three cells as a mutation suite — "how do you know your probe is anchored
correctly?" → "run the three perturbations."

Experiment: `probe-structural-invariant-anchor-test.py`  
Result: `results-v2/probe-structural-invariant-anchor.json`  
n=40 good+bad per cell, seed=7, T3 checksum domain, offline.

Survival = locate≥0.95 ∧ catch≥0.95 ∧ FR≤0.05:

| anchor | honest | rename | reorder | type_wrap | dual_list | dual_first |
|--------|--------|--------|---------|-----------|-----------|------------|
| key_name | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ |
| position | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| type | ✓ | ✓ | ✓ | ✗ | ✓* | ✗ |
| cardinality | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |

\*type survives dual_list only when the true list is first — dual_first
latches the decoy (locate 1.0, FR 1.0). Order is not a type law.

No anchor survives all cells. Spectrum prediction holds cell-by-cell.

Verification cut (beyond the mutation suite alone):
1. Contract — declare invariant class; locator separate from leaf checks; unlocated → fail-closed
2. Honest — align locate/catch/FR with fixed_matched on clean T3
3. Mutation gate — claimed class must SURVIVE its promised cells; other cells may FAIL

---

## English (paste to DEV.to)

```text
Agreed — rename_keys is the design-changing cell, and cue_erase / decoy_nest / rename_keys already form a clean mutation suite for the routing+probe stack.

On "what counts as a structural invariant" I ran your three candidates plus the key_name baseline on T3 (n=40 good+bad/cell). Survival = locate≥0.95 ∧ catch≥0.95 ∧ FR≤0.05.

key_name dies on rename (and type_wrap) — same hardcoded art.get("services") break.
position survives rename, dies on reorder — your split.
type survives rename+reorder, dies on type_wrap. Caveat: dual_list "survives" only if the true list is first; put the decoy first and type latches it (FR 100%). Order is not a type law.
cardinality survives rename+reorder; dies when zero or two pattern matches (dual_list / dual_first), and on type_wrap.

No single anchor survives the full table. So the principle stands, and "pick the cleverest invariant" does not.

One sharpening on your closing question — "how do you know your probe is anchored correctly?" → "run the three perturbations." The suite is necessary as a *regression gate*, not sufficient as the whole answer. Authoring-side you can also: generate paths from schema, or have the router pass an already-resolved referent so the probe never re-finds by key; verification-side you want three layers — (1) declare the invariant class and fail-closed on locate miss, (2) align locate/catch/FR with fixed_matched on honest artifacts, (3) run the mutation suite against *that claimed class* (promised cells must SURVIVE; cells outside the claim may FAIL). Your three perturbations stay the stack test; the table above is the authoring test for the baseline probe. Together: declare → honest-align → mutate — not mutate alone.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/probe-structural-invariant-anchor-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/probe-structural-invariant-anchor.json
```

---

## 中文备忘（不贴帖）

- 矩阵结论不变：无万能锚点；边界与预测一致
- 补一刀：三格是回归门，不是「唯一验法」
- 三层：声明不变量 → 诚实样本对齐 fixed_matched → 按声称类跑变异
- 写作侧还可：schema 生成路径 / 路由传入已解析指称物
