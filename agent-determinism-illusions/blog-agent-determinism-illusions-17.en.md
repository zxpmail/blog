<!--
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  When the reply triggers another revision — Xiao Man's anchor relocation
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Round 2: when the reply triggers another revision"
published: false
description: "Xiao Man's 'remove anchor from probe' refinement on the rename_keys cell. Path-passing redesign (probe v1 false_reject 100% → v2 0%), declaration-anchor survival matrix (4 anchors × 8 perturbations, no anchor 8/8), and the boundary-leak-detector rule for future fixtures."
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

# Round 2: when the reply triggers another revision

**Agent Determinism Illusions (Part 17)**

> **Where this fits:** Part 16 collected four reader-driven revisions — Mike HHI pair-join, Tom Jones position-adjacency, Xiao Man shape-routing (rename_keys), Mike quiet-failure. Before Part 16 shipped, Xiao Man replied to the rename_keys section of the draft with a refinement: not "pick a better anchor," but "remove the anchor from the probe's responsibility." This part is the response — what the refinement predicts, what the experiments on this fixture support, and the methodological rule that falls out.

---

## 1. The refinement

Xiao Man's reply (2026-07-30) on the rename_keys cell:

> The probe should never re-find what the router already resolved. The mutation suite then becomes: "did we accidentally put lookup responsibility back into the probe?"

Two claims, separable:

- **Probe layer:** if the router passes the resolved path (e.g., "services is at `art['components']` after rename"), the probe stops doing key-name lookup and becomes rename-immune by construction.
- **System layer:** the anchor doesn't disappear; it relocates from probe to declaration/router. The new anchor layer has its own survival question.

Round 1 said: shape-routing is fragile under rename. Round 2 sharpens: the fix isn't a better anchor, it's a boundary redraw.

---

## 2. Path-passing probe — confirmed on fixture

Script: `probe-path-passing-redesign-test.py` → `results-v2/probe-path-passing-redesign.json`.

Two probe designs on the same rename_keys population (T3 good artifacts, `services → components` + inner renames, n=40, seed=7):

| Probe | Design | false_reject on rename_keys (n=40) |
|-------|--------|:---------------------------:|
| v1 (current) | hardcoded `art.get("services")` | **100%** (40/40) |
| v2 (refined) | path passed by declaration-aware router | **0%** (0/40) |

Probe-side fix works. The probe becomes a value-checker at a router-resolved coordinate, not a finder.

**Implementation leak worth naming.** First v2 draft only took the services path from the router; it still hardcoded the inner `timeout_ms` lookup — and rename_keys also changes `timeout_ms → request_timeout_ms`. v2 still rejected everything. The probe had to take **all** renamed keys as router-resolved paths before it became rename-immune. Exactly the failure mode Xiao Man named: "did we accidentally put lookup responsibility back into the probe?"

---

## 3. Declaration-anchor survival matrix

Script: `declaration-anchor-survival-test.py` → `results-v2/declaration-anchor-survival.json`.

Probe-side fix is one half. The other half: the new anchor layer (declaration/router) has its own survival envelope. Four anchors × eight perturbations; each cell is a single deterministic resolution check, not a stochastic trial:

| anchor | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | survived |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--------:|
| synonym_list | ✓ | ✓ | **✗** | ✓ | ✓ | ✓ | ✓ | ✓ | 7/8 |
| structural | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | ✓ | 7/8 |
| cardinality | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | **✗** | ✓ | 6/8 |
| cross_field | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | 7/8 |

Perturbations:
- P0 baseline; P1 services→components (in synonym list); P2 services→instances (out-of-decl); P3 add decoy field; P4 inner shape corrupt; P5 add third entry; P6 decoy-with-limits inserted before services (shape clone); P7 inner field rename (port→port_number).

**No anchor survives 8/8.** Each has a distinct failure signature:

- **synonym_list** dies on out-of-declaration rename (P2). Narrow but predictable.
- **structural** dies on shape clone (P6). Can't distinguish `services` from a decoy that mimics list-of-dicts-with-limits.
- **cardinality** dies on count change (P5) and shape clone (P6).
- **cross_field** dies on inner field rename (P7). Semantic-structural breaks under inner synonym rename.

The "wide" anchors (structural, cross_field) trade robustness on outer rename for fragility on shape clone and inner rename. **Narrow vs wide is a trade-off, not a monotone improvement.** Any "X is more robust than Y" claim must name the attack class.

---

## 4. Boundary-leak detector rule

Xiao Man's deeper reframe — mutation suite as architectural-violation detector, not bug-finder:

> rename_keys doesn't introduce a defect; it only swaps key names. If the system boundary is clean, rename should be a no-op. If rename triggers failure, someone put lookup where it doesn't belong.

Codified as a fixture-design rule (`working-notes/boundary-leak-detector-rule.md`):

> Any fixture with router/probe or judge/lookup layering must include a set of **neutral mutations** — rename, position-permute, cardinality-preserve. Neutral mutations introduce no defect by design. Failures under neutral mutation count as **boundary leaks**, reported independently of catch rate.

Neutral-mutation classes:

| Mutation | What it does | Failure implies |
|----------|--------------|-----------------|
| `rename_keys` | synonym rename | probe hardcoded key lookup |
| `position_permute` | swap siblings | probe did index-based lookup router didn't sanction |
| `cardinality_preserve_add` | add shape-identical sibling | anchor used cardinality over cross-field |
| `inner_field_rename` | rename inner field | anchor checked key-presence over semantic invariant |
| `decoy_with_same_shape` | insert shape-identical decoy | anchor only inspects shape |

**The rule is a label, not a framework.** Existing fixtures (rename_keys, decoy_nest, cue_erase, cross-model pair-join) already run neutral mutations — they just weren't called that. Future fixtures should declare their neutral-mutation inventory up front and report boundary-leak count as a primary metric, alongside catch rate.

What this rule does **not** do: replace catch rate. A fixture with zero boundary leaks can still have wrong catch rate. The two metrics are independent.

---

## 5. Closing

Round 1 said: depth-from-shape is fragile under rename. Round 2 sharpens:

- **Probe layer:** anchor can be removed. Path-passing redesign confirmed (n=40, seed=7); probe becomes rename-immune by construction.
- **System layer:** anchor doesn't vanish, it relocates. Declaration/router is the new anchor site, with its own measurable survival envelope.
- **Methodological consequence:** neutral mutations are boundary-leak detectors. Future fixtures should report leak count alongside catch rate.

Xiao Man named the architectural principle. The empirical work on this fixture supports it: probe becomes anchor-free; system stays anchor-bound at a different layer; the survival question moves with the anchor.

**Probe without anchor, system with anchor at a different layer. That's the relocation.**

---

**Series:** Agent Determinism Illusions · Scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**Previous:** [Part 16 — Reader-driven revisions: four comments that bit back](https://dev.to/zxpmail/reader-driven-revisions-four-comments-that-bit-back-30p8)  
**Comment thread origin:** [Part 6](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) · [Part 7](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513)
