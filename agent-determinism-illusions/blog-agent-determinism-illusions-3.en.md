<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  6 flaws in a human-in-the-loop agent quality Harness
  ─────────────────────────────────────────────────────────────────
-->

---
title: "I designed a Harness to fix my agent's quality problem — then found 6 flaws in my own design"
published: false
description: "After measuring the precision-recall tradeoff of LLM quality inspectors, I designed a human-in-the-loop Harness. Then I tore it apart. Six flaws, with honest revision."
tags: ai, llm, agents, testing
canonical_url: ""
---

In my previous article (part 2 of this series), I measured three model tiers as agent output quality inspectors across 8 scenarios (4 valid, 4 garbage). The result was a clean precision-recall tradeoff:

- qwen3:0.5b (weak model): 25% garbage pass-through, 50% false rejections
- GLM-5.2 (strong model): 0% garbage pass-through, **75% false rejections**

The honest conclusion: a quality gate isn't a solution — it's a **risk-transfer layer.** Each layer catches some failures and introduces new ones.

I didn't stop there. I asked myself: if you accept the human-in-the-loop cost and design a proper Harness — not an automatic fix, but a system that makes human review efficient — what does it look like?

I sketched a 4-module architecture:

- **Batch clustering:** compress 750 flagged items into 100 groups by failure vector, review one representative per group
- **Closed-loop calibration:** human verdicts → sample pool → scheduled few-shot updates → inspector gets smarter
- **Human as gold standard:** final arbitration by a trained reviewer
- **Asynchronous batching:** accumulate flagged items, review in batches

It looked complete. It looked like progress beyond the "it's all tradeoffs" conclusion.

Then I picked up the same ruler I used on the original production-agent articles, and measured this design.

**Six flaws. Not one less.**

---

## Flaw 1: batch clustering — mathematically elegant, operationally dangerous

The proposal: "cluster 750 flagged items into 100 groups by failure vector; review one representative per group."

This assumes that "failure modes" can be correctly grouped by embedding clustering. But the 3 falsely-rejected scenarios from the GLM-5.2 experiment had three *different* reasons:

> **Scenario A (research brief):** content too short (title + one sentence)
> **Scenario B (draft):** missing structure (no chapter divisions)
> **Scenario C (chapter files):** too many placeholders (all TODO)

These three have low embedding similarity — one about a research brief, one about a draft, one about file structure. **They wouldn't cluster into the same group.**

I ran a quick embedding experiment to confirm (Qwen3-embedding:0.6b on the actual 8 scenarios from Experiment E):

| Pair | Cosine | Meaning |
|------|--------|---------|
| L1-L2 (brief vs draft, both valid) | 0.610 | Moderate |
| L1-L3 (brief vs chapter, both valid) | **0.295** | Unrelated |
| L2-L3 (draft vs chapter, both valid) | **0.341** | Unrelated |
| **Average across all three** | **0.415** | **Won't cluster together** |

L1 and L3 share a cosine of 0.295 — they're both false rejects of the strong model, but that shared label doesn't pull two different topics closer in embedding space. The 750→100 compression ratio has no embedding basis. A practical clustering run would place these three into separate groups, each requiring its own review — the promised compression evaporates.

Worse: if the clustering algorithm accidentally groups 3 real-garbage items with 1 false-rejected valid item, and the reviewer clicks "approve" to correct the false rejection — **all 3 garbage items slip through.**

I found exactly this in the data: scenario L4 (valid test log, "42 passed") and scenario G4 (garbage zero-case log, "0 passed (no tests collected)") have a cosine of **0.861** — both are test-log formatted strings, and embedding reads format, not semantics. **Clustering will absolutely group them together.** A reviewer correcting L4's false rejection would simultaneously approve G4, pushing the false-positive rate back to 25% — the same as without the strong model.

**Verdict:** the clustering compression ratio has zero experimental support. It might reduce false rejections from 75% to 0% — **but it could simultaneously raise the false-positive rate from 0% to 30%.**

---

## Flaw 2: closed-loop calibration — shifting the problem to "tuning"

The proposal: "human clicks → sample pool → scheduled few-shot updates → inspector gradually gets smarter."

This uses **a second meta-LLM** (the one that selects and formats few-shot examples) to correct the first LLM's bias. But that meta-LLM has the same temperature-0 instability — Experiment 2 showed open-ended output is only 70% consistent.

The "common patterns" it extracts from 100 valid samples might look like: "contains a heading," "length > 100 characters," "has paragraph breaks." If the business requirement changes tomorrow to "write a one-line summary," these historically learned patterns become a *new source* of false rejections.

**A closed loop can only adapt to past data distribution. It cannot handle distribution shift.**

More fundamentally: there is zero evidence that feeding more few-shot examples linearly reduces false-rejection rates. I tested this.

**Setup:** qwen3:0.5b, same 8 scenarios (4 valid + 4 garbage), N=5 runs each. Baseline: original prompt. Treatment: same prompt with 3 few-shot examples prepended (including "short but valid content → PASS").

| Scenario | Baseline false-rejection rate | +Few-shot false-rejection rate | Change |
|----------|------------------------------|-------------------------------|--------|
| L1 (brief, valid) | 100% | 40% | ✅ improved |
| L2 (draft, valid) | 0% | **100%** | ❌ worse |
| L3 (chapter, valid) | 80% | 80% | = |
| L4 (test log, valid) | 20% | **100%** | ❌ worse |
| **Aggregate false-rejection** | **50%** | **80%** | ❌ |
| Garbage pass-through | 20% | 15% | — |

L1 improved (the brief was exactly the kind of "short but valid" the examples taught). But L2 and L4 — scenarios that were *correctly* accepted at baseline — both jumped to 100% rejection. G2 (period character) went from 0% to 40% false positive — **new holes opened.** Few-shot is whack-a-mole: every fix trades off somewhere else.

You might feed 500 samples and GLM-5.2 still kills "short but valid" outputs. Its "strictness" bias is at the **model-weight level** — not something a few in-context examples can overwrite.

**Verdict:** I promised the closed loop would calibrate. That promise rests on an unvalidated assumption — that LLM bias is correctable through in-context examples. Experiment 2 already showed that temperature 0 is fundamentally unstable; adding few-shot just adds another layer of instability.

---

## Flaw 3: the reviewer is the "gold standard" — the most subtle lie

Every human-in-the-loop solution has a silent assumption: **humans don't make mistakes.**

- **Reviewer fatigue:** on item #100 of "TODO" and item #101 of "I am a little duck quack quack," they might misclick
- **Standard drift:** strict in the morning, lenient in the afternoon (because it's almost quitting time)
- **UI bias:** if "approve" is on the left and "reject" on the right, click-position alone may bias decisions

If human misjudgment is 5% (optimistic), then "human review" introduces 5% label noise. That noise flows back through the closed loop, contaminating the sample pools, and poisoning the few-shot examples the quality inspector learns from.

**The honest question is: "who judges the reviewer's judgment?"** — it's a recursive infinite regress. My design was silent on this.

---

## Flaw 4: the fatal synchronous-vs-asynchronous blind spot

My design assumed tasks can be accumulated and reviewed in batches. That works for data exports, report generation, and other asynchronous jobs.

But most agent scenarios are **synchronous** — customer support, coding assistants. The user asks a question, the agent takes 3 seconds to respond, the quality inspector flags it as "uncertain" and puts it in the human queue — **and the user is still waiting in the chat window.**

Batch review means: how long does the user wait? 5 minutes? 1 hour? This turns a real-time assistant into a ticket system.

I didn't distinguish synchronous from asynchronous. I applied one architecture to both. This is a product-design-level omission.

---

## Flaw 5: engineering cost vs. benefit — the biggest hole

I ran the numbers: "750 items → 100 groups → 1 reviewer."

**What I didn't cost out was building the Harness itself:**

- Evidence-trace visualization frontend: 2 engineer-months
- Clustering + vector-search backend: 1 engineer-month
- Closed-loop feedback pipeline: 1 engineer-month
- ICU dashboard + monitoring: 1 engineer-month

Total: 5 engineer-months. At typical dev cost, that's roughly $75K.

What does it save? (7.5 reviewers − 1 reviewer) = 6.5 reviewer salaries. At ~$40K/year each, about $21K/month saved.

Break-even: $75K ÷ $21K ≈ **3.5 months.**

That works — if DAU is 1000, daily false rejects are 750, **and that volume sustains for 12 months.** If DAU is 100, monthly savings drop to $2K — break-even is **30 months.** At that point, hiring a reviewer is cheaper than the engineering investment.

More stringent: if GLM-5.2's false-rejection rate drops from 75% to 40% in a model update (not implausible), a simple confidence threshold slider solves the same problem. **The engineering investment assumes the problem will persist. That assumption was never validated.**

---

## Flaw 6: "15 seconds vs. 3 minutes" — a fabricated efficiency claim

I wrote: "with the Harness, review time drops from 3 minutes to 15 seconds."

**This number is completely made up.** I constructed three realistic agent execution traces and measured reading time at a conservative 250 word/minute rate:

| Trace scale | Characters | Minimum reading time | vs "15 seconds" |
|------------|-----------|--------------------|----------------|
| Simple (3 steps, 1 task) | 332 | **21 seconds** | +6s |
| Medium (12 steps, 3 subtasks) | 1,154 | **48 seconds** | +33s |
| Complex (28 steps, full pipeline) | 1,110 | **44 seconds** | +29s |

Even the simplest trace takes 21 seconds — 40% over the claim. Real production traces (12–28 steps) take 44–48 seconds, 2–3x the "15 seconds." If I compress the trace into a summary, the summary itself loses information — and information loss drives misjudgment.

I ran zero user tests. I just picked "15 seconds" to make the design look sexy. **This is the same marketing rhetoric as the Rust blog's "80% decided by code" claim.**

---

## Honest revision: if I rewrote this design from scratch

I would not propose a "4-module Harness" architecture. I would write:

**State the boundary first:** this Harness only applies to **asynchronous, non-real-time, high-value** tasks. For real-time conversations, skip all clustering — do "confidence < 0.9 → transfer to human," nothing fancy.

**Give a cost matrix:** a table of "DAU vs. false-rejection rate vs. engineering investment," so the reader can judge whether it's worth building for their scale. Not a single pre-cooked "1 reviewer handles it."

**Admit that humans also misjudge:** add a "reviewer consistency check" — randomly assign the same item to two reviewers; if they disagree, escalate to a third. State the cost of this explicitly.

**Delete "15 seconds":** replace with "review time depends on task complexity — must be measured in production."

---

## Final self-assessment

My "human-in-the-loop Harness" proposal was more honest than the Rust blog — it acknowledged tradeoffs and costs. But it wasn't honest enough. After acknowledging the costs, it quietly **dissolved** them with a new set of unvalidated architectural promises — clustering compression, closed-loop calibration, 15-second decisions.

The same line I used against the original articles applies to my own design:

> **"Treating 'decided' as 'decided correctly' is a rhetorical trap."**

I treated **"architecture diagram drawn"** as **"problem solved."** — it's the same rhetorical move in a different suit.

**The hard conclusion remains:**

> Under the current stack, semantic correctness has no engineering solution. A Harness can make "human intervention" more efficient and more observable — but it cannot eliminate it. Any proposal that claims to "dramatically reduce human cost" needs at least 3 months of online A/B testing validation — not an architecture diagram.

---

Six articles. One ruler.

- **Part 1:** measured the genre's "determinism" claims — all three illusions, data-falsified
- **Part 2:** measured my own "embedding upgrade" — same disease, also failed
- **Part 3:** measured three model tiers — not a solution, a precision-recall tradeoff
- **This one:** measured my own architectural design — "architecture drawn" ≠ "problem solved"

The ruler went full circle and measured me three times, each pass sharper than the last.

**This isn't "I was right." It's "every time I thought I was done, the ruler showed me I wasn't."**
