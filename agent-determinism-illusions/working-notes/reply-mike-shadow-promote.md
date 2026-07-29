# Reply draft — Mike Czerwinski (shadow-promote ladder / one knob two masters)

Source: Part 6 DEV.to thread, follow-up to posted `reply-mike-joint-failure-forensic.md`
Mike's two cuts (2026-07-29):

1. "Don't make one knob serve two masters" generalizes past the series —
   same shape as Trigger∥Rank and Shadow∥Enforce; recurring bug is one
   scalar answering two operational questions.
2. Shadow-validation caveat must be operationalized before live-catch
   numbers count as interrupt capability. Honest sequence:
   pick τ from live-catch column in sim → shadow-only against real
   outages for a validation window → promote to interrupt only once
   shadow live-catch on real data matches sim. Sim→Interrupt skips
   coupled-uniform at the moment it matters; Part 15 temporal holdout
   showed that parent doesn't survive.

Evidence (soft-couple stand-in for production parent mismatch):
- `scripts/joint-failure-shadow-promote-test.py`
- `scripts/results-v2/joint-failure-shadow-promote.json`
- Interrupt candidate τ=0.05 L=20: ρ=1 live 99% → promote YES;
  ρ=0.8 live 62% (any still 98%) → promote NO. First refuse at ρ=0.8.
- Forensic contrast τ=0.03 L=20: first refuse at ρ=0.6 (more resilient,
  still not a free interrupt warrant).

Pending: Part 7 Update next to duration section.

---

## English (paste to DEV.to)

```text
That's the sentence. Trigger∥Rank, Shadow∥Enforce, Forensic-τ∥Interrupt-τ — same architecture, different domain. One scalar asked two operational questions is the recurring bug, not any particular threshold.

And yes on the promotion ladder — so I operationalized the caveat instead of citing Part 15 as a hand-wave. Soft-couple stand-in for "production parent ≠ coupled-uniform": during the outage window, force both-fail with probability ρ (ρ=1 recovers the sim parent). Calibrate on ρ=1, shadow-eval the same (τ, L), promote_ok only if predicted_live − realized ≤ 0.10.

Interrupt candidate from the duration grid (τ=0.05, L=20):
- ρ=1.0: live 99% / any 100% → promote YES
- ρ=0.8: live 62% / any 98% → promote NO (gap 0.37)
- ρ=0.6: live 25% / any 56% → promote NO
- ρ=0.4: live 5%  → promote NO

First refuse at ρ=0.8. Note the trap: at ρ=0.8 any-alert is still 98% — the forensic column would say "monitor worked"; the live-catch column says interrupt capability already collapsed. Sim→Interrupt would have shipped a 99% live claim into a world that delivers 62%.

Forensic contrast (τ=0.03, L=20) is more resilient (first refuse at ρ=0.6) — residue after the fact can stay useful longer — but that is not a warrant to promote it to interrupt either.

So the load-bearing ops rule is yours: pick τ from live-catch in sim → shadow-only under the real parent → promote only once shadow matches. Skipping the middle step trusts coupled-uniform at the moment it matters most.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/joint-failure-shadow-promote-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/joint-failure-shadow-promote.json
```

---

## 中文备忘（不发）

- 该做实验：soft-couple ρ 打 coupled-uniform，不靠 Part 15 旁证
- Interrupt τ=0.05 L=20：ρ=1 live 99% → YES；ρ=0.8 live 62% / any 98% → NO
- 陷阱：any-alert 在 ρ=0.8 仍 98%，live 已塌 —— 两列各伺候一个主子
- Forensic τ=0.03 更耐（ρ=0.6 才拒），仍不是 interrupt 通行证
- SUPPORT Mike 晋升阶梯；挂脚本 + JSON
- 下一刀：Part 7 Update
