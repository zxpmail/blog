# Reply draft — Mike Czerwinski (cross-model pair-join closes within-model)

Source: Part 6 DEV.to thread, follow-up to posted `reply-mike-hhi-pair-join.md`
Prior ack draft: `reply-mike-pair-join-shape.md` (A path; superseded by this B run)
Mike's cut (2026-07-29): per-scenario is load-bearing; lift≈1.0 ambiguous;
close within-model next via cross-model pair-join.

Evidence (2026-07-29 cross-model run):
- `scripts/pair-join-empirical-test.py` (model-slug outputs)
- `scripts/results-v2/pair-join-empirical-qwen3-0-6b.json` (prior: lift 1.14, n_miss=30)
- `scripts/results-v2/pair-join-empirical-gemma3-latest.json` (n_miss=5, DS4-only, CD-only)
- `scripts/results-v2/pair-join-empirical-qwen2-5-1-5b.json` (n_miss=5, route-only)
- `scripts/results-v2/pair-join-empirical-cross-model.json` (comparison)

Verdict: SUPPORT Mike. qwen3's independence story does not hold as a general
claim. Cross-model reverses the DS4 co-fire cell and collapses the 2×2 onto
opposite single margins.

---

## English (paste to DEV.to)

```text
Ran the cross-model close.

Same protocol (20 scenarios × N=5 × 3 probes), two models besides qwen3:0.6b:

  qwen3:0.6b (prior)     n_miss=30  lift=1.14
    DF6+DS5: 9 MISSes neither signal
    DS4: 3/5 route∧CD co-fire

  gemma3:latest          n_miss=5   lift=N/A (P(route|MISS)=0)
    All 5 MISSes on DS4
    route 0/5, CD 4/5 — no co-fire

  qwen2.5:1.5b           n_miss=5   lift=N/A (P(CD|MISS)=0)
    DF4×3 + DF6×1 + DS8×1
    route 5/5, CD 0/5 — DS4 miss=0

Your ambiguity cut holds, and the within-model caveat bites. Aggregate lift 1.14 was compatible with both stories on qwen3; across models the 2×2 doesn't even stay in the comparable regime — one margin saturates at 0 on each second model, so lift is undefined. That is already enough to refuse "independent detectors in general."

The load-bearing cell reverses too. DS4 was qwen3's only consistent co-fire pocket; on gemma3 it is CD-only, on qwen2.5 it produces zero MISSes. DF6/DS5's "neither" pocket is similarly model-bound. So the per-scenario shape from the last run was a description of qwen3's judgment quirks on route_changed / defect_class — not a property of the detector pair.

Honest limit: the two second models only yield 5 MISSes each, so this is a shape/margin refusal, not a second lift estimate. Still stronger than adding n on the same model. Within-model was the right next close.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/pair-join-empirical-cross-model.json
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/pair-join-empirical-test.py
```

---

## 中文备忘（不发）

- SUPPORT Mike：within-model caveat 咬住了
- qwen3 lift 1.14 / DF6+DS5 neither / DS4 co-fire —— 不跨模型
- gemma3：5 MISS 全 DS4，route=0 CD=4，共触发反转
- qwen2.5:1.5b：5 MISS 全 route、CD=0，DS4 零 miss
- 两模型 n_miss 都薄，结论靠 shape/margin 反转，不是第二个 lift
- 挂 cross-model.json + 脚本；不重贴 qwen3 全表
- localhost→::1 坑已绕开（用 127.0.0.1）；输出改 model-slug
