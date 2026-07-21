# Reply draft — Mike on inverted trigger (recurrence vs novelty)

Post: Part 6 thread and/or Part 13 when live.  
Evidence: Part 13 §5 Update; `external-signal-ablation.json`

---

## English (paste)

Agreed — two arms, not one fix.

T1/T2 (known-reversal / unanimous-high-conf on historically reversal-prone classes) are the **recurrence** arm: cheap, history-built, necessary. They don't catch the first occurrence of a new systematic bias, for exactly the reason you name — nothing has been burned by it yet.

You hoped `classifier_disagree` alone might be the novelty arm (independent second read, no shared priors). We already ran that ablation on the sampling fixture: CD alone catch **24.9%**, below Part 6's cross-prompt **28.4%**. Best single external signal; still not the novelty catcher by itself. So that arm isn't "drop CD into the tripwire."

The unnamed population is **confidently-wrong-and-never-caught-before**. Closing it needs a source that doesn't share the judge's priors — out-of-channel / probe territory , not another prompt in the same text channel

---

## 中文备忘

- 落 Part 13，不落 Part 6 主叙事（Part 6 可一句指针）
- 复发臂 = T1/T2；新奇臂 ≠ CD 单独（消融已否）
- 新奇人口命名：confidently-wrong-and-never-caught-before
