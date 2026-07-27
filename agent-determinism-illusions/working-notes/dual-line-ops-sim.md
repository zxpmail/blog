# Dual-line ops simulation

`scripts/dual-line-ops-sim.py` → `results-v2/dual-line-ops-sim.json`

## Claims

1. **Trigger∥Rank** — under hard `k`, which knob moves catch more?
2. **Shadow∥Enforce** — shadow ranker vs arrival enforce; fail-closed fallback if shadow catches 0 while oracle > 0.

## Results (2026-07-27)

### Stratified + diluted 35%

| B | diluted arrival | R_hist | best trigger@arrival | rank_knob_wins |
|---|-----------------|--------|----------------------|----------------|
| 2% | 0 | 3 | class:3 | True (tie on lift) |
| 5% | 0 | 8 | class:8 | True (tie on lift) |

Shadow: hist lift +3/+8, safe mode = shadow. **SUPPORT dual-publish.**

### within_model_temporal (stale hist)

| B | diluted arrival | R_hist | best trigger@arrival | rank_knob_wins |
|---|-----------------|--------|----------------------|----------------|
| 2% | 0 | 0 | T2:3 | False |
| 5% | 0 | 0 | T2:8 | False |

Shadow hist vacuous → **fallback_arrival**; safe ≥ enforce. conf_desc shadow would have lifted (3/8) — feature choice still matters. **SUPPORT fallback-only.**

## Reading

- Calibrated hist: Rank line recovers the same catch as picking a pure high-precision trigger under arrival — dual-line is coherent.
- Stale hist: Trigger line (pick T2) beats Rank-with-R_hist; Shadow must not promote hist to Enforce without fallback.
- Production dual-line is experimentally motivated: separate knobs, shadow before enforce, fail closed on vacuous shadow.
