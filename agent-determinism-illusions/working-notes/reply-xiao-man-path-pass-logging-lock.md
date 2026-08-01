# Reply draft — Xiao Man (path-passing + logging + three-cell suite)

Thread: https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513  

Xiao Man (≈ Aug 1):
- Path-passing as discipline; v1→v2 100%→0% FR + timeout_ms leak = boundary-leak audit
- Fallback-with-logging over voting (one gate; secondary = telemetry)
- Mutation suite as design tool: rename_keys / cue_erase / decoy_nest

We ran logging claim: `declaration-anchor-fallback-logging-test.py` (PASS)

---

## English (paste to DEV.to)

```text
Agreed — path-passing as discipline, and the three-cell suite (rename_keys / cue_erase / decoy_nest) as the boundary-leak detector. Same tool, different layer: on the declaration anchors the disagree cells are P2 (out-of-decl rename) and P6 (shape-clone).

Ran primary synonym_list + secondary structural with logging, no vote (n=400/mix). Rename-heavy traffic: disagreements cluster on P2 → pressure on the primary (declaration review covers it). Shape-clone-heavy: cluster on P6 → pressure on the secondary (do not promote to co-gate). Modal disagree cell says which side is under pressure. No committee at commit time.

https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/declaration-anchor-fallback-logging-test.py
https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/declaration-anchor-fallback-logging.json
```

---

## 中文对照

```text
同意——path-passing 是纪律；三格套件（rename_keys / cue_erase / decoy_nest）是边界泄漏探测器。同一工具、另一层：声明锚上分歧格是 P2（声明外改名）和 P6（外形克隆）。

主 synonym_list + 次 structural，只记日志不投票（每混 n=400）。改名多：分歧堆 P2 → 压主锚（声明审查盖）。外形克隆多：堆 P6 → 压次锚（别升共门）。众数分歧格告诉哪侧吃紧。提交门不开委员会。

（挂脚本 + JSON）
```
