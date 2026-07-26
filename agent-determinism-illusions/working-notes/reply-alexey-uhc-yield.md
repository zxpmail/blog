# Reply draft — Alexey Spinov on UHC vs class list (Part 6 thread)

Post under his comment on:
https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f

---

```text
You asked for the mirror. Fresh multi-perspective rerun (Strict/Balanced/Lenient × DF v2 × qwen3:0.5b / gemma3 / deepseek-v4-flash; 60 scenario-rows):

u = P(unanimous ∧ conf≥0.9 | RIGHT) = 19/47 ≈ 0.404
h = P(unanimous ∧ conf≥0.9 | MISS)  = 4/7  ≈ 0.571

(RIGHT = true_pass ∨ true_reject; MISS = dangerous_accept. Joint rates counted directly — no independence assumption.)

Yield on that traffic (fire% / precision / % of MISS):

divergence        42.6% /  8.7% /  28.6%
class list alone  79.6% / 16.3% / 100.0%
UHC alone         42.6% / 17.4% /  57.1%
UHC ∧ class       33.3% / 22.2% /  57.1%

Precision lift from adding UHC on top of class: 1.365×.
So on this cell your sign holds in part — UHC is not the main selector — but the lift is above your grid median (1.01×), inside your max (1.88×). The 0.958 in Part 6 is still only P(self-conf≥0.9|MISS) from the single-judge DF v2 dump; it is not h under real unanimity.
https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f

Two caveats that bound how far this settles anything:

1. All 7 MISSes are qwen. gemma and deepseek had 0 dangerous accepts this run. u is therefore a mixture: deepseek 0.90, gemma 0.00, qwen 0.14 on their RIGHT rows.
2. rm = P(class|MISS) = 1.0 on this fixture — every MISS sid is already DF*/DS*. Class-list 100% MISS capture is the oracle ceiling Part 7 already flagged, not an independent discovery. With ro also high (0.77), class barely thins the RIGHT population either, so your "class does ~97% of the volume cut" does not reproduce here (measured class-cut of UHC volume ≈ 22%).
https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513

What I think survives from your comment: the open question is ranking inside the stream under a budget, not a cleverer trigger definition; and wiring still beats detection. What doesn't: treating 0.958 as if it were u's twin under the same event. Plug u≈0.40 into your cell instead of 0.70 and the UHC-alone precision drops further — which is exactly why you asked for the number.

Scripts / dump:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/alexey-trigger-yield-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/alexey-trigger-yield.json
https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts/results-v2
(files: df-multiperspective-*-alexey-uhc.json)

stdlib, offline analyzer; three runs byte-identical on sha256(sorted summary)=5c0b7567c82d26c452b98b0d4a611cc772b1e90b53c94bb07472534af3c4977f
```
