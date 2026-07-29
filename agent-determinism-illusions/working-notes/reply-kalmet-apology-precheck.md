# Reply draft — Kalmet (fabricated-claim apology)

Post: https://dev.to/zxpmail/i-fabricated-a-claim-about-llm-judges-then-i-ran-the-apology-experiment-2p0g  
Comment: Kalmet — DF6/DS9-style param validation in scenario pre-checks; looking for 1B–2B to test “clipping”

---

## English (paste to DEV.to)

```text
Glad that landed.

Pre-checking DF6/DS9-style value mismatch before the judge runs is exactly the cheap Layer-0/1 win — it also keeps DS4 from polluting the miss table as if it were the same defect. One caveat worth keeping in the protocol: a pure `taskParam !== outputParam` check *passes* DS4 (10 === 10). DS4 still needs its own contract rule (change-shaped task vs “no change needed” completion), not the value gate. Otherwise the pre-check quietly re-introduces the conflation the apology had to walk back.

On the 1B–2B clip test: that band is the interesting hole in the v2 table (0.5B cliff vs ~4B near-clean). If you report anything, the useful split is still explicit DF vs subtle DF vs DS4-under-label — not a single accuracy. Happy to see the sprint numbers when you have them.
```

---

## 中文备忘（不贴帖）

- 肯定：DF6/DS9 参数预检降噪 DS4
- 钉住：纯数值相等过不了 DS4 的语义问题，别又混回去
- 1B–2B：补 0.5B↔4B 悬崖中间；分三类报，别只报一个准确率
