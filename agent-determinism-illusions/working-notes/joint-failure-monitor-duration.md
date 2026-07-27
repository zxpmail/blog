# Joint-failure monitor vs outage lifespan

## Question

Is detection delay (≈9 / ≈15) short enough vs outage lifespan? Where does
the monitor fail because too slow, not wrong?

## Protocol

```bash
python scripts/joint-failure-monitor-duration-test.py --trials 100
```

Results: `scripts/results-v2/joint-failure-monitor-duration.json`

## Result (2026-07-27)

| τ | L*_live≥90% | L*_any≥90% | at L≈parent delay |
|---|-------------|------------|-------------------|
| 0.03 | 15 | 9 | L=9 → live 25% / late 65% |
| 0.05 | 20 | 15 | L=15 → live 37% / late 62% |

## Reply / on-page

- `working-notes/reply-mike-joint-failure-duration.md`
- Part 7 Update under `#joint-failure-monitor-duration-mike`
