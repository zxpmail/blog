# Ranker acceptance stress sweep

`scripts/ranker-acceptance-stress-sweep.py` → `results-v2/ranker-acceptance-stress-sweep.json`

Three axes on top of the G0–G7 ship gate:
1. **Features** — R_hist / R_hist_conf / R_conf_asc / R_conf_desc / R_reversal / R_uhc
2. **Dilution** — queue miss-rate 15%→95% + natural D+T2
3. **Holdout** — stratified / within_model_temporal / global_temporal

G7 added: if oracle>0 then candidate>0 (blocks 0=0 SHIP).

## Stratified (same family as the SHIP certificate)

| cand | 15–80% | 95% | natural |
|------|--------|-----|---------|
| R_hist, R_hist_conf | SHIP all | SHIP | INC (G6) |
| R_conf_asc | SHIP | FAIL (G2) | INC |
| R_conf_desc | FAIL | SHIP | INC |
| R_reversal | FAIL until 80% | SHIP | INC |
| R_uhc | FAIL all diluted | — | INC |

**R_hist does not drop across the dilution sweep on stratified.** Fragility shows up on time-like holdout instead.

## within_model_temporal (per-model first 70% → train)

- miss_test=27 (G0 ok); global_temporal still miss_test=1 → INC.
- **R_hist @ 15–65%: NO_SHIP** (mostly G2 — conf_desc beats hist on that cut; at sparse 15% also G7 after fix).
- R_hist recovers SHIP only at dense queues 80–95%.
- R_conf_desc / R_uhc look strong on this cut — different feature wins under time shift.

## Reading

1. Dilution alone doesn't kill R_hist on stratified — the 35% SHIP wasn't a knife-edge.
2. **Time-like holdout does** — train-window class table stops beating conf_desc under within-model temporal for mid dilutions.
3. Feature swap matters: hist wins stratified adversarial dilution; conf_desc/uhc win temporal. No single feature ships everywhere.
4. global_temporal still can't certify (G0) on this dump.
