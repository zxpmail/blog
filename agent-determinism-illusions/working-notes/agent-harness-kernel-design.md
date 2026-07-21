# Agent 内核设计：怯懦、易逝、舍得丢弃

> **体裁：** 设计立场 + 碰撞测试报告（非「四层 Harness 已产品化」声明）  
> **日期：** 2026-07-22（修订：P1 — 环境感知超时 + 进程自毁探针）  
> **测试链：** `c0f8304 → … → 222b34b` + P1 探针修订  
> **测的是什么：** `forge-verify-layered-prototype.py` 上的硬约束探针 + 三碰撞脚本  
> **不是什么：** 已上线的独立 Rust Agent 运行时

---

## 摘要

Agent 工程常见做法是用更长上下文、更复杂框架、更多重试去对抗 LLM 的随机性。本文主张相反：**可靠 Harness 的设计偏好是露怯、易逝、舍得丢**——用物理超时、预算/押金信号、遗忘与重置吸收不确定性，而不是用更复杂逻辑假装能管住模型。

本文给出：目标四层约束草图、三根不可覆盖常量、五层测试演进、以及对照 `results-v2/crash-test-*.json` 的**证据地图**（已支持 / 不支持）。

**不声称：** Token 节省百分比、调试时间减半、整套 L0–L4 运行时已落地。  
**本机（Windows）已绿：** 运行时推导 `PHYSICAL_TIMEOUT_MS`、进程 `os._exit(1)` + 工作区擦除。  
**需 Linux 才绿：** `is_truly_ephemeral`（`/dev/shm`）、`selfdestruct_verified`（O_DIRECT）— 用 `scripts/run-crash-p1-linux.sh` 或 `Dockerfile.crash-p1`。

---

## 1. 问题

核心矛盾：

- LLM 输出带不可约随机性。  
- Harness 要把概率输出接到确定性副作用上。  
- 用更复杂逻辑对抗随机性，常使 Harness 自己变成新的不确定源，并放大失败半径。

偏好：更硬的止损与遗忘，而不是更聪明的编排。

---

## 2. 他山之石（两硬四软）

| 来源 | 角色 | 用法 |
|------|------|------|
| 分布式账本 → 时间戳落地 | **硬启发** | 冲突不靠嘴炮仲裁 |
| 神经科学 → 反射 | **硬启发** | 超时/越界不经 LLM |
| 热力学 / 博弈 / 生态 / 量子 | **修辞框架** | 支撑态度，不映射代码 |

---

## 3. 目标架构（草图）与证据地图

下列 L0–L4 是**目标约束**。右侧「证据」只引用已跑脚本；无证据则标「未测」。

### L0 物理锚点（目标）

目标：不经 LLM 的硬超时 / 预算耗尽终止。

| 证据 | 结果文件字段 | 结论 |
|------|--------------|------|
| `crash-test-chaos.py` | `collision_points=40`，`all_pass`，latency ≪ `PHYSICAL_TIMEOUT_MS` | **支持：** Mock 信道故障下 L0/L1 判决不漂 |
| 同文件 `arch_constants` | `TIMEOUT_FORMULA=3 * max(BASELINE_RTT_MS, L01_PROBE_MS)`，本机例：rtt≈14.5ms → 红线≈43.5ms | **支持：** 环境感知超时（非写死 200ms） |
| 同文件 `env_health` | `net_delay_mode=software` → `degraded=true` | **不支持：** tc netem 真延迟；OS 信号杀真 agent 进程 |

### L1 原语 / 测量（目标）

目标：只记物理事实（时间、hash），沙箱可遗忘。

| 证据 | 字段 | 结论 |
|------|------|------|
| `crash-test-reset.py` | 4 强度 `pass`，前后 hash 一致 | **支持：** 重置后工作区内容可字节级复原 |
| 同文件 `ephemeral_probe` | Windows：`pass=true` 但 `is_tmpfs=false` | **支持：** 会话销毁清密钥；**不支持：** 本机真 tmpfs |
| 同文件 | `is_truly_ephemeral=null`，`storage_compliant=false`，`degraded=true` | **待 Linux：** `/dev/shm` 或 `CRASH_TEST_EPHEMERAL_ROOT` |

### L2 Turn：押金与反射（目标）

目标：错误/试错消耗预算；异常延迟触发反射，不经 LLM。

| 证据 | 字段 | 结论 |
|------|------|------|
| `crash-test-adversarial.py` | `deposit_fire_probe.pass=true` | **支持：** 连续 3 次错误 L2 → `fire` |
| 同文件 | `selfdestruct_process_probe.pass=true` | **支持：** 子进程 `os._exit(1)` + 父进程清空工作区 |
| 同文件 | `per_mode.*.fire_signals=0` | **解释：** 主循环每场景只跑 1 次 |
| 同文件 | `selfdestruct_verified=null`（非 Linux） | **不支持：** O_DIRECT 物理完整性；Token%→退出码；惊跳反射 |

### L3 编排：火烧山 / 自毁（目标）

| 证据 | 结论 |
|------|------|
| `UNCLEAR_ACTION=SELFDESTRUCT` | **支持：** 政策焊死为自毁（非 RETRY） |
| `selfdestruct_process_probe` | **支持：** 退出码 + 工作区擦除（集成探针） |
| plan 清空、死亡前 60s 收尾 | **未测** |

### L4 可观测：env_health（目标）

| 证据 | 结论 |
|------|------|
| 三份结果均含 `env_health`，Windows 上常 `degraded=true` | **支持：** 降级可观测，比假装全绿诚实 |
| Linux 一键跑绿 | 见 `run-crash-p1-linux.sh` / `Dockerfile.crash-p1` |

---

## 4. 三根龙骨（意图常量）

```text
PHYSICAL_TIMEOUT_MS   — 怯懦：启动时 = 3 × max(BASELINE_RTT, L01_PROBE)
SESSION_MAX_LIFETIME  — 易逝：会话寿命（目标；未在三碰撞中测）
STORAGE_BACKEND=TMPFS — 丢弃：真易失存储（Windows degraded；Linux /dev/shm 可绿）
```

---

## 5. 碰撞测试演进

| 阶段 | 动作 |
|------|------|
| 骨架→清排 | `c0f8304 … 222b34b` |
| P1 | 3×RTT 推导；进程自毁探针；tmpfs `/dev/shm` 路径 + Docker |

**引用口径：**

- 混沌：**8 × 5 = 40 碰撞点**  
- 对抗：**38 × 4 = 152 碰撞点**  
- 重置：**4 强度** + 可选 tmpfs 易失探针  

结果：`scripts/results-v2/crash-test-{chaos,adversarial,reset}_result.json`

---

## 6. 成本与收益（机制预期，非测得）

- **预期代价：** 误杀、重置频率、日志体积。  
- **预期收益：** 灾难半径下降、减少无效 Turn、故障可观测。  
- **原则：** Pessimistic 优于 Optimistic——设计偏好，非本次效应量。

---

## 7. 已知失效与缺口

笔记原有失效模式仍成立。

**P1 后剩余缺口：**

1. ~~`3×BASELINE_RTT` 未接入~~ → **已接入**（公式含 L01 探针下界）。  
2. ~~进程级自毁 / 工作区擦除未测~~ → **已测**（`selfdestruct_process_probe`）。  
3. 真 tmpfs：本机 Windows 仍 degraded；**Linux `/dev/shm` 路径已写好，待跑**。  
4. `selfdestruct_verified`（O_DIRECT）：**待 Linux**。  
5. tc netem、Token% 扣款、惊跳反射：仍未测。

---

## 8. 结论

好的 Harness 不是「更能管住 LLM」，而是「知道管不住，所以先焊止损与遗忘」。

**已有：** 三碰撞、环境感知超时、押金阈值、进程自毁+擦除、`evidence_map`。  
**未有（本机）：** 真 tmpfs 全绿、O_DIRECT 自毁完整性、完整 L0–L4 运行时。

---

## 附录：成稿检查清单

- [ ] 凡写「已验证」，必须带脚本名 + JSON 字段  
- [ ] 碰撞点 ≠ 场景数  
- [ ] `degraded=true` 写成降级成功，不写成失败隐瞒  
- [ ] 无「约 30% / 50%」类无出处数字  
- [ ] 六石不平均用力  
- [ ] 真 tmpfs / O_DIRECT 仅在 Linux 结果为 true 时声称  
