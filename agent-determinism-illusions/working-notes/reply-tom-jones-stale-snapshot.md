# Reply draft — Tom Jones (stale snapshot / watermark bootstrap)

Thread: https://dev.to/zxpmail/wengs-harness-ladder-has-a-blind-step-26f1  
Prior: `reply-tom-jones-instrumentation-rung.md` (asked: who is the alarm channel to?)

Tom's field answer (Aug 13, dated incident Aug 3):
- Third collapse is real, on an alerting path not a verifier.
- Alerts append-only; session reads the file at startup and never again.
- 3 Aug: message 18:49 unseen for 30 min. Boot surface printed
  `alerts: OK, 0 new or unresolved since last boot` — generated 17:04,
  read 19:27. Four alerts in the gap. True when written, false when read,
  wording carried no age. Green stayed green, no component broken.
- Three failures stacked, each invisible alone: no push channel; status
  line with no age; watcher alive that never fired.
- Bug inside the fix: drain watermark. Cold start returned `now` as
  watermark without persisting it; every call recomputed cutoff; alerts
  between tool calls always older than the window. Never reported, no
  error, no log. Bootstrap value returned not written = healthy while
  dropping everything.
- Failure was never a human ignoring a queue. Sample schedule could not
  contain the event + snapshot asserting freshness it could not check.
- Two properties for the rung: status line carries computed-at; drain
  declares what it dropped instead of silently capping.
- Earlier pure form: producer wrote a queue no code path read. Now they
  name the consumer line before trusting the channel.

Map:
- Third collapse = the prediction from the instrumentation reply, now dated.
- 17:04/19:27 = DPI on the status line (Theorem 2 one layer up).
- Watermark bootstrap = empty-denominator inside the drain; reproduced offline.
- Two properties accepted; C3 shows dropped must be over the file not the window.
- Spine: the system must not truncate on a time it did not observe.
- Next collapse: `now` stamped at render, dual of `now` as cutoff.
- Do not mention the iron-law package (internal; Tom did not propose it).

Experiment: `watermark-bootstrap-collapse-test.py`  
Result: `results-v2/watermark-bootstrap-collapse.json`  
Offline sim, no API. All three claims PASS.

| config | persist | alert | reported | drop_win | drop_file | silent_healthy |
|--------|---------|-------|----------|----------|-----------|----------------|
| C1 unpersisted now | N | between | 0 | 0 | 1 | Y |
| C2 persisted now | Y | between | 1 | 0 | 0 | N |
| C3 persist-now pre-boot | Y | pre-boot | 0 | 0 | 1 | Y |

C1 = incident. C2 isolates persist. C3 = naive persist-now still silent on the window count.

---

## English (paste to DEV.to)

```text
Taken — dated, and on the alarm path, which is the version I only had as a prediction. Assertion held, alarm fired, sampled once per session, green stayed green, nothing broken. Not a human ignoring a queue. A schedule that could not contain the event, plus a snapshot asserting freshness it had no field for.

The 17:04 line read at 19:27 is the DPI face. True when written, false when read, wording carried no age — so a text-channel reader had nothing to detect. Same bound as Theorem 2, one layer up: a status line that does not carry computed-at is Channel A reading a Channel B that has already aged out. The four alerts in the gap were not hidden. They were unreadable from a snapshot that had no age.

The watermark bootstrap reproduced offline. Three configs, only persist and alert-timing varied:

| config | persist | alert | reported | drop_win | drop_file | silent_healthy |
|---|---|---|---|---|---|---|
| C1 unpersisted now | N | between | 0 | 0 | 1 | Y |
| C2 persisted now | Y | between | 1 | 0 | 0 | N |
| C3 persist-now pre-boot | Y | pre-boot | 0 | 0 | 1 | Y |

C1 is your incident: returning `now` without writing it means every call recomputes the cutoff, so anything between calls is always older than the window. Drain reports healthy, drops everything, no error. C2 isolates persist as load-bearing — same drain, same `now` bootstrap, write the value, between-call alert surfaces. C3 is the residue the naive fix leaves: persist-now still silently caps anything already in the file, and `dropped: 0` is honest about the watermarked window. Declaration has to be over the append-only file.

The load-bearing cut across both faces is the same: the system must not make a truncation decision about a time it did not observe. `now` as cutoff, a status line with no computed-at, and dropped counted over the already-capped window are three forms of that decision. Both properties belong on the rung because they refuse it. Status line carries computed-at, or freshness is an assertion with no witness. Drain declares what it dropped, counted over the file — C3 is why the window count is not enough. Naming the consumer before trusting the producer is the dual of the question I asked; the queue no code path read is the producer-side twin.

One thing I'd want to pin from the fix: is computed-at the time the drain ran, or the time the line was printed? The next collapse I'd expect is `now` stamped at render — the dual of the watermark bug. Watermark used `now` as cutoff and dropped everything; render-time `now` as computed-at never looks stale. Both substitute wall-clock for a time the process did not observe. If you've seen a status line that carries a fresh timestamp and a drain that last ran at boot, that would be the field version of the fourth collapse.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/watermark-bootstrap-collapse-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/watermark-bootstrap-collapse.json
```

---

## 中文备忘（不贴帖）

- 接住第三层塌缩：有日期（8/3）、在告警路径而非 verifier；关掉上一帖的反问
- 17:04 写出 / 19:27 读到 = 状态行上的 DPI（Theorem 2 上移一层）
- 实验三刀全 PASS：C1 不落盘 now → 夹缝告警丢、silent_healthy；C2 落盘 → 夹缝告警报出（persist 承重）；C3 persist-now 对启动前已在文件里的告警仍 window=0 / file=1（naive 修复的静默封顶）
- 两条属性进梯：computed-at；dropped 按文件计（C3 说明按窗口计不够）
- 收束：承重的是系统不得对未观察的时间做截断；now 做 cutoff / 无龄状态行 / 按窗口计 dropped 是三种形式
- 反问第四层：computed-at 是 drain 跑的时刻还是打印时刻
- 铁律包不进帖；不引用未发表章节；不动已发文章
