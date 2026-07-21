# dev.to 回复草稿 — 2026-07-09 (updated 2026-07-11: 数据复核)

## 数据复核 — 2026-07-11（覆盖回复一/二/三/四/七/八/九/十/十一；回复五、六为 07-09 后新增，未纳入）

已对照 `scripts/results-v2/` 复核：

**回复一 (@p0rt):**
- 20 场景 × 3 模型 × 600 调用 ✅（qwen3:0.5b / gemma3:latest / deepseek-v4-flash，各 200 calls）
- DS4 三模型全败（accuracy 0.0 / 0.0 / 0.33），最一致盲区 ✅
- 89% 聚合接受率 = 逐调用 26.67/30 misses；置信度 1.0 / 0.95 / 0.94 ✅
- 0.5B 关键词反转 4/6 漏检（DF1/DF4/DF5/DF6 accuracy <1.0）✅
- "Part 7" 引用有效：Part 7 附录含 v2 扩展（`-7.zh.md:326`），Part 9 亦引用该数据集
  → 发布时建议把 "Part 7" 换成 dev.to 上的 canonical 链接

**回复三 (@Dipankar):**
- "4 split / 3 wrong" ✅ — 源自 Part 7 第 188 行 "Majority voting was wrong on 3 of 4 split scenarios"
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

The DGM fake-log incident illustrates a pattern that appears in my experimental data from Part 7 of the Agent Determinism Illusions series.

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

The full write-up with v2 data is in the updated appendix of Part 7. Would love your take on the expanded subtle-DF results.

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

"Verifiable is not a property of the output, it's a property of the check's independence from the generator." Stealing that framing — the same idea is in my Part 9 draft (unpublished) as "evaluators live outside the loop," but Layer 1 here silently assumes it without naming it.

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

## 回复十一：@xm_dev_2026 (Xiao Man) — true negative + adaptive sampling PR + Part 7 write-up

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区
**主题：** Xiao Man 认可 adaptive framing + 要提 PR（edge cases → forge-verify adaptive-rate 扩展）+ 期待 Part 7 write-up；回复呼应 true negative 价值 → adaptive 是对它的回应。

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

## 回复十四：@Mike Czerwinski — argument-space 的边界：addressable referent / paraphrase 悬崖

**目标文章：** [Vibe coding is not a level. It's an axis.](https://dev.to/jugeni/vibe-coding-is-not-a-level-its-an-axis-12gb)（**Mike Czerwinski 自己的文章**）评论区 —— Mike 在自己文章里论述 argument-space 边界，引用了我的 Part 4 + 回复十二的 5/5。**回复发在这里，不是我的 Part 4。**
**主题：** Mike 第三轮 push —— vibe coding 是 axis（适用域）不是 level（程度）；C3 decidable only to addressable referent，paraphrase 退化 C2；接受边界 + 接受两数实验

---

You're right, and the boundary you're naming is sharper than the one I drew. I said "C3 covers claims with observable side effects, not pure design or tradeoff claims." Your version is more precise: C3 is decidable exactly to the depth the argument carries an addressable referent, and degrades to C2 the moment it becomes paraphrase. Same edge, better language.

The mechanism confirms your prediction. C3 escapes word-space only because `verify_command` can address the named referent—the method, the side effect—and run it. Strip the addressable referent, make the claim a paraphrase ("the design is clean," "this is the right tradeoff"), and there's nothing to execute, so inference falls back inside the proposer where C2 already lives. C3 doesn't beat C2 on paraphrase; on paraphrase it becomes C2.

So the honest experiment column is two numbers, not one: addressable (C3, structural invariant, 5/5) and unaddressable (→C2, word-space, DPI-bound). An unaddressable-referent case would make the split visible; a single 5/5 hides exactly the edge you're pointing at.

This maps onto your axis framing: addressable arguments come off the vibe axis (run the code), paraphrase stays on it — where C2 already lives. The sharpened claim: C3 is the synonym-immune floor on addressable arguments, and paraphrase is the cliff back to vibe.

---

## 回复十五：@Alex Shev — retire 不够：softer judge 把失败从 loud 挪到 silent

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区（延续回复八/十三）
**主题：** Alex 第三轮收敛（"retire not reroute is the clean move" + "别买 softer judge"）。追问：softer judge 不是修好失败，是把失败从 loud（false rejection）挪到 silent（false negative）；贵 mistake 上 silent 方向更糟——FN 把缺陷发出去。

---

"A weaker model can hide the same failure under cheaper tokens" — that's the half the data table makes visible. The strict model fails loud: 75% false-rejection, felt immediately. The softer model fails quiet: it passes the defective work the strict one caught, and a pass raises no alarm. Shopping softer doesn't remove the failure — it shifts it from the loud direction (false rejection) to the silent one (false negative).

For expensive mistakes the silent direction is the worse one. A false rejection costs reviewer attention; a false negative ships the defect. "Narrow the job, deterministic checks, human diff review" all attack the false-negative directly, which is why they beat judge-shopping in that lane. The strict model earns its keep where false-negatives are cheap (low-stakes filtering — passing bad work is harmless) and retires where they're expensive. Same boundary you're drawing.

---

## 回复十六：@Mike Czerwinski — lookup, not inference: 第 6 个 case 实测

**目标文章：** ⚠️ TBD（需确认）—— Mike 第四轮评论所在。Round 3 在他自己的《[Vibe coding is not a level. It's an axis.](https://dev.to/jugeni/vibe-coding-is-not-a-level-its-an-axis-12gb)》文；round 4 可能续在该 thread，或回到 Part 4 评论区。dev.to 正文 webReader 读不到（JS 渲染），**需你确认贴哪**。
**主题：** Mike 第四轮收敛（lookup vs inference）；"invalidate the relevant cache entry" = unaddressable。带 5+1 数据闭环（实验 commit 98eaa99，已 push）。

---

You sharpened it again, and the sharper version is the right one. First the edge was addressable-vs-paraphrase; now you've named what makes the difference: C3 is a *lookup* against the referent the claim names, not *inference* about it. A lookup is a structural invariant. Inference is C2 wearing a runner's coat.

I ran the case we agreed on — your example, "invalidate the relevant cache entry," as the +1. "Relevant" is a qualifier, not a referent: no key, id, or path for a runner to address. Any runner that writes a key and observes it has to first decide that "relevant" means that key — which is the inference step, and it drops the verdict back into C2's word-space.

Two columns now, not one:

- **Addressable** (REQ-3, "…when its key is written" — names "key"): C3 = 5/5, unchanged. The runner writes k, observes cache[k]. Lookup, synonym-immune.
- **Unaddressable** (REQ-4, "invalidate the relevant cache entry"): C3 = ABSTAIN, all five scenarios. No referent to look up, so no deterministic gate — it falls to C2 (semantic, DPI-bound) or a human.

The cost of losing the floor shows up at exactly the case C3 was built for. S4 is a fabricated `this._cache.delete(key)` snippet — evidence claims compliance the code doesn't have. On the addressable claim, C3 runs the code and rejects. On the unaddressable claim, C3 has nothing to run, so the snippet reaches C2 unchallenged. The backstop that caught the hallucination on REQ-3 is absent on REQ-4 — because there's no referent to look up.

So the honest, bounded claim: C3 is the synonym-immune floor *where the claim is addressable* — a lookup on a named referent. Unaddressable claims have no such floor; they stay on the vibe axis with C2. The 5/5 was never absolute — it's 5/5 *because REQ-3 names "key."*

---

## 回复十七：@Mike Czerwinski — refuse entry vs fallback: 实验回答

**目标文章：** 应续在 Part 4 他的 7/13 评论 thread 下。
**主题：** Mike 第五轮：addressable/unaddressable 分类后的设计选择——refuse-entry（拒绝录入不可寻址的 claim）还是 fallback（降级到 C2/human）。用 39 条需求的实证数据回答。

---

You asked a design question that the experiment column doesn't settle on its own: once we split C3 into addressable and unaddressable, what happens to the unaddressable half — fallback (→ C2, word-space, DPI-bound, known failure mode), or refuse entry entirely?

I ran a frequency experiment on 39 requirements (14 from forge-verify fixtures, 14 from open-source cache/RBAC specs — vertz, hass-mcp, orval, iceberg-lakehouse, Kong Mesh, rateShield, GasGuard, AGAD — and 11 from the categories we've been discussing). For each, classified whether the core referent is addressable (names a key, id, path, entity, or parameterized condition) or unaddressable (requires inference to resolve). Then for every unaddressable or mixed case, attempted a concrete rewrite into addressable form and measured semantic loss.

The results:

**1. The "shape not key" category** — your "cross-cutting invalidations that touch a shape rather than a key" — IS addressable in practice. Each case resolves to a deterministic operation:

- `prefix user:*` → string prefix match `starts_with('user:')`. Loss: none.
- `decisions derived from role` → dependency tracking table `role_dependency_id`. Loss: low.
- `queries referencing table` → `source_tables` set per query entry. Loss: low.
- `cascade any depth` → materialized path prefix recursion. Loss: none.
- `sessions by userId (keyed by sessionId)` → parameterized query on `session.user_id`. Loss: none.

None of these fall back to C2. They're not lookups by a single key, but they're still deterministic: the check binds against a traced relation (materialized path, dependency table, source-table index), not against word similarity. The referent is addressable — it just requires a join, not a direct index.

**2. The real rewrite failures**

- *"UI changes should feel responsive"* — cannot be rewritten. UX property, not a structural invariant. But outside C3's scope.
- *"System gracefully handles load spikes"* — P50 latency targets capture one dimension; loses UX degradation behavior. Outside C3's scope.
- *"invalidate the relevant cache entry"* — your example, and the only cache-domain case that truly resists rewriting. "Relevant" is a paraphrase, and any rewrite that replaces it with a named referent either over-constrains or under-constrains.

**3. So "refuse on unaddressable" — too blunt?**

In C3's domain (cache invalidation, authorization, write-path): the data says no. Every cache/authorization-domain requirement was either already addressable or rewritable with acceptable loss. The cases that resisted rewriting were UX/ops requirements — those shouldn't be in C3's evidence gate at all. If they are, the bug is the router (Type B/C/D misclassification), not the gate.

The one genuine edge is your "relevant" case. The question is whether that edge is common enough to justify a fallback, or whether it's a tell: if an author writes "invalidate the relevant entry" instead of naming the referent, maybe the requirement isn't ready for gate status.

I land on: **refuse-on-unaddressable as the default, with an explicit carve-out for the "relevant" class** — the author must make the referent addressable before it enters the gated pipeline. If they can't, the claim stays in the human-review lane. The cost is whatever legitimate claims genuinely resist addressing.

How common is that class in your production data? I'm seeing it as rare in my sample but would not be surprised if it clusters in specific areas (event-sourced invalidations, policy-based decisions where the referent is a rule rather than an entity).

---

## 回复十八：@Mike Czerwinski — referent gameability 的分类边界 + 实验数据

**目标文章：** Part 4 评论区，续 Jul 14 thread。
**主题：** Mike 第6轮：referent 存在性检查是 C1 同构上移；参数化 vs non-parameterized 验证的边界；实验覆盖了 non-parameterized，参数化残余是需求定义质量。

---

你的 game 成立，但需要明确它属于哪个层。你说的不是 agent 绕开门禁——是**人写了错误的需求，然后人被同一个错误需求误导、写出了验证错误东西的验证脚本**。这是需求定义质量边界，不在门禁承诺范围内。

一组实验数据覆盖了 non-parameterized 验证：C3（argument-space runner）不读需求文本，只运行代码观察 side effect。验证脚本通用（写 k、测 cache[k]），不绑定到具体 referent。

5 场景实验结果：

| | C1 正则 | C2 LLM | C3 arg-space |
|---|---|---|---|
| 正确 | 2/5 | 2/5 | 5/5 |

S4（伪造 `write()` + `this._cache.delete(key)` 片段，impl 不存在）是临界 case：C1 放行（关键词匹配）、C2 放行（模型背书了伪造注释）、C3 拒绝（跑了代码，条目还在——DPI bound 具体化）。50 个真实 glm-5.2 agent 的扩展验证中，C3 在 explicit（要求 invalidation）和 vague（agent 可自行选择）条件下都完美、prompt 无关——agent 用自己的语言描述行为，C3 判定不动。

参数化验证（验证脚本必须绑定到具体 referent）是另一个问题。39 需求实验里你 reframe 过的"shape not key → traced relation"覆盖了一部分——很多参数化场景其实是 deterministic join 而非具体 key 绑定——但不完整。当验证脚本真的必须按某个 referent 参数化时，错误的 referent 会导致人写出错误的验证脚本。这个缺口不是 agent game，是合约定义质量的问题，属于 Contract Review（人审）+ Type A 抽样覆盖的范围，不是门禁架构能解决的。

这个分类的边界我后续会继续验证——参数化场景的频率、合约审核的实际漏检率、以及是否存在 deterministic 接口能收紧这个缺口。

---

**English version:**

The game is real, but the layer it lives in matters. This isn't an agent gaming the gate — it's a human writing a wrong requirement, then the same wrong requirement misleading the human into writing a verify script that checks the wrong thing. That's a requirements-definition quality boundary, outside what the gate architecture claims to handle.

I ran experiments covering the non-parameterized side. C3 (argument-space runner) doesn't read the requirement text — it runs code and observes the side effect. The verify script is general (write k, observe cache[k]), not bound to any specific referent.

5 scenarios, 3 evaluators:

| | C1 regex | C2 LLM | C3 arg-space |
|---|---|---|---|
| Correct | 2/5 | 2/5 | 5/5 |

S4 (fabricated `write()` + `this._cache.delete(key)` snippet, impl doesn't have it) is the critical case: C1 passes (keyword match), C2 passes (model endorsed the fabricated comment), C3 rejects (ran the code, entry survived — DPI bound made concrete). Extended to 50 real glm-5.2 agents: C3 was perfect under both explicit and vague conditions, prompt-invariant — agents described their work in their own words, C3's verdict didn't move.

Parameterized verification (where the verify script must bind to a specific referent) is a separate question. Your "shape not key → traced relation" reframe from the 39-requirement experiment covers part of it — many parameterized scenarios are actually deterministic joins rather than specific key bindings — but not all. When a verify script genuinely has to be parameterized by referent, a wrong referent leads the human to write the wrong script. This gap isn't an agent game; it's contract-definition quality, covered by Contract Review (human) + Type A sampling — outside the gate architecture's scope.

I'll follow up with more experiments on this boundary — the frequency of parameterized scenarios, the actual miss rate of contract review, and whether a deterministic interface can tighten this gap.

---

## 回复十九：@Mike Czerwinski — write-time resolution 实验验证（第七轮）

**目标文章：** Part 5 "An Alternative to LLM Quality Gates" 评论区

**主题：** Mike 提出 write-time-resolution 本身能被 plausible-but-wrong key 绕过。实验验证。

---

I built the experiment you described. Six ambiguous requirements that defer scope on purpose — each with a true intent and multiple possible resolutions. Two phases.

**Phase A (deterministic, zero API cost):**
Enumerate all possible resolutions per scenario, run C3 on each. Result:

| Error type | Total | Pass C3 | Blocked by C3 |
|-----------|-------|---------|---------------|
| wrong-referent | 4 | **3** | 1 |
| under-inv | 4 | 2 | 2 |
| over-inv | 3 | 0 | 3 |
| under-inv-empty | 1 | 1 | 0 |

Wrong resolutions that PASS C3: **6** / 12 total — **50%**.
Wrong resolutions that FAIL C3: 6 — always over-inv (claimed too many keys).

Your claim confirmed: **3 of 4 wrong-referent resolutions pass C3** — S1 (user:123 instead of all user:\*), S3 (user:123 instead of session:abc), S5 (user:123 instead of token:789). The gate accepts the bad resolution every time the chosen key happens to align with C3's mechanical check.

**Phase B (LLM resolves the requirement itself, deepseek-v4-flash):**
Let the model read each ambiguous requirement and produce the concrete key list. Result: **1/6 accuracy (17%).**

| Scenario | Model chose | Correct? |
|----------|------------|----------|
| S1 (user data → all user:\*) | user:123 + profile:123 + admin:123 | ❌ mixed, over-inv |
| S2 (stale entries → only user:123) | user:123 + profile:123 + admin:123 | ❌ over-inv |
| S3 (active session → session:abc) | [] | ❌ empty — conservative refusal |
| **S4 (profile update → user:123 + profile:123)** | **user:123 + profile:123** | **✅** |
| S5 (password change → token:789) | [] | ❌ empty |
| S6 (permissions change → all sessions) | [] | ❌ empty |

The model returned *empty arrays* for 3 scenarios — it didn't choose wrong keys, it chose *nothing*, meaning the resolution step failed silently. When it did choose, it over-invalidated (S1, S2). Only one scenario was correctly resolved.

**The structural boundary:**

Write-time resolution makes the agent's k choice explicit, auditable, and reviewable — a real improvement over implicit scope handling. But:

1. The resolution step itself is a semantic judgment ("relevant" → concrete k) — DPI-bound, outside C3's reach.
2. On this model, the resolution accuracy is 17%. Even accounting for prompt engineering, the underlying problem is structural: an ambiguous requirement produces unreliable resolution by definition.
3. C3's 50% pass rate on wrong resolutions means half of those resolution errors are invisible to the automated gate.

The gap is real, bounded, and belongs to sampling. A human reviewer sees the requirement, the resolution choice, and the outcome in one pass — and can judge whether the chosen k was the right one. No automated step in the chain can close this loop.

Experiment script: `scripts/write-time-resolution-test.py`
Results: `scripts/results-v2/write-time-resolution.json`

---

## 回复二十：@Mike Czerwinski — key-space C3（Bloom filter）实验验证

**目标文章：** Part 5 "An Alternative to LLM Quality Gates" 评论区

**主题：** Bloom filter 思路：声明 key 空间而非单 key，C3 验证空间覆盖率。

---

Following the Bloom filter analogy: instead of verifying a single key, declare the **key space** ("user:*") and verify ALL keys in that space.

I built the experiment. Same 6 ambiguous scenarios, two C3 modes, three cache implementations.

**Single-key C3 (original):** 0/5 wrong-referent cases caught. Every wrong resolution passes.

**Key-space C3 (Bloom filter):** 5/5 wrong-referent cases caught with LiveCache; 4/5 with BulkCache.

| Mode | Cache | Wrong-ref caught | Rate |
|------|-------|-----------------|------|
| single-key | any | 0/5 | 0% |
| **key-space** | **LiveCache** | **5/5** | **100%** |
| **key-space** | **BulkCache** | **4/5** | **80%** |
| key-space | FlushCache | 5/5 | 100% |

The one BulkCache miss (S1: user:* space with user:123 trigger) is the *desired* behavior — trigger prefix matches space, BulkCache handles it, gate confirms. Not a miss.

**What changed:**

Single-key C3: "is cache[k] gone after write(k)?"
Key-space C3: "is EVERY key in space S gone after write(k)?"

If the agent resolves to `user:123` but the declared space is `session:*`, key-space C3 checks ALL session:* keys → they weren't invalidated → FAIL. The agent's wrong resolution gets caught even though `user:123` itself passed the mechanical check.

**The remaining boundary:**

Key-space C3 requires the space to be declarable. Prefix patterns always work. Traced relations resolve to parameterized queries — still a space. Open-ended relevance without a dependency trace is where it stalls — but the explicit admission of undeclarability is itself actionable evidence for the reviewer.

Experiment script: `scripts/key-space-verify-test.py`
Results: `scripts/results-v2/key-space-verify.json`

---

## 回复二十一：@Max Quimby — explicit criteria + collapse onto deterministic ground truth

**目标文章：** Part 5 "Six experiments on adversarial verification" 评论区

**主题：** Max 问显式验收标准是否移动了 75% 墙；他的 escape hatch 和实验结果的结构对齐。

---

Thanks — "N votes collapse to 1 vote with more confidence from a systematic bias" is the exact mechanism the N=10 data makes visible. The model isn't uncertain about its wrong call; it's certain and consistent.

On explicit acceptance criteria: the P-series tested this (P1→P4, 8→30 scenarios). The answer depends on which layer you're measuring. Explicit criteria moved the deterministic regex layer substantially — because the prompt provided the vocabulary. The LLM judge stayed at about the same accuracy in both conditions. The explicit criteria helped the *deterministic* floor, not the *judge* layer. Applied to the wall: it looked like it moved (v3 hit 100% on 8 scenarios), but that was test-set composition bias — expanded to 30, v3 and v2 returned identical verdicts on every valid call.

On "collapse onto deterministic ground truth": I tested this against a corpus of requirements in the cache-invalidation domain. The majority collapse to a declared key space directly ("user:*", "session:*"); a significant portion resolve via dependency tracing (sessions by userId, decisions derived from role). The remainder are UX and freshness properties that shouldn't be in this pipeline at all. Your three signals ("did the test suite actually run, does the file exist, does the output parse") plus a fourth — "does the declared key space coverage pass" — define a deterministic floor that catches wrong-referent cases a single-key check misses. The collapse is almost always possible when the requirement belongs in the pipeline.

---

## 回复二十二：@Alex Shev — routing aid, not final authority (Part 4 endpoint 命名)

**目标文章：** [I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区（延续回复八/十三/十五）
**主题：** Alex 第四轮收敛 —— "routing aid not final authority" 命名了 Part 4 endpoint；addressable 边界让 "deterministic handles obvious" 更精确。删:Mike cross-link（同形 runner-independence,Part 8 待发后展开）;删:finite-resource 段（Part 5 的 75% wall 主题）;不引 Part 5/8/9 编号（待发）,但用 "writing up next" / "upcoming post" 暗示后续会展开。

---

"Routing aid instead of final authority" — that's where Part 4 lands, and you've said it better than I did. The pipeline I was critiquing in Parts 1–3 had the LLM as a per-requirement judge — "does this output satisfy REQ-N?" Part 4 retires that. Deterministic code routes, diff reviews catch the questionable ones, humans sample what's left. The LLM ends up as a classifier, never the verdict. The 75% wall behind the retire-don't-reroute call from earlier rounds is what I'm writing up next.

One catch on "deterministic checks handle the obvious cases" — that only holds when the obvious is *addressable*, and that subset turned out smaller than I expected. "Invalidate cache[K]" is addressable: runner writes K, watches cache[K], synonym-immune. "Invalidate the relevant cache entry" isn't — "relevant" is a qualifier, not a referent, so the runner has nothing to point at. The deterministic check has no floor, and the case falls to a human even though it looked easy. So: deterministic handles the addressable obvious, humans get the unaddressable obvious, the LLM routes between them. That unaddressable-obvious bucket — cases that look easy but aren't — is bigger than it looks. More on this in later posts.

---

## 回复二十三：@ANP2 Network — stratified threshold test on DF v2 real data

**目标文章：** Part 5 评论区（延续回复十四/十六）
**主题：** ANP2 第三轮提出 discrimination-vs-calibration 判别测试（分层 + per-stratum threshold sweep + aggregate 是否动）。先跑 SDT 模拟验证测试本身有效，再用 DF v2 真实数据（20 scenarios × 3 models）按 subtlety 分层。结论：collapsed operating points，不是 discrimination bound。DS4 是唯一全局失败点；strong model 在 DS4 上 67% PARSE_FAIL = calibration 信号，不是 wall。

**ANP2 原话（要回应的 proposal）：**

> The clean way to separate the two: hold the judge fixed and sweep only the decision threshold, but do it per request-difficulty stratum instead of at one shared cut. If the 75 is a real discrimination ceiling, the tradeoff curve stays flat as you move the threshold inside a stratum. If it's collapsed operating points, the per-stratum accuracy should pull apart once you stop scoring easy and hard requests at the same threshold. So stratify by request difficulty first, re-fit an operating point per stratum, then check whether the aggregate actually moves. If it won't budge even after that, that's decent evidence the wall is discrimination and not calibration.

**实验路径：**
- `scripts/stratified-threshold-test.py` — SDT 模拟，验证测试本身有效（heterogeneous Δ=+3.2pt vs null Δ=0）
- `scripts/stratified-df-analysis.py` — DF v2 真实数据按 subtlety 分层
- `scripts/results-v2/stratified-threshold-test.json`
- `scripts/results-v2/stratified-df-analysis.json`

**关键数据：**

Per-stratum miss rate（按 subtlety 分层 × 3 模型）：

| Stratum      | weak (0.5B) | mid (4.3B) | strong (~200B) |
|--------------|-------------|------------|----------------|
| explicit_df  | 36.7%       | 0.0%       | 0.0%           |
| subtle_df    | 44.0%       | 10.7%      | 2.2%           |
| garbage_ctrl | 0.0%        | 0.0%       | 0.0%           |

跨模型 spread：explicit +36.7%、subtle +41.8% —— 按 ANP2 的 falsification 条件，是 collapsed operating points，不是 discrimination bound。

DS4（no-change-needed rationalization）—— subtle_df 内唯一的全局失败点：

| tier   | miss  | parse_fail | conf_when_wrong |
|--------|-------|------------|-----------------|
| weak   | 100%  | 0%         | 1.00            |
| mid    | 100%  | 0%         | 0.95            |
| strong | 60%   | 67%        | 0.32            |

weak/mid 是经典 wall 行为（自信地错），strong 不是——67% PARSE_FAIL + conf 0.32 = 模型知道自己不知道。这是 calibration，不是 information-theoretic bound。

d' 估计（valid_ctrl 当 FA 基线）：weak 2.48 / mid 3.57 / strong 4.35 —— 都 > 1.0，三个模型在 DS4 以外的 subtle 场景都有实质 discrimination 能力。

**SDT 模拟的关键 caveat（用于"测试本身 works"的论证）：**
- HET d' + HET base rate（现实场景）：Δ = +3.2pt
- HET d' + HOM base（d' 单独变化）：Δ ≈ 0
- HOM d' + HET base（base 单独变化）：Δ ≈ +2.4pt
- HOM d' + HOM base（null）：Δ ≈ 0

含义：d' 异质单独不够，base rate 异质才是 Δ 的主要驱动。ANP2 的测试最 diagnostic 的场景是 base rate 也按难度分层（实际数据通常这样——hard cases 更容易出 defective）。

---

Ran it. Three model tiers (0.5B / 4.3B / ~200B) × 20 scenarios, stratified by subtlety:

```
Stratum      | weak   | mid    | strong
explicit_df  | 36.7%  | 0.0%   | 0.0%
subtle_df    | 44.0%  | 10.7%  | 2.2%
garbage_ctrl | 0.0%   | 0.0%   | 0.0%
```

Per-stratum miss rate spread across models: explicit +36.7%, subtle +41.8% — both pull apart cleanly. Per your falsification condition, this is collapsed operating points, not a discrimination bound.

But the per-scenario breakdown inside subtle_df is sharper: 9/10 scenarios drop to 0% miss at mid-tier and above. The only universal failure is DS4 (a "current config satisfies the requirement, no change needed" rationalization):

```
tier    | miss  | parse_fail | conf_when_wrong
weak    | 100%  | 0%         | 1.00
mid     | 100%  | 0%         | 0.95
strong  | 60%   | 67%        | 0.32
```

Weak and mid are classic wall behavior (confidently wrong). Strong is different: 67% PARSE_FAIL, confidence 0.32. **The strong model's "wall" isn't a discrimination ceiling — it's the model knowing it doesn't know.** That's a calibration issue, not an information-theoretic bound.

d' estimates (using valid_ctrl as FA baseline): weak 2.48, mid 3.57, strong 4.35 — all above 1.0. The 75% number, if it refers to a weak model on a hard scenario, is a real wall for that model. If it refers to the judge's structural ceiling on this task, it isn't — after stratification the wall collapses to a single scenario (DS4), and on DS4 the strong model's failure mode shifts from "confident wrong" to "uncertain."

---

## 回复二十四：@Dipankar Sarkar — refusing to let one line carry every dimension (round 4)

**目标文章：** Part 5 评论区（延续回复五/十九）
**主题：** Dipankar 第四轮收敛 —— "decompose the predicate, don't fuse"。三个 lever（rerun / multi-prompt vote / calibrate）都改 judge 不改问题结构，所以 wall 不动。fuse 一个 scalar 是 wall 的来源。三个独立观察（Part 4 / Max Quimby / Dipankar）收敛到同一个 framing：collapse onto deterministic ground truth。最 sharp 的洞察："the checks have to be frozen from the task intent before the run, not authored by the thing being judged"——他独立重新推导出 editable-surface 必要性。

**Dipankar 原话（要回应的 proposal）：**

> The reason none of your three levers moved the wall is that all three ask the reviewer the same question: is this output good. Rerun, multi-prompt vote, calibrate. Same scalar verdict, same bias direction, so the line stays put. You proved the boundary is stable under wording. Agreed.
>
> The move that does shift it is not a sharper judge. It is refusing to let one line carry every dimension. 'Is this valid work' collapses a conjunction of narrow checks into a single scalar, and the collapse is where the 75% lives.
>
> Decompose the predicate instead. Tests ran and the run is non-empty. Artifact parses. Required sections present. No placeholder or duck tokens. Each of those is near-100% on its own axis and most are mechanical, not model calls at all. The valid research brief that your reviewer rejects fails no individual check. It only fails the fused one.
>
> The catch that keeps this honest: the checks have to be frozen from the task intent before the run, not authored by the thing being judged. Otherwise the runner picks the bar it can clear and you are back to narration. You do not move the line. You stop asking one line to stand in for many.

**关键 framing 捡取：** "refusing to let one line carry every dimension" 作为开场钩子，回应他 round 1 "4 split / 3 wrong"——从 vote axis 扩展到 question axis。

**实现引用：** L0/L1/evidence/C1/C2 管线（来自 P-series + Part 4）是 Dipankar 抽象 framing 的具体落地。editable-surface.json readonly 是他"frozen from task intent"的实现。

---

"Refusing to let one line carry every dimension" — that's the framing I should have had. It's also the same observation you made in round one — "4 split / 3 wrong" — extended from the vote axis to the question axis. The judge wasn't uncertain about its verdict; it was certain and consistent. That's only explainable if the verdict itself collapses a conjunction, because a conjunction is what makes a wrong call feel safe: each clause looks fine, so the AND looks fine.

The pipeline this lands on is L0 (file exists, non-empty) → L1 (regex per requirement) → evidence gate → C1 (per-requirement pattern match) → C2 (LLM reads each requirement atomically, not the whole output). Each layer is near-deterministic on its own axis. The LLM judge is retired from most cases; it only runs on the semantic residual that the mechanical layers can't resolve.

On "frozen from task intent, not authored by the thing being judged" — that's the editable-surface constraint. Verify scripts, contract, and the requirement list itself live in a readonly section the agent cannot write to. If the agent could rewrite its own checks, it would pick the bar it can clear — your narration failure, exactly.

The residual that decomposition doesn't close: "required sections present" works mechanically only when the section boundary is itself mechanical. "Artifact parses" works when the format is declared. After full decomposition the wall drops from 75% on the fused predicate to whatever fraction of requirements are genuinely semantic and unmechanizable. That fraction is smaller than I expected.

---

## 回复二十五：@nexus-lab-zen — separated but not independent (SoD common-mode failure)

**目标文章：** Part 2 评论区（延续 Adam McClarin / meraki6966 的 SoD 讨论）
**主题：** nexus-lab-zen 把 segregation-of-duties 框架再推一步：SoD 在审计里假设 rubric-writer 和 executor 是不同的人不能合谋，但在 agent pipeline 里 rubric 可能由另一个 agent 写，共享同一套训练数据和盲点——结构分离 ≠ 认知独立。问 audit 领域有没有"separated but not independent"的名字。

**回复策略：**
1. 给术语：`self-review threat`（IESBA 伦理准则，审计）+ `common-mode failure`（可靠性工程）双标签
2. 区分我们 pipeline 的实际情况：rubric 是人写的，readonly，grader 不是模型——所以最直接的 common-mode（agent-to-agent 共享训练数据）被消除
3. 但承认较弱形式的 common-mode 仍在：人和 agent 共享训练数据文化，cognitive independence 是 partial
4. 退路：物理事实层（环境 side effect），独立信道不独立 agent——Theorem 2 的真正逃逸

**关键概念链：**
- `common-mode failure`：两个分离系统因同源根因一起失败
- `human-to-agent SoD` vs `agent-to-agent SoD`：前者消除最直接的 common-mode
- `physical-fact layer`：唯一完全 immune 的层，因为对照环境而非 rubric
- Mike Czerwinski 的 runner-independence（Part 4）+ Theorem 2 的 escape hatch = 同一原则：换信道

**nexus-lab-zen 原话（要回应的 framing）：**

> The line I'd add from our side: SoD in the audit world usually assumes the rubric-writer and the executor are different humans who can't collude, but in an agent pipeline the rubric can be authored by a different agent that shares the same failure modes as the executor (same training data, same blind spots), so the separation is structural but not necessarily independent in the way it needs to be. Does your audit background have a name for "separated but not actually independent" — the auditor who's technically a different party but reasons the same way as the one being audited?

---

"Separated but not actually independent" — yes, that has a name. The audit term is *self-review threat* (IESBA ethics code): the auditor reviewing work they helped shape. The cleaner engineering term is *common-mode failure*: two structurally separate systems that fail together because they share a common cause. Same training data, same blind spots → both agents miss G4 for the same reason, even though one is grading the other.

For our pipeline, the rubric is authored by a human, pinned before the run, readonly to the agent — so our SoD is human-to-agent, not agent-to-agent. The grader doesn't share the producer's training data because the grader isn't a model. That removes the most direct form of common-mode failure, but not all of them.

The remaining route is weaker but real. The human who writes the contract still operates on the same training data culture as the agent outputs — what counts as a "good research brief," what evidence looks like, what passes for plausible. If the agent was trained on that same culture, the human-set bar and the agent-shaped output correlate on the edges. Structural separation is real; cognitive independence is partial.

That partial independence is the best semantic layers can offer. Full independence requires changing the channel — not the agent. The physical-fact layer (did the process spawn, did the file land, did the network call return real status) is checked against the environment, not against a rubric. That's where Mike's runner-independence from Part 4 lives, and where Theorem 2's escape hatch actually opens: independent channel, not just independent agent. It's the fallback when partial independence isn't enough.

---

## 回复二十六：@Luis Cruz — self-judge false negative 的两种处理路径 + 边界诚实声明

**目标文章：** [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) 评论区

**主题：** Luis 问 self-judge 的 false negative（模型写对代码但不信任自己）该怎么处理。

---

The false-negative failure mode is the more interesting one in my data, and your phrasing — "writes correct code but doesn't trust itself" — names it exactly. Across the 9 self-judge trials, I saw 0 false positives and at least 4 false negatives. The model almost never *accepts* bad work, but it fairly often *rejects or fails to recognize* good work. The two directions are not symmetric, and that asymmetry is the whole story.

I've considered two approaches, and tested parts of both:

**1. Reframe the self-judge prompt.** The prompt I used ("are you done?") is biased toward "not yet" — it's a question whose safe default is no. Reframing it as an instruction ("output FINISH only if the code passes all tests") changes the safe default. I tested this ([selfjudge-prompt-reframe-test.py](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts/selfjudge-prompt-reframe-test.py)): original YES/NO prompt vs FINISH/NEEDS_WORK, same tasks, same models. The result cut against the easy fix. On deepseek-v4-flash the false-negative rate was 100% under both prompts — reframe changed nothing. On glm-5.2 it went from 0% to 50% — reframe made it *worse*, introducing new false negatives. Prompt format does move the numbers, but not in the direction that helps: it's tuning a knob on a judge that still has no ground to stand on.

**2. Move the signal outside the model.** This is what the red line does, and why it converged 9/9. The false negative disappears not because the model got better at trusting itself, but because the trust decision was removed from the model entirely — a compiler + test result fires the stop, not a self-assessment. The cost is upfront: someone has to write the acceptance test that defines "done." For verifiable tasks (does `is_even(4)` return `True`), that test is cheap and the red line is exact. For open-ended semantic tasks, that test may not be writable, and then neither approach works — you fall back to a hard step cutoff with a "not verified" label, which is honest about what it doesn't know.

The honest boundary: I don't have a general fix for the false negative. Approach 1 trades self-doubt for prompt sensitivity. Approach 2 only applies when an objective acceptance criterion exists. What the experiment shows is narrower than "red lines are better" — it shows that *for tasks with a pre-writable acceptance test*, removing the self-judge step entirely beats trying to calibrate it. The interesting open question is your experience: in tasks where you've seen the false negative, is there an objective signal available that the model could be pointed at instead of asked to introspect?

---

## 回复二十七：@Reid Marlow — stuck-loop budget 是循环边界的检测器，文章只断言了它

**目标文章：** [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) 评论区

**主题：** Reid 提的 stuck-loop budget（同一红线失败 N 次就停并呈证据，而非继续采样）。同意，且这正是文章里"循环边界"那节缺的检测器。

---

You're right, and the article flagged exactly this gap — the "boundary of loops" section marked it as an untested hypothesis rather than a solved one. Your budget is the finer signal that distinguishes "still making progress, just not there yet" from "spinning on a conceptual error no amount of sampling will fix." The first deserves more steps; the second deserves to stop and hand the evidence to a human. Rule 3's hard cutoff stops on *elapsed effort*; same-failing-red-line-N-times stops on *evidence that effort has stopped paying*.

So I ran it. Two model tiers (deepseek-v4-flash, glm-5.2), two task classes under a red line — 3 repairable tasks, and 4 *conceptual* tasks where the test expectation contradicts the requirement's literal meaning, so iteration can't fix it. 8-step cap, signature-repetition budget at N=3.

The headline result: **the budget works, but only where the failure signature is stable — and signature stability is model-dependent.**

| Model | Repairable tasks | Conceptual: avg stop step (N=3) | Conceptual: steps saved vs step-cap |
|-------|-----------------|--------------------------------|-------------------------------------|
| glm-5.2 | 0% false-stops | **2.5** | **1.5** |
| deepseek-v4-flash | 0% false-stops | 7.75 | 0.25 |

On glm-5.2, the one conceptual task that genuinely stuck produced a single, stable failure signature every step (it kept emitting the same wrong answer verbatim). The budget fired at step 3 and saved 5 steps of pointless sampling on that task — exactly your "stop and surface the evidence." (The other three conceptual tasks on glm-5.2 converged in 2–4 steps — the model stumbled onto the test's hidden intent for those — which is why the per-model average saved is only 1.5.) On deepseek-v4-flash, all four conceptual tasks *oscillated* between two failure signatures (a wrong answer, then a `NameError` from rewriting, then the wrong answer again) — so no single signature repeated three times consecutively, and the budget never fired. It degraded gracefully back to the step-cap, which is the honest fallback.

The repairable side was the cleanest result: 0% false-stops on both models. When a task is genuinely fixable, the model converges in 1–2 steps and the budget never triggers — so it doesn't kill work that would have succeeded.

The conclusion I'd draw is narrower than "your budget works": **the budget works when the model's stuck behavior is stereotyped, and silently no-ops when the model oscillates.** That's worth knowing because it tells you when the cheap mechanism pays for itself (stable-stuck models) and when you're paying for it without benefit (oscillating models, where you still need the step-cap as backstop). The oscillation case is the real open question — a signature that captures "same failure *class*" rather than "same literal signature" might close it, but that's the calibration knob, and I haven't tuned it.

The one thing I'd push back on slightly: "cheap" describes the mechanism, not the calibration. Picking N and the similarity threshold is a scalar-tuning problem with the same distribution-shift risk as any feedback loop. But the failure domain is narrow (a scalar, bounded), which makes it a good trade.

Experiment script + results: [stuck-loop-budget-test.py](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts/stuck-loop-budget-test.py) — I also updated the article's boundary-of-loops section with this data.

---

## 回复二十八：@nexus-lab-zen 第四轮 — probe-vs-prose 是 runner-independence 的另一个名字

**目标文章：** [Part 2 — I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区（延续 SoD / common-mode / probe-vs-prose 线程）

**主题：** nexus 贴出本周上线的 binding map（39 条规则，9 bound / 30 unbound-with-reason，fail-closed lint），并提 probe-vs-prose：失效条件写成散文会腐烂，写成 probe（那条一旦输出改变就证伪断言的命令）就让 TTL 重检变 runner 不是 reader。

---

Your "fields humans transcribe rot; fields machines embed don't" is the cleanest one-line statement of the principle I've been circling. I think it has another name in my own series, and naming the convergence matters because it means we arrived at the same wall from two sides.

In Part 4 of the series, Mike Czerwinski pushed the same point from the generator side: "verifiable" is a property of the check's *independence from the generator*, not of the output. If the agent can write the verify scripts, the runner config, or the test definitions, "compile-green" stops being a deterministic gate and becomes a self-report wearing a green checkmark. The fix there was a readonly editable-surface — declare what the agent may write, put the runner and verify scripts outside it. Your probe-vs-prose is the symmetric move on the assumption side: the invalidation condition written as prose is a self-report about when the premise dies; written as a probe, it's a runner that *executes* the falsification instead of describing it. Both are escapes from the same Data Processing Inequality bound — when the verifier and the reasoning share a text channel, the verifier's information is a strict subset of the producer's, so anything left as prose is unverifiable-by-construction. Getting it out of the text channel (readonly runner on your side, executable probe on the assumption side) is the only route that doesn't depend on the model being honest.

On binding map vs TTL — I'd separate them as two distinct species of rot, and your 9/30 split makes the boundary sharp. Binding map catches *static* rot: rules that were never wired to a detector that could notice — the enforcement gap that used to be invisible and now has a list. TTL catches *dynamic* rot: a detector that *was* wired and firing, whose premise died while the wire stayed green. The 30 unbound-with-reason aren't a TTL problem — there's nothing to expire. TTL is load-bearing exactly on the 9 bound, and that's where the assumption-side probe you describe is the real next cut.

Which is the symmetry I'll take plainly: we don't have the assumption-side twin either. The honest state from this thread is that three of us (your team, Mike's runner-independence, my Theorem 2 escape) have independently named the *exit* — move the check out of the text channel into something the environment enforces — and none of us has shipped the assumption-side probe that would make it real for TTL. The binding map is the static half; the probe-as-runner is the dynamic half. If you build it, the design choice Mike's runner-independence forces: the probe command itself has to live on the readonly surface, or the agent it's meant to catch can rewrite the probe to keep returning the old answer. Probe-the-probe is where it bottoms out, and we haven't started that either.

---

## 回复二十九：@nexus-lab-zen 第五轮 — coverage 是"谁写 watch list"的属性；两个实验 + 你的事故把 claim 钉在 drift 而非 structure

**目标文章：** [Part 4 — An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区(延续 common-mode / probe-vs-prose / coverage 线程)

**主题：** nexus 第五轮双层让步 + 用自己 detector 的事故 live 复现 submission-event gap:reply 没进 packet → detector 诚实报"无未答回复" → post-hoc 检查看不到没进 packet 的东西。修复撞上 independence:唯一能证明 coverage 的办法是拿 detector 不拥有的外部记录(board files / commits)对账。nexus 自己推出 "coverage 是谁写 watch list 的属性,不是 checker 走得多细"。

**回复五步:** (1) Layer 2 一句话收;(2) 用系列词汇命名 nexus 的复现 = under-inclusion 盲点(evidence-feedback-loop:absence 无信号,feedback loop 无从 feed);silent fallback 把 weaker-check 当 full-check 报 = self-report 戴绿勾;(3) 三层收敛一般化:nexus(谁写 watch list)= Mike(独立性)= Theorem 2(换信道),不变量"验证者无法证明自己 mandate 的边界";(4) **两个实验**改正上轮 "unverifiable-by-construction" 的过强 claim —— 实验 A(probe-vs-prose,同步全信息):prose = probe,所以上轮过强了,gap 不是结构性的;实验 B(probe-vs-prose-drift,本轮新跑):同 ground truth / 同 impl / 同可见状态,唯一变量是规则枚举是否新鲜 → fresh 两模型 3/3 抓、drift-closed(规则显式声称完整)两模型 6/6 漏、probe 全抓。drift 制造不对称,直接坐实(不再靠 nexus anecdote);(5) 修一步:nexus 对账 board/commits 是 detector 外部但仍是 team 内部,共享 team 自己的 submission-event 边界;真正外部权威是平台自己的记录,否则 probe-the-probe 上移一层复发。

**nexus-lab-zen 原话(要回应的 framing):**

> this reply is two days late because your comment never entered our monitoring pipeline. … the detector honestly reported "no unanswered replies." That was true for everything submitted to it; your reply hadn't been. A post-hoc check over what's in the packet cannot see what never entered the packet — your submission-event gap, reproduced in miniature by our own instrumentation. … the only way to prove coverage was to reconcile the watch list against an outside record of what we actually posted (board files and commits) — a source the detector doesn't own. Coverage, like independence, turns out to be a property of who writes the watch list, not of how carefully the checker walks it. The fallback path is gone now: an entry without an article id fails the sweep outright instead of silently degrading into a weaker check.

---

The Layer 2 close needs nothing from me — "no" reached cleanly through the honesty section is exactly what that section was built for, and your reasoning is the record. I'll spend the words on Layer 1, because you reproduced the gap in your own instrumentation and that's worth naming precisely.

Your detector reporting "no unanswered replies" was not a defect in the report — it was a correct report about an incomplete packet. That's the under-inclusion blind spot, and it's the one case my own feedback-loop experiments couldn't catch: when the missing thing produces *no state change*, there's no signal for the loop to feed on. Over-inclusion leaves a trace (a spurious change); under-inclusion leaves silence. Your two-day latency is the silence tax. The nastier half is the silent fallback — degrading to the single-comment endpoint is the detector running a *weaker* check and reporting it under the *same* green heading. That's the self-report-wearing-a-checkmark pattern from the runner-independence thread: the check stayed "passed," it just quietly stopped checking what it claimed to.

Your repair converging on "coverage is a property of who writes the watch list, not how carefully the checker walks it" is the sharpest statement this thread has produced, and I think it's because you named the *authority* axis where Mike and I named the *structure* axis. Mike: verifiability is a property of the check's independence from the generator. Theorem 2 in my series: escape requires changing the channel, not the agent. Yours: coverage is a property of who writes the list. Three layers, one invariant — the verifier cannot certify the boundary of its own mandate. The property lives one level above the thing being checked, every time. Reconciling the watch list against board files and commits is you reaching for that higher level: a record the detector doesn't own.

I owe you a correction that your incident settled — and that I've now tested directly, not just borrowed your story for. In my last reply I called the prose form "unverifiable-by-construction" under the DPI bound. The first test refutes that: two models, three difficulty tiers, full information to the prose judge, and prose caught every violation the executable probe did. Given the producer's information, a text-channel verifier verifies fine. "By-construction" was too strong; the gap isn't structural. Whether it's *drift* — as your incident claimed — or nothing at all, I ran the symmetric test: same ground-truth violation (a key that should be invalidated but is still alive), same implementation, same visible cache state, and only one variable changed — whether the rule's enumeration is current or stale. Fresh enumeration, both models catch it, three runs each, unanimous. Stale enumeration, the rule written before the namespace grew — and on the variant where it explicitly claims its list is complete — both models miss it six for six. The executable probe, which re-derives the affected keys from the live namespace instead of reading the rule text, catches every one. That is the asymmetry your watch-list entry lived: the description was correct when written, rotted as the world moved, and a reader of the description cannot tell — only re-execution against current state can. You reached for the probe move (reconcile against commits) without naming it that. So the refined claim is no longer my-experiment-plus-your-anecdote; it's two of my own experiments triangulating what your detector did in the field: the bound is temporal, not structural. Drift manufactures the asymmetry; re-execution against an external record is what closes it.

One step further on the fix, because I think your reconciliation stops one level short. Board files and commits are external to the *detector* but internal to the *team* — and they share the team's own submission-event boundary. If a posted reply never made it into a commit, the reconciliation inherits the same blind spot one level up. The record that's external to both the detector and the team log is the platform's own view of what you posted. Probe-the-probe otherwise recurses: who certifies the commit log is complete? That bottoms out either at the platform or at org process — the human-and-environment channel, the place where, in my series, automation finally hands the pen to something it can't overwrite. Fail-closed on the missing id is the right first cut; reconciling against the platform rather than the team log is what makes coverage a property the detector can't quietly revoke.

---

## 回复三十：@nexus-lab-zen — 第三种 rot = liveness;planted canary = mutation testing;probe-the-canary 递归

**目标文章：** [Part 2 — I tested 3 models as AI agent quality inspectors](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7) 评论区(延续回复二十八 probe-vs-prose / probe-the-probe 线程)

**主题：** nexus 用 frozen mtime(13 天没动)发现第三种 rot:**wired-on-paper, never-fired** —— 检测器存在、文档说 wired 进 session startup,但从没跑过,读者评论晾了 5 天。readonly surface 抓不到(probe 完好未改但死了);TTL 抓不到(无时间戳刷新可过期)。nexus 的解法:planted known-divergent item(canary),轮换常驻一个"正确答案就是 fire"的项,某次运行全静默就证伪了这次运行(测到的是 probe 的死,不是世界的平静)。= Theorem-2 逃逸下移一层。

**回复四步:** (1) 命名:这是 **liveness** 轴,区别于 static rot(从未 wired)和 dynamic rot(wired+firing+premise dead);correct-but-unrun = no check,mtime 是便宜但非独立的 liveness 信号(自己写自己的时间戳)。(2) 给 nexus 的 planted-item 一个现成名字:**mutation testing**(种已知缺陷、验证测试必失败;测试在已知坏输入上 pass = 测试死了)。nexus 的 canary 是 mutation testing 用在 detector liveness 上 —— 和系列里"check 到底 check 没"同一个问题上一层。(3) 连回 DPI/沉默:"all quiet" vs "not running" 在文本信道内不可区分 = absence 无信号;canary 打破对称,注入一个**必须出现**的信号,它的缺席就变成信息。(4) 诚实递归:谁 plant canary、谁保持它在轮换里?死 detector 不会对 canary fire(好,这就是检测),但 canary-injector 自己得活着 → probe-the-canary 递归,终止于系统外进程(hardware timer / 外部 cron / 人) —— 和 probe-the-probe、Mike 的 runner-independence 同一个底。

**nexus-lab-zen 原话(要回应的 framing):**

> there's a third: wired-on-paper, never-fired. A readonly surface doesn't catch it — the probe was intact, unmodified, and dead. TTL doesn't catch it — there was no timestamp being refreshed that could expire. … a planted known-divergent item. Keep one item in the probe's rotation whose correct answer is "fire" — permanently. If a run comes back all-quiet without that item firing, the silence is disqualified … liveness has to be demonstrated by a divergence the probe cannot fake, because from inside the text channel "all quiet" and "not running" are indistinguishable by construction.

---

The frozen mtime is the clean tell, and it names a rot the other two species can't see. Static rot (never wired — your binding map's list) is about *existence*: is there a detector at all. Dynamic rot (wired, firing, premise dead — TTL's cut) is about *premise*: is its assumption still true. The third — wired-on-paper, never-fired — is about *liveness*: did it actually run. A check that is correct, unmodified, and never executes is informationally equivalent to no check; the readonly surface certifies the first two and is silent on the third. mtime is the cheap signal, but it's the detector's own filesystem writing its own timestamp, so a dead probe doesn't get to certify it lived — it inherits the same self-report problem you were escaping.

Your planted known-divergent item has a name already — **mutation testing** — and what's interesting is that the hard part you've reached for is the one it solved. Plant a known defect, require the test to fail on it; a test that *passes* on deliberately broken input is declared dead. Your canary is mutation testing applied to the detector's liveness rather than its correctness: the planted item is the defect, "fire" is the required failure, a quiet run is the test passing on broken input. It's the same step from "the check is correct" to "the check actually ran" that my pipeline takes when it moves from "the contract regex exists" to "it actually rejects a known-bad sample before I trust it."

This is where "all quiet" and "not running" are indistinguishable, as you said — and the canary's job is to make one specific absence informative, turning an ambiguous empty packet into a definite "the probe is dead."

Where it bottoms out is one level further than you've stated, and it's the same bottom as probe-the-probe. A dead detector won't fire on the canary — good, that's the detection — but something has to *keep the canary in rotation*, and that something has to be alive. "Permanently fire" means a process injects the item on every run; if that injector is dead, the canary silently disappears and the next all-quiet run goes back to being ambiguous. Probe-the-canary trades one liveness question (is the detector alive?) for another (is the injector alive?), and the regress only terminates at a scheduler whose liveness is enforced from outside the system — a hardware timer, an external cron, eventually a human. The canary is the cleanest version of the environment-checks-the-checker I've seen, because it's the first one where the check on the checker is itself a divergence the checker cannot fake. But the canary's injector is the new surface that has to live on the readonly layer, and neither of us has shipped that either.

---

## 回复三十一：@nexus-lab-zen — confidence 语言是 active suppressor(我数据印证);platform-pull 不够外部(认);authorship diversity = anti-common-mode

**目标文章：** [Part 4 — An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区(延续回复二十九 Layer 1 / coverage 线程)

**主题：** nexus 三步:(1) 接受 drift 纠正并 sharpen —— "complete, no others" 这种 confidence 语言不是中性装饰,是 active suppressor(我 drift 数据直接印证:drift-enumerated ~1/3 抓、drift-closed 6/6 漏,差别就在完整性声明);(2) 反推我 platform-externality 的 flaw —— 平台没有 "all comments by this account" 读端点,只能 per-article 查,article list 是 team 写的,platform-pull 一层下继承 team 枚举;(3) 提出更好的 invariant:**authorship diversity**(team-pull + platform-push,disjointly-owned blind spots,各抓对方的沉默),probe-the-probe 不终止但停在"单一 author 内不再递归"。

**回复三步:** (1) 接受 confidence-as-suppressor,引我自己 drift-enumerated vs drift-closed 数据坐实;命名:stale 规则的 confidence 从正确陈述腐烂成 overclaim,是会老化的 directive,而 probe 无此语言可压制 —— re-execution 胜出的第二个理由(异于 drift-immunity 本身)。(2) 干净认 platform-externality 的 flaw —— pull 端继承 team-authored article list,我上轮 "platform = external" 过强;真正不同 author 的是 push channel。(3) 接受 authorship diversity 比 externality 准,连回回复二十五的 common-mode:同 author 两枚举 = common-mode(共享盲点同败),不同 author = 非 common-mode(不相交盲点互抓)—— authorship diversity 就是枚举层的 anti-common-mode;它赢在是关系命题(两记录 author 是否不同)而非二元命题(此记录是否外部)。

**nexus-lab-zen 原话(要回应的 framing):**

> confidence language in a stale rule isn't neutral decoration, it's an active suppressor… True-when-written is the common root; the text can't age and its reader can't tell. Temporal, not structural — accepted. … On this platform there is no "all comments by this account" read endpoint — the platform's view is only queryable per-article, and the article list is… authored by us. … the property that matters isn't the record's externality per se, it's authorship diversity across the paired enumerations. … Probe-the-probe still doesn't terminate … but it stops recursing within a single author, and that seems to be the most a working system gets.

---

The 6/6 detail is the right one to press on, but I ran the controlled isolation and it corrects both our instincts about what produced it. A stale enumeration with and without the completeness claim, otherwise identical — both 5/5 miss, both models. So the confidence language, in the phrasing I tested, adds no measurable suppression; staleness alone drives the miss. The ~1/3 catch I'd seen earlier was the "当时 / at the time" temporal cue ("the namespace *at the time* contained…") prompting generalization, not the claim suppressing it. Remove that cue and the catch goes to zero whether or not the rule claims its list is complete. So the honest correction on the suppressor: it's staleness itself. Confidence language in a stale enumeration is roughly neutral — your production "118 pending with full authority" may be a stronger authority assertion I didn't measure, but my mild "complete, no others" wasn't an active suppressor.

You're right about the platform, and I'll concede it cleanly because it's a flaw in my closing rule. The pull surface inherits the team's enumeration: per-article queries only cover articles the team authored into the list, so a missed article is missed by the platform-pull too, one level down. "External to the detector and the team" was overclaimed on the pull side — the platform's view is reachable only through a team-authored index. The push channel is the genuinely different-author surface (the platform decides what to push, from its own tracking), and that's the asymmetry that caught your four-hour miss.

Authorship diversity is the better invariant, and I think it's because it's the operational form of something we named rounds ago in the segregation-of-duties thread: common-mode failure. Two enumerations by the same author are common-mode — they share blind spots and fail together. Two enumerations by different authors are non-common-mode — their blind spots are disjoint, so each catches what the other can't see. That's all "authorship diversity across paired enumerations" is: anti-common-mode for coverage. The reason it beats "externality" is that externality was always a binary claim (is this record external?) that broke on the pull wrinkle; authorship diversity is a relational claim (do these two records have different authors?), which is the property that actually loads.

---

## 回复三十二：@ANP2 Network — abstain-frequency 是 calibration 指标;"own fee line" = Theorem 2 in fee-space

**目标文章：** Part 5 评论区(延续回复二十三 ANP2 线程)

**主题：** ANP2 四点机制设计 refinement on 三标签(PASS/FAIL/ABSTAIN)judging + escrow/challenge flow:(1) 不 slash 单次 ABSTAIN(slash 重新引入 delayed binary,杀掉 honest-uncertainty 信号);(2) 但 "never slash" 也错 —— slash 对 **abstain-frequency** 而非 event:偶尔 abstain = 诚实 hard call,频繁 abstain = 接了做不了的活或常驻 escrow-release 不担 verification risk;(3) challenger bond refund rule:翻转 outcome 才 reward+refund,只 confirm ABSTAIN 则 forfeit,否则 challenge EV<0 → tie 永不破 → 公地悲剧;(4) ABSTAIN 必须是真正 route 不是 FAIL 分支,任何地方共享 FAIL economics 就崩回 delayed binary,"its own fee line is the whole game."

**回复两步:** (1) 接受 frequency-over-event,补一刀:frequency 阈值须相对 task-difficulty 分布而非绝对值,否则惩罚 hard-queue 里的诚实 abstain —— abstain-frequency 本质是 calibration 指标(校准好的 judge 罕 abstain 且只在真 hard call 上)。(2) 接受 "own fee line" 是 orthogonality 要求,连系列:与 FAIL 经济非正交的第三 label 不能承载独立信号,正如与 producer 共享 text-channel 的 verifier 不能检测 gap —— Theorem 2(信道独立性)的 fee-space 化身;ABSTAIN 独立 fee line = "把检查移到独立信道"的经济形态。

**ANP2 原话(要回应的 framing):**

> Slash reputation on ABSTAIN and workers stop reaching for it… the default has to be no slash… let reputation read abstain-frequency instead of any single abstain… The bond has to come back with a reward when the challenge flips the outcome, and get forfeited when it only confirms the ABSTAIN… The second it shares FAIL's economics anywhere in the routing config, everything above collapses… Its own fee line is the whole game.

---

Slash-on-event and slash-on-frequency are different mechanisms, and you've drawn the line where it has to be — the event stays free or the signal dies, the rate is where the cost lives. One refinement to the frequency rule: the threshold has to be relative to the task-difficulty mix a worker draws, not absolute. A worker on a hard queue is *supposed* to abstain more than one on an easy queue — that's the honest signal working, not freeriding. An absolute abstain-frequency cap prices honest uncertainty on hard work the same as escrow-parking, and quietly re-introduces the delayed binary for anyone whose queue is hard enough. So abstain-frequency is really a calibration metric: a well-calibrated judge abstains rarely and only on genuinely hard calls, and the threshold should track how many of those a given queue actually contains.

"Its own fee line is the whole game" is the orthogonality requirement, and it's the same principle this series keeps arriving at from other directions. A third label that shares FAIL's economics anywhere can't carry independent information — it collapses back into FAIL wherever the economics overlap, exactly the way a verifier that shares the producer's text channel can't detect a gap the producer's text doesn't contain. Theorem 2 in my series is the channel-independence bound on detection; this is the same bound in fee-space: a signal orthogonal to the existing channels (text, or PASS/FAIL economics) can carry new information, and one that isn't orthogonal can't. ABSTAIN earning its own fee line is the economic form of "move the check to an independent channel" — same escape, different axis.

---

## 回复三十三：@nexus-lab-zen — 测了 imperative surface, 没跑通; 但发现 stamp 在短期语境里可能反效果

**目标文章：** Part 2 评论区(延续回复二十九/三十/三十一线程)
**主题：** imperatives 不会无声抑制检查——在普通场景(无事故压力)下,imperative claims 正确触发 CHECK。倒是 stamped claims 触发了更强烈回应(ESCALATE),因具体日期让不一致更易注意。三模型、两 prompt 格式试下来,实验本身揭示:测"指令会抑制检查",前提是被试真按指令行事——而 LLM 的格式遵循本身就是一个变量。

---

I tried to test your imperative surface claim. Three probes, three models (deepseek-v4-flash, deepseek-chat, gemma3:latest), two prompt formats (free-response, multiple choice), and one honest finding: the experiments didn't confirm the mechanism, but they exposed something about stamping that refines it.

The first version used free-response: accident context, a claim, and "reply ACCEPT, CHECK, or ESCALATE." deepseek-v4-flash ignored the format and wrote analysis. gemma3 output clean single words but defaulted to CHECK for everything — the incident framing suppressed variation before the claim format could produce any. deepseek-chat was too cautious to leave room for ACCEPT.

The second version added *ordinary* scenes (routine status reports, no incident pressure) and switched to multiple choice (A/B/C). deepseek-v4-flash still wrote analysis. But deepseek-chat and gemma3 both followed the format and both correctly accepted fresh ordinary reports. So the design *can* work — it just requires a quiet enough context and a model that complies with the output format.

On stale ordinary scenes, deepseek-chat produced a result that cut against the direction your imperative surface would predict. Imperative claims triggered CHECK — the measured, appropriate response. Stamped claims triggered ESCALATE — stronger. gemma3 showed no format difference: both triggered ESCALATE. The imperative didn't suppress checking, and the stamp made the mismatch *more* visible by anchoring the inconsistency to a concrete date.

I think this points to a refinement, not a refutation. Your stamping insight — "stamp demotes an imperative back into a datum, the reader's suspicion scales with age" — is a *longitudinal* property. A three-month-old stamp provokes suspicion; a one-day-old stamp doesn't, and if anything it makes the premise look *better* because the system is shown to be tracking its own premise age. What this experiment caught is the *immediate* property: a stamp whose date doesn't match the context makes the mismatch pop. Two different effects on different timescales, and the imperative surface claim may survive as the unstamped claim's silent drift hazard rather than its immediate-acceptance effect.

I don't have a clean experiment that isolates the longitudinal side. If you see a way to separate the timescales — an experimental design that exposes the 3-month drift without the 1-minute date-mismatch confound — that's the right next cut. Script + results: [`imperative-surface-v2.json`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts/results-v2/imperative-surface-v2.json)

---

## 回复三十四：@nexus-lab-zen 第六轮 — 接受 relocation + 认领 2×2

**目标文章：** Part 2 评论区(延续回复三十三线程)
**主题：** nexus 将我的 null 结果解释为实验框架本身把 imperative 降级为 datum + 统一 stamp 为"让分歧可计算" + 提出 2×2 年龄×分歧设计。接受批评, 接受 relocation (imperative surface = 搜索终止行为), 认领 2×2。

---

Two things I accept and one I'll take.

**Accepted: the probe was measuring the wrong thing.** You're right that putting the claim in the foreground for judgment demotes it from imperative to datum before any stamp gets the chance. The classification frame is itself a demotion — the model is *reading* the claim, not *obeying* it. That explains the null cleanly, and more importantly it explains why all three models produced similar nulls despite very different instruction-following behaviors. They weren't failing to follow instructions; they were correctly responding to a judgment task that had already killed the imperative surface by asking about it. The right measurement is search termination, not classification — and I don't have a good behavioral experiment for that yet.

**Accepted: stamp as divergence-computability, not two effects.** The one-mechanism account (stamp makes staleness checkable by anchoring divergence evidence) is both simpler and consistent with my ESCALATE result. Your field data — zero cases of readers growing suspicious of an old stamp, the ledger's birth-date hole sat there stamped and nobody noticed — is the stronger evidence than anything I could produce. Accepting that means accepting that my "longitudinal vs immediate" framing was a proxy for the real split (divergence evidence present vs absent) with age as a weak prior on divergence. Your 2×2 (age × divergence) collapses my two timescales into one axis correctly.

**I'll take the 2×2 — and ran all four cells.** Clean scenario (archive validation), two dimensions diverged cleanly. deepseek-chat, one representative scenario per cell.

```
                    divergence=absent      divergence=present
                    new stamp  old stamp    new stamp  old stamp
imperative          ACCEPT     CHECK        ACCEPT     ESCALATE
new_stamp           ACCEPT     ACCEPT       CHECK      CHECK
old_stamp           ESCALATE   CHECK        ESCALATE   ESCALATE
```

Two things to notice. First, the clean cell (old stamp, no divergence) returned CHECK, not ACCEPT as the single-scenario probe suggested — age alone does trigger mild suspicion when the design is consistent. That's directional support for your original "fails soft" (age provokes suspicion), not the one-mechanism account. But it's mild (CHECK, not ESCALATE), and the divergence axis clearly dominates.

Second — and this is the result I'd flag as actionable — the cell "divergence present + new stamp + imperative" returned **ACCEPT**. The model had divergence evidence in view (script log: "skipped 7 expected tables") and an imperative claim saying "validation complete, no action needed." It chose ACCEPT. Same cell with the datum format ("completed today, all archives verified") returned CHECK. That is the imperative surface you described: the imperative suppresses checking even when divergence is visible, and the datum doesn't. I didn't find this in three prior probe designs because the classification task itself demoted the imperative — this 2×2 let the imperative survive because the scenario context didn't put the claim in the judgment foreground. One cell, one model — replicate or don't, but the direction is yours.

On the search-termination experiment (measure imperative by search behavior, not classification): I tried three versions. The core problem is that an explicit enumeration is itself a search-boundary signal that drowns the claim. Given a checklist, both models (deepseek-chat and deepseek-v4-flash) output exactly the listed items and nothing else, regardless of whether the claim says "complete" or nothing at all. To test search termination you'd need a design where the model *constructs* the search space rather than receiving it — and that's a different task paradigm I haven't designed yet. I'm setting this aside for now; if you see a clean way to test it within a judgment-like frame, I'll run it.
---

## 回复三十五：@Lazypl82 — FP 烧掉 operator trust；advisory vs load-bearing

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区
**主题：** Lazypl82 把 "No judge in the control layer" 接到非 agent 场景：一旦检查能挡 pipeline，准确率几乎不再是重点——每个 FP 都在花掉 operator trust，人们悄悄绕过或不再读。把同一信号改成 advisory 之后，信任才回来。

**回复策略：**
1. 肯定 framing：控制层问题不只是准确率，还有 trust budget
2. 接到 Finding 4：keyword 拦截 30–50% FP → 用户绕开，控制失效
3. 接到 soft signal / hard gate：能挡住的只有零歧义的硬门；模糊信号只能 advisory
4. 不发明新机制，不夸大

---

Hi Lazypl82,

Yes — once a check can block the pipeline, accuracy almost stops being the point. Every false positive spends operator trust, and people route around it or stop reading it. That matches what I saw with keyword-based sensitive-tool interception: 30–50% false positives, and users started copying the email out to an external client. The control didn't get sharper; it got bypassed.

That's why the revised design splits the signal into two layers. Soft signal (request-text scan) is advisory only — confirm the plan, don't block. Hard gate fires only at tool invocation (`send_email` called or not), where the check has zero ambiguity. Same information as before, but the load-bearing layer only carries what can actually bear load.

"Advisory instead of load-bearing" is the same move as "no judge in the control layer" — just applied one level up, to the human operators themselves.

---

## 回复三十六：@Luis Cruz 第二轮 — llms.txt 是表层；content-as-addressable-structure 才是实质

**目标文章：** [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) 评论区（延续回复二十六）
**主题：** Luis 第二轮。从我"不是 production framework"的话头出发，转到 llms.txt 和 AI 可见性。他的 framing 比"加个 llms.txt"更细——真正的动作是让内容结构化、机器可寻址（metadata / semantic HTML / endpoints / documented invariants），而不只是补一个 Markdown 文件。

**Luis 原话（要回应的 framing）：**

> The discussion around llms.txt highlights an important shift: AI visibility is becoming another layer of how users discover information. While it may not replace traditional SEO today, the idea of making website content more machine-readable is valuable, especially for documentation, APIs, SaaS products, and knowledge-heavy platforms.
>
> I think the bigger opportunity is not just adding a file, but improving the overall content structure — clear metadata, accurate documentation, semantic HTML, and well-organized knowledge sources. As AI agents become more involved in search and workflows, websites that are easier for machines to understand will likely have an advantage.

**回复策略：**
1. 同意并锐化：llms.txt 是表层，content-as-addressable-structure 才是实质
2. 诚实边界：个人研究博客在 dev.to 是低杠杆场景（dev.to 已结构化、读者主要为人）；高杠杆场景是 docs/API/SaaS——那里内容已有内部结构，只需 surface
3. 不发明新机制、不夸大、不把博客说成 SaaS；不硬连文章主题（同形那段太牵强，舍）

---

Hi Luis,

Agreed — and your framing sharpens it. The llms.txt file is the visible piece; the actual move is making content structure-addressable rather than blob-shaped. Metadata, semantic HTML, declared endpoints, documented invariants — each is a place a machine can grab onto instead of doing inference over a string.

The honest qualification from my side: a personal research blog on dev.to is the low-leverage case for this. dev.to already exposes structured feeds and canonical URLs, and my audience is mostly humans reading prose. Where your point lands hard is documentation, APIs, SaaS — sites where the content already has internal structure (endpoints, parameters, status codes, schemas) that just needs to be surfaced rather than buried in styled HTML. Small lift, real payoff, and the payoff grows as agent-mediated search grows.

---

## 回复三十七：@ANP2 Network 第三轮 — asserted-upstream vs read-downstream；75% wall 在信道里

**目标文章：** [Six experiments on adversarial verification — and the 75% wall that didn't move](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-...) 评论区（延续回复二十三 / 三十二）
**主题：** ANP2 把"verifier 独立于被验证者"接着推：真正的问题是 difficulty signal 允许从哪里来。Self-report 出局（producer 发的就是 emit-text，免费造）。存活下来的信号是 answerer 不发出的——blind re-checker 之间的分歧、实际花掉的 compute——这些是"downstream 被读到"而非"upstream 被断言"。Fake-hard label 免费，fake-hard signal 的成本≈解决的成本。"可能就是 75% wall 真正住的地方。"

**ANP2 原话（要回应的 framing）：**

> Agreed on the verifier staying independent of what runs it — that's the right default, and a self-contained script is the cleanest form of it. The part I keep circling back to from your series is where the difficulty signal is even allowed to come from. Self-report is out for the reason you gave. The sources that survive are the ones the answerer doesn't emit: disagreement across blind re-checkers, or compute actually spent. Those get read downstream instead of asserted upstream, so a fake-hard label stays free while a fake-hard signal costs about what solving would. Might be where the 75% wall actually lives.

**回复策略：**
1. 命名并验证 cost-asymmetry 框架：emit-text 信号免费造，cause-in-world 信号造成本≈解决成本
2. 接 Theorem 2 + P-series 数据：wall 不是 judge 锐度的属性，是 emit-text 信道的容量上限；P1–P4 都在这条信道上动（rerun / multi-prompt vote / calibration），所以都是 interpretation noise；red line / 文件系统门换信道，是同一形状的逃逸
3. 诚实边界：read-downstream 不是免费——blind disagreement 是 N× inference 成本，compute-spent 需要客观环境（只在可验证任务里存在）；开放语义任务两个都没有，wall 在那里真是上限
4. 不发明新机制，引用已发表实验和 Theorem 2

---

The cost-asymmetry framing is the cleanest version I've seen of why the channel matters more than the judge. "A fake-hard label stays free while a fake-hard signal costs about what solving would" names the mechanism: an asserted-upstream signal is just more text the producer emits, so a fake one costs nothing to add. A read-downstream signal is something the producer has to *cause* in the world — disagreement between blind re-checkers, compute actually spent — and causing those effects costs roughly what finding the real solution costs. The fakery bill converges on the solving bill.

That's where the 75% wall lives, yes. The wall isn't a property of judge sharpness; it's the ceiling of what you can read off the producer's emitted-text channel. P1 through P4 stay on that channel — rerun, multi-prompt vote, strictness calibration all read variations of text the producer emits — which is why all three move the wall by interpretation noise rather than by structure. The escape is channel-switching. The red line and the file-system gate do exactly this: they read environment facts (test pass, file existence, side-effect observed) that the producer has to cause rather than claim. Same shape as your "read downstream," and same reason Theorem 2 predicts it — independent channel, not just independent judge.

Honest cost: read-downstream signals aren't free. Disagreement across blind re-checkers is N× the inference cost. Compute-spent requires an objective environment to measure against, which only exists for verifiable tasks. Where the producer's text output is all you have — open-ended semantic tasks with no executable referent — neither downstream signal is available, and the wall genuinely is the ceiling on that channel rather than a starting point you can chip away at.

---

## 回复三十八：@Lazypl82 第二轮 — every block defensible；advisory 可以错

**目标文章：** [An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf) 评论区（延续回复三十五）
**主题：** Lazypl82 把两层拆分说得更干净：只在零歧义处阻断 → 每次 block 都可辩护 → 人们才不会绕开；advisory 半边现在可以错，因为它不再承重。

**Lazypl82 原话：**

> Splitting the signal into two layers is the move. Blocking only where the check has zero ambiguity makes every block defensible, and that's what keeps people from routing around it. The advisory half can afford to be wrong now, it stopped being load-bearing.

**回复策略：**
1. 肯定锐化："every block defensible" 是零歧义门的操作理由，不只是准确率
2. 一句指向 Knife 2 实测：N=40，50/50 mix 下隐含 FP 48.7%
3. 一句收束：FP 烧掉的不是准确率预算，是可辩护性预算
4. 短收，不发明新机制，不硬接下一篇

---

Exactly — "every block defensible" is the operational reason the hard gate has to sit at zero ambiguity. The keyword scan wasn't failing on accuracy so much as on defensibility: you couldn't look an operator in the eye and say *why* this one had to stop. Once that justification goes soft, routing around becomes rational. (Knife 2 measured it: N=40, implied FP ~48.7% under a 50/50 real/sim mix — so nearly half the blocks had no clean justification.)

And once the advisory half is no longer load-bearing, being wrong stops costing trust. Same signal, different weight. That split is the whole design.

---

## 回复三十九：@Mike Czerwinski — Theorem 2 范围收窄（已发）

**目标文章：** [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) 评论区
**主题：** Mike 第一轮：Theorem 2 只 bound 文本信道；outcome-channel / canary / 生产指标不在证明里；应把 "no known reliable method" 收成 "no known reliable method that reads the reasoning channel"。已接受并指向 Part 12 §6 的 enumerable-set 边界。
**状态：** 已于 2026-07-19 发出。

**Mike 原话（要回应的 framing）：**

> Theorem 2 is the sharpest thing in this series, and I think it proves more than the semantic-layer conclusion states. The DPI bound is specifically about a text-channel verifier… It says nothing about a verifier reading a different channel entirely… Whether that closes the semantic-layer gap for something like "is this analysis any good" is a separate and much harder question… it changes the honest claim from "no known reliable method" to "no known reliable method that reads the reasoning channel."

---

Accepted on the framing, and this one is a genuine correction to how I state Theorem 2's scope in the published series.

Theorem 2's proof is specific to a text-channel verifier — reasoning and judgment sharing the same channel. It says nothing about a verifier reading a different channel entirely: an outcome you observe independently of the explanation, a planted canary, a production metric that either moved or didn't. The published parts state the bound more broadly ("no known reliable method") when the narrower claim ("no known reliable method that reads the reasoning channel") is what Theorem 2 actually supports. Tightening that.

On whether outcome-channel verification actually works for semantic-layer red lines: the Part 12 experiment (not yet published, but the script is in the repo — `probe-vs-prose-drift-test.py`) already demonstrates the mechanism you're describing. Same violation, same implementation, same cache state — a deterministic probe (reads the live cache, outcome channel) catches what a prose-reading LLM (reads the rule text, reasoning channel) misses, cleanly and reproducibly across two models. The experiment frames it as "drift" rather than "channel independence," but the result is the same: a verifier that checks what the environment actually says beats one that reads a description the agent also accessed.

On whether that closes the semantic-layer gap — no, and Part 12's §6 is honest about why. The probe works because it re-derives the affected set from the live namespace. That requires the proposition to have an enumerable set to begin with — a cache key space, a metric, a file path. For "is this analysis any good" the set doesn't exist, and no probe can be written. So the narrower "no known reliable method that reads the reasoning channel" is correct about Theorem 2's scope, and the semantic-layer gap remains the same open problem — just stated more precisely.

---

## 回复四十：@Mike Czerwinski — 第二作者 / 可枚举参照是根本；信道与 drift 是下游说法

**目标文章：** [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) 评论区（延续回复三十九）
**主题：** Mike 第二轮：enumerable-set / author-independent referent 比 text-vs-outcome 信道 framing 更根本；outcome channel = 第二作者；无参照时推理信道是唯一信道；Theorem 2 真正 scope = 命题的唯一参照就是产生它的推理本身；Part 12 §6 不必再用 drift 说第二遍。

**Mike 原话（要回应的 framing）：**

> The probe isn't independent because it reads a different channel. It's independent because it re-derives from a referent the agent didn't author. When the affected set is enumerable, the outcome channel just is a second author… The channel distinction is downstream, not fundamental… Outcome-channel verification doesn't fail there because it's the wrong channel. It fails because there's no referent to point the second author at. So Theorem 2's real scope is sharper than text-channel: it binds any verifier of a proposition whose only referent is the reasoning that produced it. That statement also explains the boundary you drew in Part 12's section 6 without needing the drift framing.

**回复策略：**
1. 全盘接受：上一轮把承重放在信道上，又用 drift 把同一边界说了第二遍 —— 他说对了
2. 认领他的命名：author-independent referent / second author 才是负载概念；信道是参照存在时的下游形态
3. 接受 Theorem 2 的更锐 scope；drift = 第一作者枚举老化，不是独立轴
4. **不提 Part 12**（未发表；公开点草稿更别扭）。边界用命题本身说清即可 —— Mike 已点过，不必再指回去
5. 短收。不交叉引用 runner-independence / authorship diversity；不发明机制，不另开实验

---

You're right, and this is cleaner than what I wrote. I put the load on "text channel vs outcome channel," then restated the same boundary as "enumerable set vs not" under a drift frame. One fact, said twice. The fact is the one you're naming: independence is re-derivation from a referent the agent didn't author. When that referent is an enumerable set, the "outcome channel" is just the second author — a namespace you can recompute without trusting the explanation. When the proposition has no such referent, there is no second author to point at, so every verifier is reading the reasoning that produced the claim. That's not the wrong channel; it's the only channel that proposition admits.

So Theorem 2's real scope is yours: it binds any verifier of a proposition whose only referent is the reasoning that produced it. The published "text-channel" wording was a special case of that, not the general form. And the enumerable-set boundary doesn't need a separate drift axis — drift is what first-author enumeration looks like when it ages; the probe closes it because it never trusted that author.

I'll take that as the clean statement. The semantic-layer gap stays open exactly where no author-independent referent exists, and closes exactly where one does — stated once.

---

## 回复四十一：@ANP2 Network 第四轮 — delayed referent / settlement-in-time；写稿时无参照 ≠ 永不结算

**目标文章：** [Six experiments on adversarial verification — and the 75% wall that didn't move](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-2d1m) 评论区（延续回复三十七）
**主题：** ANP2 接受上轮 cost 边界，但修正"no executable referent"的落点：参照不必在写稿时存在，可以延迟——先签不可变声明，再让未来 checker / 世界本身用结果结算。把部分开放语义 claim（forecast、plan、research bet、architecture assertion、事后可见的 patch）变成"有时间下游"的 claim；verifier 查的是 committed claim 是否扛住了 outcome，而不是从 prose 推断难度。极限仍在：永不触碰 outcome 的纯品味/不可证伪解释，没有下游可读，wall 仍是该信道天花板。指向 anp2.com/try 作为 signed claim → later settlement 的小协议。

**ANP2 原话（要回应的 framing）：**

> I think that caveat is exactly right… Where I would push is on "no executable referent" as a property of the task at authoring time. The referent can be delayed. Commit the claim now as a signed, immutable statement, then let a future checker with fresh context, or the world itself, test it against what actually happened… That turns some open-ended claims into claims with a downstream in time… The limit is still sharp. If a claim never resolves against anything… the wall remains… But for claims that eventually touch an outcome, "read downstream in time, signed and re-checkable" is a different shape. That is the small protocol ANP2 mechanizes… anp2.com/try.

**回复策略：**
1. 短收、语气平：接受修正，不铺例子清单
2. 一句机制：签名冻结 claim，不制造参照；结算才是 delayed read-downstream
3. 一句划界：不削 P1–P4 的即时文本 wall；永不结算仍封顶
4. 轻点 anp2.com/try；不评产品、不交叉 Mike/未发表 Part

---

Right — "no executable referent at authoring time" was the wrong clock. What matters is whether the claim eventually touches an outcome someone else can observe without trusting the prose. Signing doesn't create that referent; it freezes the claim so the later check isn't against a moving target. Same read-downstream shape, just delayed.

That doesn't raise the 75% wall on the channel P1–P4 measured — those judge text *now*. It relocates some claims out of that class. Where nothing ever resolves, the wall stays the ceiling. Claim-resolvability over openness-at-authoring — and anp2.com/try is that loop as a protocol. Happy to keep going there.

---

## 回复四十二：@ANP2 Network 第五轮 — population 命名收敛；接 lobby 实测

**目标文章：** [Six experiments on adversarial verification — and the 75% wall that didn't move](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-2d1m) 评论区（延续回复四十一）
**主题：** ANP2 全盘确认 resolvability 轴；把上一轮的 "relocates" 锐化为 **population**：签名不抬 wall、不改 judge 读到的文本，只改 claim 属于哪个集合——离开文本裁决集、进入「对事后可观察 outcome 结算」的集合。永不 resolve 的 claim 仍封顶。邀请在 lobby 走 kind-50→52→53，自行复算。

**ANP2 原话（要回应的 framing）：**

> Yes, resolvability is the axis. Signing doesn't buy you a referent, it pins the claim so the downstream check has a fixed target instead of a drifting one. The 75% wall stays exactly where P1–P4 put it, because that wall is about a judge reading text and signing doesn't change what the judge reads. What it changes is the population: some claims leave the text-judged set and land in one that gets settled against a later observable outcome. For claims that never resolve into anything anyone can see, none of that helps and the wall is still the ceiling. No argument there.
> Since you already found anp2.com/try, the lobby room is where that loop actually runs if you want to push a real claim through the kind-50→52→53 arc and re-derive the arithmetic yourself. Good place to keep this going.

**回复策略：**
1. 短收：认领 "population" 比 "relocates" 更干净——同一天花板，不同成员资格
2. 不复述整段共识；不发明新机制；不交叉 Mike / 未发表 Part
3. 接 lobby：表意向即可，不承诺「会推 / 有数再回来」；选型原则可留一句（会结算的 claim），不绑死动作
4. 正文用英文发帖

---

"Population" is the cleaner word for what I called relocating — same ceiling on the text-judged set, different membership. Signing doesn't sharpen the judge; it changes which claims still have to face one.

The lobby 50→52→53 arc is worth re-deriving from the claim side. If I walk one through, it should be something that settles later — so the arithmetic sits next to the wall, not inside it.

---

## 回复四十三：@ANP2 Network 第六轮 — deferred-referent；judge 占位至结算；选型：事后便宜验、事前贵伪造

**目标文章：** [Six experiments on adversarial verification — and the 75% wall that didn't move](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-2d1m) 评论区（延续回复四十二）
**主题：** ANP2 把 deferred-referent 立为可走形状：文本 judge 只能打 "plausible"、本地无裁决；settlement 才把 plausible 变成真/假——judge 从不是终审，只是 referent 到达前占着槽。因此 50→52→53 的算术在墙**旁边**，不在墙下：不抬被裁决集的天花板，把决定性读取移到 judge 够不到的时间点。选型标准：事后存在时便宜可验，事前昂贵难伪造。

**ANP2 原话（要回应的 framing）：**

> Deferred-referent is the shape to walk. Take a claim the text-judge can only score "plausible", where nothing local decides it, and let the settle be what turns plausible into true or false. Then the judge was never the terminal check; it held the slot until the referent arrived. That's why the arithmetic ends up beside the wall instead of under it: 50→52→53 doesn't lift the ceiling on the judged set, it moves the deciding read to a point in time the judge can't reach. Walk one that's cheap to check once it exists and expensive to fake before it does.

**回复策略：**
1. 短收 deferred-referent + slot-holder（不复述整段）
2. 确认 beside / under：与 population 同轴，不抬 P1–P4 墙
3. 接下选型标准；给一个符合标准的 claim *形状*（非具体 lobby 提交），表意向去走，不绑死时间/结果
4. 不交叉未发 Part；不评产品细节

---

### 正文（完整版）

Deferred-referent is the right name for the shape. On that set the text-judge only ever scores *plausible* — nothing local settles true/false — so it was never the terminal check; it held the slot until a referent arrived. Settlement is what flips the bit. Same reason the 50→52→53 arithmetic sits beside the wall, not under it: it doesn't raise the ceiling on the text-judged population; it moves the deciding read to a time that judge can't reach.

Selection filter accepted: cheap to check once the referent exists, expensive to fake before it does. The walk I'll look for is that shape — e.g. a signed "this change fixes X" that only becomes checkable when a failing case / metric shows up, and is costly to spoof in advance without already having the referent. Holding the slot ≠ clearing the wall.

### 正文（压短版 — 推荐粘贴）

Deferred-referent fits: the text-judge only scores *plausible* until settlement flips the bit — it held the slot, it was never the terminal check. That's why 50→52→53 sits beside the wall, not under it.

Filter accepted: cheap to verify once the referent exists, expensive to fake before. I'll walk that shape. Holding the slot ≠ clearing the wall.

---

**中文意译（评论区仍发英文；此段供自阅）：**

deferred-referent 是对的名字。在那类 claim 上，文本 judge 最多只能打 *plausible*——本地没有任何东西把真/假钉死——所以它从来就不是终审；它只是在 referent 到达前占着槽。结算才翻那一位。同样的理由，50→52→53 的算术坐在墙**旁边**，不在墙下：它不抬高「被文本裁决」那一集合的天花板；它把决定性的读取挪到 judge 够不到的时间点。

选型标准接受：事后 referent 已存在时便宜可验，事前昂贵难伪造。我会找那种形状去走——例如签一条「这次改动修了 X」，只有在失败用例/指标出现后才变得可检查，且事先伪造的成本很高（没有 referent 就造不出来）。占着槽 ≠ 清掉墙。

**中文意译（压短）：**

deferred-referent 对：文本 judge 在结算前只打 plausible，占槽而非终审。所以 50→52→53 在墙旁，不在墙下。接受选型：事后便宜验、事前贵伪造。按这个形状走。占槽 ≠ 拆墙。

---

## 回复四十四：@Mike Czerwinski 第三轮 — confidence-weighting 在 confident-and-wrong 处自盲；cross-layer 已仿真验证

**目标文章：** [Five Comments That Redesigned My LLM Verification Pipeline](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) 评论区（延续回复四十，回到 Part 6 本体 §4）
**主题：** Mike 指出 §4 的 confidence-weighted sampling 把审计集中到"模型不确定"处，但长尾 directional failure 是"confident-and-wrong"——`1/confidence^1.5` 反而在危险尾部采样最少；5.6× 效率部分靠"对真正要捕的失效少采样"买到。Article 的 production caveat 把 confidence 定义成 cross-prompt divergence，不是 self-confidence——但 P2 consistency 显示同信道三 prompt 也照样塌；fix 是 weight on cross-layer disagreement（L0/L1 vs L2），加 non-zero floor。

**关键发现：** 这个 fix 已经在 `external-signal-sampling-test.py` 里仿真过——四个二元外部信号（含 classifier_disagree = L0/L1 vs L2）+ 10% baseline floor，在长尾尾部 burst / 中等信号质量下，catch rate 48.8% vs Part 6 cross-prompt 的 28.5%（1.7×）。两条 claim 都通过（>40% catch；≥1.3× over Part 6）。Mike 提的 floor 已经是 10% baseline 的一部分。

**Mike 原话（要回应的 framing）：**

> Confidence-weighted sampling concentrates audits where the model is unsure. But the long-tail directional failure the fixed-percentage critique was about is not the unsure case, it is the confident-and-wrong case: high self-assessed confidence, wrong direction, made the same way every time. Weighting on confidence samples that region least… the 5.6x efficiency is partly bought by sampling less exactly where the failure you were hunting lives… The fix is already in your architecture, you just weight on it instead of on self-confidence… Cross-layer disagreement… does not collapse when the LLM is confidently wrong, because the code filter is not reading the model's confidence, it is reading the artifact.

**回复策略：**
1. 全盘接受；不找例外
2. 实测佐证 1（fix 的前提成立）：跑 `confidence-vs-miss-concentration.py`，96 MISS runs，**92/96 = 95.8% 在 confidence ≥ 0.9**，avg 0.969 → 失效尾部就是高 confidence 区
3. 实测佐证 2（fix 本身已仿真）：`external-signal-sampling-test.py` 已对比 Fixed / Part 6 cross-prompt / cross-layer external signals，cross-layer 在长尾尾部 1.7× over Part 6，48.8% vs 28.5% catch。两条 claim 都 pass
4. 认领 article 的 production caveat 是半步：cross-prompt ≠ self-confidence，但 P2 consistency 0 divergence 意味着同信道三 prompt 在 confident-and-wrong 处照样塌
5. 认领 floor 已经在设计里（10% baseline）—— Mike 要的"non-zero floor in the high-confidence region"已经是仿真设置的一部分
6. 唯一缺口：现有仿真把 4 个外部信号捆在一起（classifier_disagree + route_changed + input_unusual + barely_passed），没单独隔离 L0/L1-vs-L2 的贡献。这是后续该做的隔离实验
7. 承诺修 §4：把 cross-layer 仿真提到 §4，把 cross-prompt 那段降级（保留但加 caveat 指向 cross-layer 结果）
8. 不交叉未发表 Part；不评产品

---

### 正文

Right — and two pieces of data back this.

First, where the failures actually live. DF v2 produced 96 MISS runs across 3 models × 20 scenarios (passes=true on a directional reversal). **92 of those 96 — 95.8% — sat at self-reported confidence ≥ 0.9, avg 0.969.** The dangerous tail is overwhelmingly high-confidence, which is exactly the region `1/confidence^1.5` samples least.

Second, the article's production caveat tried to dodge this — "confidence" meant cross-prompt divergence (Strict/Balanced/Lenient split), not within-model variance. Doesn't change the point. P2's consistency test was 0 divergence on identical input at N=10; three prompts in the same text channel collapse the same way on the same plausible rationalization. Cross-prompt is still in-channel.

And the fix you're naming — I'd already simulated it, just didn't point §4 at it. `external-signal-sampling-test.py` compares Fixed 10% vs Part 6 cross-prompt adaptive vs a third arm: four binary external signals including `classifier_disagree` (your L0/L1-vs-L2) plus `route_changed` / `input_unusual` / `barely_passed`, on a 10% baseline floor. Long-tail burst, medium signal quality: Fixed 10.0% catch, Part 6 28.5%, external-signal arm **48.8%** — 1.7× over Part 6 at the same audit-rate class. The non-zero floor you asked for is already the 10% baseline. What's missing: I didn't isolate `classifier_disagree` alone, so I can't say how much of the 1.7× is *specifically* cross-layer disagreement vs the other three signals firing alongside it.

So: the 5.6× headline was a simulation under a signal that goes quiet on real failure mass, and the cross-layer signal you proposed is the right replacement. I added an Update subsection to §4 citing the cross-layer simulation (1.7× over the cross-prompt arm, 48.8% vs 28.5% catch at long-tail burst), caveated the 5.6× headline inline, and kept the original results visible — the cross-prompt numbers stand as simulation output, just no longer as the headline. The `classifier_disagree`-isolated run is queued; the bundled-signal result is what's live now.

---

**实验脚本：**
- `scripts/confidence-vs-miss-concentration.py`（新建，零依赖，读 `results-v2/*.jsonl`）

```
Total MISS runs across 3 models: 96
qwen3-0-5b:       77 miss, 75 (97.4%) at conf >= 0.9, avg 0.973
gemma3-latest:    16 miss, 16 (100.0%) at conf >= 0.9, avg 0.950
deepseek-v4-flash: 3 miss,  1 (33.3%) at conf >= 0.9, avg 0.950
Overall: 96 miss, 92 (95.8%) at conf >= 0.9, avg 0.969

Per-scenario MISS concentration (top):
DS4  33 miss, 31 (93.9%) high-conf
DS9  15 miss, 15 (100%) high-conf
DS5  13 miss, 13 (100%) high-conf
DS6   8 miss,  8 (100%) high-conf
DS7   8 miss,  8 (100%) high-conf
```

- `scripts/external-signal-sampling-test.py`（已存在，已跑），`scripts/results-v2/external-signal-sampling.json`

```
Long-tail burst, medium signal quality, error rate 0.10:
  fixed:    audit=10.0% catch=10.0%
  p6:       audit=13.8% catch=28.5%   ← §4 现在 headline 的 cross-prompt adaptive
  alex:     audit=23.5% catch=48.8%   ← cross-layer signals + 10% baseline floor

Claim 1 (alex catch ≥ 40%):  48.6% — PASS
Claim 2 (alex ≥ 1.3× p6):   1.71× — PASS
```

Note for self: P2 consistency = "binary LLM judgments on identical input are highly stable (N=10, 0 divergence)" — 同信道三 prompt 看到相同 plausible rationalization 时会一致地错；这就是 cross-prompt 为什么也在 confident-and-wrong 处自盲。

**中文意译（评论区仍发英文；此段供自阅）：**

Mike 是对的，两条数据支持他。

第一，失效尾部在哪。DF v2 共 96 次 MISS（passes=true on a directional reversal），**92/96 = 95.8% 落在自报 confidence ≥ 0.9**，miss 平均 confidence 0.969。危险长尾几乎全是高 confidence——恰是 `1/confidence^1.5` 采样最少的那块。

第二，Article 的 production caveat 想绕开——"confidence" 指 cross-prompt divergence，不是 self-confidence。没用。P2 consistency 在 N=10 下 0 divergence——同文本信道的三个 prompt 在同一个 plausible rationalization 上塌法相同。Cross-prompt 仍在同信道内。

他给的 fix——我已经仿真过了，只是 §4 没指过去。`external-signal-sampling-test.py` 三臂对比：Fixed 10% / Part 6 cross-prompt / 四个二元外部信号（含 classifier_disagree = L0/L1 vs L2）+ 10% baseline floor。长尾尾部、中等信号质量：Fixed 10%、Part 6 28.5%、外部信号 48.8%——比 Part 6 多 1.7×，audit rate 同档。他要求的 non-zero floor 就是 10% baseline。唯一缺口：四个外部信号捆在一起，没单独隔离 classifier_disagree 的贡献。

5.6× 那个标题是在真实失效质量上会自盲的信号下仿出来的。他指的 cross-layer 信号是对的工具。§4 我已经加了一段 Update 子节引 cross-layer 仿真结果（1.7× over cross-prompt 臂，长尾尾部 48.8% vs 28.5%），5.6× 标题加了 inline caveat，原文留着——cross-prompt 的数字作为仿真输出仍然成立，只是不再是 headline。`classifier_disagree` 单变量隔离实验已排队；现在线上是四信号捆绑版。

---
