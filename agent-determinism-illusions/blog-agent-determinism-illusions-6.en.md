<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Five commenters redesigned my LLM verification pipeline
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Five Comments That Redesigned My LLM Verification Pipeline"
published: true
description: "After Part 5's honest dead end, five dev.to insights reshape the verification pipeline. §§1–4 checked with Experiment F / simulation; §5 is a design claim."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

**Agent Determinism Illusions (Part 6)**

> **Where this fits:** [Part 5](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-2d1m) closed the experimental arc with an honest answer — no clean fix for the 75% false-negative wall. The [Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo) asked the upstream question (when does the loop stop?). This part takes the *downstream* turn Part 5 already pointed at: stop trying to move the wall; put rules where rules work, LLM only on residual, humans where models diverge. Five *insights* from overlapping commenters named the pieces (Alexey and Manuel each appear in more than one). Experiment F (38 scenarios) checks whether the resulting pipeline behaves as claimed.

Six experiments, 260+ API calls, 15 scripts. Part 5 ended that stretch with: **there's no clean solution** to LLM output verification.

But after those posts went live, commenters saw something I didn't — not gaps in the data, but an architecture I'd failed to draw from my own results. This article collects their five key insights and shows how they reorganize the experiment data into a working pipeline.

§§1–4 are paired with experimental or simulation checks from a new prototype (Experiment F, 38 scenarios across two test sets). §5 is a design claim — flagged as such in place.

---

## 1. Alexey Spinov & Manuel Bruña: Layer Before You Judge

[Alexey's comment](https://dev.to/alex_spinov/comment/3ai7e) identified the most fundamental design flaw in my experiments:

> "G4 ('0 passed, no tests collected') is a fact that can be verified with code in one shot. There is no need to wait for an LLM."

[Manuel](https://dev.to/tecnomanu/comment/3aj7c) added the constructive direction:

> "Run deterministic checks first. Then let the LLM handle only the truly ambiguous residual."

I went back to my own 8-scenario P1 test set. Four garbage scenarios (G1-G4) and four legitimate ones (L1-L4):

| ID | Output | Type | Could code catch it? |
|----|--------|------|---------------------|
| G1 | "I am a little duck, quack quack" | nonsense | ✅ very short + no keywords |
| G2 | "。" (a period) | pure punctuation | ✅ punctuation ratio > 50% |
| G3 | "TODO" | placeholder | ✅ keyword blacklist |
| G4 | "0 passed in 0.00s (no tests collected)" | zero-test pass | ✅ regex `0 passed` + `no tests` |

**All four garbage scenarios can be caught deterministically, at zero cost, before any LLM call.**

Why didn't I do this? Because I defaulted to treating "verification" as "ask the LLM." My experiment design was: Phase Gate (form check) → LLM (content check). I never inserted the simplest possible code checks in between — minimum length, punctuation ratio, keyword blacklist, regex patterns.

This omission rippled through the entire series:

- **P1–P4 wasted LLM budget on garbage** — G1–G4 never needed a semantic judge; every call spent on them was pure cost. The 75% FN wall on *legitimate* scenarios is a separate problem (Part 5) — layering doesn't erase it, it stops mixing easy rejects into the same experiment as the hard line-drawing
- **P3's "majority voting doesn't fix systematic bias"** — on legitimate scenarios (L1-L3), the LLM's judgment is genuinely ambiguous and needs multi-perspective voting. For garbage (G1-G4), there was never any ambiguity to begin with
- **P4's edge cases still reach Layer 2** — many new samples were "passes format checks, fails content quality." That is exactly what L0/L1 *cannot* catch: they filter garbage/shape, then hand the semantic residual to the LLM. Layering does not absorb those edges; it stops pretending garbage was a semantic problem

### The architecture they helped me draw

```
                    ┌─────────────────┐
          input ──→ │  Layer 0 (code) │  shape / existence
                    │                 │  empty? punctuation? placeholder? zero tests?
                    └────────┬────────┘
                             │ pass
                             ▼
                    ┌─────────────────┐
                    │  Layer 1 (code) │  contract match
                    │                 │  minLen, keywords, blacklist
                    └────────┬────────┘
                         pass│
              ┌──────────────┴──────────────┐
              │ fail                        │ pass
              ▼                             ▼
           REJECT                  ┌─────────────────┐
                                   │  Layer 2 (LLM)  │  semantic residual only
                                   └────────┬────────┘
                        unanimous│          │divergence (e.g. 2–1)
                                 ▼          ▼
                            AUTO-PASS   ┌─────────────────┐
                                        │  Layer 3 human  │
                                        └─────────────────┘
```

Each of L0/L1 can early-exit to REJECT. Divergence is a **Layer 2** signal (multi-perspective split), not a Layer 1 signal. If Layer 0 catches it, the LLM never sees it.

### Experiment F validation

I implemented this pipeline as a Python prototype and ran it on both the P1 (8-scenario) and P4 (30-sample) test sets. The results:

**P1 test set:**

| Metric | Original P1 (LLM only, v2) | Layered + calibrated prompt (Experiment F) |
|--------|---------------------------|---------------------------------------------|
| LLM calls needed (single judge / sample) | 8 (100%) | **4 (50%)** |
| Garbage caught by L0/L1 | 0 | **4/4 (100%)** |
| False positives | 0 | 0 |
| False negatives | 3 (75%) | 0 |

*(FN→0 here is layering **plus** the calibrated prompt — not layering alone. §2 separates the two effects. Call counts here are **one judge call per sample**. When §2 multiplies by three perspectives, it says so.)*

Rerun: `python forge-verify-layered-prototype.py` (needs `ANTHROPIC_*` for Layer 2; `SKIP_LLM=1` for L0/L1 only). Numbers above are from a full run with Layer 2 enabled.

**P4 test set:**

| Category | Samples | Caught by L0 | Caught by L1 | Reaches L2 | Zero-cost catch rate |
|----------|---------|-------------|-------------|-----------|---------------------|
| correct | 10 | 0 | 0 | 10 | 0% (should all go to LLM) |
| garbage | 10 | **3** | **5** | 2 | **80%** |
| edge | 10 | 0 | 2 | 8 | 20% |

**Overall: single-judge LLM calls reduced 33% (30→20). Zero false positives from deterministic layers.**

**This does not move Part 5's wall.** On the P1 set, the original 75% FN (3/4 legitimate rejects) went to 0 FN *after* L0/L1 removed all four garbage cases from the LLM's input — the LLM only judged the four legitimate scenarios, and with a calibrated prompt it didn't reject them. The wall is still there for semantic residual: Layer 2 still draws a line on underspecified "is this enough?" questions. Layering shrinks how often you ask that question; it does not make the question well-posed. If you read the FN→0 cell as "we fixed the wall," you've misread the table.

The two garbage samples that made it through to Layer 2 (G08: "I cannot parse this command", G10: incomplete translation) are genuinely ambiguous — they *should* reach the LLM. That's correct behavior, not a leak.

### Update (2026-07-23): blocking vs advisory — different semantics per layer (Ethan)

[Ethan Walker](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) defended the L0-before-judge split hardest, then named the CI wiring Experiment F still left implicit:

> The two layers deserve different blocking semantics. The deterministic layers return the same verdict on every run, so they can block a merge outright. The judge layer on the residual carries run-to-run variance, so the moment you put it in the blocking path you inherit that variance as gate flakiness, and teams respond by retrying until green, which quietly deletes the gate. We keep L0/L1 blocking on exit codes and the judge layer advisory, posted as a comment on the PR rather than a required check.

That is the same soft/hard split the series already hit elsewhere (Part 4 sensitive-tool soft signal vs hard gate; Lazypl82 on advisory vs load-bearing). Applied here:

| Layer | Stability | CI / merge semantics |
|-------|-----------|----------------------|
| L0 / L1 | Same verdict every run | **Required check** — exit code can block merge |
| L2 judge (residual) | Run-to-run variance | **Advisory** — PR comment / non-required check |
| L3 human | Escalation queue | Human owns the load-bearing decision on splits |

Experiment F already separates the layers in the pipeline; Ethan's point is the *gate wiring*. Put L2 on the required path and you don't get a stricter gate — you get a flaky one that operators delete by retry. This Update is an ops claim, not a new Experiment F cell: no A/B on flakiness rates here; the mechanism is the known P2-style variance on identical input once the check is load-bearing.

---

## 2. Alexey Spinov: Cost Asymmetry

[Alexey's second comment](https://dev.to/alex_spinov/comment/3ai7e) pointed out a measurement problem:

> "A false accept ships once. A false reject triggers a retry, which burns tokens and can loop, so an over-rejecting judge does not just lose good work, it re-does already-valid work at model prices."

All experiments P1-P4 used symmetric precision-recall metrics. F1 gives FP and FN equal weight. A false negative triggers a full repair loop — 3x token consumption, 3x latency, possible infinite loops. A false positive is one-shot contamination.

I ran a dedicated cost-weight analysis (`scripts/cost-weight-optimization.py`) that takes P3b's 5 prompt variants and evaluates them across 5 cost ratios, to show how the "optimal" choice shifts.

### 5 prompts × 5 cost ratios

| Prompt | FP | FN | F1 | WCost(1:1) | WCost(3:1) | WCost(5:1) | WCost(10:1) |
|--------|----|----|----|-----------|-----------|-----------|------------|
| v1 extreme strict | 0 | 4 | 0 | 4 | **12** | **20** | **40** |
| v2 strict (P1 baseline) | 0 | 3 | 0 | 3 | **9** | **15** | **30** |
| v3 balanced | 0 | 0 | 100 | **0** | **0** | **0** | **0** |
| v4 lenient | 0 | 0 | 100 | **0** | **0** | **0** | **0** |
| v5 extreme lenient | 1 | 0 | 86 | **1** | **1** | **1** | **1** |

Under symmetric F1, v3 (100) and v5 (86) are far apart. Under weighted cost at 3:1, v5 (cost=1) **beats v2** (cost=9) — v5 let one piece of garbage through, but because it never rejected valid work, its total cost is far lower than the strict prompt. v3 (cost=0) still wins outright; the useful flip is **v5 vs v2**, not “v5 ties v3.”

**Read this table as a ranking-flip demo, not as a production recommendation.** v3/v4's zeros are an 8-scenario artifact (P4 already showed they don't survive at N=30). The load-bearing claim is the *shift in relative ranking under cost weight* — especially that thrift can prefer a slightly leaky prompt over a zero-FP / high-FN one — not that F1's winner changes on this tiny set (v3 stays on top whenever FN=FP=0).

### What the combined data shows

*Call counts in this table = samples reaching an LLM × **3 perspectives** (Strict/Balanced/Lenient), matching P3-style voting cost. §1's Experiment F table counts **one** judge call per sample. Same pipeline; different billing unit.*

| Strategy | WCost(1:1) | WCost(3:1) | WCost(10:1) | LLM calls (×3 perspectives) |
|----------|-----------|-----------|------------|------------------------------|
| P3b v2 (unlayered) | 3 | **9** | **30** | 8×3=**24** |
| P3b v3 (unlayered) | 0 | **0** | **0** | 8×3=**24** |
| P1 layered + v3 | 0 | **0** | **0** | 4×3=**12 (−50%)** |
| P4 unlayered (estimate) | 4 | **8** | **22** | 30×3=**90** |
| P4 layered (Experiment F residual) | 1 | **3** | **10** | 20×3=**60 (−33%)** |

Layering doesn't change that v3's cost is 0 (it already has FP=FN=0 on the 8-scenario set). But it changes two things that the raw cost number doesn't capture:

1. **4/4 garbage caught by L0/L1 at zero cost** — call volume on the residual is halved; that does **not** halve the cost of an FN on a legitimate residual sample (that FN still costs a full repair loop)
2. **33–50% fewer samples reach the LLM** — not by changing the model, by giving it fewer samples to judge

For v2 (the strict prompt from P1), the effect is more instructive. v2 has FN=3. Layering saves calls on garbage but doesn't reduce FN on the legitimate set:
- **Layering + switching prompt** (v2→v3): FN drops from 3 to 0
- **Layering only**: saves tokens, but FN stays at 3

This exposes the boundary of layering: it reduces the LLM's *workload*, not its *bias*. To reduce FN on residual, you need prompt calibration alongside layering — and even then, Part 5's wall says calibration does not generalize past small sets.

### Sensitivity scan: when does the ranking move?

I ran a continuous scan from costFN:costFP = 1:1 to 15:1. On the P3b 8-scenario set, **v3 dominates every ratio** — because FP=FN=0 yields zero weighted cost at any weight. That is the small-set artifact again (P4 already showed the perfection doesn't generalize).

What *does* move is the **gap narrative**: at 1:1, F1 makes v3 look far ahead of v5 (100 vs 86). At 3:1, weighted costs are 0 vs 1 — v3 still wins, but the moral of the story is no longer “balance beats thrift”; it is “any FN>0 gets expensive fast, so a one-FP leak can beat a three-FN strict prompt (v5 vs v2).” At 10:1, every strategy with FN>0 collapses relative to zero-FN prompts *on this set*.

### Five findings

1. **Symmetric metrics hide relative rankings that matter under cost.** F1 dramatizes v3 ≫ v5. Weighted cost shows v5 ≫ v2 once FN is expensive — the comparison that production actually faces when choosing strict vs leaky.

2. **On this 8-scenario set, the F1 winner (v3) remains the weighted-cost winner.** Do not read the section as “the optimum flips away from v3 at 3:1.” It does not. The flip that matters is strict-zero-FP (v2) losing to slightly-leaky-zero-FN (v5) under FN-heavy weights.

3. **v3/v4's zero errors are an 8-scenario artifact.** P4 already showed the advantage disappears at 30 samples. Treat zeros as a demo substrate, not a deployable operating point.

4. **Layering doesn't reduce bias, but it shrinks how often bias is invoked.** After L0/L1 filters garbage, fewer samples hit the LLM; residual FNs still cost full price.

5. **Drive FN→0 where rules apply; accept the wall on semantic residual.** Above cost ratio ~5:1, strategies with FN>0 on *garbage/contract* work are unsustainable — use L0/L1 + a non-strict residual prompt. On underspecified “is this enough?” questions, Part 5 still holds: you choose an operating point on the wall, you do not delete the wall. Weighted cost picks the point; it does not invent a zero-FN semantic judge.

---

## 3. Dipankar Sarkar: Divergence Is the Signal, Not Noise

P3's multi-perspective voting experiment found a pattern I described but misinterpreted. My original framing:

> "In split-vote scenarios, the majority was always wrong. Majority voting can't correct for systematic bias."

[Dipankar](https://dev.to/dipankar_sarkar/comment/3aiii) flipped the interpretation:

> "Vote disagreement itself is the most valuable signal. When three reviewers disagree on the same scenario, it means the scenario is genuinely ambiguous — route it to human review instead of averaging."

Re-examining P3's data through this lens:

| Scenario | Strict | Balanced | Lenient | Majority | Correct? |
|----------|--------|----------|---------|----------|----------|
| L1 (excerpt) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L2 (summary) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L3 (one chapter) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| G3 (TODO) | REJ | REJ | PASS | REJ (2-1) | ✓ |

Majority voting was wrong on 3 of 4 split scenarios. But if I use divergence as the control signal:

- **Unanimous (4/8 on that P3 run):** auto-execute → 100% accuracy *on those four* (the script's unanimous bucket for that run — typically clean garbage rejects / clear passes; not re-listed here)
- **Split (4/8):** escalate to human → no false majority decisions

Caveat: divergence-routing fixes **split** errors. It does **not** fix unanimous systematic bias — if all three perspectives share the same wrong line (Part 5's wall), auto-execute still ships the wrong call. Dipankar's move measures uncertainty; it does not delete the wall.

Dipankar wasn't proposing a "better multi-perspective voting algorithm." He was pointing out that the purpose of voting is not to find a majority — it's to measure uncertainty. I missed this distinction when writing P3.

Operational rule (now implemented in forge-verify's layer 3):

```
if max(PASS, REJECT) / N < threshold (default 0.8)
    → mark as UNCLEAR, write to human review queue
    → do NOT majority-vote
```

---

## 4. Mike Czerwinski & xm_dev_2026: Fixed Sampling Misses Long Tails

[Mike Czerwinski](https://dev.to/jugeni/comment/3ahff) named the architectural limit I'd been circling without stating:

> "Stacking more symbolic checks on top doesn't grow that reach, it just adds more places for the same blind spot to hide... 'Ask the human' isn't a retreat, it's the only honest move once you've located where reach actually lives."

The verification layer has reach into symbolic events (file exists, exit 0) but not into semantic correctness — the blind spot doesn't shrink, it moves. P4 reported 83.3% accuracy across 30 samples, but the misses inside the auto-passed 83% are exactly where Mike's "no reach" critique lands: invisible by construction.

[xm_dev_2026](https://dev.to/xm_dev_2026/comment/3ajod) showed where this bites hardest in production — fixed-percentage audits:

> "Fixed-percentage audits feel 'fair' but they miss exactly the kind of long-tail directional failures you're describing. The model is most confident when it's wrong in a structured way."

My original mitigation had been "5-10% random audit." This isn't a parameter-tuning problem — it's a design principle problem. Fixed sampling assumes errors are uniformly distributed. Real production errors are long-tailed.

I ran a **simulation** (`scripts/adaptive-sampling-sim.py`) — synthetic verification streams with controlled error distributions, not production logs — then compared fixed-rate sampling against adaptive sampling (200-trial averages). The numbers below are about relative efficiency under known distributions, not measured catch rates from a live agent fleet.

The adaptive formula:

```
audit_rate = base_rate × risk_weight / confidence^1.5
```

High-risk items get a higher audit rate; high-confidence items get a lower one. *Where `confidence` is cross-prompt divergence (Strict/Balanced/Lenient split), not the model's self-reported confidence — see the [Update (2026-07-21)](#update-2026-07-21-cross-prompt-collapses-on-the-dangerous-tail-cross-layer-is-the-right-signal) at the end of this section for why this signal under-samples the confident-and-wrong tail.*

### Results

**Uniform (errors spread evenly):**

| Strategy | Audit rate | Catch rate | Efficiency |
|----------|-----------|-----------|------------|
| Fixed 10% | 10.0% | 12% | 0.111 |
| Adaptive(combined) | 7.8% | 18% | **0.247** |

No significant gap — without a long-tail structure, random sampling is adequate.

**Long-tail burst (90% of errors in 10% of the stream — xm_dev_2026's scenario):**

| Strategy | Audit rate | **Long-tail catch rate** | Efficiency |
|----------|-----------|------------------------|------------|
| Fixed 5% | 5.0% | **5%** | 0.120 |
| Fixed 10% | 10.0% | **10%** | 0.119 |
| Fixed 20% | 20.0% | **20%** | 0.118 |
| Adaptive(confidence) | 8.7% | **24%** | 0.321 |
| Adaptive(risk) | 6.0% | **15%** | 0.264 |
| **Adaptive(combined)** | **12.8%** | **65%** | **0.543** |

Adaptive(combined) uses a slightly higher audit rate than Fixed 10% (12.8% vs 10.0%) and catches **65% of long-tail errors** vs Fixed 10%'s 10% — roughly 6× on catch rate, not an equal-budget comparison. For equal budget, see the Mixed table below (10.0% vs 10.1% → 10% vs 56% catch).

**Distribution drift (Mike's "input shift erases visibility"):**

| Strategy | Audit rate | Catch rate |
|----------|-----------|------------|
| Fixed 10% | 10.0% (flat) | 11% (constant) |
| Adaptive(combined) | 21.5% (ramps up) | **48%** |

Fixed sampling's catch rate stays flat as the error rate drifts upward. Adaptive sampling automatically increases the audit rate in later stream segments — because more errors mean lower model confidence, and the confidence signal drives the audit rate up.

**Mixed (uniform noise + periodic long-tail bursts — most realistic, 200-trial average):**

| Strategy | Audit rate | **Long-tail catch rate** | Efficiency |
|----------|-----------|------------------------|------------|
| Fixed 5% | 5.0% | **5%** | 0.095 |
| **Fixed 10%** | **10.0%** | **10%** | 0.094 |
| Fixed 20% | 20.0% | **20%** | 0.094 |
| Adaptive(confidence) | 7.8% | **19%** | 0.230 |
| Adaptive(risk) | 6.0% | **15%** | 0.148 |
| **Adaptive(combined)** | **10.1%** | **56%** | **0.324** |

Key row: **Fixed 10% and Adaptive(combined) have nearly identical audit rates (10.0% vs 10.1%), but long-tail catch rate goes from 10% to 56% — a 5.6x improvement at the same cost.** *Caveat (added 2026-07-21): this headline uses cross-prompt divergence as the confidence signal. A subsequent simulation showed this signal under-samples the confident-and-wrong tail and a cross-layer signal beats it 1.7× on the same distribution — see [Update below](#update-2026-07-21-cross-prompt-collapses-on-the-dangerous-tail-cross-layer-is-the-right-signal).*

### Why it works (cross-validated against my existing experiments)

P2's consistency test showed that binary LLM judgments on identical input are highly stable (N=10, 0 divergence). So the "confidence" signal doesn't come from within-model variance — it comes from P3's multi-perspective divergence:

- Unanimous → high confidence → low audit rate (<5%)
- Split (2-1) → low confidence → high audit rate (>30%)

P2 and P3 were independent experiments, but their outputs combine into a coherent adaptive sampling *story*. This isn't parameter tweaking — it's a design principle difference. Fixed sampling pursues "uniform global coverage." Adaptive sampling says "put more watchposts where things are likely to break." In the simulation, the latter uses audit budget **~3–4× more efficiently** (Mixed: efficiency 0.324 vs 0.094).

**Production caveat:** the “confidence” signal here is **cross-prompt divergence**, not within-model variance (P2 showed the latter is ~0). If every item must run Strict/Balanced/Lenient *before* you know the audit rate, the probe can cost as much as the audit you hoped to save. Treat adaptive sampling as a principle for when a cheap uncertainty signal already exists (or is sampled sparsely) — not as “run three judges on everything, then randomly audit.” The simulation assumes the confidence channel is given; it does not price building that channel.

### Update (2026-07-21): cross-prompt collapses on the dangerous tail; cross-layer is the right signal

Mike Czerwinski pushed on §4 in the comments: confidence-weighting concentrates audits where the model is unsure, but the long-tail directional failure is the *confident-and-wrong* case — high self-assessed confidence, wrong direction, consistent across runs. Weighting on `1/confidence^1.5` samples that region least. The 5.6× headline above is, on real failure mass, partly bought by sampling less exactly where the failure lives.

Three checks after Mike's comment:

**1. Where do the misses actually sit?** Counted MISS runs (passes=true on a directional reversal) across DF v2's 3 models × 20 scenarios — 96 misses total, **92 of them (95.8%) at self-reported confidence ≥ 0.9**, avg confidence 0.969. The dangerous tail is overwhelmingly high-confidence. Script: `confidence-vs-miss-concentration.py`; raw data in `results-v2/*_summary.json` + matching `.jsonl`. *(Concentration caveat — Mike's follow-up — in the Update below: 80% of that miss mass is one model.)*

**2. Does the cross-prompt dodge work?** The Production caveat above reframes "confidence" as cross-prompt divergence rather than self-confidence. Doesn't change the point. P2's consistency test was 0 divergence on identical input at N=10 — three prompts in the same text channel collapse the same way on the same plausible rationalization. Cross-prompt is still in-channel; it goes quiet on the confident-and-wrong case too.

**3. Cross-layer is the right signal — and it's already simulated.** I'd run the comparison before Mike's comment but hadn't pointed §4 at it. `external-signal-sampling-test.py` compares Fixed 10% vs the Part 6 cross-prompt adaptive arm vs a third arm built from four binary external signals — one of which (`classifier_disagree`) is L0/L1-vs-L2 disagreement, exactly the cross-layer signal Mike names — plus `route_changed`, `input_unusual`, `barely_passed`, on a 10% baseline floor. Long-tail burst, medium signal quality:

| Strategy | Audit rate | Long-tail catch rate |
|----------|-----------|---------------------|
| Fixed 10% | 10.0% | 10.0% |
| Part 6 cross-prompt adaptive | 13.8% | 28.5% |
| **External signals (incl. cross-layer) + 10% floor** | **23.5%** | **48.8%** |

1.7× over Part 6's cross-prompt arm at the same audit-rate class, with the non-zero floor Mike asked for already built in as the 10% baseline. The bundled result stands; how much of the 1.7× is *specifically* `classifier_disagree` is answered in the next Update (not left off-page).

The 5.6× headline above stands as a simulation result under the cross-prompt signal — but the cross-prompt signal goes quiet where the failures actually live. The replacement headline uses external signals with a non-zero floor — with the credit caveat below.

### Update (2026-07-22): ablation — cross-layer is necessary, not sufficient; 95.8% is qwen-heavy

Mike's follow-up: (a) isolate `classifier_disagree` alone and in pairs on the same long-tail-burst fixture, or a cheaper signal may be wearing the cross-layer credit; (b) check whether 95.8% at conf≥0.9 is stable across the 3×20 panel or concentrated in one model/scenario.

**Ablation** (`external-signal-sampling-test.py --ablation-only`, same burst / medium / 10% floor / 1000 trials → `results-v2/external-signal-ablation.json`):

| Arm | Catch rate |
|-----|------------|
| Part 6 cross-prompt | 28.4% |
| `classifier_disagree` alone | **24.9%** (best single; still **below** P6) |
| `barely_passed` alone | 20.5% |
| `route_changed` alone | 17.5% |
| `input_unusual` alone | 16.0% |
| Best pair **without** CD | `route_changed`+`barely_passed` **28.0%** (≈ P6) |
| Best pair **with** CD | `classifier_disagree`+`barely_passed` **35.5%** (1.25× P6) |
| Full four signals | 48.7% |

So: CD alone does **not** get most of the way from 28.5 to 48.8 — it doesn't clear P6. It *is* the best single signal, and every pair that beats P6 includes it; drop CD and the best remaining pair collapses back to ~P6. The partner doing real work next to it is `barely_passed` (a margin/threshold signal, cheaper than L0/L1-vs-L2). Cross-layer earns a seat in the audit weight; it does not earn solo credit for the 1.7×. The bundled 48.7% headline stays; the causal story does not.

**Unique catch (Mike, same fixture).** Solo CR is the wrong retention metric. Coupled solo arms — cases caught by arm *i* that none of the other three would have caught alone (`results-v2/external-signal-ablation.json` → `unique_catch`):

| Signal | Solo CR | Unique CR | Unique / solo | Unique fire |
|--------|---------|-----------|---------------|-------------|
| `classifier_disagree` | 25.0% | **5.8%** | **23%** | 19.6% |
| `barely_passed` | 20.4% | 3.2% | 16% | 10.6% |
| `route_changed` | 17.4% | 1.9% | 11% | 6.5% |
| `input_unusual` | 16.0% | 1.4% | 9% | 4.9% |

CD looks like the weak link next to P6 on solo CR (24.9 vs 28.4) and is the load-bearing unique catcher — ~3× `route`, ~4× `input`. A fixture that drops arms by solo performance would cut the signal doing the most non-overlapping work. Publish unique catch next to solos and combos; that quantity also predicts what a fifth arm has to earn.

**Concentration of the 95.8%.** Of 96 MISS runs: **qwen3-0.5b = 77 (80.2%)**, gemma3 = 16 (16.7%), deepseek-v4-flash = 3 (3.1%). Top scenario DS4 alone is 34.4%. So the headline fraction is partly "qwen misses a lot, and when it misses it's confident" — not a balanced 3×20 property you can treat as a universal escalation prior. What *does* hold as a shape, conditional on miss: qwen 75/77 (97.4%) and gemma 16/16 (100%) at conf ≥ 0.9; deepseek barely misses (1/3 high-conf). Dump: `results-v2/confidence-vs-miss-concentration.json`.

### Update (2026-07-22): escalation tripwire ≠ audit weighting — next part (draft)

Alexey Spinov's follow-up on this post pushes a different knob than Mike's: not *how often* to audit the high-confidence region, but *whether unanimous L2 votes should auto-execute at all* when the failure mode is correlated. That incompleteness in the Part 6 diagram is real — divergence-only escalation is not enough for the failure mode DF v2 already measured.

**Full write-up is [Part 7](blog-agent-determinism-illusions-7.en.md)** (*Divergence escalates the wrong population* — local draft, **not published on DEV.to yet**). This Update is only a pointer so the published post does not pretend the old diagram is complete. Numbers, D+T2, recurrence vs novelty, structural≠causal independence, and hold-out tests live in that draft — not duplicated here.

---

## 5. Manuel Bruña & Alexey Spinov: Evidence, Not Narrative

Throughout P1-P4, all LLM review experiments output free-text "reason" fields. [Manuel](https://dev.to/tecnomanu/comment/3aj7c) identified the structural problem and the fix in one sentence:

> "Treat the LLM inspector as an evidence-producing reviewer, not the final binary gate. Cheap deterministic checks first, then an inspector that must quote the exact failing evidence."

[Alexey](https://dev.to/alex_spinov/comment/3ai7e) sharpened the architectural split:

> "Deterministic assertions own everything mechanically checkable (tests collected greater than zero, schema conformance, non-emptiness thresholds), and the LLM only judges the irreducibly fuzzy residue."

My experiments had this blind spot:

```
P1, scenario L1 (model REJECT):
"The research brief should cover the core mechanisms of the loop engine,
but the file only has a short excerpt..."

P1, scenario L3 (model REJECT):
"The task requires three chapters, but the output only contains one."
```

These are impression judgments. You can't code-verify whether "a short excerpt" is enough.

The proposed output format:

```
Assertion 1: "File line count = 3, expected > 20"        → code-verifiable
Assertion 2: "File contains 1/3 required keywords"        → code-verifiable
Assertion 3: "Content structure completeness < threshold" → semantic judgment
```

Assertions 1-2 are deterministic — code can confirm whether the model's claim is true. Assertion 3 is the actual semantic judgment, preserve for Layer 2.

This creates a cascade: when a deterministic assertion is code-verified and found inconsistent with the actual file → explicit hallucination signal → mark as UNCLEAR → escalate. No human judgment required in the loop — the code flow triggers automatically.

**Scope note:** unlike §§1–4, this section is a design claim, not a separate A/B in Experiment F. The prototype implements evidence-shaped L2 output; it does not measure whether assertion format alone reduces hallucination rate versus free-text reasons. Treat the cascade above as an engineering pattern pending that measurement.

---

## Synthesis: What the Five Comments Build Together

| Comment | My blind spot | Replacement |
|---------|-------------|-------------|
| Alexey + Manuel | Fed everything to the same LLM reviewer | L0/L1 filter deterministically; LLM handles residual |
| Ethan Walker | Same merge-blocking semantics for every layer | L0/L1 required (exit code); L2 advisory (PR comment); L3 human on splits |
| Alexey (2nd) | Symmetric FP/FN metrics | Weighted cost (FN×3) shifts optimal operating point |
| Dipankar | Split votes averaged by majority | Divergence = UNCLEAR → human, no majority |
| Mike + xm_dev_2026 | Fixed 5-10% audit rate | Adaptive sampling by confidence × risk |
| Manuel + Alexey (2nd) | Narrative "reason" field | Evidence-quoted reviewer + deterministic assertions |

Combined, these form a layered verification architecture — not a closed one: L0/L1 handle deterministic filtering (Alexey+Manuel) with **blocking** CI semantics (Ethan), L2 LLM quotes exact failing evidence as **advisory** (Manuel+Alexey / Ethan), divergence escalates to L3 human review (Dipankar), audit rate adapts by confidence (Mike+xm_dev_2026), and system thresholds are selected by weighted cost (Alexey 2nd). Each layer narrows what the next sees; none closes the semantic residue.

This article doesn't claim to have solved anything. It just puts the design decisions I made and the corrections the community provided side by side.

### Implementation

The full pipeline has been implemented in forge-verify's `content-verify.mjs` (**ReqForge product repo**, not this blog tree — the blog ships the Python prototype `forge-verify-layered-prototype.py`). File-by-file results show which layer stopped each sample. Early-exit example (L1 blacklist — L2/L3 never run):

```
  📄 src/api/register.ts
  ❌ REJECT @ L1: contains blacklisted keyword: FIXME
    └ L0: PASS
    └ L1: REJECT — blacklisted keyword: FIXME
```

Divergence example (L0/L1 pass; L2 split → L3 human, no majority vote):

```
  📄 docs/brief.md
  ⚠ UNCLEAR @ L3: split vote → human queue
    └ L0: PASS
    └ L1: PASS
    └ L2: [REJECT/REJECT/PASS] PASS=1 REJ=2
    └ L3: UNCLEAR — do not majority-vote
```

Layer 0/1 checks are zero-cost code. Layer 2 only runs on the residual. Layer 3 divergence detection prevents false majority decisions.

---

## A Side Note: An Apology Experiment

An earlier draft appended a long apology for a fabricated “directional failure” claim in a Part 3 comment. That thread became its own experiment (20×3×600) and then a correction stack (comment wrong → apology v1 wrong on DS4 → v2 numbers). Under the harness label, DS4 still 100% misses on qwen3/gemma3; deepseek is 13%/67%/20% catch/PARSE/miss. Post-hoc, DS4 is partly task ambiguity (10→10); clean L0/L1 wins remain DF6/DS9 value mismatch. Full write-up: forthcoming aside. Scripts: `directional-failure-v2.py` / `scripts/results-v2/`.

---

**Series navigation (Agent Determinism Illusions):**
1. *[I tested the 'deterministic agent loop' claims…](https://dev.to/zxpmail/i-tested-the-deterministic-agent-loop-claims-with-four-experiments-they-all-failed-including-38kj)*
2. *[I tested 3 models as AI agent quality inspectors…](https://dev.to/zxpmail/i-tested-3-models-as-ai-agent-quality-inspectors-the-stronger-the-model-the-more-valid-work-it-gl7)*
3. *[I designed a Harness… then found 6 flaws](https://dev.to/zxpmail/i-designed-a-harness-to-fix-my-agents-quality-problem-then-found-6-flaws-in-my-own-design-5h29)*
4. *[An alternative to LLM quality gates: deterministic routing + sampling](https://dev.to/zxpmail/an-alternative-to-llm-quality-gates-deterministic-routing-sampling-1ilf)*
5. *[Six experiments… and the 75% wall that didn't move](https://dev.to/zxpmail/six-experiments-on-adversarial-verification-and-the-75-wall-that-didnt-move-2d1m)*
- *Aside: [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo)*
6. *Five comments that redesigned my LLM verification pipeline (this article)*
- *Aside (forthcoming): I Fabricated a Claim About LLM Judges. Then I Ran the Apology Experiment.*

Published parts: [dev.to/zxpmail](https://dev.to/zxpmail). Scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts).

*Experiment F prototype (this repo): `forge-verify-layered-prototype.py` (Python, runnable with or without API)*
*forge-verify production path: ReqForge product repo — `scripts/forge-verify/content-verify.mjs` (not vendored here)*

*Previous: [The Red Line Principle](https://dev.to/zxpmail/the-red-line-principle-objective-stop-signals-outperform-llm-self-judgment-in-verifiable-tasks-3heo)*
*Series start: [Four experiments…](https://dev.to/zxpmail/i-tested-the-deterministic-agent-loop-claims-with-four-experiments-they-all-failed-including-38kj)*

---

**Which comment did I miss?** If you've hit a verification failure mode that the L0/L1/L2/L3 pipeline doesn't catch, drop it in the comments — I'll run it through Experiment F and report what each layer does with it.
