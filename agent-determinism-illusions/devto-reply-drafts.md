# dev.to 回复草稿 — 2026-07-08

## 回复一：@renezander.com — Theorem 2 (Data Processing Inequality) + L0e 验证

**目标文章：** Part 1 或 Part 10 评论区
**主题：** Compliance Gap 实验验证 Theorem 2，L0e 与 skillgate 的互补关系

---

Hi René,

You were right about Theorem 2. I ran the experiment.

Four test files — one normal implementation, one TODO stub (full function bodies but all TODO), one structurally perfect but semantically missing the target (a cache layer with get/set/invalidate but no write-invalidation as the task required), and one comment-module (entirely JSDoc/TODO with no real code).

The L0e Re-Stat check (based on nexus-lab-zen's zero-verified=RED design) caught the comment-module at zero cost — 4 red-zone indicators triggered (future-tense density 6.9%, comment ratio 72%, 4 meta-descriptions, 2 stub locations). But the structurally perfect compliance gap? Passed L0e clean. Passed L2 with an API_PARSE_ERROR — the LLM itself couldn't decide whether the output satisfied the requirement.

This is the Data Processing Inequality in action. A file with correct function signatures, proper class structure, and all CRUD methods — but missing the one write-invalidation path the task required — is textually indistinguishable from a correct implementation to any observer, LLM or human.

I wrote up the full comparison with your skillgate design in `compliance-gap-test.md` in the repo. The key finding: L0e and skillgate are complementary, not competing. L0e catches re-stat patterns (future-tense density, stub code, social-signaling) at the agent-loop level for near-zero cost. skillgate catches the things L0e can't see — contract violations, secret leaks, test failures — at the CI/pre-commit level outside the loop.

Together they cover most of the compliance gap surface. But Theorem 2 means there will always be a residual that neither catches. I've accepted that as a design constraint rather than something to engineer away.

The updated directional failure appendix (v2, 20 scenarios, 600 calls across 3 models) also references your framework. Would welcome your read on it.

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
