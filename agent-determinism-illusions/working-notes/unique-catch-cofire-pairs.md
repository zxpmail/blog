# All-pairs induced co-fire (extension of Mike caveat)

## Question

Mike named route∧CD. Remaining hole: other forced pairs — especially barely∧route (direct middle attack). Does *any* of C(4,2)=6 reorder unique-CR?

## Protocol

```bash
python scripts/unique-catch-cofire-test.py --all-pairs --trials 400
```

Results: `scripts/results-v2/unique-catch-cofire-pairs.json`

Same injection: after i.i.d. medium fires, force named pair = 1 on ρ of defectives.

## Result (2026-07-27)

All 6 pairs × ρ∈{0..0.8}: **no middle swap, no rank change, extremes hold.**

Including the direct middle attack `route_changed ∧ barely_passed`.

## Still not production lock

Sim family only; real multi-signal latent classes / production co-occurrence still open.
