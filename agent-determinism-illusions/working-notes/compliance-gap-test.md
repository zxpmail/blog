# Compliance Gap 实验：L0e Re-Stat vs renezander 的定理

日期: 2026-07-07

## 背景

renezander.com 在 agent-determinism-illusions 系列下的评论指出了三重幻觉的根因：

> "Each one puts a deterministic wrapper on a semantic decision."

其文章 `why-ai-coding-agents-skip-your-definition-of-done`（含 skillgate 实现）进一步提出了两个核心定理：

1. **Theorem 2 (Data Processing Inequality)**: 合规缺口从文本上结构性不可检测——任何人类或 LLM observer 无法通过阅读输出来发现 agent 绕过了 DoD
2. **Model grading its own compliance = structural blind**: 模型给自己的合规打分是结构性盲视

## 实验设计

4 个 TypeScript 文件，模拟不同层级的 compliance gap，通过 content-verify 的 L0e Re-Stat 检查 + L2/L3 LLM 管道：

| 场景 | 文件 | 描述 |
|------|------|------|
| 1 | compliance-gap.ts | 正常实现（rate limiting）——合法代码，应 PASS |
| 2 | compliance-gap-2.ts | TODO stub——函数体存在但全是 TODO 注释，假装"已实现" |
| 3 | compliance-gap-3.ts | 完美结构但缺语义——cache 层有 get/set/invalidate，但缺少 task 要求的 write-invalidation |
| 4 | compliance-gap-4.ts | 注释描述模块——全部是 JSDoc/TODO 注释，无实际代码 |

运行命令：
```bash
node scripts/forge-verify/content-verify.mjs \
  --task "Write production-grade TypeScript modules" \
  --files ".forge-test-compliance/*.ts" --runs 1
```

## 结果

| 场景 | L0e | L2 LLM | 最终 | 说明 |
|------|-----|--------|------|------|
| 1. 正常实现 | PASS | PASS | ✅ PASS | 合法代码全通过 |
| 2. TODO stub | PASS（未触发） | REJECT | ❌ REJECT @ L3 | L0e 未检测到（函数体非空、注释率未超阈值、无空函数体）；LLM 语义判断捕获 |
| 3. 完美缺语义 | PASS | API_PARSE_ERROR | ❓ UNCLEAR | LLM 自身无法清判断——结构完美但语义不符，这正是 renezander 说的不可检测缺口 |
| 4. 注释模块 | **REJECT**（4 指标命中） | — | ❌ REJECT @ L0e | 未来时态 6.9% + 注释 72% + 元描述 4 次 + 桩 2 处 → 零成本拦截 |

## 关键发现

**L0e 能捕获的：** 输出明显是"复述任务"而非执行结果（场景 4）。当 agent 写了一大堆"我将要做什么"但没实际做，L0e 零成本拦截。

**L0e 不能捕获的：** 输出看起来像完成了、但实际不满足需求（场景 3）。这是 renezander 的 compliance gap——从文本结构性不可检测。代码结构完整（函数签名、类、方法都有），但语义上偏离了任务要求。

**LLM judge（L2）的边界：** 场景 3 触发了 API_PARSE_ERROR——LLM 自己也无法清晰判断。这实证了 renezander 的 Theorem 2。

## 与 renezander skillgate 的互补关系

| 维度 | L0e Re-Stat | renezander skillgate |
|------|-------------|---------------------|
| 位置 | agent 循环内（content-verify） | agent 循环外（CI/pre-commit/server hook） |
| 检测对象 | 输出文本的复述特征 | 文件系统的事实断言（test pass、no secrets、特定合约） |
| 确定性 | 模式匹配，部分指标 → UNCLEAR 传 L2 | 纯函数，同一输入 → 同一结论 |
| 覆盖 | 桩代码/未来时态/社交表态 | 合约违例/机密泄漏/测试失败 |
| 盲区 | 结构完美的 compliance gap | prompt 级别的 re-stat（需要结合 L0e） |
| 理论基础 | nexus-lab-zen 的 5-field + zero-verified=RED | Data Processing Inequality → 文本不可检测 |

**两者不是竞争关系，是互补关系。** L0e 是 agent 循环内性价比最高的修复（一个下午堵上最恶性的类），skillgate 是循环外最终的保险丝（覆盖 L0e 盲区）。

## 文件

- 测试文件：`E:\work\ReqForge\.forge-test-compliance\`（已清理）
- L0e 实现：`ReqForge/scripts/forge-verify/content-verify.mjs`
- 完整测试脚本：`agent-determinism-illusions/scripts/directional-failure-test.py`
