---
title: "Key-space C3：关闭 referent 可博弈性的布隆过滤器——实测"
published: false
description: "两组实验验证 Mike Czerwinski 第 7 轮：write-time-resolution 通过 50% 的错误 referent，LLM 准确率 17%。解方：声明 key 空间而非单 key——key-space C3 抓到 5/5 wrong-referent。"
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent 确定性幻觉"
---

# Key-space C3：关闭 referent 可博弈性的布隆过滤器——实测

**Agent 确定性幻觉（第 11 篇）**

*2026-07-15*

第 10 篇识别了 C3 的一个结构缺口：当 write-time-resolution 产出一个 plausible-but-wrong key（"user:123" 而非 "session:abc"）时，C3 验证了选中的 key 并 pass——gate 接受了错误的 resolution，因为它在错误的 target 上做了机械验证。

Mike Czerwinski 主张这个失败属于 gate 而非上游。resolution 步骤是 gate 自身的机制，如果 gate 接受了一个 plausible-but-wrong key，失败发生在架构边界以内。

本文用两组实验测试这个主张，然后加上修复。

---

## 1. 实验 I：Write-time resolution 实测

### 设计

六个有意模糊 scope 的需求。每个有一个 true intent（应该发生什么）和多个可能的 resolution（agent 可能合理选出的 key）。C3 验证 agent 选的任何 key。

**Phase A（确定性枚举）：** 列举所有可能的 resolution，每个跑 C3。

| 场景 | 需求 | True intent | 通过 C3 的错误 resolution |
|------|------|------------|-------------------------|
| S1 | "用户数据变化时 invalidate 相关缓存条目" | 所有 user:* | 只查 user:123 → PASS（under-inv） |
| S2 | "写新数据前清除陈旧缓存条目" | 只 user:123 | （over-inv 被抓） |
| S3 | "如果 write 影响用户活跃 session，invalidate 缓存" | session:abc | user:123 → PASS（wrong-referent） |
| S4 | "更新用户资料时 invalidate 所有相关条目" | user:123 + profile:123 | 只 user:123 → PASS（under-inv） |
| S5 | "密码变更时 invalidate 用户安全令牌" | token:789 | user:123 → PASS（wrong-referent） |
| S6 | "权限变更时 invalidate 用户所有 session" | 所有 session:* | user:123 → PASS（wrong-referent） |

### 结果

**C3 拦截错误 resolution 率：6/12（50%）。** 但分布是关键：

| 错误类型 | 总数 | 通过 C3 | 被 C3 拦截 |
|---------|------|--------|-----------|
| wrong-referent | 4 | **3** | 1 |
| under-inv | 4 | 2 | 2 |
| over-inv | 3 | 0 | 3 |
| under-inv-empty | 1 | 1 | 0 |

*注：6 条"正确"resolution（每场景 1 条）被排除——C3 正确验证了它们，它们不是失败 case。6/12 的分母只统计错误 resolution。*

**Mike 的主张确认：4 个 wrong-referent 中有 3 个通过 C3。** S1、S3、S5：agent 选了恰好是触发器的 key，C3 验证它，pass。Gate 接受了错误 resolution，因为机械检查的 key 碰巧对齐了写操作，而不是需求意图。

Over-inv 是对称镜像：当 resolution 声明了比实现实际触碰的更多的 key 时，C3 正确 FAIL。Over-inv 产生可检测证据（resolution 声称应消失但实际存活的 key）。Under-inv 和 wrong-referent 不产生。

**Phase B（LLM 执行 resolution，deepseek-v4-flash）：** 让模型读每个模糊需求，产出具体的 key 列表。

| 场景 | 模型选择 | 正确？ |
|------|---------|-------|
| S1 | user:123 + profile:123 + admin:123 | ❌ mixed |
| S2 | user:123 + profile:123 + admin:123 | ❌ over-inv |
| S3 | [] | ❌ 空（保守拒绝） |
| **S4** | **user:123 + profile:123** | **✅** |
| S5 | [] | ❌ 空 |
| S6 | [] | ❌ 空 |

**LLM 解析准确率：1/6（17%）。** 模型要么过度 invalidate（加无关 key），要么不足 invalidate（返回空——保守拒绝）。只有 S4 正确解析。

这给 Mike 的担忧加上了一个硬数字：在 write-time resolution 中，agent 在这个测试集上 83% 的情况是错的。Gate 对其中 50% 的错误无声 pass。

---

## 2. 布隆过滤器思路

结构模式是一个 **membership test** 问题。Single-key C3 问"cache[k] 消失了吗？"——一个点检查，agent 命名什么 k 就通过什么 k，不管 k 对不对。

修复：声明 **key 空间**而非单 key。"user:*" 而非 "user:123"。C3 在写操作后检查该空间内的**所有** key。这类似于缓存上游的布隆过滤器：你不问"这个特定 key 存在吗？"——你问"声明空间中有任何 key 存在吗？"

合约字段变成：

```json
{
  "id": "REQ-3",
  "desc": "缓存写时失效",
  "verify_command": "node .forge/verify/write-invalidation.js",
  "verify_keyspace": "user:*",
  "type": "argument-space"
}
```

C3 迭代 `keys_in_space("user:*")` → `["user:123", "user:456"]` → 验证写后两者都不存在。

---

## 3. 实验 II：Key-space C3

### 设计

同样的 6 个场景。每个有声明好的 key 空间。两种 C3 模式：

| 模式 | 回答的问题 |
|------|----------|
| Single-key C3 | "cache[k] 在 write(k) 后消失了吗？" |
| Key-space C3 | "空间 S 中的**每一个** key 在 write(k) 后消失了吗？" |

三种缓存实现：
- **LiveCache：** write(k) 只删除 k（定向删除，默认 under-inv）
- **BulkCache：** write(k) 删除所有匹配 k 前缀的 key（前缀级删除）
- **FlushCache：** write(k) 删除所有（极端 over-inv）

### 结果

| 模式 | 缓存 | Wrong-ref 捕获 | 比例 |
|------|------|---------------|------|
| single-key | 任意 | 0/5 | **0%** |
| **key-space** | **LiveCache** | **5/5** | **100%** |
| **key-space** | **BulkCache** | **4/5** | **80%** |
| key-space | FlushCache | 5/5 | 100% |

**Key-space C3 在 LiveCache 上抓到 5/5 wrong-referent。** 所有 single-key C3 看不见的错误 resolution，在 C3 检查声明空间时都被捕获。

BulkCache 那一次"漏"（S1：空间 `user:*`，触发器 `user:123`）是**预期的正确行为**：触发器前缀匹配空间，BulkCache 正确 invalidate 所有 user:*，gate 通过。Resolution 正确、实现处理了空间、gate 确认了它。

**每个场景的工作机制：**

| 场景 | Agent 解析为 | 声明空间 | Key-space C3 检查 | 结果 |
|------|------------|---------|------------------|------|
| S1 | user:123 | user:* | user:123 ✅ user:456 ❌（存活） | FAIL |
| S3 | user:123 | session:* | session:abc ❌ session:xyz ❌（未 invalidate） | FAIL |
| S4 | user:123 | user:*,profile:* | user:123 ✅ user:456 ❌ profile:123 ❌ | FAIL |
| S5 | user:123 | token:* | token:789 ❌（未 invalidate） | FAIL |
| S6 | user:123 | session:* | session:abc ❌ session:xyz ❌（未 invalidate） | FAIL |

每次，agent 的错误 resolution 都被捕获，因为声明空间包含写操作未触碰的 key。

---

## 4. 剩下的边界——实测

Key-space C3 要求 key 空间**可声明**。边界问题是：不可声明类在真实需求中到底有多大？

我跑了语料分类实验：35 条来自 cache invalidation、authorization、write-path 领域的需求。每条由人肉 ground truth（能声明 key 空间吗？）和自动化分类器（确定性规则）分别判断。

### 人肉 ground truth

| 类别 | 数量 | 比例 |
|------|------|------|
| 可声明 | 20 | 57% |
| 部分（需人解决） | 7 | 20% |
| 不可声明 | 5 | 14% |
| 域外（UX/ops/freshness） | 3 | 9% |

### 不可声明类——到底是什么？

8 条不可声明 + 域外的 case，**没有一条是 cache write-path 需求**：

- **Freshness/时序属性**（3）："eventually consistent"、"latest state"、"latest hierarchy"
- **UX/鲁棒性声明**（2）："gracefully handle cache misses"、"feel responsive"
- **非 write-path 机制**（2）：TTL 过期、数据完整性一致性
- **分布属性**（1）："synchronize across all nodes"

**这些都不属于 C3 域。** 它们不是 write-path cache invalidation 需求——在路由步骤就被分类错了。

### 部分类——可解决吗？

| 子类型 | 数量 | 解法 |
|-------|------|------|
| 需要依赖追踪 | 3 | `SELECT session_id FROM sessions WHERE user_id = ?`——架构上可解决 |
| 需要意图推断 | 4 | "relevant"、"related"、"stale"——需要人类判断 |

### 自动化分类器

分类器（确定性模式规则）与人肉 ground truth 的精确一致率 66%——不足以无人值守运行。它偏向保守（8 条人说"可声明"它说"部分"），拖慢节奏但不重新打开缺口。关键方向：**零条 false undeclarable**——分类器永不说"不能声明"当人说能声明时。反方向有 1 条 false-declarable，所以分类器是一个保守的初筛——接受"可声明"判决前需人工复核。

### 这意味着什么

会重新打开 Part 10 under-inv 缺口的"空间不可声明"类——**在真正属于 C3 域的需求中，小且有界**。35 条语料中，5 条（14%）即使人也无法声明——freshness、时序、分布属性，没有 key 空间表达式能捕获。另有 3 条（9%）域外（UX/ops/数据完整性）本不该进入 C3 管线。

诚实的边界从"不可声明空间的大小"转移到了**"路由进入 C3 的准确性"**——门禁上游的一个分类问题，由同样的采样层处理，但不是 key-space C3 本身的结构缺口。

---

## 5. 这对架构意味着什么

| 机制 | 应对的缺口 | 捕获率 | 剩下的边界 |
|-----|----------|--------|-----------|
| Single-key C3 | DPI-bound 伪造 | 5/5（Part 9） | Referent 可博弈性（0/5） |
| **Key-space C3** | **Referent 可博弈性** | **5/5** | **路由到 C3 的准确性（非空间大小）** |
| Evidence 反馈循环 | Over-invalidation | 2 轮收敛 | Under-inv 不可见 |
| 采样 | 所有残余缺口 | — | 固定成本，无自适应信号 |

从 single-key 到 key-space C3 的移动是结构性的改进：它把问题从"这一个 key 变了吗？"改为"声明空间被覆盖了吗？"——并以此关闭 Mike 识别的 wrong-referent 缺口。

Part 10 的三种机制（C3、evidence 反馈、L3 人类审阅）现在有了第四个：**key-space 声明**。这不是一个新机制——它是一个更精确的合约字段，约束 C3 迭代的范围。布隆过滤器的类比成立：对声明空间的 membership test 强于点查找，声明空间（而非隐含它）使合约的 scope 显式化。

诚实的声明：**对可声明空间，wrong-referent 可博弈性已被结构性地关闭。** 35 条语料给出残余的数字：14% 人也无法声明，9% 被错误路由，剩余 77% 要么现在就可声明（57%），要么可通过依赖追踪解决（20%）。边界不是空间大小，而是路由进入门禁管线的准确性。

---

*实验脚本：*
- [`write-time-resolution-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 6 场景 × resolution 枚举 + LLM 阶段
- [`key-space-verify-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 6 场景 × 2 C3 模式 × 3 缓存实现
- [`space-declarability-test.py`](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts) — 35 条语料 × 人肉 × 自动化分类器

*结果：`results-v2/write-time-resolution.json`、`results-v2/key-space-verify.json`、`results-v2/space-declarability.json`*

*上一篇：[argument-space 验证的诚实边界——以及 Evidence Locker 补了什么](blog-agent-determinism-illusions-10.zh.md)*
*系列：[Agent 确定性幻觉系列](https://dev.to/zxpmail)*
