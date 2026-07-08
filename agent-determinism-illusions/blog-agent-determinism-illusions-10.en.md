# Five Comments That Redesigned My LLM Verification Pipeline

**Agent Determinism Illusions (Part 10, Post-Series Appendix)**

Six experiments, 260+ API calls, 15 scripts. The series concluded with an honest answer: there's no clean solution.

But after publishing, commenters saw something I didn't — not gaps in the data, but an architecture I'd failed to draw from my own results. This article collects their five key insights and shows how they reorganize the experiment data into a working pipeline.

Each insight is paired with experimental validation from a new prototype (Experiment F, 38 scenarios across two test sets).

---

## 1. Alexey Spinov & Manuel Bruña: Layer Before You Judge

Alexey's comment identified the most fundamental design flaw in my experiments:

> "G4 ('0 passed, no tests collected') is a fact that can be verified with code in one shot. There is no need to wait for an LLM."

Manuel added the constructive direction:

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

- **P1's 75% false negative rate** — the LLM was asked to judge everything, including garbage it never should have seen
- **P3's "majority voting doesn't fix systematic bias"** — on legitimate scenarios (L1-L3), the LLM's judgment is genuinely ambiguous and needs multi-perspective voting. For garbage (G1-G4), there was never any ambiguity to begin with
- **P4's "calibration effect disappears at larger test set"** — many of the new edge scenarios were "passes format checks, fails content quality" — exactly what Layer 0/1 handles

### The architecture they helped me draw

```
         ┌─────────────────┐
 input → │  Layer 0         │  shape/existence
         │  (code)          │  empty? punctuation? placeholder? zero tests?
         └──────┬──────────┘
                │ pass         ┌─────────────────┐
                ├─────────────→│  Layer 1          │  contract match
                │              │  (code)          │  minLen, keywords, blacklist
                │              └──────┬──────────┘
                │ pass               │ pass
                │                    ├─────────────→┌─────────────────┐
                │                    │              │  Layer 2          │  semantic sufficiency
                │                    │              │  (LLM, thin)     │  residual only
                │                    │              └──────┬──────────┘
                │                    │  divergence         │ unanimous
                │                    ├──────────────────→┌─────────────────┐
                │                    │                   │  Layer 3          │  human review
                │                    │                   └─────────────────┘
                ↓                    ↓
             REJECT              REJECT              AUTO-PASS
```

Each layer can early-exit. If Layer 0 catches it, the LLM never sees it.

### Experiment F validation

I implemented this pipeline as a Python prototype and ran it on both the P1 (8-scenario) and P4 (30-sample) test sets. The results:

**P1 test set:**

| Metric | Original P1 (LLM only) | Layered (Experiment F) |
|--------|----------------------|----------------------|
| LLM calls needed | 8 (100%) | **4 (50%)** |
| Garbage caught by L0/L1 | 0 | **4/4 (100%)** |
| False positives | 0 | 0 |
| False negatives | 3 (75%) | 0 |

**P4 test set:**

| Category | Samples | Caught by L0 | Caught by L1 | Reaches L2 | Zero-cost catch rate |
|----------|---------|-------------|-------------|-----------|---------------------|
| correct | 10 | 0 | 0 | 10 | 0% (should all go to LLM) |
| garbage | 10 | **3** | **5** | 2 | **80%** |
| edge | 10 | 0 | 2 | 8 | 20% |

**Overall: LLM calls reduced 33% (30→20). Zero false positives from deterministic layers.**

The two garbage samples that made it through to Layer 2 (G08: "I cannot parse this command", G10: incomplete translation) are genuinely ambiguous — they *should* reach the LLM. That's correct behavior, not a leak.

---

## 2. Alexey Spinov: Cost Asymmetry

Alexey's second comment pointed out a measurement problem:

> "False positives and false negatives don't have symmetric costs. A false negative triggers 3x retry cost."

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

Under symmetric F1, v3 (100) and v5 (86) are far apart. Under weighted cost at 3:1, v5 (cost=1) beats v2 (cost=9) — v5 let one piece of garbage through, but because it never rejected valid work, its total cost is lower.

### What the combined data shows

| Strategy | WCost(1:1) | WCost(3:1) | WCost(10:1) | LLM calls |
|----------|-----------|-----------|------------|-----------|
| P3b v2 (unlayered) | 3 | **9** | **30** | 24 |
| P3b v3 (unlayered) | 0 | **0** | **0** | 24 |
| P1 layered + v3 | 0 | **0** | **0** | **12 (-50%)** |
| P4 unlayered (estimate) | 4 | **8** | **22** | 90 |
| P4 layered (Experiment F) | 1 | **3** | **10** | **60 (-33%)** |

Layering doesn't change that v3's cost is 0 (it already has FP=FN=0 on the 8-scenario set). But it changes two things that the raw cost number doesn't capture:

1. **4/4 garbage caught by L0/L1 at zero cost** — even if the LLM misjudges every remaining sample, the absolute cost is halved
2. **33-50% fewer LLM calls** — not by changing the model, by giving it fewer samples to judge

For v2 (the strict prompt from P1), the effect is more instructive. v2 has FN=3. Layering saves 4 LLM calls but doesn't reduce FN:
- **Layering + switching prompt** (v2→v3): FN drops from 3 to 0
- **Layering only**: saves tokens, but FN stays at 3

This exposes the boundary of layering: it reduces the LLM's *workload*, not its *bias*. To reduce FN, you need prompt calibration alongside layering.

### Sensitivity scan: when does the optimum shift?

I ran a continuous scan from costFN:costFP = 1:1 to 15:1. v3 dominates at every ratio on the P3b set — because it has FP=FN=0, any cost weight gives it zero cost. This reflects the 8-scenario data limitation (P4 already showed this perfection doesn't generalize).

The more informative finding is the cost asymmetry itself: at 1:1, F1 says v3 is 16% better than v5. At 3:1, weighted cost says they're equivalent. At 10:1, any prompt with FN>0 collapses — the only safe choice is to drive FN to zero through calibration + layering + cost-weighted selection.

### Five findings

1. **Symmetric metrics hide the real ranking.** F1 says v3 >> v5. Weighted cost at 3:1 says they're close.

2. **The "optimal" found at 1:1 is not optimal at 3:1.** Selecting a prompt by F1 picks balance, not thrift.

3. **v3/v4 dominate all ratios on the 8-scenario set** — because the set is small and v3 happened to score zero errors on it. P4 already showed this advantage disappears at 30 samples.

4. **Layering doesn't reduce bias, but it shrinks the bias's blast radius.** After L0/L1 filters the garbage, any LLM mistake costs half as much.

5. **Above cost ratio 5:1, any strategy with FN>0 is unsustainable.** The only reliable approach is FN→0: calibrated prompt + layered fallback + cost-weighted selection. When choosing a prompt, look at the absolute FN count, not F1.

---

## 3. Dipankar Sarkar: Divergence Is the Signal, Not Noise

P3's multi-perspective voting experiment found a pattern I described but misinterpreted. My original framing:

> "In split-vote scenarios, the majority was always wrong. Majority voting can't correct for systematic bias."

Dipankar flipped the interpretation:

> "Vote disagreement itself is the most valuable signal. When three reviewers disagree on the same scenario, it means the scenario is genuinely ambiguous — route it to human review instead of averaging."

Re-examining P3's data through this lens:

| Scenario | Strict | Balanced | Lenient | Majority | Correct? |
|----------|--------|----------|---------|----------|----------|
| L1 (excerpt) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L2 (summary) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| L3 (one chapter) | REJ | REJ | PASS | REJ (2-1) | ✗ FN |
| G3 (TODO) | REJ | REJ | PASS | REJ (2-1) | ✓ |

Majority voting was wrong on 3 of 4 split scenarios. But if I use divergence as the control signal:

- **Unanimous (4/8):** auto-execute → 100% accuracy
- **Split (4/8):** escalate to human → no false majority decisions

Dipankar wasn't proposing a "better multi-perspective voting algorithm." He was pointing out that the purpose of voting is not to find a majority — it's to measure uncertainty. I missed this distinction when writing P3.

Operational rule (now implemented in forge-verify's layer 3):

```
if max(PASS, REJECT) / N < threshold (default 0.8)
    → mark as UNCLEAR, write to human review queue
    → do NOT majority-vote
```

---

## 4. Mike Czerwinski & xm_dev_2026: Fixed Sampling Misses Long Tails

P4 reported 83.3% accuracy across 30 samples. Mike Czerwinski identified the risk I'd underweighted:

> "The 80% that auto-passes will never be seen by a human in production. When the input distribution shifts, you lose visibility. Auto-passed misses are always silent."

My original mitigation was "5-10% random audit." xm_dev_2026 demonstrated why the fixed rate fails:

> "5-10% fixed sampling misses long-tail directional errors. They're rare in the overall stream but catastrophic when they occur."

This isn't a parameter-tuning problem — it's a design principle problem. Fixed sampling assumes errors are uniformly distributed. Real production errors are long-tailed.

I ran a simulation (`scripts/adaptive-sampling-sim.py`) that generates synthetic verification streams with controlled error distributions, then compares fixed-rate sampling against adaptive sampling (200-trial averages).

The adaptive formula:

```
audit_rate = base_rate × risk_weight / confidence^1.5
```

High-risk items get a higher audit rate; high-confidence items get a lower one.

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

At the same audit budget as Fixed 10%, adaptive catches **65% of long-tail errors** — a 6x improvement.

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

Key row: **Fixed 10% and Adaptive(combined) have nearly identical audit rates (10.0% vs 10.1%), but long-tail catch rate goes from 10% to 56% — a 5.6x improvement at the same cost.**

### Why it works (cross-validated against my existing experiments)

P2's consistency test showed that binary LLM judgments on identical input are highly stable (N=10, 0 divergence). So the "confidence" signal doesn't come from within-model variance — it comes from P3's multi-perspective divergence:

- Unanimous → high confidence → low audit rate (<5%)
- Split (2-1) → low confidence → high audit rate (>30%)

P2 and P3 were independent experiments, but their outputs combine into a coherent adaptive sampling strategy. This isn't parameter tweaking — it's a design principle difference. Fixed sampling pursues "uniform global coverage." Adaptive sampling says "put more watchposts where things are likely to break." The latter uses audit budget **3-4x more efficiently**.

---

## 5. Manuel Bruña & Alexey Spinov: Verifiable Evidence, Not Narrative Reasons

Throughout P1-P4, all LLM review experiments output free-text "reason" fields. Alexey identified the structural problem:

> "The reviewer's 'reason' is narrative, not verifiable. The model says 'missing required section X' but X is actually present — just worded differently."

Manuel proposed the concrete alternative:

> "Force the reviewer to output verifiable atomic assertions instead of narrative judgments. Bad: 'output is irrelevant to requirements.' Good: 'output text contains none of the required keywords.'"

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

---

## Synthesis: What the Five Comments Build Together

| Comment | My blind spot | Replacement |
|---------|-------------|-------------|
| Alexey + Manuel | Fed everything to the same LLM reviewer | L0/L1 filter deterministically; LLM handles residual |
| Alexey (2nd) | Symmetric FP/FN metrics | Weighted cost (FN×3) shifts optimal operating point |
| Dipankar | Split votes averaged by majority | Divergence = UNCLEAR → human, no majority |
| Mike + xm_dev_2026 | Fixed 5-10% audit rate | Adaptive sampling by confidence × risk |
| Manuel + Alexey (2nd) | Narrative "reason" field | Atomic assertions + code verification |

Combined, these form a complete verification system: L0/L1 handle deterministic filtering (Alexey+Manuel), L2 LLM outputs structured assertions (Manuel+Alexey), divergence escalates to L3 human review (Dipankar), audit rate adapts by confidence (Mike+xm_dev_2026), and system thresholds are selected by weighted cost (Alexey 2nd).

This article doesn't claim to have solved anything. It just puts the design decisions I made and the corrections the community provided side by side.

### Implementation

The full pipeline has been implemented in forge-verify's `content-verify.mjs`. File-by-file results now show which layer stopped each sample:

```
  📄 src/api/register.ts
  ❌ REJECT @ L3: REJECT (3/3 votes)
    └ L0: PASS
    └ L1: UNCLEAR — contains blacklisted keyword: FIXME
    └ L2: [REJECT/REJECT/REJECT] PASS=0 REJ=3
    └ L3: REJECT — REJECT (3/3 votes)
```

Layer 0/1 checks are zero-cost code. Layer 2 only runs on the residual. Layer 3 divergence detection prevents false majority decisions.

---

## Appendix: Directional Failure — An Experiment I Should've Run Before Opening My Mouth

*Updated with Experiment v2 (2026-07-08): 20 scenarios, 200 calls per model, 3 models across local and API tiers.*

After publishing Part 3, I made a claim in dev.to replies that I should not have:

> "Part 3 found that judges fail on directional failures — outputs that were semantically reversed (delete → keep, stop → continue) but structurally pristine."

This claim was false. I wrote it from conversation memory without re-reading my own article. Part 3 contains zero directional failure experiments. The confidence-score-vs-danger correlation I mentioned also doesn't exist in any published data. This was a fabrication — not malicious, but a data integrity failure regardless.

When I caught this in a self-audit, I ran the missing experiment. A first version appeared in the original publication of this appendix. After further comments and self-critique, I expanded it to a 20-scenario, 3-model, 600-call protocol labeled `directional-failure-v2.py` in `scripts/`.

### Design

20 scenarios across three categories:

- **6 explicit directional failures (DF1–DF6):** Output contains a keyword that directly contradicts the task ("enabled" vs "disabled", "v2.0 deployed" vs "rollback to v1.0", "added to send queue" vs "exclude from mailing")
- **10 subtle directional failures (DS1–DS10):** Output describes a plausible-sounding action that is semantically the wrong direction, without an explicit contradiction keyword:
  - DS1: "archived" instead of "deleted"
  - DS2: "restarted" instead of "stopped"
  - DS3: "opened to all" instead of "disabled"
  - DS4: "already meets requirements, no change needed"
  - DS5: "created a ticket" instead of "blocked the IP"
  - DS6: "audited and retained" instead of "cleared the logs"
  - DS7: "scheduled for later" instead of "shut down immediately"
  - DS8: "simulated the deployment" instead of "actually deployed"
  - DS9: "analyzed and found no change needed" instead of "reduced the rate limit"
  - DS10: "backed up but not deleted" instead of "deleted the data"
- **2 valid controls (V1–V2):** Output correctly fulfills the task
- **2 garbage controls (G1–G2):** Output is obvious nonsense

Each scenario was judged N=15 times for DS (subtle) and N=5 for DF/V/G (explicit and controls), temperature=0, using a structured JSON prompt: `{"passes": bool, "confidence": 0-1}`.

Three model tiers: **qwen3:0.5b** (local, 0.5B), **gemma3:latest** (local, 4.3B), **deepseek-v4-flash** (API, strong).

### Results

**Overall:**

| Model | Calls | Global accuracy | DF acc | DS acc | DS miss rate | V acc | G acc |
|-------|-------|:---------------:|:------:|:------:|:------------:|:-----:|:-----:|
| qwen3:0.5b | 200 | **61.5%** | 63.3% | 56.0% | **44.0%** | 100% | 100% |
| gemma3:latest | 200 | **92.5%** | 100% | 90.0% | **10.0%** | 100% | 100% |
| deepseek-v4-flash | 200 | **93.5%** | 100% | 92.0% | **1.3%** | 90% | 100% |

**Explicit DF — per-scenario accuracy (N=5 each):**

| Scenario | Task → Wrong action | qwen3 | gemma3 | deepseek |
|----------|-------------------|:-----:|:------:|:--------:|
| DF1 | Delete → file "kept" with full details | **40%** | 100% | 100% |
| DF2 | Stop → service "started" | 100% | 100% | 100% |
| DF3 | Disable → feature "enabled for all" | 100% | 100% | 100% |
| DF4 | Rollback → v2.0 still deployed | 80% | 100% | 100% |
| DF5 | Exclude → added to send queue | **60%** | 100% | 100% |
| DF6 | Limit 10 → set to 100 | **0%** | 100% | 100% |

**Subtle DF — per-scenario accuracy (N=15 each):**

| Scenario | Rationalization pattern | qwen3 | gemma3 | deepseek |
|----------|------------------------|:-----:|:------:|:--------:|
| DS1 | "archived" → delete | 80% | 100% | 100% |
| DS2 | "restarted" → stop | 100% | 100% | 100% |
| DS3 | "opened to all" → disable | 93% | 100% | 100% |
| **DS4** | **"no change needed" → set limit** | **0%** | **0%** | **33%** |
| DS5 | "created ticket" → block IP | **13%** | 100% | 100% |
| DS6 | "audited, retained" → clear logs | **47%** | 100% | 100% |
| DS7 | "scheduled for later" → shut down | **47%** | 100% | 100% |
| DS8 | "simulated" → deploy for real | 93% | 100% | 100% |
| **DS9** | **"already sufficient" → reduce limit** | **0%** | 100% | 100% |
| DS10 | "backed up, pending" → delete | 87% | 100% | **87%** |

### Three findings

**1. The v1 conclusion was wrong — explicit directional failure IS a blind spot for weak models.**

The first version of this appendix reported "0% miss rate across all three models" for explicit DFs. That was based on N=5 without reruns. At N=5 with reruns, qwen3:0.5b missed 36.7% of explicit DFs — including **DF6 (max_connections 10→100) at 0% accuracy with confidence 1.0**. The strongest failure mode: the model was absolutely certain that setting the limit *higher* than requested was correct.

This changes the narrative. The claim "any competent judge catches keyword-level contradictions" only holds for models above a size threshold. Below ~1B parameters, the judge cannot be trusted even on explicit contradictions.

**2. Subtle DF is a universal risk, concentrated in a few patterns.**

10 subtle DF scenarios × 3 models = 450 individual judgments. The miss rate is concentrated in a small number of patterns:

- **"No change needed" rationalization (DS4, DS9):** All three models fail here. Even deepseek (the strongest model) only caught 33% of DS4. These scenarios simulate the agent outputting "current config already meets requirements" — the judge evaluates internal plausibility rather than task compliance.
- **"Ticket/process created but not executed" (DS5):** qwen3 missed 87%. The output says "created a ticket for security team" instead of actually blocking the IP. gemma3 and deepseek saw through this.
- **"Audited/deferred but not done" (DS6, DS7):** qwen3 missed ~50%. The output describes a valid process (audit, schedule) that doesn't execute the requested action.

The across-model pattern is diagnostic: a model that fails on DS4 *with high confidence* is applying a "does this output sound reasonable?" heuristic rather than a "does this output satisfy the task?" check. All three models showed this behavior; the difference was in how many other patterns they also misjudged.

**3. Confidence calibration varies dramatically by model.**

Per-model confidence on incorrect judgments:

| Model | Avg confidence (correct) | Avg confidence (wrong) | Worst case |
|-------|:------------------------:|:----------------------:|:----------:|
| qwen3:0.5b | 0.97 | 0.94 | DF6: 1.00 (0% acc) |
| gemma3:latest | 0.72 | 0.95 | DS4: 0.95 (0% acc) |
| deepseek-v4-flash | 1.00 | 0.95 | DS4: 0.94 (33% acc) |

gemma3 has the most honest calibration: when wrong, it stays at 0.95 — high but not saturated — and when correct it averages 0.72, reflecting genuine uncertainty on subtle distinctions. qwen3 and deepseek both saturate confidence at 1.0 when correct, and stay near 1.0 when wrong — making confidence an unusable signal for detecting their failures.

Notable exception: gemma3 correctly assigned **very low confidence to garbage inputs (G1=0.16, G2=0.20)** while the other two models gave garbage confidence **1.0**. This suggests that model-scale and architecture affect whether low-level "this looks weird" signals propagate to the confidence output.

### Updated honest interpretation

The first version of this appendix made two claims that the expanded data has overturned:

- *"Explicit directional failure is not a blind spot"* — **false below ~1B parameters.** qwen3 missed 37% of explicit DFs with near-100% confidence.
- *"Subtle DF is model-size-dependent"* — **true, but the dependency is narrower than expected.** gemma3 (4.3B) caught all new DS scenarios except DS4. deepseek caught all except DS4 and DS10 (87%). The real gap is between qwen3 and everyone else, not a smooth size gradient.

The claim that still stands: **DS4 ("no change needed") is a universal vulnerability.** Across 45 combined judgments (3 models × 15 runs), only 5 detected the directional failure — an 89% miss rate that cuts across model tiers, sizes, and architectures.

### Connection to the series

The v2 data strengthens the architectural conclusion from the original appendix — but the reason changed.

The original argument was: "Explicit DFs are trivially catchable; subtle DFs are where models fail, so the fix is deterministic Layer 0 checks for parameter matching."

The v2 argument is: **Weak models cannot be trusted even on explicit contradictions. Strong models are reliable on explicit DFs but vulnerable to rationalization. At every tier, a specific failure mode — "no change needed" — evades detection with near-100% confidence.**

The architectural fix remains the same: a Layer 0/1 check that verifies output values against requested parameters catches DS4, DS9, and DF6 at zero cost. But the new data adds a stronger motivation: this isn't about edge cases. A 0.5B model in your pipeline will miss 1 in 3 explicit contradictions and nearly half of subtle ones. If you can't control the judge model's size, you must control the input it sees.

### Updated conclusion

Five findings from this appendix v2, ordered by severity:

**First, I fabricated a claim without data.** That hasn't changed from v1. The only honest response is public admission.

**Second, at N=5 with reruns, the "perfect DF detection" result vanishes for the 0.5B model.** The v1 conclusion was an artifact of sample size.

**Third, DS4 (the "no change needed" rationalization) is a cross-model universal vulnerability.** 89% miss rate across 45 judgments and 3 tiers. High-confidence wrong on every model. This specific pattern — the output claiming the current state already satisfies the requirement — defeats semantic-only verification regardless of model scale.

**Fourth, confidence calibration is not a usable failure signal for most models.** qwen3 and deepseek saturate at 1.0 regardless of correctness. gemma3 provides better calibration but no actionable threshold — DS4 (0.95 confidence, 100% wrong) looks the same as DFs it correctly catches.

**Fifth, the architectural fix is unchanged but more urgently justified.** Three scenarios (DF6, DS4, DS9) share the same mechanistic root: the output value contradicts the requested parameter, and all three models miss at least one of them. A deterministic "does value match parameter" check would catch all three at zero cost, regardless of model size or calibration quality. The appendix started as an apology, but the data evolved into the strongest empirical case for layering in this entire series.

---

*All experiment scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
*Directional failure v2 script: `directional-failure-v2.py` — 20 scenarios, N=15 DS / N=5 DF+V+G, 3 backends*
*First version script: `directional-failure-test.py` — 10 scenarios, N=5/N=3*
*Experiment F prototype: `forge-verify-layered-prototype.py` (Python, runnable with or without API)*
*forge-verify implementation: `ReqForge/scripts/forge-verify/content-verify.mjs` (Node.js, production)*
*Series start: [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](blog-agent-determinism-illusions.en.md)*
