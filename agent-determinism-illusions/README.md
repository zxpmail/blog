# Agent Determinism Illusions — 实验与文章

用实验数据拆解 AI Agent 工程中流行的"确定性"神话,给出经过实证检验的生产级 Agent 设计原则。

## 快速入口

如果你是第一次来,按这个顺序读:

1. **[红线法则](/agent-determinism-illusions/blog-redline-principle.zh.md)**(独立文章,不依赖系列)——3 组核心实验,结论:生产级 Agent 需要客观收敛信号,不是更聪明的循环设计
2. **中文系列 5 篇**(含修正框架)——从拆靶子到给替代方案,一条完整弧线
3. **英文系列 4 篇**——dev.to/HN 准备就绪

## 文件清单

### 中文(5 篇)

| 篇 | 标题 | 核心 |
|----|------|------|
| 主文 | 我用四组数据拆穿了一篇 7000 行的「生产级」Agent 文章 | 靶子三刀 + embedding 自拆 |
| 续篇一 | …这次连我自己也拆了 | embedding 自拆展开 |
| 续篇二 | 0%假阳是个会骗人的指标 | 三档模型权衡曲线 |
| 续篇三 | 把「架构画了」当「问题解决了」 | 六刀拆自己的 Harness 方案 |
| 续篇四 | LLM 质量检查的替代方案：确定性路由 + 抽样 | 风险分流框架 + 三刀修正 |

### 英文(4 篇)

| # | dev.to 标题 | HN 标题 |
|---|-----------|---------|
| 1 | I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix. | Lexical overlap, temperature 0, phase gates: tested and failed |
| 2 | I tested 3 models as AI agent quality inspectors: the stronger the model, the more valid work it rejects | 3 model tiers as agent quality inspectors — the false-positive/false-rejection tradeoff |
| 3 | I designed a Harness to fix my agent's quality problem — then found 6 flaws in my own design | 6 flaws in a human-in-the-loop agent quality Harness |
| 4 | An alternative to LLM quality gates: deterministic routing + sampling | Risk-based agent output quality: an alternative to LLM quality gates |

### 红线法则(独立文章)

| 语言 | 标题 | 核心 |
|------|------|------|
| 中文 | 红线法则:生产级 Agent 的收敛条件 | 同一任务有红线 vs 无红线,收敛率 +78%(N=3 指示性) |
| 英文 | The Red Line Principle | objective stop signal outperforms LLM self-judgment |

## 实验脚本

`scripts/` 目录下 15 个可复跑 Python 脚本:

| 脚本 | 实验 | 依赖 |
|------|------|------|
| `lexical-overlap-test.py` | 词汇重叠阈值(30 对样本) | 无 |
| `temp0-determinism-test.py` | 温度 0 输出一致性 | API |
| `phasegate-formalism-test.py` | Phase Gate 假阳率 | 无 |
| `embedding-semantic-test.py` | embedding 同义/反义分离 | Ollama |
| `harness-verify-test.py` | 三档质检权衡(参数化,三后端) | Ollama/API |
| `trace-length-test.py` | Agent 轨迹审核时间 | 无 |
| `spc-behavior-test.py` | SPC 格式异常检测 | 无 |
| `spc-coldstart-test.py` | SPC 冷启动基线漂移模拟 | 无 |
| `routing-accuracy-test.py` | 路由分类准确率(40 条任务) | 无 |
| `redline-v2-experiment.py` | 红线对比实验(支持 `--task-file`) | Ollama/API |
| `handoff-protocol-sim.py` | 人工介入协议仿真 | 无 |
| `convergence-loop-test.py` | 收敛循环条件 | Ollama/API |

## 协议

MIT
