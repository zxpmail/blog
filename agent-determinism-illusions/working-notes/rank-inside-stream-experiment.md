# Rank-inside-stream experiment

Design approved 2026-07-27 (option 3: oracle ceiling + LOO class-precision).

## Script

`scripts/rank-inside-stream-test.py` → `scripts/results-v2/rank-inside-stream.json`

Offline. Arms: `arrival` | `loo_class` | `oracle`. Budgets 1%/2%/5% of traffic.

## Headline results (2026-07-27 run)

### multiperspective (N=60, MISS=6)

- Floor-volume holds: at B=2% (k=1), oracle leaves most TP unseen on every stream with tp>k.
- `loo_class` never beats arrival (WEAK on this small fixture) — oracle still lifts D/class/D+T2.
- Under arrival at B=5%, high-precision small streams win hard: UHC∧class/T2 catch **3**, D+T2/class/D catch **0**. Stream choice still matters when you refuse to rank.
- Merged D∪S wiring: NULL (D@arrival already 0).

### df_proxy (N=585 all runs, MISS=94)

- Floor-volume holds hard: B=2% k=11 vs tp≈92–94 → oracle leaves ~81–83 TP unseen.
- **SUPPORT deployable-rank shape:** loo beats arrival in **6/18** cells (tie 7, worse 5). Biggest lifts on fat low-precision heads: D+T2 at 5% arrival 10 → loo 29 (=oracle); class 10 → 27.
- loo can *hurt* on UHC / UHC∧class when arrival’s prefix is already MISS-dense (−2).
- Merged D∪S wiring: NULL here because D@arrival catch=0 at these B (only 2 MISS in D, buried). Oracle merge never worse than D-alone (0 cells).

## What this does / doesn’t settle

- Settles: budget binds harder than trigger once tp > k; a non-oracle ranker *can* move catch on measured traffic; oracle is the ceiling Mike/Alexey implied.
- Does not settle: a production ranker (loo class is a toy proxy).
- Settled 2026-07-28 via `scripts/merge-displacement-grid-test.py`: Alexey’s 76/720 displacement shape returns STRUCTURAL NULL on df_proxy — D stream is miss-starved (qwen3 D=2/115, gemma3 D=0/147); 3 models × 8 budgets × 4 added streams = 96 cells, D@arrival=0 in every cell. Shape has nowhere to fire on this fixture; do not force a 76/N number.
