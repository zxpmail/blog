# Reply draft — Tom Jones (operation check / quarantine)

Thread: https://dev.to/nexuslabzen/is-your-agents-done-real-a-15-minute-self-check-before-you-trust-it-36cc  
Prior (ours): existence check as field twin of the duck; gap named — covers
present-tense claims, not wrong-intent declarations / wrong-behaviour witnesses.  
Tom (≈ Jul 31): residue case worse — patch script existed, named right, exit 0,
never ran insertion path (docstring triple-quote; always took already-applied
branch). Guard = **operation check**: plant pre-fix, assert fire, restore;
quarantine before trusting new checkers (caught 2). Composes with existence
(dispatch/stat) vs quarantine (review). One-line-of-why is cheapest skipped item.

No new experiment this round — field case is load-bearing; compose, don't re-sim.

---

## English (paste to DEV.to)

```text
Taken — and the patch-script case is nastier than the residue I named. The file exists, the name is right, the run exits zero, and the insertion path still never executed. So both cheap faces of "done" are green while the operation itself is a ghost: every run took the already-applied branch. Existence and exit-0 are present-tense claims about the instrument. Neither asks whether the instrument has ever observed the pre-condition it claims to police.

Your operation check closes that. Plant the pre-fix state, assert the checker fires, restore. If you cannot force a fail on demand, a pass is uninformative — same shape as a suite that has only ever been green. Quarantine-before-trust is the right slot for it: review-time cost, not a dispatch-time stat, so it composes with the existence gate instead of replacing it. Dispatch asks "is the claimed artifact there?"; quarantine asks "has this checker ever failed for the right reason?"

That leaves the correspondence gap you point back to — declaration ↔ intended behaviour. The one-line-of-why is the cheapest human-readable handle on that correspondence, which is exactly why skipping it is expensive: without it the review really does degrade into a glance at a filename. Writing this out is making me add it on our side too.

So the chain as I now have it: existence at dispatch (stat) → operation quarantine at review (must-fail-on-demand) → human correspondence check (why + intent). The first two are mechanical. The third is still a sentence — and the one we keep omitting.
```

---

## 中文备忘（不贴帖）

- 接住病例：存在 + exit 0 仍可从未走过插入路径（ghost operation）
- 同意：operation check = 种预缺陷 → 必须响 → 恢复；检疫在 review，存在检查在 dispatch
- 残余仍是 declaration↔intent 对应；one-line-of-why 最便宜却最常被跳
- 收束三层链，不新开实验、不挂 Part 编号
- 与冻结声明篇可互指但不强挂链接（本帖在 nexuslabzen，不在系列主帖）
