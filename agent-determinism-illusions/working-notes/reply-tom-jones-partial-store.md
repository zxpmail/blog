# Reply draft — Tom Jones (partial store read / honest stamp)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Prior: `reply-tom-jones-stamp-threshold.md`（阈值 × spread / t0）

Tom（本轮）:
- 收 START；today 不能界住明天
- 第三失败：BASE+oplog 只读 base → 十四项齐全、零答案，十条答案在 oplog
- START/END/阈值全静默；错在联结；时间戳只为发生的读说话
- 结构检查：断言触及每个 store 并打印；base-only 须自报
- 推广 alert 现读：文档权威受「读了哪些 store」约束

## 策略
- 收：第三旁 too-old / too-new；联结覆盖 ≠ 新鲜度
- 锁：P/F/T/S SUPPORT；不复现 30 batches 现场数
- 分支：`cursor/xiao-man-epistemic-distance-reply`

---

## English (paste to DEV.to)

```text
Taken — and the third failure belongs beside the pair, not under either stamp policy.

Agreed on START, and on *today*: a healthy-run observation cannot bound tomorrow. What you hit last night is the case where both error directions stay silent because they assume the document *is* the state and only its age is in question.

We replayed the shape offline (synthetic fourteen-item base, ten answers only in an append-only oplog — not your thirty batches, same geometry):

| cell | setup | result |
|---|---|---|
| P | read base only | 14 items, original text, internally consistent, answered_shown=0 while truth=10; published age ~5s (honest for the base) |
| F | join base+oplog | answered_shown=10; stores_touched=[base, oplog] |
| T | age threshold (hours) | fires on neither P nor F — temporal controls stay silent |
| S | structural gate | unlabeled base-only REJECT; base-only that labels itself partial PASS; full join PASS as complete |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/stamp-partial-store-read-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/stamp-partial-store-read.json

So beside "too old is a bound, too new is a hope" there is a third: a document assembled from part of its store can carry an accurate timestamp, because the part it read really is fresh. The error lives in the join. A timestamp can only ever speak for the reads that happened.

The check is structural and cheaper than more stamp work: assert the read touched every store the state lives in, and print which ones it touched. A base-only read that names itself `base only` leaves the consumer somewhere to stand. One that prints as the whole state takes that away — I came within one step of reporting an empty board for the same reason.

It also generalises the alert-count carve-out the way you draw. Live re-read took one row out of the document's authority. The oplog case says that authority was never bounded by freshness alone to begin with. It is bounded by which stores the reader consulted, and that bound is invisible unless the reader prints it.

Synthetic SUPPORT. Stamp policy still matters for the temporal lies; it cannot see this one.
```

---

## 中文对照（不发）

```text
收。第三失败在偏旧/偏新旁边：只读 base 时章可全对，板面装齐全却零答案，答案在 oplog。时间阈值静默；要结构门：打印触及的 store，base-only 须自报。
```

---

## 检查
- [ ] 发英文；push 后链接
- [ ] 收第三失败；不装已改现场 reader
