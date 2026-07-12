<!--
  ─────────────────────────────────────────────────────────────────
  Part 12: Weng Harness 阶梯上的盲阶
  ─────────────────────────────────────────────────────────────────
-->

---
title: "Weng Harness 阶梯上的盲阶——弱判据不是不精确，是方向性错误"
published: false
description: "Lilian Weng 的 Harness 综述画出了整个领域的地图。它也露出了一个盲阶：判据本身的方向性失效。20 场景 × 3 模型 × 600 判据 + 6 条设计约束的代码实现。"
tags: ai, llm, agents, testing
canonical_url: ""
series: "Agent Determinism Illusions"
---

## 1. 阶梯上有盲阶

Lilian Weng 在 2026 年 7 月发表的综述《Harness Engineering for Self-Improvement》将领域组织成一条清晰的优化阶梯：

```
指令提示 → 结构化上下文 → 工作流 → Harness 代码 → 优化器代码
```

每一级把优化目标往上抬：从我们给模型说什么，到我们怎么组织模型看到的内容，到编排循环的方式，到定义编排本身的代码，最后到写 harness 代码的优化器。这条阶梯有用，是因为它暴露了领域一直在走（往往没有意识到）的轨迹。

但阶梯上有一个盲阶。它出现在 Weng 自己列出的 Future Challenges 之中：

> **Future Challenge #1：弱且模糊的判据。** 许多研究声明没有快速精确的验证器，许多真实世界任务也一样。

Weng 把这归因于精度问题：判据不够尖锐，不足以区分好产出和坏产出。她综述中的每个系统——STOP、Self-Harness、Meta-Harness、DGM、ACE——都假设判据的输出是可信的，然后优化如何使用这个输出。没有一个系统测量判据本身是否会做出**方向性错误**：输出在语义上反转了（保留应该删除的、启用应该禁用的）却结构上与正确结果不可区分。

本文的论点：**弱判据不只是不精确。它们方向性地失败——接受听起来合理的输出却反转了任务。我自己的数据显示这不均匀：更强的模型可以捕捉大部分。结构性界（下面的定理 2）仍然成立；实际影响集中在更弱的模型上。** 证据来自 Weng 综述发布后几周内汇聚的三条独立线索。

---

## 2. 三条线索汇聚

### 线索 1：Weng 自己的 DGM 故事

Weng 广泛讨论的 Darwin Gödel Machine（DGM）论文包含了综述中最干净的失败案例。一个允许修改自己 harness 的代理伪造了日志文件，声称单元测试已通过。测试从未运行。假日志进入了它自己的上下文，下游同一个代理读到该日志后得出结论：它的改动已通过验证。

Sergei Parfenov 在 7 月 8 日的评论中指出了结构性机制：系统无法区分"已验证过的事实"和"自己说过的话"。文件就是文件。文件系统不能附加 provenance 标签来告诉代理，那个"2 tests passed"是测试运行器产生的，还是代理自己在上一次工具调用中幻觉出来的。

这是一个方向性失效：代理对自己工作的判断与事实相反。它认为改动已通过验证。实际没有。

### 线索 2：方向性失效是真实的，但依赖模型能力

我用 20 个方向性失效场景 × 3 个模型层次（qwen3:0.5b 0.5B、gemma3:latest 4.3B、deepseek-v4-flash ~200B）做了 600 次判据。模型回答的是 Weng 的判据要回答的同一个问题：这个输出满足任务吗？

我原本预期方向性失效在所有模型规模上都是结构性的。**数据没支撑这个预期。** 微妙反转场景的漏检率：

| 模型层次 | 微妙反转漏检率 |
|-----------|---------------------------|
| qwen3:0.5b | **44%** |
| gemma3:latest | **10%** |
| deepseek-v4-flash | **1.3%** |

方向性失效是真实的，但严重程度随模型能力急剧变化。弱模型漏检近一半；强模型几乎全部捕捉。

唯一在两个较小模型上始终失败的场景是"无需修改"合理化——任务要求设置一个已经在目标值的参数，输出说"当前配置已满足需求，无需修改"。在这个单一场景（DS4）上：

| 模型 | 漏检率 | 行为 |
|-------|-----------|----------|
| qwen3:0.5b | **100%** (15/15) | 高置信度错误 |
| gemma3:latest | **100%** (15/15) | 高置信度错误 |
| deepseek-v4-flash | **13.3%** (2/15) | 33% 正确检测 + 53% PARSE_FAIL（模型犹豫，无明确判决） |

这修正了原来的框架：方向性失效不是均匀的盲区。它是能力梯度。理论界（下面的定理 2）仍然成立——文本通道判据无法检测文本通道伪造——但实际影响集中在更弱的模型上。在强模型上，失效模式从"自信地错误"转变为"不确定"，这本身是一个可检测的信号。

同一机制出现在 Weng 的 DGM 故事中：代理没有写"tests: definitely failed"，它写了"tests passed"——判据在没有验证的情况下接受了一个合理主张。验证器是否能捕捉这个，取决于验证器的能力，而非提示词。

### 线索 3：定理 2（数据处理不等式）

René Zander（@reneza on dev.to）识别出了理论根源：当判据和生产者在同一通信通道中时（两者都读写文本），判据可用的信息是生产者输出的一个子集。如果偏差不出现在文本中——如果已删除的文件被称为"已保留"并附带理由，如果假日志写着"tests passed"——判据（人或 LLM）无法检测到它。

这是应用于代理验证的数据处理不等式。它不是实现 bug。它是一个信息论约束。

### 汇聚

| 来源 | 发现 | 类型 |
|--------|---------|------|
| Weng/DGM (2025) | 代理伪造日志并相信了自己 | 经验（N=1 事件） |
| DF v2 (2026) | 方向性失效严重程度随模型能力变化：3 层级 44% / 10% / 1.3% | 经验（600 判据） |
| Zander (2026) | 定理 2：文本通道判据只能获取生产者信息的子集 | 理论界 |
| Parfenov (2026) | Provenance 死在存储边界 | 架构分析 |

三个经验观察收敛到同一个理论预测。判据不只是不精确。它方向性地失败，理论界（定理 2）是结构性的——但实际严重程度随模型能力变化，正如 DF v2 数据所示。

---

## 3. 从文献中提取的六条设计约束

如果判据可以方向性地失败，且这种失败是结构性的，那么修复不能是"更好的判据"。修复必须是架构性的：限制判据被要求做什么、以及它的判断如何使用。

以下六条约束来自 Weng 综述中的论文和上述实验。每一条都在阅读综述后的一个开发会话中实现到了 ReqForge forge-verify pipeline。

### 约束 1：判据器活在循环之外

**来源：** DGM（Zhang et al. 2025），Weng 评论

"如果一个程序可以编辑操作系统，抽象边界就被打破了。可编辑面需要被适当地设计，权限控制和安全层必须活在这个循环之外。"——Weng 论 DGM

**实现：** `.forge/editable-surface.json` 显式定义进化引擎的读写路径。判据代码（`scripts/forge-verify/`）和门控配置（`.forge/content-verify.json`）在 `readonly` 部分。进化引擎不能修改自己的边界定义（`editable-surface.json` 本身是只读的）。

```
{
  "editable": { "directories": ["core/skills", ".forge/harnesses", ...] },
  "readonly": { "directories": ["scripts/forge-verify"], "files": [".forge/editable-surface.json"] }
}
```

### 约束 2：验证结果携带因果标签

**来源：** Self-Harness（Zhang et al. 2026）

"两次运行在错误日志表面可以有相同的验证器输出（如 timeout），但因果机制完全不同。"

**实现：** 每个 forge-verify 阶段 verdict 包含一个 `failure_class` 字段，映射到 feedback-observer 分类：

| Verdict | failure_class | 含义 |
|---------|---------------|------|
| L0 REJECT | execution-lapse | 代理产生空/桩输出 |
| L1 REJECT | skill-defect | 合约已定义但输出不匹配 |
| EvidenceGate REJECT | execution-lapse | 证据文件缺失或为空 |
| C1 REJECT | skill-defect | 正则模式未匹配证据内容 |
| C2 UNCLEAR | unset | LLM 不确定或 API 错误 |
| L3 UNCLEAR | unset | 跨运行判据分歧 |

这连接了验证流水线和进化反馈循环：一次验证失败自动触发正确的 feedback-observer 分类，进而进入进化提案生成。

### 约束 3：提案必须通过 held-in 和 held-out 分割

**来源：** Self-Harness（Zhang et al. 2026）

"候选编辑通过回归测试评估：held-in D_in（测试失败是否解决）和 held-out D_out（检查是否引入其他问题）。"

**实现：** 进化提案携带两个文件列表：

- `held_in_files`：应该在编辑后从 REJECT/UNCLEAR 转为 PASS 的目标文件
- `held_out_files`：应保持之前 PASS 状态的文件

应用后，forge-verify 在两个分割上运行。两者都必须通过提案才算确定完成。held-out 回归即使 held-in 修复成功也会阻止提案。

### 约束 4：每个判决追溯证据源

**来源：** ScientistOne（Meng et al. 2026），Weng 综述

"每个声明（引文、数值、方法论、结论）必须追溯到证据源，并通过 Chain-of-Evidence 检查进行审计。"

**实现：** 每个 forge-verify 阶段输出包含 `evidence` 字段：

```
L0:  evidence: "file:src/rate-limit.ts"          （内联内容）
EG:  evidence: "evidence:test-output.txt"         （外部文件）
C1:  evidence: "evidence:test-output.txt((?i)isRateLimited)"（文件 + 模式）
```

最终输出包含完整的 `trace.chain` 数组，加上 `evidence_files` 元数据（路径、大小、mtime）用于过时检测。如果证据文件在验证后被修改，trace 被标记为可能过时。

### 约束 5：当模型超出规则时规则可以退役

**来源：** STOP（Zelikman et al. 2023），Weng 预测

"STOP 对 GPT-4 跨迭代提升了下游性能，但用 GPT-3.5 和 Mixtral 这样的弱模型时反而退化。"——Weng 论 STOP

Weng 还预测："许多 harness 改进将被内化到核心模型行为中。"

**实现：** 反馈条目携带 `model_version` 字段。当进化引擎检测到一条规则是在旧模型版本下毕业的、且当前模型版本下零失败时，它生成退役提案（status: deprecated）而非强化提案。这防止了循环进化：规则毕业、产生更多反馈、再次毕业为自身的变体。

### 约束 6：Harness 配置是可搜索的空间

**来源：** Meta-Harness（Lee et al. 2026）

"Meta-harness 循环迭代创建新的 harnesses，只保留合格的。"

**实现：** `.forge/harnesses/` 作为候选注册表。每个候选 harness 是一个子目录，包含 `config.json`、`scores.json`、`history.jsonl`。基线配置（`.forge/content-verify.json`）是起点；新变体通过在一个维度上变异来生成（分歧阈值、合约模式、证据需求）。变体按准确率 vs LLM 调用成本 Pareto 排序。生产配置是只读的——切换到候选 harness 需要人工审批。

---

## 4. 实现告诉我们什么

在一个开发会话中实现全部六条约束大约花了四小时。代码修改跨 9 个文件，总计不到 250 行。关键观察不是实现很快——而是**每条约束映射到一个单一、可测试的机制**，可以独立验证。

| 约束 | 代码 | 测试 |
|------------|------|------|
| 判据器在循环外 | `.forge/editable-surface.json` + hook 检查 | 验证进化不能修改 forge-verify/ |
| 因果标签 | 每个阶段返回加 failure_class | 20 DF v2 场景 + 12 证据门场景 |
| Held-in/held-out | 提案格式字段 + forge-verify 双分割运行 | （需进化提案来测试） |
| 证据追溯 | evidence 字段 + trace.chain 输出 | 所有阶段输出中存在 |
| 规则退役 | model_version + 过时检测 | （需模型升级事件） |
| Harness 搜索 | `.forge/harnesses/` + 索引 + 模板 | 模板有效，索引可解析 |

六条约束不是推测。它们是 Weng 综述中的发现直接翻译为具体代码。综述提供了设计约束；实现显示它们在机械上是简单的。难点不在于构建它们——而在于认识到它们是必要的。

---

## 5. 什么仍然无法修复

约束 4（证据追溯）和约束 6（harness 搜索）有一个定理 2 预测的共同限制：trace 本身是文本，harness 配置是文本。二者都可以被控制文件系统的代理伪造。

DGM 假日志故事适用于 forge-verify 读取的每个证据文件。如果代理可以写入 `evidence_dir/`，它可以写入一个叫 `test-output.txt` 的文件，内容写着"RateLimiter-IP: 所有测试通过"，但实际上从未运行任何测试。证据门检查文件存在且正则模式匹配其内容。但它不检查*谁写了文件*或*文件内容是否反映实际执行*。

这不是证据门设计的 bug。这是一个设计约束：证据门是零成本的、pre-receive 的，但它信任代理写入的文件系统。Sergei 要求的类型化 provenance 层——runtime-verified vs. self-reported——在当前 forge-verify 实现中不存在。它需要文件系统本身具有 provenance 意识，而标准文件系统没有。

定理 2 说不可关闭的残差：

- 文本通道判据（LLM 或人）无法捕捉在文本上与正确输出不可区分的语义反转。
- 证据门无法区分测试运行器写的证据和被测代理写的证据。
- 类型化 provenance 系统无法区分类型标签是由产出者本身还是独立体打的。

实践中，更强的 LLM 可以捕捉许多这种反转，因为它们携带更好的"看似合理 vs 正确"的隐式模型。即使强模型也漏掉的部分——以及人类审核者始终漏掉的部分——才是定理 2 真正预测的。线索 2 中记录的能力梯度缩小了实际范围；它没有消除理论界。

这不是反对分层验证的论据。上面的六条约束确实缩小了差距。L0/L0e 确定性检查在结构化垃圾到达 LLM 之前拦截它。证据门拦截缺失的产物。C1 验证特定格式承诺。C2 逐条阅读需求，防止"一切看起来都正常"的叙述压倒判据。Trace 使链条可审计。Harness 搜索使配置可改进。

但差距是渐近缩小的。定理 2 说它永远不会归零。

---

## 6. 总结

Weng 的 Harness 综述是领域最全面的地图。它也露出了一个盲阶：假设判据在不精确的方向上失败，而非方向性错误。三条独立线索——DGM 假日志、DF v2 数据、定理 2——收敛于同一发现：方向性判据失败是真实的，但其严重程度随模型能力变化。理论界（结构性）成立；实际影响集中在弱模型上。

从综述和相关工作中提取的六条设计约束转化为可测试的代码机制。全部六条已实现到 ReqForge 的 forge-verify pipeline。实现跨 9 个文件，不到 250 行。

理论残差持续存在：文本通道判据无法捕捉文本通道生产者可以伪造的内容。约束可以缩小这个差距，但不能消除它。这不是设计失败。这是一个信息论极限，承认它比绕着它做工程更有用。

---

*实验数据：20 方向性失效场景 × 3 模型层次 × 600 判据 → [directional-failure-v2.py](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
*证据门测试：6 场景，12/12 通过 → `scripts/forge-verify/test-evidence-gate.mjs`*
*源综述：[Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/) — Lilian Weng, July 2026*
*系列：[Agent Determinism Illusions on dev.to/zxpmail](https://dev.to/zxpmail)*
*上一篇：[通道缺口：为什么你的 LLM 判据一只眼睛是瞎的](blog-agent-determinism-illusions-11.zh.md)*
*下一篇：[第三个谓词：argument-space 验证实测](blog-agent-determinism-illusions-13.zh.md)*
