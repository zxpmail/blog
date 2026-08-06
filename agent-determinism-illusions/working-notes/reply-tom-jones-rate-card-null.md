# Reply draft — Tom Jones (rate-card: null ≡ no)

Thread: https://dev.to/zxpmail/round-2-when-the-reply-triggers-another-revision-5h8m  
Parent: Round 2 (Part 17) — Xiao Man's anchor relocation  
Tom (Aug 6): rate-card guard asserted "tool-capable" while capability was
literally unknown. Direct-served rung; probe looked up model id in a
*different* catalogue, got null, `null is False` failed → passed. First fix
was an alias ("better anchor" hat). Boundary redraw: serving config
DECLARES capability. Anchor relocates; stale declaration is checkable on a
schedule; failed lookup is indistinguishable from genuine absence — that
collapse was the damage.

Experiment: `rate-card-null-collapse-test.py`  
Result: `results-v2/rate-card-null-collapse.json`  
Offline sim, no API. All five claims PASS.

| guard | cap | verdict | shopping |
|-------|-----|---------|----------|
| boolean `is False` | null | PASS | yes |
| three-state | null | BLOCK | yes |
| alias lookup | True | PASS | yes |
| declare-then-assert | True | PASS | no |
| declare undeclared | null | BLOCK | no |

Stale schedule: declare True / provider False → caught.  
Omit-incapable catalogue: lookup-miss and genuine-no both return null → indistinguishable.

Tone: shorter than v1; lead with the table; drop the "type should have
refused" lecture; keep absence≠blindness as one clause, not a closer.

---

## English (paste to DEV.to)

```text
Taken — and the price-card land was exact enough to reproduce offline.

Same rung shape you described: direct-served, model id absent from the probe catalogue, truth = tool-capable. Four guards:

| guard | cap | verdict | shopping |
|---|---|---|---|
| boolean `is False` | null | PASS | yes |
| three-state | null | BLOCK | yes |
| alias lookup | True | PASS | yes |
| declare-then-assert | True | PASS | no |

Your damage is C1: null fails `is False`, so unknown certifies as capable. Alias is the Round 2 wrong half — it PASSes and still shops. Declaration is the redraw — PASS with shopping=False.

On the survival move you named: planted declare=True against provider=False; schedule check catches it. And under a catalogue that omits incapable rows, lookup-miss and genuine-no both return null — indistinguishable. So yes: the damage was not the failed lookup, it was that failing and "no" shared a cell. Three-state on the relocated declaration is the residue the survival matrix did not name — same pressure as absence ≠ blindness.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/rate-card-null-collapse-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/rate-card-null-collapse.json
```

---

## 中文备忘（不贴帖）

- 语气：Taken 起笔；表格先行；去掉类型系统说教；absence≠blindness 收成一句
- 实验五条全 PASS：C1 boolean null→PASS；C2 三值 BLOCK；C3 alias 仍 shopping；C4 declare 不 shopping；C5 陈旧可捕 + omit 目录下 miss≡no
- 挂脚本 + JSON
