# Reply draft — Tom Jones (partial store round-2 修正后续: 撤 Intent, 三谓词)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Prior: `reply-tom-jones-partial-store.md`（P/F/T/S SUPPORT；Tom 已跑脚本 32/32）  
Round-2 已贴 2026-08-19（U/W/I + provenance，commit 780e15b，链接已验 200）。**本稿是对已贴 round-2 的修正后续。**

## 背景与走查
- 已贴版把 Intent 升为**第四谓词 + 仲裁锚**（ops_complete REJECT / archive_base PASS 同一 partial；W 对 archive 假红）
- 复盘：Intent 仲裁锚是 synthetic 撑不住的一等公民主张（frozen-intent 目录是夹具，不是生产接线）→ **撤回**
- 修订后：**全收 Tom 的 required 盲区**——required 由 reader 自报是门内盲步，fix = 从 store 枚举
- 三条谓词并列：age / coverage / provenance
- 脚本已改：`stamp-partial-store-read-test.py` 删 I 格、留 U/W；JSON 同步；清单行 7 同步

## 策略
- 公开撤回已贴版 Intent 段（承认 overclaim），不辩解
- 全收 required 盲区：cell S 的 informed caller 是 fixture epistemic bar，不是 production claim
- 锁 U/W 格 + provenance 脚本 SUPPORT
- 三条谓词并列写进回复；SUPPORT 仅命名谓词，不说生产已焊

---

## English (paste to DEV.to — 修正后续)

```text
One correction to my reply above: I put Intent up as a fourth predicate and called it the arbitration anchor for the gate. That was me reaching past what the cells show. Your `required` push is the right shape — reader-supplied `required` is a blind step *inside* the gate, and the fix is deriving `required` from the store at the connection, not from the reader's claim. So the predicates are three: age, coverage, provenance.

Same partial document, one argument changed:

| required source | required | same doc (P) | gate |
|---|---|---|---|
| informed caller | `["base","oplog"]` | answered_shown=0, looks_complete=True | REJECT unlabeled_partial |
| reader declares | `["base"]` | identical | PASS complete |

So the structural gate is strictly better than age alone when the reader knows about the oplog, and it stops short of the reader who would declare `required=["base"]` in good faith because they never heard of the oplog. "I did not know it was there" has to become expressible. Printing `stores_touched` is what makes that reachable; deriving `required` from enumeration at the connection — object stores, schema tables, partitions — is the step after.

Updated cells to match the walk-back (I row is gone):

| cell | setup | result |
|---|---|---|
| U | reader-supplied `required=["base"]` on P | PASS as complete — blind step inside the gate |
| W | store-enumerated `required=["base","oplog"]` on same P | REJECT unlabeled_partial |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/stamp-partial-store-read-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/stamp-partial-store-read.json

Your pattern still holds: a document has to publish what it **is** alongside when it was made — age, coverage, provenance, three separate predicates, and we had been printing one. The drill row is `stores_touched` rotated from "which stores did the read touch" to "what kind of run produced this row"; the fix is the same shape — label in the body, gate at ingest.

Synthetic SUPPORT on both extensions. Production still owes store enumeration wired to the reader and ingest that drops self-labelled drills — the cells name the predicates, not the deployment.
```

---

## 中文对照（不发）

```text
修正已贴版一处：我把 Intent 升成第四谓词、称它是门控仲裁锚——这是 synthetic 撑不住的一等公民主张，撤回。全收你的 required 盲区：required 由 reader 自报是门内盲步，fix 是从连接处枚举 store，不来自 reader。U 同一文档 reader 报 base → PASS；W store 枚举 → REJECT。谓词三个：age / coverage / provenance。drill 行 = stores_touched 旋到 run_kind，同形状。SUPPORT 只命名谓词，不说生产已焊。
```

---

## 检查
- [x] push 后链接可点
- [x] 发英文（修正后续，DEV.to 线程回，2026-08-20 已贴）
- [x] 不把 SUPPORT 说成生产已焊
- [x] notes 同步 + 记忆改三谓词
