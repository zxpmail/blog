# dev.to 回复草稿 — 2026-07-09 (updated 2026-07-11: 数据复核)

## 数据复核 — 2026-07-11（覆盖回复一/二/三/四/七/八/九/十/十一；回复五、六为 07-09 后新增，未纳入）

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

## 回复七：@Kartik N V J K — Type A 的 format-vs-demand 区分 + 采样率

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区
**主题：** Kartik 击中 Type A（well-formed ≠ correct）+ 问采样率是固定还是 blast-radius 加权

---

Hi Kartik,

On Type D — fully agree, and you've put the principle more cleanly than the article. "Did this change introduce an error?" is deliberately a *narrower* question than "is this good?", and that narrowing is why diff review runs ~30–90s instead of a full judgment. You defending it hardest is defending the load-bearing column.

On Type A — you're right, and your framing names a distinction worth making explicit: there are really two different things under "verifiable." A **format check** (file exists / compile / schema) verifies the output is *well-formed*; a **demand check** (test output matches expected, assertion pass) verifies it actually *satisfies the requirement*. Your sentence — "compile and schema checks confirm the output is well-formed, not that it does the right thing" — is the format-vs-demand gap stated from the other direction. So Type A isn't monolithic: a Type A task backed only by a format check is exactly the case where sampled diff review does the load-bearing work you're pointing at; a Type A task backed by a demand check (real test assertions) has far less riding on the sample. The original Layer 4 table flattened that by giving Type A 0%, which Dipankar Sarkar pushed on in the comments and I corrected to X% (1–2% to start). (Mike Czerwinski separately raised the adjacent runner-independence problem — if the agent can author the verify scripts, "compile-green" is a self-report wearing a green checkmark.)

On your actual question — **fixed percentage, tiered by criticality class, not weighted by per-task blast radius:** Type A X% (tuned), C 0%, D 100%, zero-shot 5% (10–20% for critical, 20% launch week).

Two reasons it's fixed rather than blast-radius-weighted, and the second is the honest one: (1) fixed rates have a computable detection probability — at 5% sampling and 20% true defect rate, single-day detection is 67%, a number you can argue about on a dashboard; (2) blast radius needs a per-task impact estimate, which is itself an unsolved problem (whose definition — static dependency graph? runtime reachability?), so "blast-radius-weighted" would hide the same uncertainty behind an extra model. Where I *did* split Type A internally, I split it by **verification power** (format vs demand), not blast radius — because verification power is definable and blast radius, in practice, isn't. Your instinct that a flat X% under-samples high-impact code (payment logic vs. README) is still correct, and blast radius is the obvious name for the missing axis — I just don't have a defensible per-task metric for it yet.

---

## 回复八：@Alex Shev — "stronger = more expensive friction" + routing 直觉

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区
**主题：** Alex 的 route + deterministic final = Part 4 方向；分歧在 suspicious lane 放 LLM 还是 human diff

---

Hi Alex,

"Stronger just means more expensive friction" is the cleanest one-line summary of the data table this post is built on — GLM-5.2 drops false-positives to 0% and pushes false-rejections to 75% in the same move. The friction isn't a bug of the strong model; it's the same property that produces the 0%.

Your routing instinct is also exactly the turn [the next post in the series](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) takes: stop asking the model to judge "correct," route by risk instead — high-risk out of the pipeline entirely, low-risk auto-release, only medium-risk reaches a human, and when it does it's a diff review ("did this change introduce an error?"), not a full-text quality judgment. Final rejection tied to deterministic evidence or a human, never to the LLM alone — same as you're saying.

Where I'd push one step further than "route high-recall models to suspicious areas": routing shrinks the scope but doesn't remove the precision-recall trap underneath. GLM-5.2's 75% false-rejection rate is still 75% even if you only run it on the suspicious bucket — you've concentrated the friction, not eliminated it. So in that suspicious lane I dropped the LLM inspector entirely and put a human diff review there instead, on the grounds that "did this change introduce an error?" is a narrower (and more reliable) question than "is this output correct?" — which is the question the LLM keeps getting wrong at 75%.

That's a design call, not a correction — your principle ("a reviewer is useful only where its error profile is acceptable") is the right framing, and it's what licenses both options. The open question is just whether the suspicious lane's error profile is ever acceptable for an LLM, or whether that lane belongs to a human + deterministic evidence and the LLM inspector gets retired rather than rerouted.

---

## 回复九：@Manuel Bruña — inspectable failure objects + evidence quality as result

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区
**主题：** Manuel 的 inspectable failure objects = forge-verify 的 trace + evidence gate + failure_class；evidence quality as result = C2 null-vote；诚实缺 observed/severity/blocking

---

Hi Manuel,

This is the same direction you've been pushing — evidence, not narrative — and the Part 2 data is actually the strongest argument for it: GLM-5.2's 75% false-rejection rate is a *narrative* judgment ("this output is not good enough") with no inspectable object underneath it. If the rejection had been an inspectable failure object — here's the check, here's the expected condition, here's where the evidence should be — a human or a deterministic re-check could have overturned most of those 75% in seconds. The friction isn't the model being wrong; it's the model being uninspectable.

I built this into [forge-verify](https://github.com/zxpmail/ReqForge) after the earlier round of your comments, and your three points map onto it almost one-to-one:

- **Inspectable failure objects** → every pipeline stage emits a `trace` entry with `evidence` pointing at the exact source: `file:src/rate-limit.ts` for inline content, `evidence:test-output.txt((?i)isRateLimited)` for a contract regex match, `evidence:test-output.txt(REQ-1)` for a per-requirement LLM check. The verdict isn't a narrative; it's a chain you can walk back to a file + mtime.
- **Evidence quality as part of the result, not the explanation** → this is the one I'd underline, because you're right and I had it backwards initially. The Evidence Gate rejects on *missing or empty* evidence files (`failure_class = execution-lapse`); C2 records API/parse errors as non-votes and downgrades to `UNCLEAR` rather than emitting a false `REJECT`; `trace.evidence_files` carries mtime so a stale evidence file is detectable. "I couldn't verify" and "I verified and it failed" are now distinct results — exactly your "downgrade confidence instead of treating the rejection as final."
- **Structured atomic checks** → `failure_class` (`execution-lapse` / `skill-defect` / `unset`) classifies *why* a stage rejected, routing automatically to feedback-observer without a second classification pass.

Where you're ahead of the current implementation: your check schema has **observed value**, **severity**, and **blocking vs advisory** as first-class fields. forge-verify's verdict is still a three-state PASS/REJECT/UNCLEAR with `failure_class` but no explicit severity or blocking/advisory distinction — so a "0 tests collected" execution-lapse and a "schema-valid but wrong value" skill-defect currently carry the same weight. Your framing is the right next cut: not all failures block, and the observed value is what lets a downstream tool re-verify without re-running the model. I haven't built those two axes yet — flagging as the honest gap.

---

## 回复十：@Google AI 文章（主动评论，非回复自己文章的评论者）— managed memory 方案的不确定性边界

**目标文章：** [Architect A Personalized Multi-Agent System with Long-Term Memory](https://dev.to/googleai/architect-a-personalized-multi-agent-system-with-long-term-memory-3o15)（Google AI / Shir Meir Lador，Dev Signal multi-agent 系列 Part 2）
**主题：** 中性补充 —— managed 方案的两个默认选择（LLM 路由 + embedding memory）的不确定性边界，引用自己量化数据。姿态：补充量化视角，非批判（Google 这篇是教程，没夸大）。

---

Solid walkthrough of the managed-memory pattern. One thing worth flagging for anyone adapting this architecture: the two default choices baked in here — **LLM-based orchestration routing** ("if the user wants X, delegate to agent Y") and **embedding-based memory retrieval** — both carry quantifiable uncertainty that's worth knowing the bounds of.

I measured the memory side: embedding cosine similarity couldn't separate synonymy from antonymy (~0.026 difference), so semantic memory retrieval can return near-identical scores for genuinely different writing-style preferences — "Witty" and "Rap" may not be as separable as the retrieval assumes. The routing side has the same precision-recall tradeoff LLM judges do: an orchestrator mis-routing a request isn't a bug, it's the structural property. Neither is a reason not to use this pattern — they're just the honest boundaries of the defaults, and knowing them lets you decide where to add a deterministic check (e.g. routing by task type instead of by LLM intent). Data + full breakdown in Part 2 of my series: https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7

---

## 回复十一：@xm_dev_2026 (Xiao Man) — true negative + adaptive sampling PR + Part 10 write-up

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区
**主题：** Xiao Man 认可 adaptive framing + 要提 PR（edge cases → forge-verify adaptive-rate 扩展）+ 期待 Part 10 write-up；回复呼应 true negative 价值 → adaptive 是对它的回应。

---

Thanks, Xiao Man — and you're right, the true-negative case deserves more credit. "This can't be done within these constraints" is a legitimate verdict, not a confidence failure. That's exactly the logic behind **Type B** in [Part 4](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) — high-risk tasks route to mandatory human, never to an LLM judge. No need to trust a model saying "impossible" when the task never reaches the model in the first place for a judgment it can't make.

Looking forward to the PR. Edge cases format cleanest as `{check, expected, observed, evidence-location}` — they map onto the per-stage `trace` + `failure_class` structure already in place. Happy to review when it's in.

On the write-up — I'll have the full version up soon (it's in final draft). Will link you the moment it's live.

---

## 回复十二：@Mike Czerwinski — argument-space, tested

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区
**主题：** Mike 第二轮 push（argument-space）— 接受 reframe + 实测 + 半步推进

---

Mike,

Conceded on both, and the reframe is the more honest version — took it, ran the test.

The negative gate is the positive gate with the sign flipped, both in word-space; "closes all but one gap" is now "narrows without closing it." Every caught lie becomes a tripwire that never has to be caught twice. And demote-not-decide is the load-bearing one — UNCLEAR routes to human, nothing silent-green.

Tested argument-space. Five scenarios × three evaluators (REQ-3 write-invalidation):

| | C1 regex | C2 LLM | C3 arg-space |
|---|---|---|---|
| correct | 2/5 | 2/5 | **5/5** |

C3 runs the code and observes the side effect; method name and vocabulary are irrelevant. Clincher — the fabricated-snippet case: evidence has a `write()` with `this._cache.delete(key)` that does not exist in the impl. C1 passes (keyword), C2 passes (snippet looks compliant — it even praised the fabricated comment), only C3 rejects (ran the code). DPI bound, DGM fake-log shape.

One caveat I ran: 50 real glm-5.2 agents later, glm didn't hallucinate (0/50), but C1 collapsed to 24% — agents describe correct work in their own words and the regex matches none of it. C1 under real agent output is a vocabulary-matching question, not a reliability question. C3 stayed perfect.

Write-up + scripts/data (draft): [github.com/zxpmail/blog — agent-determinism-illusions](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions).

So the honest framing, in your words: named evasions become permanent tripwires; everything you haven't named routes to a human instead of silently passing.

---

## 回复十三：@Alex Shev — reviewer attention / retire not reroute

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区
**主题：** Alex 的 attention-burn 点（zero-FP + 高拒收 = 操作上错）+ risk routing → retire LLM for expensive mistakes（延续回复八）

---

Alex,

"Operationally wrong if its rejection rate burns reviewer attention" — exactly the cost the Part 2 table doesn't name. Reviewer attention is finite throughput; a zero-FP model rejecting 75% of valid work isn't wrong on any single item, it's a denial-of-service on the review queue (cry wolf). The false-rejection rate burns the budget left for real reviewing.

Your risk routing is the next layer the series took — route by risk instead of asking the model to judge "correct": expensive mistakes → human with deterministic evidence, ordinary edits auto-release. One push past "let the strict model handle expensive mistakes": even in that lane, its 75% false-rejection *still* burns attention — so for genuinely expensive mistakes I retire the LLM entirely and put a human diff review there ("did this change introduce an error?"). Retire, not reroute: the strict model's value is highest where its false-rejections are cheap (low-stakes filtering), lowest exactly where you'd want it (expensive mistakes, where each false alarm is expensive).

Routing shrinks scope; it doesn't break the precision-recall trap underneath. Part 4 develops this: [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf).

---
