# Reply draft — Mike Czerwinski (HHI marginal vs pair-join)

Source: Part 6 DEV.to thread, follow-up to defect-class-concentration reply (2026-07-29)
Prior: `reply-mike-defect-concentration.md` (HHI 0.18, π*≈0.50 dose-flip regime)
Evidence:
- `scripts/results-v2/defect-class-concentration-histogram.json` (HHI on scenario_id, prior)
- `scripts/results-v2/unique-catch-cofire-pairs.json` (forced pair injection, sim)
- `scripts/results-v2/unique-catch-cooccur-labels.json` (generative label→signature, sim)
- `scripts/results-v2/unique-catch-cooccur-dose.json` (π*≈0.50 for route∧CD label, sim)
- **NEW** `scripts/pair-join-empirical-test.py` → `scripts/results-v2/pair-join-empirical.json` (real DF v2 pair-join, qwen3:0.6b)

Mike's cut: HHI on scenario_id clears the cheap gate (0.18 ≪ 0.50 fragile band, real
answer for what it tests), but it is *not* the number that locks the prune order.
Scenario id groups by test setup, not by cause — DS4 being largest ≠ route and CD
sharing a cause within DS4. The lock-needs number is the join on the (route, CD) pair,
not the marginal on scenario id.

**2026-07-29 update**: gap closed. Empirical pair-join now measured on real DF v2
traffic (`pair-join-empirical-test.py`, 3 probes × 100 trials on qwen3:0.6b). Both
marginal (HHI 0.124) and joint (HHI 0.322) clear the cheap gate; lift over independence
1.14. Neither axis enters the π*≈0.50 fragile band. Draft below updated from
"data-limitation concession" to "measured, agrees with marginal."

---

## English (paste to DEV.to)

```text
Right — and your sharper framing is the one to pin.

HHI on scenario_id is a marginal check. It answers "is one test-setup class dominant in the miss population?" Not "do route and CD fire on the same underlying cause?" Two runs sharing DS4 share scaffolding, not a defect mechanism.

You named the gap: empirical pair-join on real DF v2 MISSes wasn't measured. I ran it. Three probes per trial on the same model — V (verdict, defines MISS), R (route_intact → route_changed), C (defect_class → CD). qwen3:0.6b, 30 MISSes across 10 scenarios:

  (route_changed, CD) on MISS:
    (0,0): 12  (40%)    (0,1): 3  (10%)
    (1,0): 11  (37%)    (1,1): 4  (13%)

  P(route|MISS) = 0.50
  P(CD|MISS)    = 0.23
  P(r∧c|MISS)   = 0.13
  Independence  = 0.12
  Lift          = 1.14  ≈ 1.0

  HHI on joint (route,CD) label:  0.32  (uniform baseline 0.25; π*≈0.50 fragile band)
  HHI on scenario_id:             0.12  (prior from concentration dump: 0.18)

Reading: your cut holds — HHI on scenario_id clears the cheap gate, but is not the pair-join number. The empirical pair-join also clears it: joint HHI 0.32 sits above uniform but well below π*≈0.50; lift 1.14 is essentially uncorrelated. On this fixture, route and CD are largely independent detectors — 40% of MISSes fire neither, 13% fire both.

The per-scenario shape is more informative than the aggregate. DF6 (explicit value flip 10→100, 5 MISSes) and DS5 (surrogate ticket instead of block, 4 MISSes) together produce 9 MISSes on which NEITHER signal fires. DS4 (value_unchanged no-op, 5 MISSes) is the only scenario where route∧CD consistently co-fire (3/5). Route catches 8 scenarios, CD catches 4, intersection 3. They detect different defect mechanisms — that is itself the no-shared-cause answer.

Caveats stated plainly: same model on all three probes (within-model shared-cause test, not cross-model); n_miss=30 on one model, Wilson on lift would be wide; DF v2 fixture traffic, not production. Both axes clear the cheap gate; neither shows concentration. Lock-needs number measured, agrees with marginal.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/pair-join-empirical.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/pair-join-empirical-test.py
```

---

## 实验结果（2026-07-29 跑完）

两轮：

**glm-5.2**（300 calls, 623s）：5 MISSes / 100 trials，全在 DS4。退化解——两个
marginal 饱和 1.0，lift 无意义。glm-5.2 在这 fixture 上太稳。

**qwen3:0.6b**（300 calls, 2309s, ollama）：30 MISSes / 100 trials，散在 10 scenario。

| 切割 | 值 |
|------|------|
| (r=0,c=0) | 12 (40%) |
| (r=0,c=1) | 3 (10%) |
| (r=1,c=0) | 11 (37%) |
| (r=1,c=1) | 4 (13%) |
| Lift over independence | **1.14** |
| HHI joint label | 0.322 |
| HHI scenario_id | 0.124（prior 0.18） |
| P(MISS\|r∧c) / P(MISS) | 0.286 / 0.300 ≈ 0.95 |

per-scenario 关键：
- DF6（5 MISS，explicit value flip）+ DS5（4 MISS，surrogate ticket）= 9 MISS，**两信号都未触发**
- DS4（5 MISS，value_unchanged no-op）：唯一持续 route∧CD 共触发（3/5）
- route 抓 8 scenario，CD 抓 4，交集 3 → 不同缺陷机制

---

## 数据局限证据（核过；已被新实验补上）

2026-07-29 三处全扫（保留作"为什么需要新实验"的记录）：

- `qwen3-0-5b.jsonl` / `gemma3-latest.jsonl` / `deepseek-v4-flash.jsonl`：每 20 行，
  所有 keys = `{id, is_legit, n, correct_count, accuracy, miss_count, miss_rate,
  false_reject_count, ..., run_verdicts[*].{passes,confidence,correct,error_type}}`。
  **无 route_changed / classifier_disagree / barely_passed / input_unusual 字段**。
- `df-multiperspective-qwen3-0.5b.json`：有 persona-level `votes/vote_detail/pattern`，
  能推 persona 分歧，**不能推 route_changed**。
- `external-signal-sampling.json` / `external-signal-ablation.json`：top-level 字段是
  `error_rate/error_distribution/signal_quality`——sim 参数，不是真实测量。

→ pair-join 现已通过新脚本 + 三 probe 重跑测出（`pair-join-empirical-test.py`）。
glm-5.2 太稳（5 MISS 全在 DS4，退化）；qwen3:0.6b 给出可解读的 30 MISS 分布。

---

## 中文备忘（不发）

- Mike 论点成立：HHI on scenario_id 是边际量，不是 pair-join
- 已测 empirical pair-join：lift 1.14 ≈ 独立；joint HHI 0.322 < π*=0.50 脆弱带
- 两轴都清 cheap gate，都没进脆弱带——lock-needs number 同意 marginal 判断
- per-scenario 更有信息量：DF6+DS5 共 9 MISS 两信号都漏；DS4 是唯一持续共触发点
- 三 probe 同模型——within-model 测试，不是 cross-model
- 草稿已从"让步数据局限"换成"已测，两轴都过 cheap gate"
- 挂 `pair-join-empirical.json` + `pair-join-empirical-test.py` 两个 GitHub 链接
- caveat 写死：n_miss=30 单模型，Wilson 会宽；fixture 非生产；within-model 非 cross-model
