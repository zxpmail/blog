# Reply draft — Ethan Walker (blocking vs advisory)

Post: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f

---

## English (paste)

Agreed — and that's the wiring Experiment F left implicit.

L0/L1 are stable across runs, so they can be required checks (exit code blocks merge). L2 on the residual carries run-to-run variance; put it on the blocking path and you don't get a stricter gate — you get a flaky one that teams delete by retrying until green.

Same soft/hard split as elsewhere in the series (soft signal vs hard tool gate). Wrote it into Part 6 §1 as an Update: L0/L1 required, L2 advisory (PR comment), L3 human on splits. Pipeline already separates the layers; the change is the CI semantics, not another Experiment F cell.

---

## 中文备忘

- 落 Part 6 §1，不落 Part 7
- 运维主张，非新实验格
- 与 soft/hard、advisory vs load-bearing 同构
