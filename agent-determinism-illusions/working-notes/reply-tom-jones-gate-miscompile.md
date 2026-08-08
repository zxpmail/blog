# Reply draft — Tom Jones (Part 8 / silently miscompiled command gate)

Thread: https://dev.to/zxpmail/the-channel-gap-why-your-llm-judge-is-blind-in-one-eye-35ne

Tom (~6h):
- Evidence-channel design they run; hit a failure mode not named in thread
- Not channel blindness, not Goodhart: sandbox runs caller tests; gate returned
  verified:true for wrong answers on 5/8 shapes
- Cause: extractor kept assert indentation → nested assert after `return`;
  valid Python, never executed, exit 0
- Survived because correct impls make broken path ≡ working path; only a
  deliberately wrong impl separates them
- Third item: deterministic gate can be silently miscompiled → fail-green
- Cheap check: known-wrong impl in repo; suite must fail against it in CI
- "A gate you have only ever watched pass is not a gate, it is a habit."

## 策略
- 承认正文缺口（第三格未命名）；复现他的形状，不争 5/8 原数
- 锁：绿须带路径执行证物；普通 exit-0 证物不够
- 挂新实验；不引未发布 Part；可点 skillgate `command` 门是本文点名处

---

## English (paste to DEV.to)

```text
You're right — and that failure mode is not in the article. Channel gap and the named-evasion ratchet do not cover it. Third class: a deterministic gate can be silently miscompiled, and when it is, it fails green.

I reproduced the shape with a real subprocess (not a storyboard). Same caller asserts, two compilers, correct vs deliberately wrong `add`:

| compiler | exit-only @ correct | exit-only @ wrong | + known-wrong canary @ correct |
|---|---|---|---|
| correct_compile | GREEN | RED | GREEN |
| miscompile (asserts kept indented after `return`) | GREEN | GREEN | REJECT_DEAD_PATH |

Miscompile is valid Python. Exit 0. The exit-only gate reports success having executed nothing — and on a wrong implementation it still greens, exactly because the dead path and the live path agree whenever the code under test happens to be right. My control the same morning as yours would also have said "no difference." Only the wrong impl splits them.

So yes: alongside channel blindness and Goodhart pressure, put silent miscompile. A text judge at least fails ambiguously. A command gate that exits 0 having checked nothing is indistinguishable from one that passed — unless green is required to carry *path-execution* evidence, not an exit-0 slip. Your cheap check is that evidence: keep a known-wrong implementation and require the suite to go red against it. A gate that cannot fail the canary has not proven it ran.

Your last line is the lock: a gate you have only ever watched pass is not a gate, it is a habit.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/gate-miscompile-canary-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/gate-miscompile-canary.json
```

---

## 中文对照（不发）

```text
你说得对——这种失效正文里没有。信道缺口和 named-evasion ratchet 盖不住。第三类：确定性门可被静默误编译，一旦如此就 fail-green。

用真实 subprocess 复现了形状（见表）。miscompile 是合法 Python、exit 0；只看 exit 的门在错误实现上仍绿——正确实现上死路径和活路径本来就一致。普通过关条不够；绿必须带路径执行证物。你的廉价检查就是那证物：仓库里留已知错误实现，套件必须对其变红。不能弄红 canary 的门，没证明自己跑过。

最后一句锁死：只见过它通过的门，不是门，是习惯。
```

---

## 检查
- [ ] 发英文；挂 2 链接（push 进可访问分支/main 后再贴）
- [ ] 不争他的 5/8；用本夹具表
- [ ] 不说「门对证物就能抓」；锁路径执行证物
- [ ] 收他原句 habit
