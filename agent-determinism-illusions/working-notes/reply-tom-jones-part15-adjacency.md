# Reply draft — Tom Jones on Part 15 (shuffle kinship / cardinality / adjacency)

Thread: https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g
Prior: `reply-tom-jones-part15.md` (conf_desc shuffle + HaluEval mirror)

Tom's four moves (2026-07-29):
1. Shuffle kinship — his edge-padding control (12 notes of separation) took his
   +14.2 (p=0.046) headline to exactly 0.0 (p=1.0000). Same shape as my
   conf↔slot shuffle (+1.56 → -0.89). Both ran the falsification control on
   our own headline the same day, both headlines died.
2. Family replication — qa 7.7/summarization 40 (mine) vs qa 24/summarization 33
   (his). Different levels, same direction. Summarization is the leaky family
   in both. Intervals overlap heavily; 19.5 vs 27.5 carries no signal.
3. Binary-verdict ceiling — my gemma×gemma 1.00 is real at binary output
   cardinality; at text layer an endpoint isn't stably itself (0.305 self-self
   at temp 0, 0.182 same model different provider, 0.072 different model).
   Same-vs-cross wedge is cardinality-bounded: clean detector at binary,
   compresses at free-form.
4. Position-adjacency — last slot obeyed 60/60, every other 80–85, edge padding
   erased the ends advantage. Privileged position is adjacency to the question,
   not budget position. Two filters: budget names who gets seen; adjacency
   names who gets obeyed.

**2026-07-29 update**: ran replication experiment for (4). Scripts:
`position-adjacency-obedience-test.py` (v1, BANANA prefix) and
`position-adjacency-obedience-v2.py` (v2, uppercase override).
Results: `results-v2/position-adjacency-obedience.json` and
`results-v2/position-adjacency-obedience-v2.json`.

Finding: your position-adjacency effect does **not** replicate on this fixture.
Details in the reply below.

---

## English (paste to DEV.to)

```text
The shuffle kinship is the part that lands. We both ran the falsification control on our own headline the same day, and both headlines died — your edge padding (12 notes of separation) taking +14.2 → 0.0 at p=1.0000 is the cleaner instance; my conf↔slot shuffle taking +1.56 → -0.89 is the messier one. Same shape of control: break the joint between surface position and the latent cause, see if the edge survives. It doesn't.

Your family-replication cut is the right one. Point estimates don't carry (intervals 10.2–34.0 vs 16.1–42.8 overlap heavily; 19.5 vs 27.5 is noise). What carries is "summarization is the leaky family, both tiers, both samplers." That's the gate-designable output — a designer can bias review toward summarization outputs without needing the levels to transfer.

The binary-verdict caution is sharper than I made it, and I take it. Same-model gemma×gemma at 1.00 is real for verdicts specifically — binary output, ceiling on the same-model arm. Your text-layer numbers (0.305 self-self at temp 0, 0.182 same model different provider, 0.072 different model) put the bound cleanly: at free-form cardinality an endpoint isn't stably itself, so the same-vs-cross wedge would compress. The honest claim is "at binary cardinality the same-model arm saturates; at text cardinality it would not." Detector strength varies with output space — verdict-level wedge is real but cardinality-bounded.

On the title question — "budget names who gets seen, then one slot decides who gets obeyed" — I ran the replication. Short version: your effect does not replicate on this fixture. The honest record is useful:

Two experiments, across 3 models:

v1 (BANANA prefix — easy binary directive, same cardinality as your "60/60" binary setup):
  glm-5.2:      all cells 100% ceiling — no variance, unmeasurable.
  qwen3:0.6b:   same (100% all positions, 95–100% with 12-notes padding).
  Your binary-verdict caveat predicts exactly this ceiling: at binary cardinality,
  the same-model arm saturates.

v2 (uppercase override — sustained constraint, escapes ceiling):
  deepseek-v4-flash, K=12 block, 5 positions × 2 conditions × 20 trials/ = 200 calls:
    no_padding:  95%, 75%, 90%, 90%, 85%
    with_padding: 80%, 75%, 95%, 85%, 85%
  Position 100 (adjacent to question) is NOT the highest slot: 85% = below pos_0
  (95%) and pos_50 (90%). Position 25 is the lowest in both conditions (75%).
  The lowercase count at pos_25 is ~10× higher than at pos_50, which is
  consistent with a classic serial-position "middle dip" for mid-list items
  in a 12-slot block. Edge padding did not systematically reduce obedience.

So your 60/60 finding is real on your fixture. On this fixture, the shape is
different: no adjacency advantage; a middle dip at position 25 instead. That
itself is informative — it suggests the effect is bounded to specific
model/directive combinations, not a universal "last slot wins" property.
Same shape of control, different outcome — which is exactly what yours and
my shuffle demonstrated: the edge is a property of the fixture's joint, not
a law.

The conceptual cut (two filters: budget = seen, adjacency = obeyed) still
stands, even if the empirical shape didn't replicate here. Part 15 ended on
the first filter. The second is still unmeasured on production traffic.

Scripts/Results:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/position-adjacency-obedience-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/position-adjacency-obedience.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/position-adjacency-obedience-v2.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/position-adjacency-obedience-v2.json
```

---

## 实验结果（2026-07-29 跑完）

**v1 — BANANA prefix（二值容量，vs Tom 的 binary ceiling caveat）**

| 模型 | no_padding 全位置 | with_padding |
|------|---|---|
| glm-5.2 | 100% | 100% |
| qwen3:0.6b | 100% | 95-100% |

ceiling effect，与 Tom 的二值饱和预言一致。

**v2 — uppercase override（持续型约束，脱 ceiling）**

deepseek-v4-flash（200 calls, 657s）：

| 条件 | pos=0 | pos=25 | pos=50 | pos=75 | pos=100 |
|---|---|---|---|---|---|
| no_padding | 95% | **75%** | 90% | 90% | 85% |
| with_padding | 80% | **75%** | 95% | 85% | 85% |

- **pos_100 不是最高**（no_padding 85% vs pos_0 95%）
- **pos_25 两条件都是最低**（75%），小写字母数 ~10× 高于 pos_50——像序列位置效应的
  "middle dip"
- padding 没有系统性降低服从率

## 中文备忘（不发）

- 前三点的回复不变（shuffle kinship / family replication / cardinality bound）
- 第四点（position-adjacency）已跑实验，没复制出来
- **不声称 Tom 错了**——他的 60/60 在他 fixture 上真实。只是本 fixture 上形状不同
- 诚实记录：位置效应可能是 model-specific / directive-specific，不是普遍属性
- 这与 shuffle 方法论的结论一致——edge 是 fixture 联合分布，不是定律
- 概念性切割（budget = seen, adjacency = obeyed）仍然有信息量；Part 15 只测了第一道
- 挂 v1 + v2 共 4 个 GitHub 链接
