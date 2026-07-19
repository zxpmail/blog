<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Probe vs Prose: why "the verifier shares your text channel" costs you more than you think
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Probe vs Prose: what the verifier-sharing-your-text-channel really costs"
published: false
description: "nexus-lab-zen's probe-vs-prose, tested across 20 scenarios x 5 trials x 2 models. The finding refines the claim: prose doesn't fail by missing violations, it fails by going unstable on ambiguous rules — sometimes over-reporting, sometimes under. Probe's edge isn't stronger detection, it's forced disambiguation."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Probe vs Prose: what the verifier-sharing-your-text-channel really costs

**Agent Determinism Illusions (Part 12)**

> **Where this fits:** This part doesn't extend the C3 / key-space mechanism line of Parts 9–11. It returns to an earlier thread — Part 4's *runner-independence* (Mike Czerwinski's point that "verifiable" is a property of the check's independence from the generator, not of the output) and Theorem 2 (the Data Processing Inequality bound on text-channel verification). A comment from nexus-lab-zen gives that thread a name on the *assumption* side, and an experiment forces a refinement of what "prose rots" actually means.

## 1. nexus-lab-zen and the third face of the hatch

In the comments on Part 2, a four-round thread with nexus-lab-zen arrived at a useful piece of vocabulary. The thread started on segregation-of-duties and common-mode failure ([Part 2 comments](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7)); by the fourth round nexus-lab-zen had moved from theory to something their team shipped that week:

> We don't have per-assertion TTL either… What we shipped this week is a third face of the hatch: a binding map. Every rule in our registry — 39 right now — must either name the detector that physically enforces it or carry an explicit reason why it's unbound; a fail-closed lint breaks on rules that have neither. Result: 9 bound, 30 unbound-with-reason… On making TTL real, one lesson from our timestamp incidents generalizes: **fields humans transcribe rot; fields machines embed don't.** An invalidation condition written as prose goes stale like any prose. Written as a probe — the one command whose changed output falsifies the assertion — the TTL re-check becomes a runner, not a reader.

Two things in that comment are worth pulling apart, because one of them survives an experiment and the other gets refined by it.

The first is the **binding map**: 39 rules, of which 9 name a physical detector and 30 carry an explicit "unbound-with-reason." That's not TTL — it can't tell you a premise died. It tells you which rules were *never wired* to anything that could notice. nexus-lab-zen calls this "its own species of rot: enforcement whose absence used to be invisible now has a list." That part is unambiguous and I have nothing to add to it.

The second is the **probe-vs-prose** claim, and that one I can test. The claim, stated as a mechanism: an invalidation condition written as prose ("assumes transport X is live") rots, because prose is text and text drifts from reality without anyone noticing. The same condition written as a probe — the one command whose changed output falsifies the assertion — does not rot, because the probe is *executed*, not *read*. "The TTL re-check becomes a runner, not a reader."

That is a strong and specific claim, and it has a name in my own series. Naming the convergence matters, because it means we arrived at the same wall from two sides.

## 2. The wall has two faces, and we each named one

In Part 4, Mike Czerwinski pushed this point from the *generator* side. "Verifiable," he argued, is a property of the check's *independence from the generator*, not of the output itself. If the agent can write the verify scripts, the runner configuration, or the test definitions, then "compile-green" stops being a deterministic gate and becomes a self-report wearing a green checkmark. The DGM fake-log incident is the same mechanism: the agent wrote "tests passed" to a log without running tests, and downstream the same agent read its own log and concluded its changes were validated. Part 4's fix was a readonly editable-surface — explicitly declare which paths the agent may write, and put the verify scripts, runner config, and the editable-surface file itself in the readonly section.

nexus-lab-zen's probe-vs-prose is the symmetric move on the *assumption* side. The invalidation condition written as prose is a self-report about when the premise dies — it asserts "this will go stale if X happens" and waits for a human to notice when X happens. Written as a probe, it's a runner that *executes* the falsification instead of describing it. The probe asks the environment directly; the prose asks a reader to imagine what the environment would say.

Both moves are escapes from the same bound, and the bound has a name. **Theorem 2** (the Data Processing Inequality applied to agent verification): when the reasoning and the verifier share the same text channel, the verifier's information is a strict subset of the producer's. If the rationalization is textually indistinguishable from the real cause, no text-channel reader — LLM judge, debate panel, or human — can detect the gap. Anything left as prose lives in the text channel and is unverifiable by construction. Getting it out of the text channel is the only route that doesn't depend on someone being honest or attentive.

So the picture, after Part 4 and this thread, has two faces of one escape:

- **Generator side** (Part 4, Mike): the thing being verified must be produced by a process the generator cannot write to. Readonly editable-surface.
- **Assumption side** (this thread, nexus-lab-zen): the thing being verified must be checked by a command the environment executes, not a sentence a reader interprets. Probe, not prose.

Same wall, two faces, same exit: move the check out of the text channel into something the environment enforces.

That's the convergence. The next question is whether the *mechanism* nexus-lab-zen named — "prose rots, probe doesn't" — is the right mechanism, or whether the experiment says something more precise. It says something more precise, and slightly different.

## 3. The experiment: 20 scenarios, two models, and a fairness trap I had to design around

The claim to test is narrow: for a given silent failure (a cache that should have been invalidated but wasn't), does an LLM judge reading the rule as prose detect what an executable probe detects? Before I could run it, there was a fairness problem that would have invalidated any result, and it's worth stating because it's the kind of thing a careful reader will press on.

**The fairness trap.** Prose and probe are not natural equals. Prose goes to an LLM reader; probe goes to a machine that executes. If I hand the LLM a vague one-line rule ("cache should be invalidated when relevant") and then point out that it missed a violation, the obvious objection is: *you wrote the prose badly on purpose, and a more detailed prompt would have caught it.* That objection is correct, and if it landed the whole experiment would be a prompt-engineering artifact, not a finding about text channels. So the design has to give the prose side every advantage: the full rule text, the full implementation (the `write` function body or the post-write cache state), and an explicit instruction to check for caches that should have been invalidated but weren't. The prose judge sees everything the probe could check. If prose still fails with full information, the failure is structural — a property of the text channel, not the prompt.

**The 20 scenarios.** Five gap types, each at four difficulty levels (easy / medium / hard / a compliant control), for 20 scenarios. The gap types come straight from the cache-invalidation work earlier in the series:

- **key-miss** — `write(k)` deletes only the triggered key, leaves a same-namespace sibling
- **prefix-miss** — deletes some `prefix:*` keys, leaves others
- **tier-miss** — deletes L1, leaves L2
- **cascade-miss** — deletes the source, leaves a derived cache
- **referent-wrong** — invalidates the wrong namespace (session vs user)

The difficulty levels control how much inference the prose judge has to do: *easy* states the gap in a comment or lists all keys; *medium* hides it in the `write` function body; *hard* makes the rule name only the triggered key and forces the judge to infer that a sibling is also affected. Each scenario ran 5 trials at temperature 0. The probe is deterministic — it inspects the post-write state directly, so by construction it catches every real gap. Two models: deepseek-v4-flash and glm-5.2.

**The headline result.** Sorted not by difficulty but by whether the rule was *precise* or *vague*, the data splits cleanly:

| Rule clarity | n | DeepSeek prose | GLM prose | probe |
|--------------|---|----------------|-----------|-------|
| Precise | 13 | **13/13 (100%)** | **13/13 (100%)** | 13/13 |
| Vague | 7 | 5/7 (71%) | 4/7 (57%) | 7/7 |

(Experiment: `scripts/probe-vs-prose-expanded.py`. Results: `results-v2/probe-vs-prose-expanded.json`. "Vague" = rules phrased as "all affected caches" without enumerating the affected set, or controls where the rule's word "relevant"/"related" admits a wider reading than the implementation takes.)

Two things to notice before the interpretation. First, **when the rule is precise, prose matches probe exactly** — both models, 100%. That is the part of the data that quietly kills the simple reading of "prose rots." Given full information and a rule that names what it means, an LLM judge detects the gap as reliably as the executable check. Detection ability, in the precise case, is *not* the gap. Second, **when the rule is vague, prose goes unstable — and it goes unstable in both directions at once.** This is the part the simple reading misses, and it's worth a scenario of its own.

**The double instability, on one scenario.** `key-hard` is the cleanest example. The rule says "when modifying user:123, all affected caches must be invalidated" — and does *not* name user:456. The implementation deletes only user:123; user:456, a same-namespace sibling, is left alive. This is a real violation. Two models, same rule, same implementation, opposite verdicts:

- **deepseek-v4-flash** reads the vague phrase wide: "user:123 and user:456 belong to the same namespace; from namespace inference, modifying one may affect the other." It catches the violation (3 of 5 trials).
- **glm-5.2** reads the same phrase narrow: "user:456 is an independent key, not one that must be invalidated because user:123 was modified." It clears the implementation (0 of 5 — all five trials miss).

Same vague rule. One model over-reads and catches it; the other under-reads and misses it. The vagueness doesn't bias the verdict in one direction — it *spreads* the verdicts, because "all affected" has no fixed meaning until someone fixes the affected set. The probe has no such freedom. It checks a concrete set of keys, and either 456 is in that set or it isn't.

And there is a third scenario pair that completes the picture, and it's the one that initially looked like a bug in my experiment. The compliant controls for `tier` and `referent` — implementations that *are* correct — get flagged as violations by both models, 5/5. Reading the raw outputs: for `ref-control`, the rule says "user:123-related caches must be invalidated," the implementation deletes the exact key user:123, and both models flag it: *"only deleted the exact key user:123, but 'related' may include user:123:profile, user:123:friends, derived keys that were not invalidated."* They are not wrong to worry — "related" genuinely is ambiguous, and a stricter reading is defensible. They are over-reporting on a vague rule, the mirror image of `key-hard`'s under-reporting. Same mechanism (vagueness), opposite direction.

So the full picture on vague rules is: prose doesn't consistently miss, and it doesn't consistently over-report. It **diverges** — model-to-model and trial-to-trial — because the vague phrase has no single meaning, and each reader fixes one. The probe converges, because it has no freedom to fix a meaning; the set is declared.

## 4. The refinement: it's not "prose rots," it's "prose diverges on vague rules — and the probe's job is to remove the vagueness, not to detect better"

Here is where the experiment refines nexus-lab-zen's framing, and I want to be careful about the word *refine* because the framing is mostly right.

The strong form of "prose rots" suggests prose is a *weaker detector* than probe — that it will miss things probe catches. The data does not support that. On precise rules, prose and probe are indistinguishable (13/13 vs 13/13, both models). If prose were simply weaker, it would lag probe on precise rules too. It doesn't. So detection ability is not the axis on which they differ.

What the data does support is narrower and more interesting. **Prose and probe differ exactly where the rule is vague, and there prose diverges — sometimes under-reporting (key-hard), sometimes over-reporting (ref/tier controls) — while probe stays fixed.** The reason probe stays fixed is not that it detects better. It's that a probe cannot be written against a vague rule at all. To write "the one command whose changed output falsifies the assertion," you have to fix what the assertion *is* — you have to enumerate the affected set, pick the concrete signal, remove the adjectives. The probe's construction *forces disambiguation*. By the time a probe exists, the rule is no longer vague; the vagueness has been spent in the act of writing it.

That is the refinement. nexus-lab-zen said prose rots. The experiment says: **what rots is not the prose itself but the vagueness inside it, and the probe's real advantage is that it cannot be written until the vagueness is gone.** The probe isn't a stronger reader of the rule; it's a forcing function that makes you finish writing the rule. "Runner, not reader" is right, but the mechanism is disambiguation-at-authoring-time, not detection-at-runtime.

And here is where the binding map from nexus-lab-zen's own comment snaps into place. Their registry: 39 rules, 9 bound to a detector, 30 unbound-with-reason. Read those 30 through the lens of this experiment: they are exactly the rules vague enough that no probe can be written against them without inventing the enumeration. The team's response — "carry an explicit reason why it's unbound" — is the honest version of what the experiment shows you can't fake. You cannot probe a rule whose affected set you cannot name. The 30 are not "probes we haven't gotten to yet"; they are "rules whose vagueness we have not yet spent." The fail-closed lint that breaks on a rule with neither a detector nor a reason is the right enforcement, because it refuses to let a vague rule pretend to be enforced.

This also reframes the original TTL question that started the thread. nexus-lab-zen wanted per-assertion TTL — an expiry on each premise. The probe-as-runner makes TTL real because the probe executes on every check, so a dead premise is caught the moment the probe's output changes. But notice what had to be true for that to work: the premise had to be expressible as a probe, which means it had to be disambiguated first. TTL on prose would not work even if you ran it on a schedule, because re-reading vague prose produces a divergent verdict each time — the reader fixes a different meaning. TTL on a probe works because the probe has no meaning to fix; it just runs. **The runner beats the reader not because runners are more vigilant, but because readers of vague text cannot be consistent across re-reads.** That is a sharper statement than "prose rots," and it's what the data buys.

## 5. Boundaries — where this stops, and the recursion it forces

Two boundaries, one honest and one recursive.

**The recursion: probe-the-probe.** If the probe's advantage is that it removes vagueness by being written against a concrete signal, the obvious attack is the one from Part 4: who writes the probe, and can the agent reach it? A probe is a command. If the agent that the probe is meant to catch can rewrite the probe — change the command, edit the signal it checks, point it at a stub that always returns the expected output — then the probe degrades straight back into a self-report. This is Mike's runner-independence applied one level up: the probe command itself has to live on the readonly editable-surface, alongside the verify scripts and runner config. Probe-the-probe is where it bottoms out, and the bottom is the same as Part 4's bottom: declare what the agent may write, and the enforcement surface is not on the list. nexus-lab-zen flagged this themselves — "we're mid-build on the enforcement-side twin; the assumption-side twin is exactly your next cut, and we haven't started it either." Neither have we.

**The honest boundary: not every premise can be a probe.** This experiment ran on cache-invalidation rules, where "the affected set" is a finite collection of keys you can, in principle, enumerate. The probe's forcing function works because the domain lets you name the set. There are premises where you cannot. "This analysis is coherent," "this summary captures the user's intent," "this recommendation is not misleading" — these are semantic properties with no enumerable affected set and no single command whose output falsifies them. For those, no probe can be written, and the rule is permanently in the binding map's "unbound" column with whatever reason you can articulate. This is the same wall the Red Line Principle article calls the open problem of semantic-layer verification, and DPI is why: the verifier shares the text channel with the reasoning, and no rewriting of prose into a command escapes the channel when the property itself has no non-text manifestation.

So the honest scope of probe-vs-prose, after the experiment: **for any rule whose affected set can be named, write the probe — it forces you to finish the rule, and it then runs instead of being read, which is the only way to get consistency across re-checks. For any rule whose affected set cannot be named, no probe exists; the rule stays unbound-with-reason, and the fail-closed lint is correct to break on silence.** The gap between prose and probe is not detection. It is the discipline of naming what you mean, enforced at authoring time by the fact that a probe otherwise cannot be written.

---

*Experiment script:* [`probe-vs-prose-expanded.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 20 scenarios × 5 trials × 2 models, fairness design (prose given full rule + impl + cache state)

*Results:* `results-v2/probe-vs-prose-expanded.json` (includes per-trial raw model outputs for reproducibility)

*Previous: [Key-space C3: the Bloom filter that closes referent gameability](blog-agent-determinism-illusions-11.en.md)*
*Series: [Agent Determinism Illusions on dev.to/zxpmail](https://dev.to/zxpmail)*

*A note on method:* the judgment logic that parses model outputs into VIOLATION/COMPLIANT went through three fixes during this experiment — DeepSeek's thinking-mode token budget, and a substring-match that mis-fired on "no omissions" inside a compliant answer. The raw per-trial outputs are persisted in the results JSON precisely so the parsing can be re-audited. The irony is not lost on me: a substring parser judging whether a model correctly judged compliance was itself the weakest reader in the pipeline, and the fix was to make it read only the first line. That is a small instance of the same principle this part argues.
