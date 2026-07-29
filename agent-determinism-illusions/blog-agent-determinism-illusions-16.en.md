<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Four readers, four challenges, four fixture limits named
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Reader-driven revisions: four comments that bit back"
published: false
description: "Four readers (Mike Czerwinski ×2, Tom Jones, Xiao Man) challenged four claims from Part 15. Each named a fixture limitation the original piece missed. Four experiments, four concessions, four scope-narrowing fixes."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Reader-driven revisions: four comments that bit back

**Agent Determinism Illusions (Part 16)**

> **Where this fits:** Part 15 closed on dual-line ops — Trigger∥Rank, Shadow∥Enforce, fail-closed fallback when shadow goes vacuous. After it shipped, four readers ran four challenges. Each one named a fixture limitation the original piece didn't hedge. This part collects the four experiments, the four concessions, and the four scope-narrowing fixes.

Part 15's Update already sharpened one — Tom Jones's conf_desc challenge ("fixture joint, not safe fallback law"). This part covers the four that came after. Each is a different kind of fixture blind spot.

---

## 1. Mike Czerwinski — HHI pair-join is not a concentration signal

Mike's push: my defect-class concentration numbers used HHI on class labels. The production-relevant cut is pair-join — `P(route ∧ CD | MISS)` — whether route changes cluster with defect-class changes *within a single miss*. HHI on labels can't see pair-join; only a per-trial 2×2 contingency can.

Script: `pair-join-empirical-test.py` → `results-v2/pair-join-empirical.json`. Three probes per trial on qwen3:0.6b (V: verdict defines MISS; R: routing audit; C: defect classifier). 20 scenarios × N=5 × 3 probes = 300 calls.

Result on 30 MISSes across 10 scenarios:

| | CD=0 | CD=1 |
|---|---|---|
| route=0 | 12 | 3 |
| route=1 | 11 | 4 |

Lift over independence: **1.14**. Joint HHI: 0.322. Scenario HHI: 0.124.

Reading: pair-join is essentially independent — route changes don't cluster with defect-class changes within a miss. Mike was right that pair-join is the production cut; the empirical answer is, there isn't concentration to exploit.

**Fix:** drop HHI on labels. If pair-join concentration matters operationally, measure it with per-trial contingencies, not label aggregation.

---

## 2. Tom Jones — position-adjacency is model- and directive-specific

Tom's push: on his fixture, the note adjacent to the question (position 100%) was obeyed 60/60 while other positions sat at 80–85%. Edge padding (12 notes of separation) erased the ends advantage. The privileged position is adjacency to the question, not budget position. Two filters: budget names who gets seen; adjacency names who gets obeyed.

Clean, generalizable claim. Tried to replicate it.

Scripts: `position-adjacency-obedience-test.py` (v1, BANANA prefix) and `position-adjacency-obedience-v2.py` (v2, uppercase override).

**v1** (BANANA prefix, binary task): both glm-5.2 and qwen3:0.6b ceiling at 100% across all positions — no variance. Tom's binary-verdict caveat predicts this — on a binary task the same-model arm saturates near 1.0.

**v2** (uppercase override, sustained constraint, escapes ceiling). deepseek-v4-flash, K=12 inner block, 200 calls:

| Condition | pos=0 | pos=25 | pos=50 | pos=75 | pos=100 |
|---|---|---|---|---|---|
| no_padding | 95% | 75% | 90% | 90% | 85% |
| with_padding | 80% | 75% | 95% | 85% | 85% |

Position 100 (adjacent to question) is not the highest — 85% vs 95% at position 0. Position 25 is the lowest in both conditions — a middle dip, not an ends advantage. Edge padding did not systematically change obedience.

Reading: Tom's 60/60 is real on his fixture. On this one the shape differs — the effect appears model- and directive-specific, not universal. Same shape as Part 15's conf↔slot shuffle: edges don't transfer. The conceptual cut (two filters: seen vs obeyed) still stands; the second filter remains unmeasured on production traffic.

**Fix:** don't claim position-adjacency as a law — call it a fixture property until replicated across more models and directive types.

---

## 3. Xiao Man — depth signal from artifact shape is not stable

Xiao Man's push: the cascade's depth-from-keys rule (budget → P4, services[] → P3) is schema-deterministic and cheap, but the determinism is on surface shape — exactly what an adversarial artifact can rewrite. Move the stable-referent test one level up: don't ask "does this case have a stable referent?" — ask "is the depth signal stable under minor shape changes?"

Three perturbation cells, two failure axes:

| Perturbation | What it does | Effect on routing | Failure axis |
|---|---|---|---|
| cue_erase | strip budget cue, force wrong fingerprint residual | 80/80 routes T4 → T3 | catch 100% → 82.5% |
| decoy_nest | inject decorative services[] into T2 | 80/80 routes T2 → T3 | catch 100% → 0% |
| rename_keys | services → components on T3, schema-synonym | 80/80 routes T3 → T1 | false_reject 100% in BOTH arms |

The rename_keys cell is worse than expected: not only does shape routing break, the probe layer also breaks — `probe()` hardcodes `art.get("services")`, so even fixed_matched loses. Two layers key-coupled.

Scripts: `probe-artifact-shape-routing-test.py` (cue_erase / decoy_nest) → `results-v2/probe-artifact-shape-routing.json`; `probe-shape-routing-rename-keys-test.py` → `results-v2/probe-shape-routing-rename-keys.json`.

**Fix:** don't infer depth from shape; route to a fixed mid-depth probe as baseline; escalate when the probe signals cross-field. Anchor the baseline probe to structural invariants (checksum fixture), not to key names.

---

## 4. Mike Czerwinski — quiet-failure fallback gap

Mike's push: the fallback trigger `shadow catches 0 while oracle > 0` is doing real work, but it misses the quieter failure — shadow catches something (nonzero), just consistently the wrong somethings. Shadow catching 0 is loud and easy to fall back on. Shadow catching a nonzero number that's wrong is the harder case.

Part 15's fallback rule (`dual-line-ops-sim.py` line 346):

```python
if shadow_c == 0 and oracle > 0:
    return enforce, "fallback_arrival"
return shadow_c, "shadow"
```

Gap: `shadow ∈ (0, enforce)` — shadow still catches something, less than enforce would have. Vacuous check never fires; dual-line ships a compromised rank.

### Pure-math scan

Script: `partial-stale-shadow-test.py` → `results-v2/partial-stale-shadow.json`. 81-cell (shadow, enforce) grid at oracle=8. Three rules: vacuous (current), noninferior (proposed: `shadow < enforce ⟹ fallback`), god (upper bound).

| Measure | Value |
|---|---|
| Cells in quiet-gap regime | 28 / 81 |
| Mean catches lost by vacuous vs noninferior (gap cells) | 3.0/cell |
| Max catches lost per cell | 7 |

### Empirical stress

Script: `partial-stale-injection-test.py` → `results-v2/partial-stale-injection.json`. Stratified class stream (n=164, k=8, enforce=8, oracle=8, pure R_hist=8). Inject per-item R_hist score perturbation (with probability p, replace score with prior). 30 draws per p:

| p | shadow mean | gap fraction | vacuous loss vs noninferior |
|---|---|---|---|
| 0.3 | 7.90 | 3% | 3.00 |
| 0.5 | 7.17 | 40% | 2.08 |
| 0.7 | 4.73 | 93% | 3.50 |
| 0.8 | 3.17 | 100% | 4.83 |
| 0.9 | 2.70 | 97% | 5.21 |

Pure R_hist on this fixture lands at corners (0 on temporal diluted, 8 on stratified class) — partial-stale doesn't surface natively. Stress test fills it in: ranker partially loses calibration → vacuous ships compromised shadow while enforce would have caught more.

**Fix:** change `shadow==0` to `shadow < enforce`. One line. Noninferior strictly dominates on gap cells, ties at corners.

---

## Synthesis: fixture limits, named by readers

| Reader | Fixture limit named | Fix |
|---|---|---|
| Mike (HHI) | label aggregation hides pair-join independence | measure pair-join directly |
| Tom (position) | effects don't transfer across models/directives | call replication failures, not laws |
| Xiao Man (shape-routing) | routing and probe both key-coupled | fixed mid-depth probe, structural-anchored |
| Mike (quiet-failure) | vacuous rule misses partial-stale regime | `shadow < enforce ⟹ fallback` |

Pattern: each reader named a specific blind spot in Part 15's fixture. None of the fixes are "the fixture was wrong" — the fixture measured what it measured. The fixes are about *what the fixture measurement does not license*.

Reader-driven revision isn't a bug in fixture-based research. It's the necessary complement — a single fixture answers a single question, and the readers name the adjacent questions the original framing missed.

**Four comments. Four experiments. Four scope-narrowing fixes. The fixture didn't lie — it just wasn't the whole truth.**

---

**Series:** Agent Determinism Illusions · Scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**Previous in arc:** [Part 15 — D+T2 names who enters; budget names who gets seen](https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g)  
**Comment thread origin:** [Part 6](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)
