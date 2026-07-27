# Induced co-fire unique-catch (Mike drop-order caveat)

## Question

3×3 mix sweep held unique-CR rank identical under *independent* fires. Mike: that leaves independence untested. Force `route_changed` ∧ `classifier_disagree` co-fire from one injected defect class; does `barely_passed` vs `route_changed` reorder?

## Protocol

- Script: `scripts/unique-catch-cofire-test.py`
- Results: `scripts/results-v2/unique-catch-cofire.json`
- Same unique-catch definition as mix sweep / ablation
- Fixture: burst / medium / 10% floor / Alex(0.10 + 0.30·s)
- Injection: after i.i.d. SIGNAL_MEDIUM draws, with prob ρ set route=CD=1 on defectives only
- ρ ∈ {0.0, 0.2, 0.4, 0.6, 0.8}, 400 trials/cell

## Result (2026-07-27)

| ρ | joint(route∧CD) | unique rank | middle swapped |
|---|-----------------|-------------|----------------|
| 0.0 | 0.126 | CD > barely > route > input | — |
| 0.2 | 0.298 | same | no |
| 0.4 | 0.476 | same | no |
| 0.6 | 0.648 | same | no |
| 0.8 | 0.824 | same | no |

Unique *mass* collapses (CD unique 5.8%→1.2%; route 1.9%→0.4%) — expected under shared fires. Order holds.

## Interpretation

Stronger than nine-cell lock on the independence caveat Mike named. Still not production lock (one forced pair, one sim family).

## Reply

`working-notes/reply-mike-cofire.md`
