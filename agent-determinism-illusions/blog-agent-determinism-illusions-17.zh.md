<!--
  ─────────────────────────────────────────────────────────────────
  微信 / 知乎标题备选:
  第二轮：当回复触发了又一轮修订
  Xiao Man 的锚点搬家——探针无锚、系统仍有锚
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  When the reply triggers another revision — Xiao Man's anchor relocation
  ─────────────────────────────────────────────────────────────────
-->

# 第二轮：当回复触发又一轮修订

**Agent Determinism Illusions（第 17 篇）**

> **本文在系列中的位置：** 第 16 篇收了四条读者驱动的修订——Mike HHI pair-join、Tom Jones position-adjacency、Xiao Man shape-routing（rename_keys）、Mike quiet-failure。成稿之后、发布之前，Xiao Man 在 rename_keys 一节下回复了一条更锐利的修订：不是"选个更好的锚"，是"把锚点从探针的职责中移除"。本篇是对这一刀的回应——预言什么、在本 fixture 上确认什么、规则落在哪里。

---

## 1. 那一刀

Xiao Man 在 2026-07-30 的回复（rename_keys 节下）：

> 探针永远不应该重新查找路由器已经解析过的东西。Mutation suite 接下来的问题是："我们是不是不小心把查找职责放回了探针？"

两条可分离的论断：

- **探针层：** 如果路由器把解析过的路径直接传给探针（如"rename 后 services 在 `art['components']`"），探针不再做 key 名查找，按构造就是 rename-immune。
- **系统层：** 锚点不消失，只是从探针搬家到 declaration/router。新锚层有自己的生存问题。

Round-1 说：shape-routing 在 rename 下脆。Round-2 把刀磨利：修复不是换更好的锚，是重画 boundary。

---

## 2. Path-passing 探针——在 fixture 上确认

脚本：`probe-path-passing-redesign-test.py` → `results-v2/probe-path-passing-redesign.json`。

两种探针设计在同一组 rename_keys 总体上跑（T3 合法 artifact，`services → components` + 内层 rename，n=40，seed=7）：

| 探针 | 设计 | rename_keys 下 false_reject（n=40） |
|------|------|:---------------------------:|
| v1（现状） | 硬编码 `art.get("services")` | **100%**（40/40） |
| v2（重设计） | 路径由 declaration-aware 路由器传入 | **0%**（0/40） |

探针侧修复有效。探针从"查找器"变成"在已知坐标上的值检查器"。

**实现漏值得记。** v2 第一版只从路由器拿了 services 路径；内层 `timeout_ms` 仍然硬编码——而 rename_keys 同时把 `timeout_ms → request_timeout_ms`。结果 v2 照样拒绝全部。探针必须把**所有** rename 过的 key 都当作路由器解析过的路径接收，才能真正 rename-immune。这恰是 Xiao Man 命中的失败模式："我们是不是不小心把查找职责放回了探针？"

---

## 3. 声明层锚生存矩阵

脚本：`declaration-anchor-survival-test.py` → `results-v2/declaration-anchor-survival.json`。

探针侧修复是一半。另一半：新锚层（declaration/router）有自己的生存包络。四锚 × 八扰动；每单元是一次确定性解析检查，不是统计抽样：

| 锚 | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | 存活 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--------:|
| synonym_list | ✓ | ✓ | **✗** | ✓ | ✓ | ✓ | ✓ | ✓ | 7/8 |
| structural | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | ✓ | 7/8 |
| cardinality | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | **✗** | ✓ | 6/8 |
| cross_field | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** | 7/8 |

扰动：
- P0 基线；P1 services→components（同义列表内）；P2 services→instances（列表外）；P3 加噪声字段；P4 内层形状坏；P5 加第三条；P6 在 services 前插形状相同的 connections；P7 内层字段 rename（port→port_number）。

**没有锚跑完 8/8。** 每锚有独特失败签名：

- **synonym_list** 死于 declaration 外的 rename（P2）。窄但可预测。
- **structural** 死于形状克隆（P6）。无法在 shape 上把 services 和"也带 limits 的 list-of-dicts"区分开。
- **cardinality** 死于数量改（P5）和形状克隆（P6）。
- **cross_field** 死于内层字段 rename（P7）。语义结构在内层同义 rename 下断。

"宽"锚（structural、cross_field）抗 rename 是用"脆弱于形状克隆和内层 rename"换来的。**窄 ↔ 宽是 trade-off，不是单调改善。** 任何"X 比 Y 稳"必须标在哪种攻击下。

---

## 4. Boundary-leak detector 规则

Xiao Man 更深的重画——mutation suite 当架构违规检测器，不是 bug 抓手：

> rename_keys 不引入 defect，只换 key 名。如果系统 boundary 干净，rename 应该是 no-op；如果触发失败，必有人把 lookup 漏进了 probe。

写成 fixture 设计规则（`working-notes/boundary-leak-detector-rule.md`）：

> 任何带 router/probe 或 judge/lookup 分层的 fixture 必须包含一组**中性 mutation**——rename、position-permute、cardinality-preserve。中性 mutation 在设计上不引入 defect。中性 mutation 下的失败计为 **boundary leak**，独立于 catch rate 报。

中性 mutation 分类：

| Mutation | 做什么 | 失败说明 |
|----------|--------|----------|
| `rename_keys` | 同义 rename | 探针硬编码 key 查找 |
| `position_permute` | 交换兄弟节点 | 探针做了路由器没解析的 index-based lookup |
| `cardinality_preserve_add` | 加同形状 sibling | 锚用 cardinality 而非 cross-field 区分 |
| `inner_field_rename` | rename 内层字段 | 锚查的是键存在而非语义不变量 |
| `decoy_with_same_shape` | 插形状相同的 decoy | 锚只看形状 |

**这条规则是标签，不是框架。** 现有 fixture（rename_keys、decoy_nest、cue_erase、cross-model pair-join）已经在做中性 mutation——只是没这么叫。下一篇 fixture 应该在 docstring 末尾列出中性 mutation 清单，把 boundary-leak 计数当主指标之一报，跟 catch rate 并列。

这条规则**不替代** catch rate：零 boundary leak 的 fixture 仍可能 catch rate 错。两个指标相互独立。

---

## 5. 收束

Round-1 说：depth-from-shape 在 rename 下脆。Round-2 把刀磨利：

- **探针层：** 锚可以移除。Path-passing 重设计在 n=40、seed=7 上确认；探针按构造 rename-immune。
- **系统层：** 锚不消失，只搬家。Declaration/router 是新锚点，有自己的可测生存包络。
- **方法论后果：** 中性 mutation 是 boundary-leak 检测器。下一篇 fixture 应该把 leak 计数跟 catch rate 并列报。

Xiao Man 命名了架构原则。经验证据在本 fixture 上支持：探针变无锚；系统仍在另一层有锚；生存问题跟着锚走。

**探针无锚；系统在另一层有锚。这就是搬家。**

---

**系列：** Agent Determinism Illusions · 脚本：[GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**论证弧上一篇：** [第 16 篇 — 读者驱动的修订：四条咬回来的评论](https://dev.to/zxpmail/reader-driven-revisions-four-comments-that-bit-back-30p8)  
**评论线程起点：** [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) · [第 7 篇](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513)
