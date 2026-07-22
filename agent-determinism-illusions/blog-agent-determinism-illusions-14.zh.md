<!--
  ─────────────────────────────────────────────────────────────────
  微信 / 知乎标题备选:
  Harness 不是编排壳：闸门先于编排——一份工程备忘录
  我把 Agent 内核焊成闸门，对照实验只打赢了傻瓜编排
  ─────────────────────────────────────────────────────────────────
-->

# Harness 不是编排壳：闸门先于编排——一份工程备忘录

**Agent Determinism Illusions（第 14 篇）**

> **本文在系列中的位置：** 续篇三曾拆自己的「画了架构 = 解决了问题」。本篇换方向：不画更厚的编排壳，而把 harness 焊成**闸门**（会停、会拒、会毁），并用对照实验量假接受 / 假拒绝。体裁是**工程备忘录**，不是论文结论。

趋势在推长记忆、强自治、坚持做完、harness=能力编排。这些可以要。错的是把 harness **定义成**编排器——打断、遗忘、粉碎都会被优化掉，因为它们「妨碍完成」。

收成一句工程命题：

> **能力可以厚；harness 必须先是闸门。**  
> 长记忆里嵌寿终与可粉碎；强自治上挂超时 / 押金 / 惊跳；「做完」由合约与确定性层定义，不是自我感觉。

---

## 1. 焊了什么（可部署进程，不是产品壳）

`scripts/harness-kernel.py`：常驻进程，NDJSON / HTTP 多会话。

| 闸门 | 行为 |
|------|------|
| `PHYSICAL_TIMEOUT_MS` | 墙钟超时 → 拒 turn，**丢弃迟到答案**，进程仍活 |
| Token% 押金 | 扣光 → `BUDGET_EXIT`，清 `plan`，exit=1（单会话） |
| 惊跳 | 延迟尖峰 → 拒本 turn，不杀进程 |
| 会话寿终 | 到期拒 LLM |
| `verify` / turn→verify | forge L0→L1→（可选）L2 |
| wind_down | 清 plan，会话死 |

Docker 探针（chaos / adversarial / reset / compose / harness-kernel）与生产路径验收 A/B/C/D（`prod-gate-acceptance.py`）已绿。  
**诚实标签：** lab acceptance，不是客户生产验证。

---

## 2. 对照：ORCH vs GATE

脚本：`scripts/gate-vs-orch-controlled.py`。

| 条件 | 含义 |
|------|------|
| **ORCH** | 纯编排稻草人：非空产出即 ACCEPT |
| **GATE** | forge 分层验收 +（慢臂）墙钟硬顶 |
| 消融 | 无 verify / 无超时 |

任务集：P1+P4+write-test，外加手标注 code/test（business-proxy）。**不是私有生产流量。**

### 2.1 SKIP_LLM（只 L0/L1）时

假接受（应拒）：ORCH **15/15 = 100%**，GATE **0/13 = 0%**（Wilson 95% 见结果 JSON）。  
慢有害迟到接受（N=20）：ORCH **20/20**，GATE **0/20**。  
消融：去掉 verify → FA 回 100%；去掉超时 → late 回 100%。

应过样本在 SKIP 下大量 `UNCLEAR` → **假拒绝分母为 0**，语义误杀当时测不到。

### 2.2 打开 L2（真 API，glm-5.2）+ suite=both

| 指标 | ORCH | GATE |
|------|------|------|
| 假接受（应拒，n=20） | 20/20 = 100% | **0/20 = 0%** |
| 假拒绝（应过） | 0/20 | **4/19 = 21.1%**（Wilson ≈ [8.5%, 43.3%]） |

假拒绝终于可测。闸门有代价：大约两成应过样本被拒（本跑、单模型、CI 宽）。

结果文件：`scripts/results-v2/gate-vs-orch-controlled_both_l2_result.json`。

---

## 3. 这说明什么——以及不说明什么

**能说：**

- 相对「非空即接受」，闸门在本 proxy 上大幅压假接受；超时挡得住迟到当成功。  
- 消融对得上机制，不是玄学。  
- 开 L2 后误杀可量化（本跑 ~21%）。

**不能说：**

- 已在你们的生产上验证。  
- 打赢了真实编排器（Cursor / LangGraph / 自研 runtime）——ORCH 是稻草人。  
- 21% 假拒绝可接受或最优——没有业务代价函数。  
- 这是可审学术定理——N 小、单模型、无多重校正。

一句话：  
**证明了自己的闸门在自己的剧本里打得过傻瓜编排；还没有证明它对真实系统、真实对手、真实代价成立。**

---

## 4. 和系列主线怎么接

本系列反复拆：温度 0、Phase Gate、LLM-as-Judge、画架构。共同形状是——**把「看起来在约束」当成「已经收敛」**。

编排壳是同构的下一站：工具更多、记忆更长、更少打扰，幻觉被编排得更久。闸门不否定能力，只要求：**完成路径上先有会响的硬停。**

第 8–10 篇的 L0→L1→L2 / argument-space，是验收侧的闸门。本篇是运行时侧的闸门。两边同一偏好：**露怯、易逝、舍得丢。**

---

## 收束

趋势可以要长记忆与强自治。  
Harness 若等于编排壳，闸门会被优化掉。  

**能力可以厚。Harness 必须先是闸门。**  

本文是工程备忘录：数字可复跑，主张收窄，不写成论文结论。下一刀若较真——非稻草人基线、外部任务集、代价函数——再另开一篇。

---

**系列：** Agent Determinism Illusions · 脚本：[GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**相关脚本：** `harness-kernel.py` · `prod-gate-acceptance.py` · `gate-vs-orch-controlled.py`  
**设计笔记：** `working-notes/agent-harness-kernel-design.md` · `working-notes/gate-vs-orch-controlled.md`
