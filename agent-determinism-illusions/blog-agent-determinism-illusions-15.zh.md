<!--
  ─────────────────────────────────────────────────────────────────
  微信 / 知乎标题备选:
  D+T2 只决定谁进门；预算决定谁被看见
  进了升级队列还不等于被审到——流内排序实验
  ─────────────────────────────────────────────────────────────────
-->

# D+T2 只决定谁进门；预算决定谁被看见

**Agent Determinism Illusions（第 15 篇）**

> **本文在系列中的位置：** 本篇**不**延续第 8 篇的通道缺口 / skillgate（该编号下仍未发）。它延续 [第 7 篇](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513) 的升级线——以及 [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) 评论区里 Alexey Spinov 与 Mike Czerwinski 推过「选哪条流」之后的问题。编号跳到 15 是有意的：第 8–14 篇已占用其他弧；这里的发布顺序是 7 → **15**。

第 7 篇收束在：分歧留下；T1/T2 加入；它们都不是 novelty 臂。那回答的是 **谁进入** escalate 集合。它不回答：集合大于人工预算时，谁先被看见。

在第 6 篇线程里，Alexey 给出 wiring 警告：无序合并 D∪S 在 2% 预算下可能抓得比纯 D 还少；Mike 把开放问题凝成 **rank-inside-stream**——coverage-limited 是历史建成的 trigger R 的 load-bearing 属性，其时尚无人提出设计。

我们不在 Alexey 的 720 格上复现——那是他的参数模型（π·h·r_m），不在本仓库。在 df_proxy 上跑了一个相关检验（`scripts/merge-displacement-grid-test.py`），结果是**结构性 NULL**：D 流（conf<0.9）在该 fixture 上 miss-starved——qwen3-0.5b 上 D 流 115 条只 2 MISS，gemma3 上 147 条零 MISS；三个模型、八个预算点、四种合并之选——九十六格内，D@arrival 无一大于零。位移形态无处触发。此即发现本身：真实单 judge 输出上 D 流没有可被稀释的 miss 体积。

本篇转向更弱的命题：rank 在**任何** escalate 流内能否动针，并描出双线生产形态应有的轮廓。

---

## 1. Floor volume 压过「选哪条流」

一旦 escalate 流里的真阳性超过预算 `k`，任何 trigger 定义都给不出「谁被看见」。Class 过滤不能在不丢掉 trigger 要抓的失败的前提下缩小 TP 体积。分歧 / class / UHC / 混合之争，次于**硬顶下的队列顺序**。

第 7 篇的 D+T2 在已测 fixture 上仍是对的**进队**策略。它不是排序策略。

---

## 2. Rank-inside-stream（存在性）

脚本：`scripts/rank-inside-stream-test.py` → `results-v2/rank-inside-stream.json`。

DF v2 全量 runs（N=585），预算 1%/2%/5%：

- **Floor-volume 成立：** B=2%（k=11）时，oracle 在胖流上仍留约 80+ / ~92–94 个 TP 看不见。
- **可部署代理能动针：** 留一法 `P(MISS|class)` 在 6/18 格胜过 arrival；D+T2 在 5% 上 arrival 10 → loo 29（= oracle）。
- 自然 multiperspective（N=60）撑不起可部署主张；但仍显示 arrival 的残酷：B=5% 时 UHC∧class 捕 3，D+T2 捕 0。

开放问题由此坐实：同一条流、同一个 B，只改顺序，捕获就变。

---

## 3. Ranker 能否「上线」？预注册门禁

脚本：`scripts/ranker-prod-acceptance-test.py` → `results-v2/ranker-prod-acceptance.json`。

候选 **R_hist**：训练窗 `P̂(MISS|class)`；未见 class → 全局先验。不偷看本条标签。

门禁 G0–G6（压力扫描里加 G7）：holdout MISS 量；≥ arrival；在构造队列上赢过启发式基线；合并非劣；LOMO；冷启动；**排序 headroom**（arrival < oracle）。

**分层 holdout 上自然 D+T2 是 29/29 全 MISS**——arrival 已等于 oracle；G6 失败；那里的 SHIP 会是空通过。故决定性测试**构造**稀释 escalate 队列：holdout 全部 D+T2 MISS + 非 MISS 干扰项 ≈ 35% miss-rate，干扰项先到。

该测试上：**SHIP**——B=5% k=8，arrival **0** → R_hist **8** = oracle **8**。

范围 caveat 写死：证书只覆盖这批流量 + 这些 B + 这种稀释压力——不是通用生产许可证。

---

## 4. 压力：稀释扫不倒 hist；时间切会倒

脚本：`scripts/ranker-acceptance-stress-sweep.py` → `results-v2/ranker-acceptance-stress-sweep.json`。

轴：特征 × 稀释 miss-rate（15%→95%）× holdout（分层 / 模型内时间 / 全局时间）。G7 挡住 0=0 SHIP。

**分层：** R_hist / R_hist_conf 在**所有**扫过的稀释率上 SHIP（其他候选不是——如 R_conf_asc 在 0.95 处 NO_SHIP）。35% 不是刀刃侥幸。

**模型内时间**（每模型前 70% → train）：R_hist 在 **15–65% NO_SHIP**（G2/G7——hist 抓 0，conf_desc 满载）；只在稠密队列 80–95% 恢复 SHIP。全局时间仍 G0 失败（miss_test=1）。

读法：稀释压的是混合比与到达序，class 表仍可用。时间 holdout 压的是**表是否仍校准**。过期的 `P(MISS|class)` 把真 MISS 排到干扰项后面；高置信排序碰巧对上本 fixture 的 miss 形状。没有单一特征处处 SHIP。

---

## 5. 双线运维：Trigger∥Rank 与 Shadow∥Enforce

脚本：`scripts/dual-line-ops-sim.py` → `results-v2/dual-line-ops-sim.json`。

生产双线不是比喻：

| 线 | 职责 |
|----|------|
| **Trigger** | 谁进队 |
| **Rank** | 预算 `k` 下谁被看见 |
| **Shadow** | ranker 本会审谁 |
| **Enforce** | 人实际审谁 |
| **Fallback** | 影子抓 0 且 oracle>0 → 留在 arrival |

**分层 + 稀释 35%：** 固定 diluted 上 Rank lift（R_hist − arrival）打平/压过「只换 trigger（arrival 序）」；影子 hist lift +3/+8——**SUPPORT 双发布**。

**模型内时间：** R_hist lift 0；arrival 下最佳 trigger 是 T2（捕 3/8）——表过期时 **Trigger 旋钮赢**。影子 hist 空转 → **fallback_arrival**；safe ≥ enforce。（conf_desc 影子本可 lift——特征选择仍重要。）

---

### Update (2026-07-29)：conf_desc 是 fixture 形状；agree-set 镜像（Tom Jones）

[Tom Jones](https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g) 在 agree-set、provider 改名时间塌缩、G6/G7 余量、以及开放问题上追问：

> 你们的模型内时间 holdout 里，高置信排序碰巧对齐了 fixture 的 miss 形状。你知道那是 fixture 性质，还是置信度降序抓住了该模型何时失败的真实规律？两者对 conf_desc 能不能当安全 fallback 线，含义相反。

**1. conf_desc 拆因**（`conf-desc-miss-shape-test.py` → `results-v2/conf-desc-miss-shape.json`）

同一套 DF v2 落盘。稀释升级队列（约 35% miss；低置信拒绝作干扰项且排在前，使 arrival 在小 k 上捕获 ≈ 0）：

| 切割 | 结果 |
|------|------|
| 原始 | conf_desc 在 **9/9**（模型 × B）格上击败到达 |
| conf↔槽位置换 | conf_desc 相对 *random* 的优势塌掉（原始 **+1.56** → 置换 **−0.89**） |
| 跨模型借置信 | **5/6** 对不稳定 |

读法：「碰巧对齐」可复现，且是 fixture 的联合分布 `(conf, miss)`——同一落盘已有 95.8% MISS 在 conf≥0.9（偏 qwen）。**conf_desc 不是安全的通用双线 fallback 许可证。** Shadow 变空洞时 fallback 仍 fail-closed 到到达；conf_desc 可以当 shadow *候选*，不是安全地板。

**2. Agree-set HaluEval 镜像**（`agree-set-halueval-probe.py` → `results-v2/agree-set-halueval.json`）

分层 n=70，seed=7，DeepSeek-v4-flash × 本地 gemma3:latest（不是 Tom 的 70B 对——同题型、不同档）。跨模型可用 n=52（解析失败剔除后）：

| 指标 | 值 |
|------|-----|
| 同意率 | 78.8% |
| P(wrong\|agree) | **19.5%**（8/41），Wilson 95% **[10.2%, 34.0%]** |
| qa / summarization | 7.7% / **40%** |

与 Tom 的 27.5% [16.1, 42.8] 同属定性警告：自动放行车道可以驮着不可忽略的错误质量；这里 summarization 更差。**不要**把 P(both wrong\|disagree)=0 当证据（此处 0/11；二值 + 单一金标下的构造——Tom 的 caveat）。

同模镜像：gemma×gemma 在 temperature 0 上同意 100%（70/70）——多半是确定性。可控后端下有信息量的差距：同(1.00) − 异(0.79) ≈ +0.21。Tom 的静默 provider 改名仍是更干净的时间实例；这里只是可控的同/异模楔子。

**3. G6/G7**——同意。空洞 SHIP 比一个错数字更糟；先证明有余量再认赢，正是这些门存在的理由。

---

## 收束

第 7 篇命名了谁进门。Alexey 命名了不可缩的 floor。Mike 把开放问题凝成 rank-inside-stream。离线套件说：

1. 预算下的顺序是 load-bearing 的。  
2. 玩具 hist ranker 能在*构造*稀释队列 + 分层 holdout 上通过预注册门。  
3. 同一候选在时间样 holdout 上塌掉——所以 SHIP ≠ 可上线。  
4. 双线是贴合数据的运维形态：Trigger 与 Rank 分开；Shadow 先于 Enforce；影子空转则 fail-closed。

Tom 的追问把 (4) 钉得更锋利：**本 dump 上 conf_desc 对齐 miss 形状是 fixture 联合，不是安全 fallback 律**；即使在更小模型档，HaluEval 探针上的 agree-set 错误质量也是真的。

**D+T2 点名谁进场。预算点名谁被看见。Rank 是可校准、可降级的线——不是另一根绊线。conf_desc 不是安全地板。**

本文不主张：生产标签、agent 博弈、线上 catch@k 置信区间，或 R_hist 就是正确的生产打分器。那些是产品门禁（影子周、滑动重估、真实审结）——不是本 fixture。

---

**系列：** Agent Determinism Illusions · 脚本：[GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**论证弧上一篇：** [第 7 篇 — 分歧升级捞错了人](https://dev.to/zxpmail/divergence-escalates-the-wrong-population-unanimous-misses-auto-pass-1513)  
**评论线程起点：** [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)
