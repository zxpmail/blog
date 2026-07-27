# Simulated co-occurrence labels (unique-catch)

## Question

Can we replace "need production co-occurrence labels" with a generative stand-in:
each defective draws a **label** (latent defect class) → signature set of signals
co-fire at `p_sig=0.90` → measure unique-CR rank?

## Protocol

```bash
python scripts/unique-catch-cooccur-labels-test.py --trials 400
```

Results: `scripts/results-v2/unique-catch-cooccur-labels.json`

Mixtures: independent, mike_half, balanced_pairs, middle_attack, starve_barely,
cd_hub, triple_heavy, chaos.

## Result (2026-07-27)

| mixture | unique rank | middle flip? | extremes |
|---------|-------------|--------------|----------|
| independent | CD > barely > route > input | — | hold |
| mike_half | CD > **route > barely** > input | **YES** (0.0166 vs 0.0164 @ N=2000) | hold |
| balanced_pairs | baseline | no | hold |
| middle_attack | baseline | no | hold |
| starve_barely | baseline | no | hold |
| cd_hub | baseline | no | hold |
| triple_heavy | baseline | no | hold |
| chaos | baseline | no | hold |

## Interpretation

- Simulating co-occurrence labels **can** move the middle: Mike's named class
  at 50% mass (`mike_half`) is enough (tiny but stable delta).
- Extremes (CD top / input bottom) held across all invented π.
- So: middle prune is **not** locked under label→signature structure;
  extremes still look structural on this fixture family.
- Still not production: π/signatures invented, not fit to a real trace.

## vs prior arms

- Pair-force only (`--all-pairs`): never flipped.
- Label mixtures: mike_half flipped → the generative *structure* (mass on a
  shared class) matters more than forcing one pair after i.i.d. draws.
