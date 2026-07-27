# Reply draft — Mike Czerwinski (outage lifespan vs detection delay)

Source: Part 6 DEV.to thread (joint-failure monitor follow-up)
Prior: `reply-mike-joint-failure-monitor.md`
Evidence: `scripts/results-v2/joint-failure-monitor-duration.json`
Command: `python scripts/joint-failure-monitor-duration-test.py --trials 100`

Mike's cut: τ=0.03→0.05 improves FAR and detection together; real cost is delay (9→15). Dial is accuracy-vs-latency. Ask: is delay short enough vs outage lifespan? Sweep L shorter than delay.

---

## English (paste to DEV.to)

```text
Agreed — and naming the axis matters. On this sim the common-cause spike sits clear of the independent floor, so raising τ can improve FAR and detection together; the bill shows up as latency (≈9 → ≈15). Accuracy-versus-latency, not accuracy-versus-noise.

Ran the lifespan sweep you asked for (`joint-failure-monitor-duration-test.py`): same W=200 / K=3 monitor; single outage of length L; classify live_catch (alert while outage still on) vs late_only (alert only after it ended — residue still in the window) vs miss.

τ=0.03 (parent delay ≈9):
- L=9: live 25%, late 65%, miss 6% — most "catches" fire after the outage is already gone
- live ≥90% only once L≥15; any-alert (incl. late) ≥90% by L≥9

τ=0.05 (parent delay ≈15):
- L=15: live 37%, late 62%, miss 1%
- live ≥90% only once L≥20; any-alert ≥90% by L≥15

So yes: when outage lifespan sits at or under the detection delay, the monitor often stays silent *during* the failure and only rings on window residue afterward — useful for forensics, not for interrupting a live sensor outage. The usefulness floor is L ≳ delay (a bit above mean delay for reliable live catch), not "any L that eventually moves excess."

On-page Update on Part 7 next to the monitor section:
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-7.en.md#joint-failure-monitor-duration-mike
Dump: https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/joint-failure-monitor-duration.json
Script: https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/joint-failure-monitor-duration-test.py
```

---

## 中文备忘（不发）

- 旋钮是准确 vs 延迟，不是准确 vs 噪声
- L≈delay 时多为 late_only（停电已结束，窗里还有残渣）
- live≥90%：τ=0.03 要 L≥15；τ=0.05 要 L≥20
- 对活故障：L 得 ≳ delay；否则监视器太慢而非算错
