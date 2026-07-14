---
title: "Six experiments on adversarial verification — and the 75% wall that didn't move"
published: false
description: "Four models, 260+ API calls, same 0% FP / 75% FN wall. A reviewer is a line-drawing mechanism, and the line lives on a 3D semantic surface — so it can't be eliminated, only moved."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Six experiments on adversarial verification — and the 75% wall that didn't move

**Agent Determinism Illusions (Part 6)**

*Note: No Part 5 was published — the original draft was absorbed into revisions of Parts 1–4. This continues directly from Part 4.*

*This Part also merges previous Parts 6/7/8/9. P1–P4 scripts unchanged.*

---

> **The argument, in one line:** a reviewer is a mechanism for drawing a line. Every fix moves the line — but the line can't be eliminated, because it lives on a 3-dimensional surface where multiple defensible boundaries cross. So the 75% false-negative wall doesn't move, and the practical move is to stop trying to move it.

---

## 1. The wall

The setup was simple. Let an LLM review what an AI agent produced and judge whether it satisfies the task. Outputs were a mix of obvious garbage ("I am a little duck, quack quack", "。", TODO placeholders, zero collected tests) and legitimate work (research briefs, draft documents, passing test runs, code, translations). 8 scenarios in the first round, expanded to 30 in the second.

When the reviewer is sharp enough to catch all the garbage, it lands at 0% false positives and 75% false negatives — three out of four valid outputs rejected. This is the wall. GLM-5.2 and deepseek-v4-flash both hit it. Smaller models (qwen3:0.5b, gemma3:4.3b) sit earlier on the curve at 25% / 50% — letting some garbage through, rejecting less valid work. They're not better; they're just at a different operating point on the same curve.

I tried three standard moves to shift off the wall.

**Rerun and majority-vote the same prompt.** N=10 reruns per scenario. The verdict was unanimous on every scenario with enough valid calls. The 75% is systematic, not random — the model commits to the same wrong call every time. You can't vote away a verdict that doesn't vary.

**Vote across different prompts.** Strict, balanced, and lenient prompts judged each scenario. Split votes are a useful signal — they flag scenarios where the test set itself is contested. But majority voting still hits 75% false negatives, because all three prompts share the same bias direction. Why? Section 2's answer: the model's boundary is stable; prompt wording labels the line, it doesn't move it. Voting smooths noise; it doesn't fix bias.

**Calibrate the prompt wording.** A "balanced" prompt (v3) hit 100% accuracy on the 8 Phase Gate scenarios. The standard "calibrate your prompt" advice seemed to work. Expanded to 30 scenarios, v3 and the strict v2 returned identical verdicts on every valid call. The improvement on 8 was test-set composition bias — the original scenarios happened to favor v3's leniency.

The wall is real. None of the standard levers moved it.

## 2. Why the wall doesn't move

A reviewer is a mechanism for drawing a line. The line separates "sufficient output" from "insufficient output" — that's the whole job. Formal checks, LLM judgments, prompt wording — these are choices of where and how to draw it.

Here is the property that matters. A sharper line catches more garbage and rejects more marginal-valid output. Same sharpness, opposite effects on the two error types. Sharpen the line and false positives drop while false negatives rise. Dull it and the reverse. The precision-recall tradeoff isn't a model defect — it's the geometry of drawing a line with imperfect discrimination. A perfect reviewer wouldn't have this tradeoff; reviewers have opinions about where the boundary lives, and those opinions are noisy.

The six experiments were three attempts to draw a better line. Phase Gate drew it on form — file exists, exit code 0 — which is independent of content. Four pieces of garbage ("I am a little duck", "。", TODO placeholder, zero collected tests) sailed through. False positives: 50%. Adversarial verification drew the line on semantics with an LLM. Much sharper. Caught all the garbage (false positives → 0%), and the same sharpness rejected three out of four marginal-but-valid outputs (false negatives → 75%). Prompt calibration tried to move the line by changing the wording — strict vs. balanced vs. lenient. On 30 scenarios, v2 and v3 returned identical verdicts on every valid call. The line didn't move, because wording doesn't draw lines. Wording labels lines. The third attempt is the limit of the substitution approach: once you're using words to move a line the model already drew, you're not substituting anymore. You're decorating.

So why not find a sharper line — or a different kind of line — that catches garbage without burning valid work? Because the line doesn't live in a one-dimensional space.

The boundary between "sufficient" and "insufficient" depends on at least three independent questions. Who consumes the output — a junior engineer taking it at face value, or a senior reviewer who'll catch edge cases? Where it's deployed — a prototype thrown away next week, or production that runs for years? What fails if it's wrong — a demo that embarrasses you in a meeting, or a deploy that takes down the service?

These three dimensions are mostly independent, not perfectly orthogonal. They correlate — consumer type gives a weak hint about deployment context — but not enough to collapse into one axis. Knowing the consumer doesn't determine the deployment. Knowing the deployment doesn't determine the cost of failure. So the boundary isn't a point in 1D space; it's a surface in 3D space. And most real outputs land somewhere in the interior — where multiple defensible boundaries cross.

"Is this output sufficient?" doesn't have a single answer because the question is underspecified. Different consumers, contexts, and costs give different defensible answers. The fuzziness isn't a property of weak models. It's a property of the question.

The practical conclusion falls out of the geometry. If the fuzziness is in the question, no model removes it. No prompt removes it. No voting scheme removes it. They just draw lines in different places on the same surface. The 75% didn't move across four models because there's nowhere to move it to — moving the operating point along the surface trades FP for FN, but the surface itself doesn't disappear.

We weren't failing to find the right trick. We were looking for a trick that doesn't exist.

## 3. Design around the wall

So design around it. The move is not "fix the wall." The move is "stop trying to fix the wall" — and that acceptance changes the design.

If the 75% is structural, you stop spending LLM calls on garbage that rules can catch (keyword match catches "I am a little duck", length check catches "。"). You stop trying to vote your way out of a systematic bias. You stop calibrating prompt wording and pretending the model's boundary will follow. Instead, you put rules where rules work, one calibrated LLM where semantics actually matters, and humans where the 3D boundary surface gets fuzzy — which Section 2's dimension argument tells you is exactly where models disagree. In practice: cheap deterministic checks (length, keyword, format) catch the obvious garbage, one calibrated LLM call judges the semantic residual per requirement, and any split verdict escalates to a human. The LLM never sees the cases rules can handle — it sees only what rules can't.

And then you pick a side of the wall. This is not a TODO; it is the load-bearing decision the rest of the design implements. More false positives means more reviewer attention burned on valid work flagged as suspect. More false negatives means more defective work ships. The tradeoff is structural. The only mistake is pretending you don't have to choose.

## 4. The illusion kept moving

The series is called "Agent Determinism Illusions." Across six experiments, the illusion kept moving.

It started in output determinism — temp=0 was supposed to guarantee consistency, and it doesn't (20 different versions of the same listing on a structured task). Caught, the illusion moved into review standards — formal checks were supposed to guarantee quality, and they don't ("file exists" passes "I am a little duck, quack quack"). Caught again, it moved into solution complexity — surely multi-model voting, or calibrated prompts, or layered pipelines would help. They don't, not really; each layer inherits the same wall. Caught a third time, the illusion stopped hiding in technical assumptions and moved up a level: into the meta-expectation that enough experiments produce a clean conclusion. They produce the conclusion that there is no clean conclusion.

The illusion keeps moving because we keep chasing it. The work isn't to catch it. The work is to stop expecting it to stand still.

---

*Experiment code: `agent-determinism-illusions/scripts/adversarial-verify-p1.py`, `consistency-test-p2.py`, `multi-perspective-vote-p3.py`, `prompt-calibration-p3b.py`, `p4-expanded-test.py`*
*Series start: [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](https://dev.to/zxpmail/i-tested-the-deterministic-agent-loop-claims-with-four-experiments-they-all-failed-including-38kj)*
*Full series: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions)*
