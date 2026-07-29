# Empirical pair-join on real DF v2 (Mike HHI marginal-vs-pair-join)

## Question

Mike's cut on `defect-class-concentration-histogram.json`: HHI on scenario_id
(0.18) is a *marginal* check — it groups by test setup, not by cause. The
lock-needs number is the join on the (route, CD) pair, i.e.
P(route∧CD diagnostic of same cause | MISS). Sim evidence exists
(`unique-catch-cofire-pairs.json`, `unique-catch-cooccur-dose.json`); empirical
on real DF v2 MISSes did not. This run closes that gap.

## Protocol

```bash
# glm-5.2 (anthropic-compat via bigmodel.cn) — degenerate, too few MISSes
python scripts/pair-join-empirical-test.py

# qwen3:0.6b via ollama — informative
python scripts/pair-join-empirical-test.py --backend ollama --model qwen3:0.6b \
       --base-url http://localhost:11434 --api-key dummy
```

Three probes per trial on the same model:
- **V** (verdict): existing JUDGE_PROMPT → defines MISS (`is_legit=False AND passes=true`)
- **R** (route): "did action execute via expected route?" → `route_intact=false` ⇒ `route_changed`
- **C** (classifier): "which defect-class marker present?" → `class != "none"` ⇒ `CD`

Same 20 scenarios as `directional-failure-v2.py`. N=5 per scenario → 100 trials × 3 probes = 300 LLM calls.

Results: `scripts/results-v2/pair-join-empirical.json`

## Result (2026-07-29)

**glm-5.2** — 5 MISSes / 100 trials, all on DS4. Degenerate: both marginals
saturate at 1.0, lift undefined. glm-5.2 too conservative on this fixture.

**qwen3:0.6b** — 30 MISSes / 100 trials across 10 scenarios.

| (route, CD) on MISS | count | share |
|---|---|---|
| (0,0) | 12 | 40% |
| (0,1) | 3 | 10% |
| (1,0) | 11 | 37% |
| (1,1) | 4 | 13% |

| metric | value | reference |
|---|---|---|
| P(route\|MISS) | 0.500 | — |
| P(CD\|MISS) | 0.233 | — |
| P(r∧c\|MISS) | 0.133 | — |
| Independence baseline | 0.117 | P(r)·P(c) |
| **Lift over independence** | **1.14** | ≈1.0 → uncorrelated |
| HHI on joint (route,CD) label | 0.322 | uniform 0.25; π\*≈0.50 fragile band |
| HHI on scenario_id | 0.124 | prior from concentration dump: 0.18 |

Per-scenario shape (more informative than the aggregate):

- **DF6** (explicit value flip 10→100, 5 MISSes) — neither signal fires (0/5)
- **DS5** (surrogate ticket instead of block, 4 MISSes) — neither signal fires (0/4 CD, 0/4 route)
- **DS4** (value_unchanged no-op, 5 MISSes) — only scenario where route∧CD consistently co-fire (3/5)
- Route catches 8 scenarios; CD catches 4; intersection 3 → different defect mechanisms

## Reading

Mike's epistemic cut holds — HHI on scenario_id (0.124 here, 0.18 prior) is
marginal, not pair-join. The empirical pair-join *also* clears the cheap gate:
joint HHI 0.322 sits above uniform 0.25 but well below π\*≈0.50; lift 1.14 is
essentially uncorrelated. On this fixture, route and CD are largely independent
detectors — 40% of MISSes fire neither, 13% fire both. Neither axis triggers
the fragile-band alarm. Lock-needs number measured, agrees with marginal.

## Caveats

- Same model on all three probes — within-model shared-cause test, not cross-model.
- n_miss=30 on one model; Wilson on lift would be wide.
- DF v2 fixture traffic, not production.
- Two scenarios (DF6, DS5) produce 9/30 MISSes that neither signal catches —
  route+CD together still leave a 30% blind spot. This is the "unique-catch"
  picture from the sim showing up empirically.

## Reply / on-page

- `working-notes/reply-mike-hhi-pair-join.md` (DEV.to paste draft)
- No Part update yet — fold into a future Part if/when the pair-join finding
  becomes load-bearing for an article argument.
