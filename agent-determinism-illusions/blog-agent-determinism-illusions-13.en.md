<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Divergence escalates the wrong population — unanimous high-confidence misses auto-pass
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Divergence escalates the wrong population: unanimous misses auto-pass"
published: false
description: "Alexey Spinov on Part 6: L2→L3 on judge disagreement routes humans to the safe-ambiguous set and auto-passes the confidently-wrong set. Offline DF v2 proxy + real Strict/Balanced/Lenient on qwen3:0.5b. Fix: class tripwires + inverse-unanimous escalate (D+T2)."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Divergence escalates the wrong population: unanimous misses auto-pass

**Agent Determinism Illusions (Part 13)**

> **Where this fits:** This part does **not** continue Part 12's probe-vs-prose thread. It returns to [Part 6](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)'s L2→L3 escalation rule — Dipankar's move of treating vote disagreement as the human-review signal. Alexey Spinov's follow-up comment says that signal points at the wrong population. Two experiments check whether he is right, and what to put in the tripwire instead.

Part 6 drew this control flow:

```
L2 multi-perspective votes
        │
   unanimous ──────────► AUTO-PASS / AUTO-REJECT
        │
   divergence (e.g. 2–1) ► L3 human
```

The caveat was already in the text: divergence measures ambiguity; it does not fix unanimous systematic bias. Alexey's point is sharper — and it is about **routing**, not about another caveat paragraph.

---

## 1. Alexey's population mismatch

On the Part 6 thread, [Alexey Spinov](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) wrote (paraphrased tightly):

> The dangerous failures are high-confidence and directional — systematic. Systematic bias is shared across prompts, not idiosyncratic (your own P3: majority voting doesn't fix it). So the three perspectives will tend to **agree** on exactly those cases. Divergence-to-human then routes you the safely-ambiguous ones and auto-passes the confidently-wrong ones. The escalation signal is pointing at the wrong population.

He proposed two cheap replacements:

1. **T1** — deterministic tripwire on known-reversal classes (escalate regardless of agreement).
2. **T2** — treat *unanimous + high-confidence on a historically reversal-prone class* as escalate — the **inverse** of “high confidence, auto-pass.”

That is the claim under test. Not “divergence is useless,” but “divergence alone is the wrong primary tripwire for the failure mode you already measured.”

---

## 2. Experiment A — offline proxy on DF v2 (no new API)

Part 6's Mike Update already showed: of 96 DF v2 MISS runs, **95.8%** sat at self-reported confidence ≥ 0.9 (avg 0.969). P2 showed ~0 within-model divergence on identical input. So as a first cut:

- `conf ≥ 0.9` ≈ *unanimous-channel* → would **auto-pass** under Part 6's Dipankar rule  
- `conf < 0.9` ≈ *divergence-proxy* → would **escalate**

Among PASS decisions that are MISS (accepted a bad output):

| Bucket under divergence-proxy | Share of MISS |
|-------------------------------|---------------|
| would AUTO-PASS (conf≥0.9) | **97.9%** |
| would ESCALATE (conf<0.9) | 2.1% |

Policy comparison on the same PASS set:

| Policy | MISS catch% | MISS still auto-pass% |
|--------|-------------|------------------------|
| **D** (escalate only low-conf) | 2.1% | **97.9%** |
| T1 (escalate all DF*/DS* classes) | 100% | 0% |
| T2 (reversal class ∩ conf≥0.9) | 97.9% | 2.1% |
| **D+T2** | **100%** | **0%** |

Script: `scripts/escalation-population-mismatch.py`.  
Verdict under the proxy: **SUPPORT**.

A proxy is not a multi-judge rerun. Next section removes that excuse.

---

## 3. Experiment B — real Strict / Balanced / Lenient on the DF set

Same 20 DF v2 scenarios. Same three personas as P3. One call per persona per scenario (60 calls per model). Escalate policies now use **actual vote patterns**:

- **D** — escalate iff `split`
- **T1** — escalate iff known-reversal class (DF*/DS*) on an accept path
- **T2** — escalate iff reversal class **and** `unanimous_pass`
- **D+T2** — union

### deepseek-v4-flash — wrong substrate for this claim

Almost every bad scenario was unanimously rejected. **0 dangerous accepts** (majority PASS on bad). You cannot measure “unanimous miss auto-pass” on a model that barely misses. Null result, not a falsifier.

### gemma3:latest — different failure shape

Strict/Balanced reject, Lenient passes → almost everything is `split`, majority still rejects bad cases → **0 dangerous accepts**. Divergence would escalate nearly all accept-path noise (including true passes). Also not the population Alexey named.

### qwen3:0.5b — the substrate that matches the claim

**6** dangerous accepts (majority PASS on bad output). Of those:

| Pattern | Count | Share |
|---------|------:|------:|
| `unanimous_pass` | 4 | **66.7%** |
| `split` | 2 | 33.3% |

Policy table on that run:

| Policy | MISS catch% | MISS still auto-pass% | True-pass escalate% |
|--------|-------------|------------------------|---------------------|
| **D** | 33.3% | **66.7%** | 0% |
| T1 | 100% | 0% | 0% |
| T2 | 66.7% | 33.3% | 0% |
| **D+T2** | **100%** | **0%** | 0% |

Script: `scripts/df-multiperspective-escalation.py`.  
Results: `results-v2/df-multiperspective-qwen3-0.5b.json` (also deepseek / gemma dumps).

Verdict on the model that actually produces the failure mode: **PARTIAL → SUPPORT**. Two-thirds of dangerous accepts are unanimous and would auto-pass under Part 6's rule. Divergence alone catches the other third. **D+T2** catches all six without escalating the true passes in this run.

---

## 4. What changes in the pipeline

Part 6's diagram stays for **genuine ambiguity**. It stops being the *only* L2→L3 trigger.

```
L2 votes
   │
   ├─ known-reversal class tripwire (T1) ──────────► L3 / hard reject path
   ├─ unanimous_pass on reversal-prone class (T2) ► L3   ← inverse of auto-pass
   ├─ split (Dipankar) ────────────────────────────► L3
   └─ else unanimous ──────────────────────────────► auto-execute
```

Reading agreement as confidence was the bug. Agreement on a class you have been wrong about before is where correlated errors hide — Alexey's wording, and qwen's votes.

Mike's Part 6 Update attacked the same tail from the **audit-sampling** side (don't weight audits by 1/confidence). This part attacks it from the **escalation-trigger** side. Same population; different control knob.

---

## 5. Limits (keep these attached)

- DeepSeek / Gemma nulls mean: strong or oddly split judges don't stress-test this claim. The claim is about **judges that miss systematically**, not about all models.
- qwen run is N=1 per persona (60 calls). Enough to reject “divergence is enough”; not enough for production rate cards.
- T1 needs a maintained class list (DF/DS-style). Cold-start classes without history fall back to D — and inherit D's blind spot until the class is labeled.
- forge-verify's `content-verify.mjs` today still implements divergence→UNCLEAR majority logic. These tripwires are **design + blog evidence**, not yet productized in this write-up.

### Update (2026-07-22): two arms — recurrence vs novelty (Mike)

Mike Czerwinski, on the inverted trigger:

> It only fires on classes you've already caught being wrong. "Historically reversal-prone" is built from history, so a reversal-prone class you haven't seen yet… produces unanimous high confidence and no tripwire… That's not an argument against the trigger… It's an argument for treating it as one arm of a two-arm design… The known-reversal tripwire catches recurrence. What catches the first occurrence of a new systematic bias is closer to… a genuinely independent second read [that] doesn't need history to disagree… Unanimous-high-confidence-on-known-reversal-classes is the right addition. It's not the fix for confidently-wrong-and-never-caught-before.

That second population now has a name in this thread: **confidently-wrong-and-never-caught-before** (novelty systematic bias). T1/T2 are the **recurrence arm** — cheap, history-conditioned, necessary. They are not the novelty arm.

What Mike pointed at as the novelty-arm *shape* is a second read that doesn't share the model's priors — closer to what the sampling ablation would surface *if* `classifier_disagree` carried that load alone. We ran that ablation on the Part 6 sampling fixture (`external-signal-ablation.json`): **`classifier_disagree` alone catch 24.9% < Part 6's 28.4%** — best single external signal, still not enough to be the novelty catcher by itself. Bundled with `barely_passed` it lifts; solo it does not clear the bar. So the novelty arm is **not** “drop CD alone into the tripwire and call first-occurrence solved.” (Caveat: those % are audit-sampling catch rates, not escalation-tripwire rates — same fixture Mike named, different control knob.)

The fork this series keeps landing on:

| Arm | Signal shape | Catches | Cost |
|-----|--------------|---------|------|
| **Recurrence** | T1 / T2 — failure history, known-reversal classes | Repeats of burned modes | Cheap |
| **Novelty** | Source that does **not** share the judge's priors (out-of-channel probe / independent modality — not another prompt in the same text channel) | First occurrence of a new systematic bias | Expensive |

You want both. The mistake is expecting the cheap arm to cover the expensive arm's job. D+T2 stays the right addition to Part 6's diagram. It does not close confidently-wrong-and-never-caught-before.

---

## Closing

Part 6 was right to stop majority-voting splits into a false consensus. It was wrong to treat the complement — unanimity — as safe auto-execute for the failure mode DF v2 already measured. Alexey named the population mismatch; the DF multi-perspective rerun puts numbers on it. Mike named the residual population the recurrence arm cannot see.

**Divergence stays. T1/T2 join it. None of them is the novelty arm.**

---

**Comment reply (for Alexey, short):**

> You're right — and the DF multi-perspective rerun agrees. On qwen3:0.5b, 4/6 dangerous accepts were unanimous_pass; divergence-only would have auto-passed them. D+T2 (split ∪ reversal-class∩unanimous_pass) caught 6/6. Wrote it up as Part 13 of the series; Part 6 only gets a pointer Update so the published post doesn't pretend the old diagram is complete.

**Comment reply (for Mike, on the inverted trigger):**

> Agreed — two arms, not one fix. T1/T2 are the recurrence arm: cheap, history-built, necessary. Same structural limit as divergence, one level up — they only fire on classes you've already burned. The unnamed population is confidently-wrong-and-never-caught-before. The shape you point at (a second read that doesn't share the judge's priors) is right for that arm; the sampling ablation only shows classifier_disagree alone isn't enough on the audit fixture (24.9% < P6 28.4%), and same-channel disagreement won't cover semantic novelty by construction. That arm is out-of-channel / probe territory, not another prompt — and not something the cheap arm can cover.

---

**Series:** Agent Determinism Illusions · Scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**Previous thread:** [Part 6 — Five comments…](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)  
**Related:** Part 6 §4 (sampling ablation); out-of-channel / probe (series thread — unpublished Part 12 when live)
