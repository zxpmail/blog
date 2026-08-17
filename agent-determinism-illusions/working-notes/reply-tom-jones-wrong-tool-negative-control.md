# Reply draft — Tom Jones (wrong-tool residual + negative control)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Article: Part 10 — argument-space  
Prior Tom (Part 9 stamp thread): separate; this is the Part 10 production note.

Tom:
- Tool wall: schema/types/enums/required → schema-valid before second model; no synonym walks through
- Residual: well-formed call to the **wrong tool** with plausible args — evasion gone; confident correctness about the wrong thing remains
- Assert extractor: nested asserts after return → valid Python, exit 0, wall PASS; 5/8 false passes; accept-wrong only, never reject-right; unpatched control box
- Pass rate cannot surface it; negative control (sabotage must score zero before real numbers) would have caught sooner

## 策略
- 收：残余换形 + 方向性 + 负对照优于通过率
- 锁：实验同形状 SUPPORT；N 不写成复现他们的 5/8
- 收紧：evasion is gone 过满；负对照非银弹
- 挂脚本；分支链接
- 不提铁律包；不装 Part 18 已发

---

## English (paste to DEV.to)

```text
Taken — and reading it against Parts 8–9 is the right frame. The argument-space move only earns its keep against the channel gap and directional failure.

Your production cut matches the floor I want kept, with the limit stated the way it should be stated. A tool wall that returns at schema-valid (types, enums, required) before any second model is consulted does raise the floor: synonyms do not walk through. What still walks through is a well-formed call to the wrong tool with plausible arguments. Evasion of that lexical kind is gone; confident correctness about the wrong thing remains, and it looks like success from every angle the checker can see. That residual has a different shape from the one L2 left — not softer, just relocated.

We replayed the shape offline (not your N, same geometry):

| check | result |
|---|---|
| synonym tool name | schema REJECT |
| wrong tool, schema-valid args | schema PASS |
| assert-after-return wall (8 sabotage shapes) | 7/8 false accept, 0 false reject on right shapes |
| fixed extract (asserts before return) | 0 false accept on sabotage |
| mixed suite pass rate under broken wall | 100% while sabotage reliability ~12% |
| negative control (sabotage must score 0) | broken fails; fixed passes |

So: C3 / schema genuinely raises the floor. The leftover is not “imprecise judging” — it is directional success on the wrong referent (wrong tool, dead assert, same family as Part 9’s accept-wrong).

The generalisable piece is the one I want locked hardest. A verifier that errs only toward accepting produces aggregates indistinguishable from a verifier that works, and its pass rate can improve as its reliability drops. What would have caught your extractor sooner is exactly what you name: a negative control — deliberately sabotaged output that must score zero before any real number gets printed. Same discipline as a known-wrong canary or mutation poison on the claimed side effect: more diverse failing samples shrink how long a mis-aimed check survives. They do not prove the check correct, and they do not make “evasion gone” a universal claim — only this channel’s lexical walk-through.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/wrong-tool-negative-control-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/wrong-tool-negative-control.json

Holding one production box unpatched as control while the other ran the fix is the right empirics. I’ll keep your instance as the directional-failure handoff it is: the pass rate was never going to confess.
```

---

## 中文对照（不发）

```text
收下。对着 Part 8–9 读是对的。

生产切分：schema 墙抬地板，同义词穿不过；残余是形式正确的错工具——逃逸换形，不是消失。实验同形状：错工具 PASS；return 后断言 7/8 假绿、0 误杀正确；通过率 100% 掩盖可靠度 ~12%；负对照挡住坏墙。

锁：只朝 accept 偏的验证器，通过率不能自首；负对照/canary/变异先打零。不把 evasion gone 说成全称；N 不写成复现你们的 5/8。
```

---

## 检查
- [ ] 发英文；分支链接
- [ ] 收残余换形 + 负对照；收紧 evasion gone
- [ ] 不写复现 5/8；不提铁律包
