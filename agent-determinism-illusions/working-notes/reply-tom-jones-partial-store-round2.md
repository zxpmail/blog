# Reply draft — Tom Jones (partial store round-2: required blind step + provenance)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Prior: `reply-tom-jones-partial-store.md`（P/F/T/S SUPPORT；Tom 已跑脚本 32/32）

Tom（本轮）:
- 首次实跑脚本；comment archive 剥 HTML 截断 URL 是 gap 在他们侧
- 收 coverage  framing；第三失败 落地
- **推**：`structural_gate(required=...)` 来自 informed caller — 同一文档 `required=["base"]` → PASS complete；reader 自报 required 可 cert 缺 ten answers 的板
- **fix**：required 从 store 枚举，不来自 reader
- **第四格**：alert drill — COUNT 诚实、VERDICT 上板；缺 run_kind（provenance）；ingest 丢弃自签 drill
- **归纳**：age / coverage / provenance 三个谓词，以前只印 age

## 策略
- _plain 认跑通_；感谢实跑
- **全收** required 盲区；**Intent 一等公民**仲裁 U（假绿）与 W（假红）
- **锁** U/W/I 格 + provenance 脚本 SUPPORT
- 四谓词并列：age / coverage / provenance / intent

---

## English (paste to DEV.to)

```text
Plain credit where it belongs: first time you executed rather than read the cell table, and the runnable links were there the whole time in body_html while your archive flattened them. Glad the replay closed the loop.

Taken on the push inside the gate. Cell S used an informed caller — `required=["base","oplog"]` because the fixture already knows both stores exist. That is the epistemic bar stamped on the experiment, not a claim about your reader. Same partial document, one argument changed:

| required source | required | same doc (P) | gate |
|---|---|---|---|
| informed caller | `["base","oplog"]` | answered_shown=0, looks_complete=True | REJECT unlabeled_partial |
| reader declares | `["base"]` | identical | PASS complete |

So the structural gate lands on the same footing as the temporal controls for the case we both hit: strictly better than age alone when the reader knows about the oplog, but it stops short of the reader who would declare `required=["base"]` in good faith because they never heard of the oplog. "I did not know it was there" has to become expressible. Printing `stores_touched` is what makes that reachable; deriving `required` from enumeration at the connection — object stores, schema tables, partitions — is the step after.

We added two cells to the same grammar (U/W) and a fourth document for your drill:

| cell | setup | result |
|---|---|---|
| U | reader-supplied `required=["base"]` on P | PASS as complete — blind step inside the gate |
| W | store-enumerated `required=["base","oplog"]` on same P | REJECT unlabeled_partial |
| I | frozen intent `ops_complete_board` on same P | REJECT incomplete_for_intent |
| I′ | frozen intent `archive_base_snapshot` on same P | PASS satisfies_intent (W would false-red here) |
| V | install-verification drill COUNT, no `run_kind`; reader → VERDICT | critical alert on board; live monitor OK under real limits |
| V′ | same drill with `run_kind=install_verification_drill` | ingest DROP from alert channel |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/stamp-partial-store-read-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/stamp-partial-store-read.json
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/stamp-provenance-drill-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/stamp-provenance-drill.json

Your pattern holds: a document has to publish what it **is** alongside when it was made. Age, coverage, provenance — three separate predicates. We had been printing one. The drill row is `stores_touched` rotated from "which stores did the read touch" to "what kind of run produced this row"; the fix is the same shape — label in the body, gate at ingest.

One step further, which your required push makes unavoidable: **Intent has to be a first-class citizen — the arbitration anchor for the gate.** Without it, the system forks two ways. Reader-supplied `required` lets the ignorant through (U: false green — ops board certified complete with zero answers). Store enumeration alone lets physical rules strangle legitimate work (W: false red — same base-only document rejected when the frozen task was `archive_base_snapshot`). Neither pole is acceptable; neither pole knows what the run was *for*.

We added cell I to the same grammar — intent frozen before the run, not authored by the reader after:

| intent (frozen) | same partial doc (P) | gate |
|---|---|---|
| `ops_complete_board` | requires base+oplog | REJECT incomplete_for_intent |
| `archive_base_snapshot` | requires base only | PASS satisfies_intent |

Store enumeration still prints what exists at the connection. Intent says what this run needed from it. Coverage checks `stores_touched`; provenance checks `run_kind`; age checks `generated`. Intent is what ties the other three to a verdict instead of letting any one of them pretend to be the whole gate.

Synthetic SUPPORT on both extensions. Production still owes store enumeration wired to the reader, ingest that drops self-labelled drills, and intent frozen from the task before the run — the cells name the predicates, not the deployment.
```

---

## 中文对照（不发）

```text
感谢实跑。全收 required 盲区。U reader 报 base → 假绿；W store 枚举 → 假红（archive 场景）。**Intent 运行前冻结**是仲裁锚：ops REJECT / archive PASS 同一 partial。第四谓词与 age/coverage/provenance 并列；Intent 把三者绑到 verdict，不让任一假装是整个门。
```

---

## 检查
- [ ] push 后链接可点
- [ ] 发英文
- [ ] 不把 SUPPORT 说成生产已焊
