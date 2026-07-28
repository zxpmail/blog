# Reply draft — Tom Jones on Part 15 (agree-set / temporal / conf_desc fallback)

Thread: https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g

**状态：** conf_desc 拆因 + HaluEval n=70（DeepSeek v4-flash × gemma3）均已落盘；可贴 DEV.to。`--full` 未跑。

证据：
- https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/conf-desc-miss-shape-test.py
- https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/conf-desc-miss-shape.json
- https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/agree-set-halueval-probe.py
- https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/agree-set-halueval.json

---

```text
Tom — three measured pushes, and I ran both the conf_desc fork and a HaluEval agree-set mirror.

On your open question (fixture shape vs real failure timing): disentangling cut on the DF v2 dumps (`conf-desc-miss-shape-test.py`). Diluted escalate queues (~35% miss; low-conf rejects as distractors first):

- Raw: conf_desc beats arrival on 9/9 (model × B) cells — the "accidental match" reproduces.
- Conf↔slot shuffle: conf_desc's edge over *random* collapses (raw +1.56 → shuffle −0.89). The lift is the fixture's joint (conf, miss), not an ordering law that survives breaking that joint.
- Cross-model donor conf unstable on 5/6 pairs.

Same dump: 95.8% of MISS at conf≥0.9, qwen-heavy. Honest answer: **on this evidence conf_desc is matching the fixture's miss shape** — opposite implication for dual-line. I should not treat conf_desc as a safe universal fallback. Fallback stays fail-closed to arrival when shadow goes vacuous; conf_desc can be a shadow candidate, not the safety floor.

On the agree-set: HaluEval qa+summarization, stratified n=70, seed=7, DeepSeek-v4-flash × local gemma3:latest (not your 70B pair — same question shape, different tier). Cross-model usable n=52 after parse drops:

- Agreement 78.8%
- P(wrong|agree) = 19.5% (8/41), Wilson 95% [10.2%, 34.0%]
- By family: qa 7.7%, summarization 40%

So the auto-pass lane on *this* pair is still carrying a non-trivial error rate, with summarization worse — same qualitative warning as your 27.5% [16.1, 42.8], not a copy of the point estimate. I will not report P(both wrong|disagree)=0 as evidence (0/11 here; construction under binary + single gold, as you said).

Same-model mirror: gemma×gemma at temperature 0 agreed 100% (70/70). That is mostly determinism, not a production provider-collapse measurement. The informative gap is same(1.00) − cross(0.79) ≈ +0.21 under backends I control. Your silent rename to one underlying model is the cleaner temporal instance; I can only show the controlled same-vs-cross wedge.

G6/G7 / headroom: agreed — vacuous SHIP is worse than a wrong number. "Refuse to credit a win before proving headroom" is exactly why those gates exist.

Scripts / dumps:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/conf-desc-miss-shape-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/conf-desc-miss-shape.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/agree-set-halueval-probe.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/agree-set-halueval.json
```

---

中文备忘：
- conf_desc = fixture 联合分布，不能当安全 fallback
- HaluEval n=70：同意 78.8%，P(wrong|agree)=19.5% [10.2, 34.0]；qa 7.7% / sum 40%
- 同模 temp0 = 100%（确定性）；异模 78.8%；差距说明可控镜像，不是 provider 改名
- `--full` 未跑
