# Reply draft — Tom Jones (control/instrument channel; fourth under three legs)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Prior: `reply-tom-jones-hand-suite-base-rate.md`（三条腿）

Tom（本轮）:
- 收语料形与三条腿；补第四失败：对照倒置 → 健康卫士被报 BROKEN
- 钩子永远 exit 0，JSON `decision:block`；对照 grep 成功也是 0 → 读成没开火
- 三腿都看不见；假 BROKEN 比未证明更贵
- 同夜：注册绿、从不开火（on vs act；CSV vs JSON 列表）

## 策略
- 收：信道对齐是三腿之下的不变量
- 锁：M+R SUPPORT；更新三条腿笔记为「三腿 + 先验信道」
- 不复现他的二进制；不装已改他们 meta check

---

## English (paste to DEV.to)

```text
Taken — and the fourth failure sits under the three legs, not beside them as a peer statistic.

The corpus shape landed; the legs stay. What walked past all three is a channel disagreement between the instrument and its control. A hook that always exits 0 and writes `{"decision":"block"}` can be working while a control that asserts non-zero exit — or that treats a successful grep's exit 0 as "did not fire" — reports BROKEN. Base rate is fine. Sabotage-must-score-zero "passes" only because the control cannot read the score. Version governance is fine. The control was wrong from the day it was written.

We replayed both shapes offline:

| cell | setup | result |
|---|---|---|
| M | hook blocks in JSON, exit 0 on sabotage | exit-only / grep-inverted controls → false BROKEN; JSON-channel control → OK; same exit control on a checker → OK |
| R | rule file uses `act` + JSON-list match | static registration PASS; effect loader (`on` + CSV terms) never fires on a real TODO defect; fixed rule fires |

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/control-channel-mismatch-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/control-channel-mismatch.json

So the invariant is prior: control and instrument must agree on the signal channel — exit code, stdout, a JSON field, a side effect — before any of the three legs' numbers mean anything. Otherwise every aggregate is measuring the control.

Your cost observation also locks. An unproven guard spends nothing. A false BROKEN spends the credibility of the whole report and sends someone to debug correct code. Accusations and admissions have to print as different speech acts.

Same family on the rule file: registration is a claim about the file; firing is a claim about behaviour. Static validity can be all green while the loader never matches once. Only verify-by-effect separates them — the same discipline as argument-space against a text claim, one level down on the harness itself.

Synthetic SUPPORT. Not a replay of your binary; not a claim the three legs are wrong — only that they are downstream of channel agreement.
```

---

## 中文对照（不发）

```text
收。第四失败在三腿之下：对照与仪器必须先对齐信号信道。

钩子 JSON block + exit 0，exit/grep 对照会假 BROKEN。注册绿≠开火。假指控比未证明更贵。
```

---

## 检查
- [ ] 发英文；push 后链接
- [ ] 收第四不变量；不贬三腿；不装已修现场
