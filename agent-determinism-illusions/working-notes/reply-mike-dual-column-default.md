# Reply draft — Mike Czerwinski (carry both columns by default)

Thread: https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f  
Prior: `reply-mike-shadow-promote.md`（ρ=0.8 trap + promotion ladder）

Mike (~9h):
- ρ=0.8: any-alert 98% / live-catch 62% — not rounding; one column fine, the
  other says the protected capability collapsed
- Forensic-only dashboard would ship green
- Promotion ladder only works if you already suspected divergence enough to
  build the live-catch column
- Stronger rule: carry both by default even when they usually agree

## 策略
- 不重述整段晋升阶梯；锁「默认双列」
- 挂轻实验表（读既有 JSON）；Part 7 Update 已写入 en/zh
- 收他原句力度：第二列必须事先存在

---

## English (paste to DEV.to)

```text
Yes — and the stronger rule is the one I had left as an implication.

ρ=0.8 is not a rounding gap. Any-alert at 98% while live-catch is at 62% is one column saying the monitor worked and the other saying interrupt capability already collapsed. I ran that contrast as a dashboard policy on the same dump (no re-sim):

| ρ | live | any | forensic-only (any≥90%) | dual (live promote_ok) |
|---|---:|---:|---|---|
| 1.0 | 99% | 100% | SHIP | SHIP |
| 0.8 | 62% | 98% | SHIP | HOLD |

They usually agree. The one row they do not is exactly the case a single aggregate is built to hide. So the ops rule is yours, stated as instrumentation rather than only as a promotion caveat: carry both numbers by default — before anyone has been burned — because the second column cannot be invented after the diverge shows up on a board that never had it.

Wrote it into the Part 7 monitor arc as an Update next to the duration table.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/dual-column-dashboard-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/dual-column-dashboard.json
```

---

## 中文对照（不发）

```text
对——更强的那句才是我上回只写成暗示的东西。

ρ=0.8 不是舍入。any 98%、live 62%：一列说监视器还行，一列说中断能力已塌。同一落盘上做了仪表盘策略对照（不重跑）：ρ=1 两列都 SHIP；ρ=0.8 单列假绿、双列 HOLD。通常一致；不一致的那一行，正是单聚合结构上要藏的。所以运维规则按你的说成仪表，而不只是晋升附带条件：默认常驻两个数——在被烫到之前——因为第二列不能等裂口出现在一块从没挂过它的板上再发明。

已写入 Part 7 监视弧、紧挨 duration 表的 Update。
```

---

## 检查
- [ ] 发英文；挂 dual-column 两链接（需已在可访问分支/main）
- [ ] Part 7 en/zh Update 已落
- [ ] 不重贴整段 soft-couple 晋升表（点 Part 7 / 前回即可）
