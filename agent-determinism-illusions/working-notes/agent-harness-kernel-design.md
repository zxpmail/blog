# Agent 内核设计：怯懦、易逝、舍得丢弃

> **体裁：** 设计立场 + 碰撞测试报告（非「四层 Harness 已产品化」声明）  
> **日期：** 2026-07-22（修订：PHYSICAL_TIMEOUT 焊进 turn）  
> **测的是什么：** 探针 + 组合桩 + NDJSON/HTTP + 真 LLM/cc-switch + Bearer + 落盘 + turn→verify + **墙钟硬顶**  
> **不是什么：** 多租户 RBAC / 加密会话仓 / 完整产品 L0–L4 壳 / Rust binary

---

## 摘要

偏好：**露怯、易逝、舍得丢**。

**已有：**
- NDJSON 单会话致命路径；HTTP 多会话 + `state.json`；Bearer；cc-switch；turn→verify
- **`PHYSICAL_TIMEOUT_MS` 焊进 turn**：墙钟超时 → `PHYSICAL_TIMEOUT`（拒 turn、丢弃迟到答案、进程仍活）；与 chaos 探针同形的红线语义
  - 显式：`HARNESS_PHYSICAL_TIMEOUT_MS` / `--physical-timeout-ms`
  - 或 `3×max(HARNESS_BASELINE_RTT_MS, HARNESS_L01_PROBE_MS)`
  - 默认 60000（LLM 实用）；探针请设短红线（如 50–200）

证据：`crash-test-harness-kernel.py` → `results-v2/crash-test-harness-kernel_result.json`。

**仍不支持：** 多租户 RBAC；加密仓；无 API 时 L2；挂载外取证粉碎。

---

## 可部署进程怎么用

```powershell
# 短红线（与 chaos 同量级）
$env:HARNESS_PHYSICAL_TIMEOUT_MS="200"
python agent-determinism-illusions/scripts/harness-kernel.py --no-mock-llm

# 或 CLI
python agent-determinism-illusions/scripts/harness-kernel.py --physical-timeout-ms 200 --no-mock-llm
```

三根龙骨现均有进程内旋钮：`--physical-timeout-ms` / `--session-ms` / 工作目录（tmpfs 由部署侧挂）。

---

## 证据地图（压缩）

| 层 | 已支持 | 仍不支持 |
|----|--------|----------|
| 探针 L0–L3 | netem / tmpfs / … / PHYSICAL_TIMEOUT 推导 | 挂载外取证 |
| 组合桩 | 同进程五臂 | — |
| **可部署进程** | … + turn 墙钟硬顶 `PHYSICAL_TIMEOUT` | RBAC/加密仓；产品壳 |

---

## 结论

三根龙骨里的 **PHYSICAL_TIMEOUT** 已焊进 turn（不只探针旁路）。  
下一步更值得做的是**写进博客**；租户/加密仓仍属产品壳，不增加主张证据密度。
