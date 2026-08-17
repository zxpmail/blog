# Reply draft — Tom Jones (composite stamp + simple t0 cure)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Prior: `reply-tom-jones-stale-snapshot.md`

## 策略
- 收 mtime / live alert count
- 锁：复合章藏 spread；computed-at 属观察
- 补：最小修复 = generated 盖在 run 开始 t0（偏旧不偏新）；挂第二实验
- 不装已修好；不提铁律包

---

## English (paste to DEV.to)

```text
Pinned — and the split is cleaner than the fork I offered. Body `generated`, not render, not mtime: mtime is a property of the file, the stamp is a property of the measurement. Copy/checkout/rsync would have let a stale snapshot assert freshness; that is exactly the lie the banner is for. Live re-read of the alert count is the other half I was missing — that blocks the boot-fresh / drain-stale face of the fourth collapse.

What lands is the ownership cut. A stamp taken after every check has finished is still wall-clock standing in for a time the early checks actually observed. Your 71.7s timing is the small dose: nothing in the file names the spread. A ten-minute hang inherits the same fresh stamp. Offline:

| config | published spread | true max age at write |
|---|---:|---:|
| document stamp only | 0 | 60s span hidden |
| per-check stamps | 60s | 60s visible |
| 600s hang + end stamp | 0 | 671.7s; inherited ages all 0 |

So: computed-at belongs to the individual observation; a document stamp is at best the max of its parts, not a substitute. A composite stamp cannot report its own spread. The field case I asked about — fresh timestamp over a drain last run at boot — is the same defect with the gap grown from 72 seconds to hours.

Per-check stamps are the clean fix. If that is too heavy, the minimal safe flip is cheaper: set `generated` at run start `t0`, never at write time. Error direction becomes too old, not too new. Same hang, second run:

| stamp policy | published age | true oldest |
|---|---:|---:|
| END (write time) | 0s | 671.7s |
| START (t0) | 671.7s | 671.7s |

Normal 71.7s wall: END publishes 0s; START publishes 71.7s. Still no named spread — but the banner stops lying fresh, which is the lie it exists to prevent. Small dose survived the first fix because end-of-run stamping kept the error pointed the wrong way.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/composite-stamp-spread-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/composite-stamp-spread.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/start-stamp-vs-end-stamp-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/start-stamp-vs-end-stamp.json
```

---

## 中文对照（不发）

```text
钉住了。body generated，不是 render/mtime；alert 现读补上漏的半边。

承重的是归属：跑完才盖的章仍藏 spread；挂起继承新鲜章。锁：时间属于单次观察。

完整修是逐条盖章。嫌重则最小安全翻转：章盖在 t0 不盖写完——偏旧不偏新。挂起时 END 显示 0、真最旧 671.7；START 两边都是 671.7。横幅不再装新。
```

---

## 检查
- [ ] 发英文（4 链接需 push 后才稳）
- [ ] 收 Tom；锁 ownership；钉 t0 为最小修复
- [ ] 不提铁律包；不装已上线修好
