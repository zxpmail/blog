# Defect-class concentration vs π* (Mike cheaper step)

## Question

Before rerunning the unique-catch fixture: how concentrated is available
defect taxonomy vs π*≈0.50 fragile middle band?

## Protocol

```bash
python scripts/defect-class-concentration-histogram.py
```

Results: `scripts/results-v2/defect-class-concentration-histogram.json`

## Result (2026-07-27)

| taxonomy | max share | vs π*=0.50 |
|----------|-----------|------------|
| scenario_id | DS4 **34.4%** | below fragile band |
| model\|scenario | 15.6% | below |
| model | qwen **80.2%** | different axis (not π_route_cd) |

## Reply / on-page

- `working-notes/reply-mike-defect-concentration.md`
- Part 6 Update `#defect-class-concentration-mike`
