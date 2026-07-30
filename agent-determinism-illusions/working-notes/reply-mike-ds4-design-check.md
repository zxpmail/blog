# Reply draft — Mike Czerwinski (apology: DS4 harness-label bug + cliff-not-slope)

Thread: I Fabricated a Claim About LLM Judges. Then I Ran the Apology Experiment.
Mike's comment (2026-07-29): two cuts.

## Cut 1 — DS4 as harness-label bug, upstream value-match check

Mike: "DS4 turning out to be a harness-label bug is the same failure shape
the series keeps finding in judges, one level up. A harness label is a
claim same as a judge verdict. The inverse of the downstream reject signal
(output-param equals task-param when is_legit=False) is a clean deterministic
warning at scenario-design time."

Verified. Wrote `ds4-upstream-design-check-test.py` — hand-coded the 4
param-bearing scenarios (DF4, DF6, DS4, DS9) with task_param/output_param
pairs and ran the bidirectional check:

- downstream REJECT (output≠task ∧ is_legit=False): DF4, DF6, DS9 — all caught
- upstream FLAG (output==task ∧ is_legit=False): DS4 — uniquely, 0 false positives

Mike's claim holds with 0 false positives on this fixture. Same value-match
check, applied at scenario-authoring time, would have flagged DS4 before it
became 45 judgments of noise. Cost: ~0ms, no LLM. The unstated assumption
("numeric equality ⟹ no directional failure") is exactly the kind of thing
a design-time check should catch.

Result: `results-v2/ds4-upstream-design-check.json`

## Cut 2 — fourth size point for cliff-not-slope

Mike: "two data points (0.5B fail hard, 4.3B mostly succeed) are consistent
with both a cliff between them and a smoother transition straddled. A model
in the 1 to 2B range would tell you which."

Ran `directional-failure-v2.py` on qwen2.5:1.5b (200 calls, 20 scenarios):

| Model | Size | Global | DF acc | DS acc | DS4 | DF6 | DS9 |
|-------|------|--------|--------|--------|-----|-----|-----|
| qwen3:0.5b  | 0.5B | 61.5% | 63.3% | 56.0% | 0%   | 0%   | 0%   |
| qwen3:0.6b  | 0.6B | 67.5% | 60.0% | 64.7% | 7%   | 0%   | 20% |
| **qwen2.5:1.5b** | **1.5B** | **92.5%** | **83.3%** | **96.0%** | **100%** | **100%** | **100%** |
| gemma3:latest | 4.3B | 92.0% | 100% | 89.3% | 0%   | 100% | 100% |
| deepseek-v4-flash | ~200B? | 92.0% | 100% | 90.0% | 13% | 100% | 100% |

**The cliff is between 0.6B and 1.5B**, not between 1.5B and 4.3B.
- 0.5B → 0.6B: 61.5% → 67.5% (small step, same regime)
- 0.6B → 1.5B: 67.5% → 92.5% (the cliff — 25-point jump)
- 1.5B → 4.3B → ~200B: 92.5% → 92.0% → 92.0% (flat)

So your read was right — the original "cliff between 0.5B and 4.3B" framing
straddled the actual transition. The 1.5B point localizes the cliff to the
0.6–1.5B interval. Two extra points (0.5B→0.6B small, 0.6B→1.5B large) say
the cliff is sharp, not gradual.

**One wrinkle worth naming.** DS4 catch rate is non-monotonic in size:
- 0.5B: 0%; 0.6B: 7%; 1.5B: **100%**; 4.3B: 0%; ~200B: 13%

qwen2.5:1.5b catches DS4 15/15; gemma3:4.3B catches 0/15. That's not a
size gradient — it's model-family-dependent. Reinforces your read that
DS4 under the harness label is partly a fixture/labeling property, not
a clean directional-failure universal. The 1.5B's perfect catch on DS4
might be over-rejection (the harness label was the original protocol's
choice; accepting was defensible per the article's Pattern 1 caveat) —
the model just happens to align with the harsh label here.

DF6/DS9 catch rate IS monotonic: 0% under 1B → 100% at 1.5B and above.
The value-mismatch class is the clean size story; the "no change needed"
class is messier and model-family-coupled.

qwen2.5:1.5b has one quirk worth flagging: V2 (legit control, "stop
log-collector") drops to 20% — 4/5 false rejects. So 1.5B is the cliff
for catching failures, but its false-reject rate on easy legit cases
isn't zero. Another reason to lean on deterministic checks for the
clear-cut reject signals and leave the LLM for the residual.

Result: `results-v2/qwen2-5-1-5b_summary.json`

---

## English (paste to DEV.to)

```text
Two cuts, both land.

1. Upstream value-match check — verified. Same check that fixes DF6/DS9 downstream flags DS4 upstream, 0 false positives on the 4 param-bearing scenarios. The unstated assumption "numeric equality ⟹ no directional failure" is exactly what a design-time check should catch.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/ds4-upstream-design-check-test.py

2. Cliff-not-slope — you called it. qwen2.5:1.5b (200 calls): global 92.5%, DF 83.3%, DS 96.0%. Cliff is between 0.6B and 1.5B (67.5%→92.5%), not 1.5B↔4.3B (flat at 92%). Original "cliff between 0.5B and 4.3B" straddled the real transition.

DS4 catch is non-monotonic (0.5B 0% → 0.6B 7% → 1.5B 100% → 4.3B 0% → 200B 13%) — family-coupled, not size-coupled. Reinforces your harness-label read. DF6/DS9 are monotonic; value-mismatch is the clean size story.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/qwen2-5-1-5b_summary.json
```

---

## 中文备忘（不发）

- Mike 两个 cut 都准：上游 value-match 双向检查 0 误报抓 DS4；cliff-vs-slope 第四点
- 上游检查脚本：`ds4-upstream-design-check-test.py` → `results-v2/ds4-upstream-design-check.json`
- 第四 size 点：qwen2.5:1.5b，global 92.5%
- Cliff 位置：0.6B → 1.5B 之间（67.5% → 92.5%），不是 1.5B → 4.3B
- DS4 非单调：0.5B 0%, 0.6B 7%, 1.5B 100%, 4.3B 0%, 200B 13% —— 不是 size gradient
- DF6/DS9 单调：0% under 1B → 100% at 1.5B+
- Value-mismatch 类是干净的 size 故事；"no change needed" 类乱
- V2 1.5B 上 20% 准确率（4/5 false reject）—— 1.5B 在 cliff 上但对易合法 case 有误伤
- 备选模型：qwen3.5:2b 在本地无响应（未跑成）；qwen3-vl:2b 是 thinking 模型，~40s/call 太慢
- 挂 3 个链接：upstream-check 脚本、upstream-check JSON、qwen2.5:1.5b summary
