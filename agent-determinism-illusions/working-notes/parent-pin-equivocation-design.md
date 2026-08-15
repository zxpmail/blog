# Design — parent-pin equivocation (Peter transparency-log half)

Date: 2026-08-16  
Thread: Part 10 DEV.to — follow-up after sealed-minimum rollback reply  
Script: `scripts/parent-pin-equivocation-test.py`

## Epistemic bar (load-bearing)

SUPPORT means: under a constructed dual-view authority model, **local sealed floor + local inclusion** and **persisted prior STH + consistency** are different predicates; and the consistency prescription catches named forks **when** its assumptions hold, while named assumption breaks (rewritable prior; private priors / no cross-check) re-open dual-green.

Does **not** claim: field prevalence, real CT, HMAC security, exhaustive adversary coverage, or witness/quorum.

## Cells A–C (predicate split)

| Cell | Policy | Expect |
|------|--------|--------|
| A | Per-view sealed floor + inclusion | Both jobs locally green; fork invisible |
| B | A + consistency to unwritable honest prior | A ok; shrink fork FAIL |
| C | Honest append | inclusion + consistency PASS |

## Cells D–F (attack-family / assumption boundary)

| Cell | Attack | Expect |
|------|--------|--------|
| D | Same-size root-swap (size=2, different root) vs honest unwritable prior | consistency REJECT (`equivocating_fork`) |
| E | Rewrite persisted-prior slot to fork-compatible STH | consistency PASS + false green |
| F | Per-job private priors; no cross-view compare | both pipeline-green; global roots differ |

## Mechanics

- Leaves: approval `{version, digest}`; honest `[v1,v2]`; shrink `[v1]`; same-size `[v1, v2-alt]`.
- Merkle: RFC6962-style; STH HMAC-signed.
- Output: `scripts/results-v2/parent-pin-equivocation.json`
