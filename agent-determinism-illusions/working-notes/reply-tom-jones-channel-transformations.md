# Reply draft — Tom Jones (channel transformations: false QUIET + downstream observer)

Thread: https://dev.to/zxpmail/the-third-predicate-argument-space-verification-tested-3gfh  
Prior: `reply-tom-jones-control-channel.md`（M/R 格；信道对齐是第四不变量）  
Tom（top-level 评论，2026-08-21，三个现场收据）：

1. **DRILL marker（走对的一次）**：monitor 在非默认阈值运行时正文必须说 DRILL，强制验证 run 被 ingest 拒绝。**跳过了 fixture**——跑真实 monitor 在真实机器上、拿它实际发出的字符串过 live filter → REJECT；拿 12 天前真实 unmarked critical 过同一 filter → ACCEPT。为什么 skip fixture：fixture 和 filter 共享一个作者和一个格式假设，两者会不管 monitor 发什么都互相同意——对照的信道是「我写的字符串」，仪器的信道是「monitor 写的字符串」，只有后者在生产里存在。
2. **2>/dev/null（同一天走错两次）**：`python3 script.py 2>/dev/null` 让输出可读——失败、无输出、把空输出读成空结果。**这就是 M 格倒置**：仪器写 stderr、观察者读 stdout，真错误被记成静默。假 BROKEN 送人去 debug 正确的代码；假 QUIET 不送任何人去任何地方——更贵的那一头，也更难注意到。可读性 filter 是吃掉错误的东西；让它持久的时机：**你恰好在一个 run 吵的时候过滤它的输出——那恰是它在失败的时候。**
3. **git identity guard（今早，同一个形状进了 guard）**：commit hook 本要拒绝带 auto-derived git identity 的提交（47/116 commits 被静默记到从未写过它们的真人头上）。条件：没有配置 email **且**环境不提供任何 email → block。但 git 总是把 `GIT_AUTHOR_EMAIL` export 进 hook 环境、填上它刚猜的值——第二半永远不真，conjunction 永远不真，guard 在任何情况下都开不了火。复现原条件：打印 `identity guard PASS` 点名它存在就是为了拒绝的那个地址，然后提交了。**仪器在读一个被测工具几秒前刚写的变量。** 在 hook 里「调用方提供了这个身份」和「git 猜的」没有可观察差别——等你去看，两个字节一模一样。修法：不读环境，让 git 禁用猜测解析身份——恰在身份本会被派生时失败。

## 策略
- 全收扩展：信道对齐不止 exit/stdout/JSON 字段——覆盖**哪个流**、仪器与观察者之间为人的方便加的每一层变换、以及观察者**在被测下游**读它自写的信道
- 锁两新格（扩 `control-channel-mismatch-test.py`）：Q（false QUIET，M 倒置，stderr/stdout 静默）+ D（下游观察者读被测自写 env）
- 接成本排序：未证明 < 假 BROKEN < 假 QUIET——后者花掉仪器存在的全部理由，且是三者里唯一跑得越久越有说服力的
- 点 DRILL marker = run_kind 自签的孪生（盲区清单行 7b：正文自签、ingest 丢弃）
- SUPPORT 只命名形状，不说生产已焊

---

## English (paste to DEV.to — top-level reply)

```text
Taken, and the extension is the sharper version of the invariant I locked. My M cell caught the loud face: the control reads the wrong channel and accuses a healthy instrument (false BROKEN). Your `2>/dev/null` is the same disagreement inverted — instrument writes stderr, observer reads stdout, a real error scores as silence. That is false QUIET, and your cost ordering is the honest one: an unproven guard spends nothing, a false BROKEN spends credibility, a false QUIET spends the entire reason the instrument exists — and it is the only one of the three that grows more convincing the longer it runs. A false BROKEN sends someone to debug correct code; a false QUIET sends nobody anywhere.

The DRILL marker is the other side of the same coin, and the fixture-skip is the load-bearing part. You ran the real monitor on the real box and put its actual string through the live filter, because a fixture and the filter would have shared an author and a formatting assumption — the control's channel would have been "a string I wrote" while the instrument's channel is "a string the monitor writes," and only the second exists in production. That is exactly the run_kind discipline from the stamp line: the body labels itself (DRILL) so ingest refuses to file it as a production critical. The label in the body, the gate at ingest.

The git identity guard is the deeper class, and I had no cell for it. The instrument read `GIT_AUTHOR_EMAIL` — a variable the tool under test had itself written moments earlier, populated with its guess. Inside a hook there is no observable difference between "the caller supplied this identity" and "git guessed it"; by the time you can look, the two are byte-identical. Reading more carefully cannot fix that — the channel is the subject's own output. The fix is to change what you ask, not what you read: resolve the identity with guessing disabled, which fails exactly when the identity would have been derived. Not "read the env" but "ask git whether it can supply this without deriving it."

I extended the M fixture with both shapes:

| cell | setup | result |
|---|---|---|
| Q | instrument writes real error to stderr; observer reads stdout only | QUIET on sabotage (false quiet); stderr-aware observer FAIL; clean run OK |
| D | guard reads env var the subject itself exported (git always exports its guess) | never fires — PASS on the exact address it exists to reject; resolve-with-guessing-disabled → REJECT exactly when it would derive; truly-supplied → PASS |

So the check beside yours: before trusting a control, enumerate every transformation between the thing under test and the assertion — a redirect, a pipe, a `2>/dev/null`, a log level, an inherited environment variable — and ask which of them can turn a signal into an absence, or hand you the subject's own output as if it were independent. For your three cases the answers were a redirect, a pipe, and an inherited environment; mine were a stream split and an exported env var.

https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/control-channel-mismatch-test.py
https://github.com/zxpmail/blog/blob/cursor/xiao-man-epistemic-distance-reply/agent-determinism-illusions/scripts/results-v2/control-channel-mismatch.json

Synthetic SUPPORT on all four cells (M/R/Q/D). Your field receipts are the stronger evidence; the synthetic shapes only name the grammar. Production still owes the audit: which streams, redirects, and inherited variables sit between each instrument and its observer — the ones that read as formatting rather than instrumentation.
```

---

## 中文对照（不发）

```text
收。M 格锁的是大声那一面（对照读错信道→假 BROKEN）；你的 2>/dev/null 是同一分歧倒过来——仪器写 stderr、观察者读 stdout，真错误被记成静默。这是假 QUIET，成本排序是你对：未证明 < 假 BROKEN < 假 QUIET，后者花掉仪器存在的全部理由，且是唯一跑得越久越有说服力的。

DRILL marker 是同一硬币的另一面，skip fixture 是承重的那部分——fixture 和 filter 共享作者和格式假设，对照信道变成「我写的字符串」而非「monitor 写的字符串」。这正是 run_kind 自签：正文自签、ingest 丢弃。

git identity guard 是更深的类别：仪器读被测自己几秒前写的变量。hook 里「调用方提供」和「git 猜的」字节一致。修法不是更仔细地读，是改问法——禁用猜测解析，恰在会派生时失败。Q/D 两格 SUPPORT 只命名语法；现场收据才是强证据。
```

---

## 检查
- [x] 脚本/JSON 已 push 到分支（git cat-file OK）；链接待网络恢复后 curl 验 200（github.com 08-21 间歇断连）
- [ ] 发英文（top-level 回复，同 thread，2026-08-21）
- [x] 收扩展 + 接成本排序；不把 SUPPORT 说成生产已焊
- [x] notes 同步（回复 + 盲区清单行 7b 挂 DRILL 孪生 + CONTEXT）
