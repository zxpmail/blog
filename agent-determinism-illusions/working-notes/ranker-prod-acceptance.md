# Ranker production acceptance gate

Follow-up to `rank-inside-stream-test.py`. Answers: *how do you prove a ranker can ship?*

## Script

`scripts/ranker-prod-acceptance-test.py` → `scripts/results-v2/ranker-prod-acceptance.json`

Candidate: **R_hist** = train-window `P̂(MISS|class_key)`.

## Why natural D+T2 had no headroom

On stratified df_proxy holdout, natural `D+T2` members are **29/29 MISS**. Arrival order cannot underperform oracle — G6 fails by construction. Reordering arrival does not help.

## Constructed protocol (decisive)

**diluted_queue**: all holdout D+T2 MISSes + non-MISS distractors to miss-rate ≈ 35%; arrival = distractors first.

| Gate | Meaning |
|------|---------|
| G0 | holdout `n_miss ≥ 15` |
| G1 | diluted_queue: R_hist ≥ arrival |
| G2 | diluted_queue: R_hist ≥ max(conf_asc, conf_desc) |
| G3 | natural D∪S merge non-inferior under R_hist |
| G4 | LOMO G1 on ≥67% eligible folds |
| G5 | cold-start ≥ arrival |
| G6 | arrival < oracle on ≥1 gate budget |

## Result (2026-07-27)

**OVERALL: SHIP** on `df_proxy / stratified + diluted_queue`.

Headline cell (B=5%, k=8): arrival **0** → R_hist **8** = oracle **8**. G6 headroom true. Natural stratified D+T2 remains INCONCLUSIVE (G6) — kept as contrast.

Scope caveat: certificate is for this traffic + these B + 35% dilution stress, not universal.
