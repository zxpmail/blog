# Reply draft — Xiao Man (death-cell / synonym_list / logging lock)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  
Prior outbound: `reply-xiao-man-fallback-logging.md`  
Inbound: Xiao Man locks failure-mode / synonym_list placement / logging-as-design

Experiment (new): `declaration-anchor-fallback-logging-test.py`  
Result: `results-v2/declaration-anchor-fallback-logging.json`  
Verdict: Part A + Part B both PASS (seed=7, n=400/mix)

Finding (corrects earlier draft that said "retires the primary"):
- Disagree cells = {P2, P6} only
- rename_heavy → modal P2 → retirement pressure on **primary** (decl review covers)
- shape_clone_heavy → modal P6 → retirement pressure on **secondary** (telemetry noise; do not promote)
- Same logging design; which side feels pressure is a traffic question — never a vote

Status: short paste below. Ready to post.

---

## English (paste to DEV.to)

```text
Yes — failure mode over rate, primary as placement not ranking. Ran the logging claim.

Primary synonym_list + secondary structural, no vote. Disagreement only on P2 (primary dies) and P6 (secondary dies). Under rename-heavy traffic (n=400), disagreements cluster on P2 → pressure on the primary (declaration review already covers that cell). Under shape-clone-heavy traffic, they cluster on P6 → pressure on the secondary (primary never dies there; do not promote secondary to co-gate).

So logging is design, not compromise: the modal disagree cell says which side is under pressure. It does not reopen a committee at commit time.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/declaration-anchor-fallback-logging-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/declaration-anchor-fallback-logging.json
```

---

## 中文（对照）

```text
对——看失败模式，不看通过率；主锚是安置，不是排名。把 logging 这句跑了一遍。

主锚 synonym_list + 次锚 structural，不投票。分歧只在 P2（主死）和 P6（次死）。rename-heavy 流量（n=400）分歧堆在 P2 → 压力在主锚（声明审查已盖住）。shape-clone-heavy 堆在 P6 → 压力在次锚（主锚从不死那格；次锚别升成共门）。

所以日志是设计，不是妥协：众数分歧格告诉你哪一侧吃紧。不在提交门重开委员会。

（挂脚本 + JSON）
```

## 备忘

- 旧短稿「retires the primary」过窄；数据是「压力落在错的那一侧」
- Part A/B 均 PASS；无需再跑除非对方换夹具
