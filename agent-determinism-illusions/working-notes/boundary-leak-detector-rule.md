# Boundary-leak detector rule (fixture-design standard)

## 规则

任何带"探针-路由"或"判定-查找"分层的 fixture 必须包含一组**中性 mutation** 单元。

中性 mutation 在设计上**不引入 defect**——它们只换 key 名、调位置、保数量、改同义字段。如果系统在中性 mutation 下触发失败，那不是 defect 被漏抓，是某层偷偷做了它不该做的 lookup。中性 mutation 的失败计数 = **boundary leak 计数**，独立于 catch rate 报。

## 为什么

来源：Xiao Man 2026-07-30 refinement on rename_keys cell——
> "The probe should never re-find what the router already resolved. The mutation suite then becomes: did we accidentally put lookup responsibility back into the probe?"

把 mutation 从"抓 bug"重定向到"抓架构违规"。rename_keys 不引入 defect，只换 key 名。如果系统 boundary 干净，rename 应该是 no-op；如果触发失败，必有 lookup 漏进 probe。

## 中性 mutation 分类

| 类型 | 做什么 | 不该破坏什么 | 破坏了说明什么 |
|---|---|---|---|
| **rename_keys** | 同义 rename（services→components, timeout_ms→request_timeout_ms） | router 解析 + probe 验值 | probe 硬编码 key 查找 |
| **position_permute** | 交换兄弟节点顺序 | 结构性断言（cardinality、type） | probe 做了 index-based lookup router 没解析 |
| **cardinality_preserve_add** | 加同 shape 的 sibling | router 选择正确的 root | anchor 用 cardinality 而非 cross-field 区分 |
| **inner_field_rename** | rename 内层字段（port→port_number） | cross_field anchor | anchor 检查的是字段存在而非语义不变量 |
| **decoy_with_same_shape** | 插入形状相同但非 services 的字段 | router 区分语义 root | anchor 只看形状不看交叉不变量 |

## 已有 fixture 对应（inventory）

| Fixture | 中性 mutation 单元 | Boundary leak 表现 |
|---|---|---|
| `probe-shape-routing-rename-keys-test.py` | rename_keys | 探针硬编码 `art.get("services")` → rename 后 false_reject 100%（lookup 漏入 probe） |
| `probe-artifact-shape-routing-test.py` | cue_erase / decoy_nest | router 用 key 名 + cross-field 混判 → 中性 mutation 下路由翻转 |
| `probe-path-passing-redesign-test.py` | rename_keys + out-of-decl rename | v1 probe lookup 漏；v2 path-passed 无漏；router 端 declaration 锚死于 out-of-decl |
| `pair-join-empirical-test.py` | cross-model（services rename 跨模型语义差异） | qwen3 independence 是 within-model；cross-model 下 cell 反转——这是中性 mutation 暴露的 anchor 假定 |
| `declaration-anchor-survival-test.py` | P1-P7 全套中性 mutation | 每 anchor 有独特失败签名，无锚 8/8——boundary leak 模式可枚举 |

## 应用规则（下一篇 fixture 怎么做）

任何新 fixture 满足以下三条之一即触发规则：

1. 包含 router（路径解析、等级判断、路由判定）+ probe（值检查、断言）的分层结构
2. 包含 LLM judge + harness-label 的双层（apology 文章形态——DS4 的 harness-label bug 就是 boundary leak）
3. 包含 anchor 选择（key name / position / cardinality / cross-field）

写 fixture 时：

- 在 docstring 末尾列**中性 mutation 单元清单**（每个一行：mutation 名 + 期望 boundary leak 计数 = 0）
- 跑完后报两组数字：catch rate（缺陷检测）+ boundary leak count（架构合规）
- 如果 leak count > 0，**不允许**只解释为"defect 难抓"——必须指出哪层做了它不该做的 lookup，给出修复方向（path-passing / declaration / structural anchor）

## 反例（什么不算中性 mutation）

- 加 defect：往 services[0].limits.max_connections 改成 999。**不是中性**——这是 defect-introducing，应该让 catch rate 升高。
- 删字段：删 services[1]。**不是中性**——破坏了 cardinality，应被 cardinality anchor 抓。
- 改类型：把 services 改成 dict 而非 list。**不是中性**——破坏了 type anchor。

中性 = 只换可换的（name、位置、同义、形状相同但语义不同的克隆）。**只动 anchor 假定不动的属性，不动 anchor 假定要检查的属性。**

## 不造框架

现有 fixture 的 mutation 单元已经在做这件事，只是没用"中性 mutation / boundary leak"这个标签。把标签贴上、规则写进这篇 note，下一篇 fixture 自然按这个标准设计——成本接近零。

真正的 framework 化（统一 mutation DSL、leak-count 仪表盘）等系列再走两三篇再考虑。现在抽象太早会脱离具体场景。规则先用，framework 等证据再积累。
