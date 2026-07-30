# Reply draft — Xiao Man (anchor relocation: remove from probe)

Thread: Divergence escalates the wrong population (Part 7)
Xiao Man's 2026-07-30 reply to my Round-1 rename_keys reply.
Round-1 reply: `reply-xiao-man-inferability-first.md`

## Xiao Man's two claims

1. Probe should never re-find what router already resolved. If router
   passes the resolved path, probe becomes rename-immune by construction.
2. Mutation suite becomes "did we accidentally put lookup responsibility
   back into the probe?" — architectural-violation detector, not bug-finder.

Both verified empirically. Wrote three artifacts:

- `probe-path-passing-redesign-test.py`: probe v1 (hardcoded art.get("services")) → false_reject 100% on rename_keys; probe v2 (path passed by declaration-aware router) → false_reject 0%.
- `declaration-anchor-survival-test.py`: 4 anchors × 8 perturbations survival matrix. No anchor 8/8 — synonym_list dies P2, structural dies P6 (shape clone), cardinality dies P5/P6, cross_field dies P7 (inner rename).
- `working-notes/boundary-leak-detector-rule.md`: codified neutral-mutation rule for future fixtures.

## Implementation leak I caught while at it

First v2 draft only took services path from router; inner `timeout_ms` was
still hardcoded. rename_keys also changes timeout_ms → request_timeout_ms,
so v2 still rejected everything. Had to path-pass ALL renamed keys. This
is exactly your "did we put lookup responsibility back into the probe" —
the audit caught it the moment I looked at the false_reject number.

## Landing

Round 2 written up as Part 17 (en/zh, published:false pending Part 16):
- blog-agent-determinism-illusions-17.{en,zh}.md
- Title: "Round 2: when the reply triggers another revision"

Reply paste below uses GitHub links (Part 17 not on dev.to yet).

---

## English (paste to DEV.to)

```text
Both principles verified empirically.

1. Probe never re-finds what router resolved — verified. Wrote a path-passing variant: probe v1 (hardcoded art.get("services")) false_rejects 100% on rename_keys; probe v2 (router resolves path, passes it to probe) false_rejects 0%. The probe becomes a value-checker at a known coordinate, not a finder.

Implementation leak worth flagging — first v2 draft only took the services path from the router; inner timeout_ms was still hardcoded. rename_keys also changes timeout_ms → request_timeout_ms, so v2 still rejected everything. Had to path-pass all renamed keys before the probe was actually rename-immune. Exactly the audit case you named: "did we accidentally put lookup responsibility back into the probe?"

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/probe-path-passing-redesign-test.py

2. Mutation suite as boundary-leak detector — agreed, and the relocation point lands too. The anchor doesn't disappear; it moves to declaration/router. Ran a survival matrix for 4 anchor strategies × 8 perturbations:

| anchor | survived | dies on |
|---|---|---|
| synonym_list | 7/8 | out-of-decl rename |
| structural | 7/8 | shape clone (decoy-with-limits before services) |
| cardinality | 6/8 | count change + shape clone |
| cross_field | 7/8 | inner field rename (port→port_number) |

No anchor 8/8. Narrow vs wide is a trade-off, not monotone improvement — the "wide" anchors trade robustness on rename for fragility on shape clone and inner rename.

Codified the neutral-mutation rule: any router/probe-layered fixture must declare its neutral-mutation inventory up front and report boundary-leak count alongside catch rate. Existing fixtures (rename_keys, decoy_nest, cue_erase, cross-model pair-join) already run neutral mutations — they just weren't called that. The label is the contribution, not a new framework.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/declaration-anchor-survival-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/working-notes/boundary-leak-detector-rule.md

Round 2 written up as Part 17 (pending Part 16 publish):
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-17.en.md
```

---

## 中文备忘（不发）

- Xiao Man 两条原则都验过：探针 rename-immune、mutation 当架构检测器
- 探针 v1 false_reject 100% → v2 0%
- v2 实现漏：第一版只 path-pass services，内层 timeout_ms 仍硬编码——被抓
- 声明锚生存矩阵：4 锚 × 8 扰动，无锚 8/8
  - synonym_list 7/8 死 P2
  - structural 7/8 死 P6（形状克隆）
  - cardinality 6/8 死 P5+P6
  - cross_field 7/8 死 P7（内层 rename）
- boundary-leak 规则落 working-notes
- Part 17 en/zh 写完，published:false，跟 Part 16 一起发
- 挂 4 个 GitHub 链接：path-passing 脚本、survival 脚本、规则 note、Part 17 en
