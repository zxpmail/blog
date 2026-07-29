# Reply draft — Tom Jones (frozen declaration relocates failure)

Thread: https://dev.to/nexuslabzen/is-your-agents-done-real-a-15-minute-self-check-before-you-trust-it-36cc  
Parent: pre-declaration must itself be out of the agent's reach  
Tom (Jul 30): freeze is right; wrong declaration relocates failure into
agent-failure costume; 421 lines lost to cleanup; two guards (salvage patch +
name as spec defect); after freeze the small artifact is the only unverified
point — cheap to review, expensive to get wrong.

Experiment: `frozen-declaration-fault-attribution-test.py`  
Result: `results-v2/frozen-declaration-fault-attribution.json`  
Offline sim, n=40/cell, worker_lines=421, seed=7. All claims hold.

| policy × cause | misattribution | mean work lost |
|----------------|----------------|----------------|
| naive / spec   | 100%           | 421            |
| tom_guards / spec | 0%          | 0 (salvage 421)|
| both policies / agent | 0% (correct agent_failed) | 0 (empty art) |
| freeze rewrite | rejected; gate still blocks on original missing test |

---

## English (paste to DEV.to)

```text
Taken straight — and the failure-distribution cut is the load-bearing add.

Reproduced the shape offline (n=40, worker lines=421): freeze + mechanical gate blocks both agent-empty and missing-declared-test. Mechanism real on both. Under naive attribution every spec-missing-test block is labeled agent_failed (100% misattribution) and cleanup destroys the tree with zero salvage — mean work lost = 421. Same cells under your two guards: attributed spec_defect, salvage recovers 421/421, work lost 0. Agent-empty stays agent_failed. Freeze also rejects an agent rewrite of the verify path; the gate still compares against the original missing file.

So yes: freeze relocates the failure rather than removing it. The costume is an attribution bug plus a cleanup bug, not a gate bug. Your guards attack both surfaces. And the last line lands: after freeze, review attention has to move onto that small frozen artifact, because nothing downstream can catch a mistake inside it — the sim's gate is correct on every count and still cannot save a wrong declaration.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/frozen-declaration-fault-attribution-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/frozen-declaration-fault-attribution.json
```

---

## 中文备忘（不贴帖）

- 冻结闸门两边都拦得对；错的是归因 + 清理
- naive：规格错 100% 扮成 agent 失败，丢 421 行
- tom_guards：标成 spec_defect，救回 421 行
- 冻结后小工件是链上唯一未核验点——与 Tom 收束一致
