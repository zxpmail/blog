<!--
  ─────────────────────────────────────────────────────────────────
  微信 / 知乎标题备选:
  读者驱动的修订：四条咬回来的评论
  四位读者、四个挑战、四道 fixture 边界
  ─────────────────────────────────────────────────────────────────
  HACKER NEWS:
  Four readers, four challenges, four fixture limits named
  ─────────────────────────────────────────────────────────────────
-->

# 读者驱动的修订：四条咬回来的评论

**Agent Determinism Illusions（第 16 篇）**

> **本文在系列中的位置：** 第 15 篇收束在双线运维——Trigger∥Rank、Shadow∥Enforce、影子空转时 fail-closed 回退到到达。发布后四位读者跑了四个挑战。每一条都点名了原篇没覆盖的一道 fixture 边界。本篇收四处实验、四处让步、四处范围收窄。

第 15 篇的 Update 已经吃过一条——Tom Jones 的 conf_desc 挑战（"fixture 联合，不是安全 fallback 律"）。本篇收的是发布之后来的四条。每条是不同类型的 fixture 盲点。

---

## 1. Mike Czerwinski — HHI 对子联合不是集中度信号

Mike 的推：我的 defect-class 集中度数字用了 class 标签上的 HHI。生产相关的切分是对子联合——`P(route ∧ CD | MISS)`——route 变更是否在**同一次 miss 内**与 defect-class 变更共聚。标签上的 HHI 看不到对子联合；只有 per-trial 2×2 列联能。

脚本：`pair-join-empirical-test.py` → `results-v2/pair-join-empirical.json`。qwen3:0.6b 上每 trial 三探针（V：verdict 定义 MISS；R：routing 审计；C：defect 分类器）。20 场景 × N=5 × 3 探针 = 300 次调用。

10 个场景上 30 个 MISS 的结果：

| | CD=0 | CD=1 |
|---|---|---|
| route=0 | 12 | 3 |
| route=1 | 11 | 4 |

对独立的 lift：**1.14**。联合 HHI：0.322。场景 HHI：0.124。

读法：对子联合本质独立——route 变更在 miss 内不与 defect-class 变更共聚。Mike 说对子联合是生产切分，他对；经验答案是，没集中度可榨。

**修订：** 去掉标签上的 HHI。如果对子联合集中度在运维上重要，用 per-trial 列联实测，不要用标签聚合。

---

## 2. Tom Jones — 位置邻接是模型与指令相关的

Tom 的推：在他的 fixture 上，紧贴问题的注释（位置 100%）被服从 60/60，其他位置在 80–85%。边缘 padding（12 条间隔）抹掉了端点优势。被加权的不是预算位置而是**与问题的邻接**。两道过滤：预算点名谁被看见；邻接点名谁被服从。

干净、可泛化的论断。试图复现。

脚本：`position-adjacency-obedience-test.py`（v1，BANANA 前缀）与 `position-adjacency-obedience-v2.py`（v2，大写覆盖）。

**v1**（BANANA 前缀，二值任务）：glm-5.2 与 qwen3:0.6b 全位置都顶在 100%——无方差。Tom 的二值饱和 caveat 预言了这个——二值任务上同模型臂接近 1.0。

**v2**（大写覆盖，持续约束，逃出天花板）。deepseek-v4-flash，K=12 内块，200 次调用：

| 条件 | pos=0 | pos=25 | pos=50 | pos=75 | pos=100 |
|---|---|---|---|---|---|
| no_padding | 95% | 75% | 90% | 90% | 85% |
| with_padding | 80% | 75% | 95% | 85% | 85% |

位置 100（紧贴问题）不是最高——85% 对位置 0 的 95%。位置 25 在两种条件下都最低——中段下凹，不是端点优势。边缘 padding 没有系统改变服从率。

读法：Tom 的 60/60 在他 fixture 上是真的。在我这个上形态不同——效应看起来是模型与指令相关，不是普适。和第 15 篇 conf↔槽位置换同形：边缘不迁移。概念切分（两道过滤：被看见 vs 被服从）仍成立；第二道过滤在生产流量上仍未测。

**修订：** 不要把位置邻接当定律——在更多模型与指令类型上复现之前，称其为 fixture 性质。

---

## 3. Xiao Man — 从 artifact 形状推深度信号不稳定

Xiao Man 的推：cascade 的"按 keys 推深度"规则（budget → P4，services[] → P3）在 schema 上确定性且便宜，但确定性是建立在表层形状上的——恰恰是 adversarial artifact 可以重写的。把"稳定指代"测试往上挪一层：不要问"这个 case 有没有稳定指代"——问"深度信号在小幅形状扰动下稳不稳？"

三个扰动单元、两条失败轴：

| 扰动 | 干什么 | 对路由的影响 | 失败轴 |
|---|---|---|---|
| cue_erase | 抹掉 budget 提示，强制造错指纹残留 | 80/80 路 T4 → T3 | catch 100% → 82.5% |
| decoy_nest | 往 T2 注入装饰性 services[] | 80/80 路 T2 → T3 | catch 100% → 0% |
| rename_keys | T3 上 services → components，schema 同义 | 80/80 路 T3 → T1 | 两臂均 false_reject 100% |

rename_keys 单元比预期更糟：不仅形状路由断，探针层也断——`probe()` 硬编码 `art.get("services")`，所以 fixed_matched 也输。两层 key-coupled。

脚本：`probe-artifact-shape-routing-test.py`（cue_erase / decoy_nest）→ `results-v2/probe-artifact-shape-routing.json`；`probe-shape-routing-rename-keys-test.py` → `results-v2/probe-shape-routing-rename-keys.json`。

**修订：** 不要从形状推深度；以固定的中深度探针作基线；探针信号跨字段时再升级。基线探针锚到结构不变量（校验和 fixture），不锚到 key 名。

---

## 4. Mike Czerwinski — 静默失败的回退缺口

Mike 的推：回退触发 `shadow 抓 0 且 oracle > 0` 在做实事，但它漏了更安静的失败——shadow 抓到了东西（非零），只是抓到的全是错的。shadow 抓 0 响亮、好回退。shadow 抓一个非零但错的数字，是更难的场景。

第 15 篇的回退规则（`dual-line-ops-sim.py` 第 346 行）：

```python
if shadow_c == 0 and oracle > 0:
    return enforce, "fallback_arrival"
return shadow_c, "shadow"
```

缺口：`shadow ∈ (0, enforce)`——shadow 仍抓东西，但比 enforce 本会抓的少。空转检查从不触发；双线发布了一个妥协的 rank。

### 纯数学扫描

脚本：`partial-stale-shadow-test.py` → `results-v2/partial-stale-shadow.json`。oracle=8 上的 81 格 (shadow, enforce) 扫描。三规则：vacuous（现状）、noninferior（提议：`shadow < enforce ⟹ fallback`）、god（上界）。

| 指标 | 值 |
|---|---|
| 静默 gap 单元数 | 28 / 81 |
| vacuous 相对 noninferior 的平均损失（gap 单元） | 3.0/格 |
| 单元最大损失 | 7 |

### 经验压力

脚本：`partial-stale-injection-test.py` → `results-v2/partial-stale-injection.json`。分层 class 流（n=164，k=8，enforce=8，oracle=8，纯 R_hist=8）。按概率 p 给每条 R_hist 分数注入扰动（以概率 p 把分数替换为先验）。每个 p 做 30 次：

| p | shadow 均值 | gap 占比 | vacuous 相对 noninferior 损失 |
|---|---|---|---|
| 0.3 | 7.90 | 3% | 3.00 |
| 0.5 | 7.17 | 40% | 2.08 |
| 0.7 | 4.73 | 93% | 3.50 |
| 0.8 | 3.17 | 100% | 4.83 |
| 0.9 | 2.70 | 97% | 5.21 |

纯 R_hist 在该 fixture 上落在角点（时间稀释上 0、分层 class 上 8）——partial-stale 不自然冒出。压力测试把它填满：ranker 部分失校准 → vacuous 发布妥协 shadow，而 enforce 本会抓更多。

**修订：** 把 `shadow==0` 改成 `shadow < enforce`。一行。Noninferior 在 gap 单元严格占优，角点打平。

---

## 综合：读者点名的 fixture 边界

| 读者 | 点名的 fixture 边界 | 修订 |
|---|---|---|
| Mike（HHI） | 标签聚合掩盖了对子联合独立性 | 直接测对子联合 |
| Tom（位置） | 效应不跨模型/指令迁移 | 报复现失败，不报定律 |
| Xiao Man（shape-routing） | 路由与探针都 key-coupled | 固定中深度探针、结构锚定 |
| Mike（静默失败） | vacuous 规则漏掉 partial-stale 区间 | `shadow < enforce ⟹ fallback` |

模式：每位读者点名了第 15 篇 fixture 的一道具体盲点。没有哪个修订是"fixture 错了"——fixture 测的就是它测的。修订是关于**fixture 测量所不予授权的**。

读者驱动的修订不是 fixture 研究的 bug。它是必要的补——单个 fixture 回答单个问题，读者点名原框架漏掉的相邻问题。

四条评论，四处实验，四处范围收窄。fixture 测的是它测的——剩下的，要靠读者点名。

---

**系列：** Agent Determinism Illusions · 脚本：[GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**论证弧上一篇：** [第 15 篇 — D+T2 点名谁进场；预算点名谁被看见](https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g)  
**评论线程起点：** [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)
