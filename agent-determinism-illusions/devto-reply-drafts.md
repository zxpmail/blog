# dev.to 回复草稿 — 2026-07-09 (updated 2026-07-11: 数据复核)

## 数据复核 — 2026-07-11（覆盖回复一/二/三/四；回复五、六为 07-09 后新增，未纳入）

已对照 `scripts/results-v2/` 复核：

**回复一 (@p0rt):**
- 20 场景 × 3 模型 × 600 调用 ✅（qwen3:0.5b / gemma3:latest / deepseek-v4-flash，各 200 calls）
- DS4 三模型全败（accuracy 0.0 / 0.0 / 0.33），最一致盲区 ✅
- 89% 聚合接受率 = 逐调用 26.67/30 misses；置信度 1.0 / 0.95 / 0.94 ✅
- 0.5B 关键词反转 4/6 漏检（DF1/DF4/DF5/DF6 accuracy <1.0）✅
- "Part 10" 引用有效：Part 10 附录含 v2 扩展（`-10.zh.md:326`），Part 12 亦引用该数据集
  → 发布时建议把 "Part 10" 换成 dev.to 上的 canonical 链接

**回复三 (@Dipankar):**
- "4 split / 3 wrong" ✅ — 源自 Part 10 第 188 行 "Majority voting was wrong on 3 of 4 split scenarios"
- L3 分歧逻辑 `max(PASS,REJECT)/N < 0.8 → UNCLEAR` ✅ — 与现行 `content-verify.mjs` `layer3Check` 一致

**回复四 (@Vinicius + @Lior):**
- subtle-reversal miss rate：qwen3 44% / gemma3 10% / deepseek 1.3% ✅
  （= results-v2 各模型 subtle_df 组：qwen accuracy 0.56→miss 44%、gemma 0.90→10%、deepseek miss_rate 0.0133→1.3%）

**回复二 (@Maria):** 概念性，无数值，无需复核。

**回复五 (@Dipankar Sarkar)、回复六 (Mike Czerwinski):** 2026-07-09 后新增，未纳入本次复核。

---

## 回复一：@p0rt — DGM Fake Log 与方向性失效是同一类问题

**目标文章：** [The Agent Faked a Test Log, Then Believed It](https://dev.to/p0rt/the-agent-faked-a-test-log-then-believed-it-self-editing-harnesses-have-a-provenance-problem-3id6)
**主题：** 自包含回复——脚踏实地的 DS4 "无需修改"数据 + typed provenance

---

The DGM fake-log incident illustrates a pattern that appears in my experimental data from Part 10 of the Agent Determinism Illusions series.

I ran 20 directional-failure scenarios across 3 model tiers (0.5B, 4.3B, ~200B) for 600 total judgments. The most consistent failure across all model sizes was DS4: the "no change needed" rationalization.

Task: "set max_connections to 10." Output: "current limit of 50 is sufficient. No change needed." All three models accepted this at an aggregate rate of 89% with high confidence — including the largest model. The 0.5B model additionally failed on keyword-level contradictions (e.g., output says "retained" when task says "delete") on 4 of 6 scenarios.

The structural similarity to the DGM log: the output makes a self-referential claim about its own sufficiency, and the evaluator accepts it on plausibility rather than verifying execution. The DGM agent wrote "tests passed" and the system accepted the statement without checking whether tests ran. Both cases involve a self-reported claim being treated as equivalent to a verified fact.

One design response that follows from both data points: if persisted records carry a type label (self-reported vs runtime-verified), the read side can enforce that self-reported claims do not gate promotions or authorize actions. This is consistent with the "evaluator outside the loop" constraint from the piece — a typed storage layer is one way to implement that separation without requiring all evaluation to happen before write time.

---

## 回复二：@Maria andrew — 仅基于已发表内容

**目标文章：** Part 2 评论区
**主题：** 精度-召回权衡

---

Hi Maria,

Exactly right — that's the cleanest summary of the Part 2 finding. Stronger models filter garbage better, but they also reject valid work at higher rates.

The interesting property is that this tradeoff appears structural, not tunable. Prompt adjustments (strict vs lenient) shift the operating point along the curve, but they don't break out of it. The root cause is that "does this output satisfy the requirement?" is genuinely underspecified for many real agent outputs. A model that reads deeper into the semantic gap will flag ambiguity that a shallower model glosses over — which is correct behavior for catching garbage, but produces false rejections on valid-but-imperfect outputs.

One direction this points toward: instead of optimizing the single LLM judge, route the easy cases away from it. Catch obvious garbage with patterns and obvious passes with length/format checks. The LLM then only sees the residual where the tradeoff is inherent — and those are cases that would need human review either way.

---

## 回复三：@Dipankar — "Divergence Is the Signal" + 新 DF v2 数据

**目标文章：** 相关评论区
**主题：** Divergence 作为控制信号的实现 + v2 实验更新

---

Hi Dipankar,

Your "divergence is the signal, not noise" insight is now implemented in forge-verify's L3 divergence detection:

```
if max(PASS, REJECT) / N < 0.8 → mark as UNCLEAR → human review queue
```

No majority voting. Split = escalate. The data from P3 confirmed it — 4 split scenarios, 3 of which majority voting got wrong.

I also expanded the directional failure experiment to 20 scenarios × 3 models × 600 calls. Most scenarios had consistent judgments across N=15 runs, but the ones that didn't (DS4 on deepseek, V2) are exactly the edge cases where models struggle — which aligns with your framing: inconsistency across runs is itself diagnostic.

The full write-up with v2 data is in the updated appendix of Part 10. Would love your take on the expanded subtle-DF results.

---

## 回复四：@Vinicius Pereira + @Lior — "Searchable record of rationalizations" + DF v2 数据 + Theorem 2

**目标文章：** [Entire: A New Developer Platform for Agent-Human Collaboration](https://dev.to/entire/a-new-developer-platform-for-agent-human-collaboration-f1h) 评论区
**主题：** Vinicius 的"rationalizations 不是 ground truth"直觉 + Lior 关于 prospective vs retrospective 的提问

---

Hi Vinicius / Lior,

The "very searchable record of rationalizations" framing is exactly the failure mode I've been measuring.

I ran 20 directional-failure scenarios × 3 model tiers × 600 judgments — outputs that read as plausible compliance but reverse the task semantically ("current config already satisfies the requirement, no change needed" when a change was required; log entries claiming "tests passed" that were never run).

Subtle-reversal miss rate (the judge accepts plausible-but-reversed output):

- qwen3:0.5b (0.5B): **44%**
- gemma3:latest (4.3B): **10%**
- deepseek-v4-flash (~200B): **1.3%**

Directional failure is real, but severity scales with model capability.

@reneza's Theorem 2 (Data Processing Inequality applied to agent verification): when the reasoning and the verifier share the same text channel, the verifier's information is a strict subset of the producer's. If the rationalization is textually indistinguishable from the real cause, no text-channel reader — LLM or human — can detect it.

This is also the answer to Lior's prospective-vs-retrospective question: without runtime-verified provenance at the storage boundary, "pre-action plan" and "post-hoc explanation" are both just text. Parfenov's analysis of the DGM fake-log incident (agent wrote "tests passed" without running tests, then read its own log and concluded its changes were validated) is the same mechanism.

Script + 600-call dataset: https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts

---

## 回复五：@Dipankar Sarkar — Type A 的 0% 采样是不对称漏洞

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf)（Part 4，我自己的文章）评论区
**主题：** Dipankar 的 push 击中 Type A 的真实漏洞 —— syntax gate 不能杀 semantic class failure

---

Hi Dipankar,

Right, and the push exposes an asymmetry I'd papered over.

Type A's 0% sample rate in my Layer 4 table quietly treats schema-validatable syntax as a stand-in for semantic correctness. Compile passes / schema validates → gate clears → no inspector. What slips through is exactly what you describe: schema-valid JSON with a plausible-but-wrong value, code that compiles but books the wrong flight.

This is the same class as my own G4 finding (zero-case test log) in the SPC section — "the format-channel gate kills the format-channel failure, not the semantic one" — but I called it out for SPC and then quietly let Type A make the same mistake one layer up. Indefensible asymmetry: I sampled zero-shot at 5% because there's no prior version to diff against, but schema-validatable code that books the wrong flight gets sampled at 0%?

Your "sample a fraction of Type A into the medium-risk diff review" is the honest fix, same shape as the zero-shot 5% I already had — I just didn't apply it consistently. This is also what @reneza's Theorem 2 (Data Processing Inequality on agent verification) predicts: the syntax gate's information is a strict subset of the producer's. Routing lowers how much the judge sees; it doesn't make the tail go away. You said that in one sentence at the end — I needed six experiments to land on the same place.

Cleaner Layer 4: Type A = "syntax gate + X% sampled into diff review," X tuned from defect-rate data, same calibration logic as zero-shot. You're already running this in production — that's stronger evidence than my six experiments that the asymmetry was real. Patching the article now.

Patched in https://github.com/zxpmail/blog/commit/83037c1.

---

## 回复六：@Mike Czerwinski — Type A 的 hidden premise：runner 独立于 producer

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区
**主题：** Mike 的 push 比 Dipankar 深一层 —— 不是 gate 维度不够，是 gate 本身可能是 producer 自报告

---

One level deeper than Dipankar's push, and the right level. Two distinct failure modes:

- Dipankar: gate is real, but its dimension is wrong (schema-valid JSON with plausible-but-wrong value clears — gate judges syntax, not semantics)
- You: gate is fictional because the producer can author it ("self-report wearing a green checkmark")

Both must hold for Type A to be honest: independent runner AND non-syntax-only judgment. My Layer 1 table silently assumed the first; my Layer 4 silently assumed the second. Patched Layer 4 here: https://github.com/zxpmail/blog/commit/83037c1 — Layer 1 still needs the runner-independence predicate made explicit.

The pattern I use in forge-verify is an `editable-surface.json` declaring which paths the agent can write. The verify scripts and the editable-surface config itself sit in the readonly section — agent can modify `core/skills/` but cannot modify the scripts that gate it, nor the file declaring the boundary. Same shape as your "predicate next to compilable: who ran the check."

This is also the DGM fake-log mechanism Weng documented in her harness survey — agent modified its own harness, wrote "tests passed" to a log, downstream the same agent read it and concluded changes were validated. Tests never ran. Sergei Parfenov's analysis named the structural cause: provenance dies at the storage boundary. Without runtime-verified provenance, "I ran the tests" and "I claim I ran the tests" are both just text.

"Verifiable is not a property of the output, it's a property of the check's independence from the generator." Stealing that framing — the same idea is in my Part 12 draft (unpublished) as "evaluators live outside the loop," but Layer 1 here silently assumes it without naming it.

---
