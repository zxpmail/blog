# Reply draft — Xiao Man (epistemic distance + frozen baseline)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513
Prior: `reply-xiao-man-external-reference.md`（5×5 表 + 三选项 provenance；结尾问 baseline 归谁）

Xiao Man (≈ 2026-08-04 / 05, ~9h after prior):
- P8 + 5×5 表：传感能命名 "something is wrong"，不能拥有 "this is the wrong thing"；
  QUIET/FIRE × check/cross — cross 决定谁有裁决权。
- 三选项按 **epistemic distance** 排，不是按算力成本；成本是合法搬迁上的人审延迟。
  P9 = 用 escalation 接住原会落在 P2 的 FP，不是消除 FP。
- "总有闸门"是设计参数：参照离生产者多远（0 hop / 1 hop / unbounded），
  失效模式随距离缩放。
- 信道内门 → false confidence（分不开 P2/P8）；信道外门 → false negative /
  保守升级（分得开，但 P9 也升级——正确行为）。不对称使 tripwire 诚实。
- 开放题收束：baseline 须是 named frozen artifact，不能是 live tree；
  P9 的 FIRE(advisory) 不是 FIRE(FP) 是设计提示——参照可以慢，不能活。

## 策略
- 他贴重复了 → 回帖压短，只锁三刀，不重述整段论证。
- 锁：距离排序 / 静默 vs 保守 / baseline = frozen（可慢不可活）。
- 首推「命名 vs 拥有」也要被收到——失败段点名它是 false-confidence 的根（信道内门拥有传感只命名的东西）。
- 无新实验、不挂链接、不重贴表。

---

## English (paste to DEV.to)

```text
Locked — and yes on all three pushes.

Epistemic distance, not compute cost: same-author = 0 hops, different-author = 1, no-reference = unbounded. What you trade away moving right is answering; what you buy is failing open. The bill is human latency on legit relocations — P9 is that price, not a leftover FP.

Failure class — and it's your naming-vs-owning in motion: in-channel verdicts own what the sensor only named, so they fail by false confidence (cannot tell P2 from P8); out-of-channel owns nothing and only routes, so it fails conservative (escalates P9 too — correct, not defect). Silent bias vs honest over-routing.

Baseline must be a named frozen artifact, not the live tree — or FP/FN collapses back into whatever the working tree currently says. P9's FIRE(advisory) was the hint: the reference may be slow; it cannot be live. Refreshing the freeze is a human act, not a pull from the working tree.
```

---

## 中文对照（不发，供自阅）

```text
锁死——三刀都收。

认知距离不是算力成本：同作者 0 hop，异作者 1 hop，无参照无界。往右走放弃的是给答案，换来的是失败开放。账单是合法搬迁上的人审延迟——P9 是那笔价，不是漏掉的 FP。

失效类别——这就是你「命名 vs 拥有」的展开：信道内门拥有传感只命名的东西，所以败在虚假确信（分不开 P2/P8）；信道外门不拥有任何东西、只路由，所以败在保守（P9 也升级——正确，不是缺陷）。静默偏差 vs 诚实多看。

baseline 必须是具名冻结产物，不能是 live tree——否则 FP/FN 塌回工作树当下的状态。P9 的 FIRE(advisory) 就是提示：参照可以慢，不能活。刷新冻结是人动，不是从工作树 pull。
```

---

## 检查
- [ ] 正文发英文；不发中文对照
- [ ] 无新实验 / 不挂新脚本链接（沿用上一帖已挂的即可，本帖可不重复）
- [ ] 不引 Part 13 / Part 17
- [ ] 收束上一帖开放题（frozen named artifact）；锁定 refresh = 人类动作
- [ ] 不重贴整张 5×5
