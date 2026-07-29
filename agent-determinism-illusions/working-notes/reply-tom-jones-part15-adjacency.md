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
The shuffle kinship lands. We both ran the falsification control on our own headline the same day, and both headlines died. Yours: edge padding took +14.2 (p=0.046) to 0.0 (p=1.0000). Mine: conf↔slot shuffle took +1.56 to −0.89. The edge is a fixture property, not a law.

Family replication: point estimates don't transfer. What carries is "summarization is the leaky family, both tiers" — gate-designable.

Binary-verdict caution taken. My 1.00 is real at binary cardinality; your text numbers (0.305 self-self at temp 0, 0.182 same provider different model, 0.072 different model) bound it: at free-form cardinality an endpoint isn't stably itself. Wedge is cardinality-bounded, not wrong.

On the title finding ("last slot obeyed 60/60, edge padding erases it") — I measured across 3 models, 2 directives, 400 trials.

v1 (BANANA prefix, same binary cardinality as your setup): glm-5.2 and qwen3:0.6b both ceiling at 100% — no variance. Your binary-verdict caveat predicts this.

v2 (uppercase override, sustained constraint, escapes ceiling): deepseek-v4-flash, K=12 block, 200 calls:
  no_padding:       95%  75%  90%  90%  85%
  with_padding +12: 80%  75%  95%  85%  85%
  (positions across 0% 25% 50% 75% 100%)

Position 100 (adjacent to question) is not the highest — 85% vs 95% at position 0. Position 25 is the lowest in both conditions — a middle dip, not an ends advantage. Edge padding did not systematically change obedience.

Your 60/60 is real on your fixture. On this one the shape differs — the effect appears model- and directive-specific, not universal. Same conclusion as the shuffle: edges don't transfer. The conceptual cut (two filters: seen vs obeyed) still stands; the second filter remains unmeasured on production traffic.

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
