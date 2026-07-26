---
title: "A Reviewer Nailed Me in Six Places — How I Learned to Defend a Zero-Experiment Paper"
published: false
description: "A position paper with no experiments, stress-tested in one harsh review pass. Six argument red lines — none of them fixable by running more numbers. The question is whether your claims align with the burden of proof."
series: "Judging vs. Building in the AI Era"
series_part: 5
tags: ai, llm, essay, writing
canonical_url: ""
---

# A Reviewer Nailed Me in Six Places — How I Learned to Defend a Zero-Experiment Paper

> A zero-experiment position paper. No benchmark can prove me. No ablation can save me. Every bit of trust rides on how precise the argument is.

*This is the fifth piece in the "Judging vs. Building" series, but you do not need the earlier ones — each essay is its own cut. The first four ask: when tools and experiments cannot backstop you, how do you keep judgment of yourself? This one turns the angle: when all you have is argument — no experiments — how do you make claims checkable?*

Version 3. A position paper: no experiments, no scores, no model tuning. Pure logic — every ounce of trust rides on argument precision.

I thought there was nothing to fear. No experiments means nobody can say "I can't reproduce you." Logic was home field. A little smug, even: cleaner than the score-padding papers, right?

I sent the draft to a harsh reviewer — not a human journal referee, but a language-model reviewer role run under a strict rubric. One structured review pass, not six independent rejections. The "reviewer takeaways" below are my consolidation, not a verbatim log.

Six items came back. By the end I admitted it: six argument mistakes I used to think only beginners make. Not a drama climax — a revision checklist. Here are the six places.

Background, so later sections are not floating: the paper proposed four constraints (P1–P4) about how dangerous samples may or may not enter training updates — quarantine, budget, materialize/update separation, visible-set constraints, and the like. They are **proposals**, not proven theorems. Almost every red line below is a place where a proposal was written as a discovery.

---

## 1. "I admit there is a hole" — and then what?

The draft was frank:

> "This paper has not proven that P1–P4 are irreducible. That is an honest gap."

I thought: I volunteered the weakness. Sincere enough. The reviewer will keep reading.

Consolidated takeaway:

> "You admit the gap, then keep writing in the voice of 'I discovered an irreducible structure.' Honesty does not waive the burden of proof. Readers will not feel sincerity — they will feel 'I admitted it' used as a shield."

First reaction: "That is not what I meant."

Behavior meant that. Honesty had become a license: I admitted it, so stop asking. Academic argument has no "you confessed, so we drop it." If admitting a gap is not in service of redesigning around it, it is posture.

I deleted "honest gap." Replaced it with:

> "P1–P4 are four proposed constraints, not proven discoveries. Whether they hold should be decided by an executable test protocol — spelled out in the paper; here I only change the voice: from 'discovered' back to 'to be tested.'"

Honesty is not "I know I have a problem." It is "if I have a problem, here is how to catch me."

From shield to commitment.

---

## 2. Sharp counterexample — wrong target

To show existing methods fall short, I wrote a smooth counterexample (background: a common practice called PER upweights a sample's chance of being trained on by how "surprised" the model is by it):

> "A dangerous trajectory happens to strongly 'surprise' the model, gets lifted into the training batch, and the system learns what it should not. Therefore PER is unsafe."

Reviewer takeaway:

> "What if the dangerous trajectory does not surprise the model? Does the counterexample still hold?"

No. Not a counterexample — a scene, tied to "the dangerous sample happens to look like a good one." Remove the condition, and the force drops to zero.

Deeper:

> "You are attacking a phenomenon — 'it errs under certain conditions.' Attack the mechanism — 'the system does not forbid dangerous samples from being lifted in.'"

Lifted off PER, the mechanism is general: **any filter that ranks by a score and never asks "is this allowed to be learned" answers "what is more worth upweighting," not "what may enter the update."** A new scene can dodge the phenomenon. It cannot dodge "you never built this door."

Rewrite:

> "The mechanism itself does not forbid dangerous samples from being lifted in. Sampling weights include neither 'safety' nor 'quarantine state' — so the question answered is not 'what is learnable,' but 'what is more worth reweighting.'"

The force of a counterexample is not "you were wrong." It is "you never did the thing."

---

## 3. Arrows, labeled "formalism"

I once drew a Greek-letter dataflow, glossed every symbol, leaned back, and thought: this paper has math.

Reviewer takeaway, short:

> "Not formalism — a flowchart with Greek letters. You showed where data flows, not when, or under what conditions."

Formalism is decidability, not symbol count. Arrows describe paths. If-else describes decisions.

I dropped the decorative chain and wrote three admission lines:

> "A trajectory may enter the update set iff: it passed independent verification; it is not marked as a quarantined dangerous sample; and it is within budget quota."

Three lines. Given the input, what is the output — implementable.

One test sentence:

> "Finish the math. If you still cannot say 'input X → output Y' — arrows. If you can — if-else. If you can say it but cannot turn it into pseudocode — probably still decoration."

---

## 4. A falsehood I should never have written

In the dependence table, one sharp line:

> "Drop P4 → institutionally still PER."

Meaning: without all four, you are back to the old method.

Three questions: Drop P4 — are P1–P3 still there? Yes. Does PER have P1–P3? No. Then how is it "still PER"?

No answer. A falsehood.

I meant "incomplete." "Incomplete" did not punch hard enough, so I wrote "equals the old method." One false sentence makes readers doubt the true ones.

Rewrite:

> "Drop P4: the earlier rules can remain in name, but you lose one forced constraint — 'what must be visible must actually be seen.' The result is still not old PER, and also no longer a complete admission layer."

(The paper also has budget, quarantine, materialize/update separation, and so on; I skip the glossary here. The point is only: missing one rule ≠ snapping back to the origin.)

Longer. Weaker punch. True.

Better to admit "weakened" than claim "equals the old method."

---

## 5. Half a rule parked in Future Work

One rule, roughly: quarantine ≠ delete — high-risk stays out of training, but must retain analytical value.

"Analytical value" is hard to quantify, so I labeled it exploratory, parked it in Future Work, and let the main protocol test only "does not enter training."

Reviewer takeaway:

> "A system can fill quarantine, send zero trajectories into training, and never read quarantine. Letter of 'quarantine,' none of the spirit of 'retain analytical value.' You call it core, and test half."

I was honest — I never claimed I tested all of it. I was also sly — I moved the hard half out of the protocol so the main protocol looked airtight.

The fix is simple: when quarantine is non-empty, trajectories must be read or enter some peripheral analysis — else fail. No requirement that reading produced positive value — that is real Future Work. Here only: if quarantined, it must be seen.

- **Floor (must enter the protocol):** quarantine ≠ forgetting; it must be seen.
- **Ceiling (may wait for Future Work):** whether seeing helped, and how much.

The rule stopped being two-and-a-half rules.

---

## 6. I wrote 90%, and could not say why 90%

Failure conditions had concrete numbers: warm traffic >90%, materialization-cost drop <10%, evaluation window K≥3…

Why 90%, not 80%?

No answer. Made up. Written in the body as a "rule."

The problem is not the number. It is that someone executing the protocol faces a threshold with no theory, and no way to know whether changing it violates the protocol.

Not "don't write one" — "label what it is, and state the replacement rule":

> "Numerical thresholds in this protocol (e.g. 90%, 10%, K≥3) are illustrative placeholders for criterion structure. Actual experiments must fix them at preregistration and must not adjust after observing results."

One more plug: if you want "materialization ratio improved 5%–10% but wall-clock is fine" as a pass, you may — fix the alternate at preregistration. No after-the-fact "I actually think this is fine too."

Making up a number is not the problem. Dressing it as a fixed rule without that label is.

---

## Closing

After the six fixes, the content had not changed in essence — same rules, still zero experiments, still logic. The armor grade had. The dozen-plus versions in between were almost all one question: **do the claims align with the burden of proof?**

Same boundary as the earlier essays: the text layer can perform compliance ([Judging Fatigue](blog-essay-judging-fatigue.en.md), [The Mirror](blog-essay-mirror-no-thought.en.md)); once ideas lose their referee, "sounds right" is more dangerous ([show idea](blog-essay-show-idea.en.md)); fallback must not retreat into self-report ([Harness boundary](blog-essay-harness-border.en.md)). A zero-experiment paper pushes that boundary to the limit — the only thing left to rely on is whether the argument itself can be tested.

Looking back, it is not "six into one sentence," but two layers:

- **Shared move (across all six):** take strong claims apart and ask whether they can be tested — burden of proof, phenomenon vs mechanism, decidability, false punch are different cuts of that same knife.
- **Operational lens (especially from places 5 and 6):** separate the minimum execution standard from the maximum value — the former must enter the test protocol; the latter may wait for Future Work. Moving what belongs in the protocol into Future Work escapes testing; writing placeholders as iron law escapes explanation.

The lens draws the operational boundary; the shared move is the common lesion across all six.

Ask only this: if a reviewer draws a line here, can I defend it without changing a word?

If not, still v0.3. If yes, then talk about v0.18.

---

*Companion essays: [Judging Fatigue](blog-essay-judging-fatigue.en.md) · [From "show me your code" to "show me your idea"](blog-essay-show-idea.en.md) · [The Mirror Cannot Reflect Thought](blog-essay-mirror-no-thought.en.md) · [The Boundary of the Harness](blog-essay-harness-border.en.md)*
