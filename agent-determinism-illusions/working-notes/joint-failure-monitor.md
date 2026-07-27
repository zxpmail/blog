# Joint-failure monitor (Mike causal-independence cut)

## Question

Can a rolling joint-failure excess alert detect common-cause spikes that
checksum (structural independence) cannot certify against upfront?

## Protocol

```bash
python scripts/joint-failure-monitor-test.py --trials 100
```

Results: `scripts/results-v2/joint-failure-monitor.json`

excess = rate(claim∧probe fail) − rate(claim)·rate(probe) over W=200;
alert if excess≥τ for K=3 windows.

## Result (2026-07-27)

| τ | indep FAR | cc detect | mean delay |
|---|-----------|-----------|------------|
| 0.03 | 0.02 | 0.99 | ~9 |
| 0.05 | 0.00 | 1.00 | ~15 |

Operating point: τ=0.03 (FAR≤0.05 ∧ detect≥0.90, min delay).

## Reply / on-page

- `working-notes/reply-mike-joint-failure-monitor.md`
- Part 7 Update after structural≠causal
