<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Who enters the escalate stream is not who gets seen — rank under budget
  ─────────────────────────────────────────────────────────────────
-->

---
title: "D+T2 names who enters; budget names who gets seen"
published: true
description: "After Part 7's trigger fix: Alexey's floor-volume and Mike's rank-inside-stream open problem. Offline diluted-queue acceptance, feature×time stress, and Trigger∥Rank / Shadow∥Enforce dual-line sim. Calibrated hist ships on stratified dilution; stale tables fail closed."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# D+T2 names who enters; budget names who gets seen

**Agent Determinism Illusions (Part 15)**

> **Where this fits:** This part does **not** continue Part 8's channel-gap / skillgate thread (still unpublished in this numbering). It continues [Part 7](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513)'s escalation line — and the [Part 6](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) comment thread where Alexey Spinov and Mike Czerwinski pushed past “which stream.” Numbering jumps to 15 on purpose: Parts 8–14 already hold other arcs; publish order here is 7 → **15**.

Part 7 closed with: divergence stays; T1/T2 join it; none of them is the novelty arm. That answers **who enters** the escalate set. It does not answer what happens when the set is larger than the human budget.

On the Part 6 thread, Alexey posted a wiring warning: merging a second stream S into D under arrival order at a 2% budget can catch fewer MISSes than D alone. Mike reframed the open problem as **rank-inside-stream** — coverage-limited is a load-bearing property of any history-built trigger R, and nobody had proposed a design yet.

We do not reproduce Alexey's 720-cell grid: that was his parametric model (π·h·r_m), not in this repo. We ran a related check on df_proxy (`scripts/merge-displacement-grid-test.py`) and got a **structural NULL**: the D stream (conf<0.9) is miss-starved on this fixture — qwen3-0.5b's D has 2 MISS in 115 items, gemma3's has 0 in 147; three models, eight budgets, four added streams — 96 cells, and D@arrival exceeds 0 in none. The displacement shape has nowhere to fire. That itself is the finding: real single-judge outputs don't give D enough miss-mass to dilute.

This part pivots to a weaker proposition: can rank move the needle **inside any** escalate stream — and the shape dual-line production must take.

---

## 1. Floor volume beats stream choice

Once true positives in the escalate stream exceed budget `k`, no trigger definition supplies “who gets seen.” Class filters cannot shrink the TP mass without discarding the failures the trigger exists to find. The fight over divergence vs class vs UHC vs blend is secondary to **queue order under a hard cap**.

Part 7's D+T2 remains the right *entry* policy on the fixtures where it was measured. It is not a ranking policy.

---

## 2. Rank-inside-stream (existence)

Script: `scripts/rank-inside-stream-test.py` → `results-v2/rank-inside-stream.json`.

On DF v2 all-run traffic (N=585), under budgets 1%/2%/5%:

- **Floor-volume holds:** at B=2% (k=11), oracle leaves ~80+ of ~92–94 stream TPs unseen on fat streams.
- **Deployable proxy can move the needle:** leave-one-out `P(MISS|class)` beats arrival in 6/18 cells; on D+T2 at 5%, arrival 10 → loo 29 (= oracle).
- Natural multiperspective (N=60) is too small for the deployable claim; it still shows arrival-order cruelty: UHC∧class catches 3 while D+T2 catches 0 at B=5%.

Thus the open problem holds: same stream, same B, order alone changes catch.

---

## 3. Can a ranker “ship”? Pre-registered gates

Script: `scripts/ranker-prod-acceptance-test.py` → `results-v2/ranker-prod-acceptance.json`.

Candidate **R_hist**: train-window `P̂(MISS|class)`; unseen → global prior. Never peeks at the item's own label.

Gates G0–G6 (then G7 in the stress sweep): holdout miss mass; ≥ arrival; beat heuristic baselines on the constructed queue; merge non-inferiority; LOMO; cold-start; **ranking headroom** (arrival < oracle).

**Natural D+T2 on stratified holdout is 29/29 MISS** — arrival already equals oracle; G6 fails; a SHIP there would be vacuous. So the decisive protocol **constructs** a diluted escalate queue: all holdout D+T2 MISSes + non-MISS distractors ≈ 35% miss-rate, distractors first.

On that protocol: **SHIP** — at B=5% k=8, arrival **0** → R_hist **8** = oracle **8**.

Scope caveat, stated hard: certificate is for this traffic + these B + this dilution stress — not a universal production warrant.

---

## 4. Stress: dilution does not kill hist; time does

Script: `scripts/ranker-acceptance-stress-sweep.py` → `results-v2/ranker-acceptance-stress-sweep.json`.

Axes: features × dilution miss-rate (15%→95%) × holdout (stratified / within-model temporal / global temporal). G7 blocks 0=0 SHIP.

**Stratified:** R_hist / R_hist_conf **SHIP at every swept dilution** (other candidates do not — e.g. R_conf_asc goes NO_SHIP at 0.95). The 35% result was not a knife-edge.

**within_model_temporal** (per-model first 70% → train): R_hist **NO_SHIP at 15–65%** (G2/G7 — hist catch 0 while conf_desc saturates); recovers SHIP only on dense queues 80–95%. global_temporal still fails G0 (miss_test=1).

Reading: dilution stresses mixture and arrival order; the class table still works. Temporal holdout stresses **whether the table is still calibrated**. Stale `P(MISS|class)` ranks true misses below distractors; high-confidence ordering accidentally matches this fixture's miss shape. No single feature ships everywhere.

---

## 5. Dual-line ops: Trigger∥Rank and Shadow∥Enforce

Script: `scripts/dual-line-ops-sim.py` → `results-v2/dual-line-ops-sim.json`.

Production dual-line is not a metaphor:

| Line | Job |
|------|-----|
| **Trigger** | Who enters |
| **Rank** | Who is seen under `k` |
| **Shadow** | What the ranker would review |
| **Enforce** | What humans actually review |
| **Fallback** | If shadow catches 0 while oracle > 0 → stay on arrival |

**Stratified + diluted 35%:** Rank lift on fixed diluted (R_hist − arrival) ties/beats best trigger-only under arrival; shadow hist lifts +3/+8 — **SUPPORT dual-publish**.

**within_model_temporal:** R_hist lift 0; best trigger under arrival is T2 (catch 3/8) — **Trigger knob wins** when the rank table is stale. Shadow hist goes vacuous → **fallback_arrival**; safe ≥ enforce. (conf_desc shadow would have lifted — feature choice still matters.)

---

## Closing

Part 7 named who enters. Alexey named the unshrinkable floor. Mike named the open problem as rank-inside-stream. The offline suite says:

1. Order under budget is load-bearing.  
2. A toy hist ranker can clear a pre-registered gate on a *constructed* diluted queue under stratified holdout.  
3. The same candidate collapses under time-like holdout — so a SHIP is not a ship.  
4. Dual-line is the ops shape that matches the data: separate Trigger from Rank; Shadow before Enforce; fail closed when the shadow goes vacuous.

**D+T2 names who enters. Budget names who gets seen. Rank is a calibrated, degradable line — not another tripwire.**

What this does *not* claim: production labels, agent gaming, live catch@k confidence intervals, or that R_hist is the right production scorer. Those are product gates (shadow weeks, sliding recalibration, real audit outcomes) — not this fixture.

---

**Series:** Agent Determinism Illusions · Scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**Previous (argument arc):** [Part 7 — Divergence escalates the wrong population](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513)  
**Comment thread origin:** [Part 6](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)
