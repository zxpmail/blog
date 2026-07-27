# Co-occurrence-label dose-response

## Question

After mike_half (π=0.5) flipped middle by a hair: what is π* — the critical
mass of a single co-occurrence label that stably unlocks barely↔route?

## Protocol

```bash
python scripts/unique-catch-cooccur-dose-test.py --trials 400 --step 0.05
```

Results: `scripts/results-v2/unique-catch-cooccur-dose.json`

Attacks: `route_cd`, `barely_route`, `cd_barely`. Remainder = independent.
π* = first π where flip holds for this step and the next (anti-flicker).

## Result (2026-07-27)

| attack | π* (middle) | notes |
|--------|-------------|-------|
| **route_cd** (Mike) | **0.50** | Flip from π≥0.50 onward; at π=1.0 extremes also break (route overtakes CD) |
| barely_route | null | Never flips middle on the grid |
| cd_barely | null | Never flips middle; extremes always hold |

So only Mike's named class unlocks the middle, and the threshold is ~half the defectives carrying that co-occurrence label — matching `mike_half`. Ends are structural until extreme concentration (π_route_cd→1).
