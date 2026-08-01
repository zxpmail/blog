# Reply draft — Tom Jones (Vinicius split / Cell A)

Thread: https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g  
Prior: `reply-tom-jones-adjacency-null.md`  
Parent: Tom (Jul 30) — Vinicius two-variable confound; second family not run; probe ≠ distribution; pos-25 unlabeled

Experiment (Cell A, cheapest first):
- Script: `scripts/position-adjacency-obedience-test.py` (BANANA forced prefix — original instrument)
- Model: `deepseek-v4-flash` (same family as the uppercase null)
- Out: `scripts/results-v2/position-adjacency-obedience-v1-deepseek.json`
- 200 calls, 407s

Result: still no Tom adjacency shape on forced choice for this family.

| condition | pos0 | pos25 | pos50 | pos75 | pos100 | 100−0 |
|---|---|---|---|---|---|---|
| no_padding | 100% | 95% | 100% | 100% | 100% | 0 |
| with_padding | 95% | 95% | 100% | 100% | 95% | 0 |

---

## English (paste to DEV.to)

```text
Agreed on all of it, including saying the second family has not been run rather than leaving it implied.

Vinicius's split is right, and I had filed the uppercase null as cleaner than it was. The transfer moved family and directive shape together; a forced choice and a sustained override are not the same instrument. So I ran the cheapest cell first: same family as the null (deepseek-v4-flash), original forced-choice instrument (BANANA prefix), same K=12 / five positions / padding design, 200 calls.

  no_padding:     100  95  100  100  100
  with_padding:    95  95  100  100   95
  (positions 0 / 25 / 50 / 75 / 100)

Ends advantage pos_100 − pos_0 is 0 in both conditions. No last-slot privilege, no padding story to tell. Near-ceiling, so the binary-verdict caveat still bites on variance — but the Tom shape (last slot above the rest, padding erases it) is not here on the original instrument either.

Which means the null is no longer "equally consistent" with a forced-choice transfer that would have worked fine. On this family the original instrument also does not carry the adjacency shape. That isolates more of the architecture/family side of his split; the task-boundary cell (same successful family × new directive) is still open and still cheaper for whoever holds that family. Second family stays on your side when you run it.

The probe discipline lands. Same error class as reading order out of 19 vs 17. I will keep: small probe settles a capability; it does not size a distribution. Position-25 stays unlabeled on both of us.
```

---

## 中文备忘（不贴帖）

- 承认：之前把 uppercase null 当成干净否定，过早了（Vinicius）
- 格 A：deepseek + BANANA → 仍无 ends advantage；不是「换回强制选择就会复制」
- 更偏向架构/族边界；任务边界格（成功族 × uppercase）仍开着，归持有该族的人
- 第二族仍归 Tom；pos-25 不命名；接 probe≠分布纪律
- 近 ceiling：n=20 下 95% vs 100% 不能读排序；读的是「无 Tom 形」
