---
title: "argument-space 验证的诚实边界——以及 Evidence Locker 补了什么"
published: false
description: "四组实验确定 C3 对 referent mismatch 的抓取率为 4/5，并揭示剩下的 1/5 是结构边界而非可修复缺口。Evidence Locker 风格反馈循环能检测 over-invalidation，不能检测 under-invalidation。"
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent 确定性幻觉"
---

# argument-space 验证的诚实边界——以及 Evidence Locker 补了什么

**Agent 确定性幻觉（第 14 篇）**

*2026-07-14*

第 13 篇用五个场景、三个评估器测试了 C3（argument-space runner）。结果：C3 得 5/5，同义词免疫，数据加工不等式（DPI）被具体化——可寻址 claim 上一个结构性的底。

那个底有一条裂缝。Mike Czerwinski 在 dev.to 的 Part 4 评论区找到了它。本文测试这条裂缝，测量它的深度，并说明为什么它不能被闭合——只能被界定。

然后加上第二个机制：一个受 Pascal Cescato 的"Evidence Locker"概念启发的 **evidence 反馈循环**。这个循环能抓到 over-invalidation（实现做了合约没要求的），但在 under-invalidation（实现做少了）上卡住。那条裂缝和循环的盲点，是同一个结构边界。

---

## 1. 裂缝：referent 的可博弈性

第 13 篇的 C3 通过执行 verify 命令来工作——跑一段代码，观察实际行为：写一个 key，看缓存条目是否消失。verify 命令不读需求文本——它运行代码。

Mike Czerwinski 指出了这个设计里的一个缺口。一个知道门禁检查 referent-presence 的作者可以写：

> "invalidate user:123"

这在技术上可寻址（命名了一个 key，满足 referent 门禁）。但真实的意图更宽——invalidate 所有 user 条目，不只是 user:123。门禁在窄 referent 上通过，实际的 scope 却被错过了。

问题是：C3 能抓到这种情况吗——即便 verify 命令是从那个错误的 referent 写出来的？

---

## 2. 实验 I：C3 对阵 referent mismatch

### 设计

五个场景。每个场景里，一个人读了一个带错误/狭窄 referent 的需求，从它出发写了**一条** verify 命令，C3 执行它。如果 C3 **PASS**，博弈成功——verify 对着错误的 referent 批准了工作。如果 C3 **FAIL**，mismatch 被抓住了。

| 场景 | 实现 | 错误 referent (需求) | 真正意图 | Verify 检查 | 结果 |
|------|------|---------------------|----------|------------|------|
| S1 | 定向 key-level 删除 | invalidate user:123 | invalidate **所有** user:* | user:123 消失 | **PASS** → 博弈成功 |
| S2 | flush-all | 保留 user:456 | 同上 | user:456 存活 | **FAIL** → 抓到了 |
| S3 | prefix:user/* 只 | invalidate admin:123 | invalidate user:123 | admin:* 消失 | **FAIL** → 抓到了 |
| S4 | 分层 L1/L2 | invalidate L1 | invalidate L1+L2 | L2 消失 | **FAIL** → 抓到了 |
| S5 | cascade over-inv all | 保留 user:456 | 同上 | user:456 存活 | **FAIL** → 抓到了 |

### 结果

**C3 抓取率：4/5。** 博弈只在 S1 上成功。

S1 成功是因为 verify 命令碰巧检查了正确的机械行为，尽管追踪的是错误的 referent。"检查 user:123 是否消失" → 实现确实 invalidate 了 user:123 → PASS。但 user:456 从未被检查，因为狭窄的需求从未提起它。

**诚实的解读：** C3 能抓到 referent mismatch——当错误的 referent 导致 verify 命令与实现的实际 scope 不匹配时。它错过的情况是：verify 命令在机械上检查了正确的行为——尽管*本应检查的 scope* 是错的。

---

## 3. 1/5 缺口到底是什么

S1 缺口不是 C3 的缺陷。它是**合约定义质量**问题。

事件序列：
1. 人写需求："invalidate user:123"（窄的、不完整的）
2. 人读需求、写 verify 命令：检查 user:123 消失
3. C3 执行 verify 命令 → PASS（user:123 **确实** 被 invalidate）
4. 但 user:456 从未被检查，因为没人要求检查它

第 2 步是缺口所在。写 verify 命令的那个人，是基于一个已经太窄的需求工作的。Verify 命令正确地验证了需求所说的话——但需求本身是错的。

**没有确定性门禁能修复这个。** 门禁验证告诉它验证的东西。如果指令错了，门禁在错误的 scope 上产生一个正确的 pass。这是不可约的 L3（人类审阅）边界。

---

## 4. Evidence Locker 模式

在研究这个缺口的过程中，我读到了 Pascal Cescato 的"Evidence Locker"概念——一个结构化的运行时证据集合，用以挑战模型而非默认接受其输出。

核心洞察：**没有 upfront 门禁能在第一次尝试时就是对的。** 诚实的路径是：**跑 → 收集 evidence → 挑战模型 → 精炼合约 → 重复。**

这正是当前架构中缺失的反馈循环。C3 产生 evidence（每个 key 的 PASS/FAIL）。这些 evidence 应该反馈到合约 scope 中，而不只是流进人工审阅队列。

---

## 5. 实验 II：evidence 反馈循环

### 设计

多轮仿真。每轮：
1. C3 对当前合约 scope 执行验证
2. **Post-audit**：快照写前和写后的 **所有** key，检测 verify scope 之外的状态变化
3. Post-audit 发现的 evidence 用于扩大下一轮的合约 scope
4. 重复，直到 scope 收敛

两种缓存实现，用来测试循环能检测什么、不能检测什么：

- **Scenario A（定向、under-invalidation）：** write(k) 只删除 k。user:456 存活。这就是实验 I 的 S1 缺口。
- **Scenario B（flush、over-invalidation）：** write(k) 删除 **所有东西**。admin:123 也被清除了。

### 结果

**Scenario A（under-invalidation）：卡在 50%（8 轮）。**

| 轮次 | Scope | 覆盖 | Evidence 信号 |
|------|-------|------|-------------|
| 1 | user:123 | 50% | user:123 确认 → 无缺口信号 |
| 2-8 | user:123 | 50% | 同上。user:456 未变 → 不可见 |

循环检测不到 under-invalidation，因为**没有状态变化 = 没有 evidence**。user:456 保持未触碰，post-audit 看不到任何意外活动，scope 从未扩大。这与实验 I 的 S1 缺口是同一个诚实边界。

**Scenario B（over-invalidation）：2 轮收敛。**

| 轮次 | Scope | 覆盖 | Evidence 信号 |
|------|-------|------|-------------|
| 1 | user:123 | 50% | **admin:123 意外变化** |
| 2 | user:123 + user:456 + admin:123 | 100% | 全部确认 → 收敛 |

循环检测到 over-invalidation，因为实现产生了**意外的状态变化**——合约没问及、但实际移动了的 key。"即便我们只写了 user:123，admin:123 也被删了"是一个可检测的信号。

### 诚实边界

| 信号类型 | 可检测？ | 机制 | 对应场景 |
|---------|--------|------|--------|
| Over-invalidation | ✅ | 意外的状态变化 | flush、cascade |
| Under-invalidation | ❌ | 无状态变化 = 无 evidence | S1 缺口、Mike 的博弈 |

反馈循环是一个部分答案。它在实现超出合约要求时扩大 scope，但它不能闭合 under-invalidation 缺口——因为缺口是一个**可观测事件的缺席**。

---

## 6. 三种机制，三种失效模式

| 机制 | 能抓 | 不能抓 | 为什么 |
|------|------|--------|-------|
| C3 verify（非参数化） | 行为不匹配、DPI-bound 伪造 | 不完整的 verify scope（错误 referent） | 执行交给它的指令 |
| C3 verify + 更宽 referent 检查 | 与实现行为不匹配的错误 referent（4/5） | 碰巧通过的错误 referent（1/5） | Verify 测试给它的 referent |
| Evidence 反馈循环 | Over-invalidation（意外的状态变化） | Under-invalidation（无变化 = 无信号） | 审计检测变化，不能检测缺席 |
| L3 人类审阅 | 以上全部 | 注意力预算、疲劳、偏见 | 没有机制代替人类判断 |

诚实的表述：这三种机制不是收敛到 100% 的管道。它们是三个不同的失效模式检测器，各有盲点，且盲点在一个地方重合——**under-invalidation 缺口**，它属于合约定义质量，归属人类审阅。

---

## 7. 这对架构意味着什么

Evidence Locker 模式增加了一个具体的工程构件：一个 **post-audit 层**，它在每次 C3 verify 之后运行，快照持久状态，并标记 verify scope 之外发生了变化的所有 key。

用 forge-verify 的语言说：
- **C3 verify** 执行人类撰写的 verify_command → 每个需求的 PASS/FAIL
- **Evidence 反馈** 运行 post-audit，比较所有已知 key 的 pre/post 状态 → 标记意外变化
- **合约精炼** 用标记的意外变化来扩大下次运行的 verify scope

诚实的收益：**over-invalidation 快速收敛**（flush、cascade、宽 scope 实现都产生可检测信号）。诚实的局限：**under-invalidation 不收敛**（碰巧工作的错误 referent 仍然不可见）。

这不是更聪明的审计能修复的。它是自动化验证的结构性属性：**你无法检测一个事件的缺席，除非你知道那个事件本应发生，而知道这个需要人类领域知识。** 缺口被命名了、被界定了、分配给 L3——这是设计的诚实工作，不是它的失败。

---

*实验脚本：*
- [`referent-mismatch-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 5 场景、单个 verify 命令、C3 抓取率 4/5
- [`evidence-feedback-loop-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 2 场景 × 8 轮、over-inv 2 轮收敛、under-inv 卡住

*结果：`results-v2/referent-mismatch.json`、`results-v2/evidence-feedback-loop-{A,B}.json`*

*上一篇：[第三个谓词：argument-space 验证实测](blog-agent-determinism-illusions-13.zh.md)*
*系列：[Agent 确定性幻觉系列](https://dev.to/zxpmail)*
