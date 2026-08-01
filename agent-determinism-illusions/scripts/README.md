# "确定性约束"三道幻象 — 复跑脚本

本目录四个脚本对应文章的四个实验,用于实测证伪某生产级 Agent 文章的三个核心机制断言,以及验证"用 embedding 升级"方案的有效性。

**全部可一键复跑,样本公开,无 cherry-pick。欢迎替换成你自己的业务数据重测。**

---

## 实验一:词汇重叠度阈值(`lexical-overlap-test.py`)

**靶断言:** 词汇重叠度 ≥0.24 判同任务 / ≤0.08 判新任务,"80% 用代码秒判"。

**方法:** 30 对带标注样本(同义改写 / 跨语言 / 反义高重叠 / 易样本基线),套阈值,三种分词(字符 2-gram / 3-gram / 空白分词)。

**运行:**
```bash
python3 lexical-overlap-test.py
```
零外部依赖,纯本地,秒级出结果。

**预期结论:** 硬误判率 ~50%。同义改写、跨语言、反义三类难样本几乎全错,易样本全对(暗示阈值在易样本上调过)。

---

## 实验二:温度 0 确定性(`temp0-determinism-test.py`)

**靶断言:** 评估器温度 0.0 → "输出几乎完全确定"。

**方法:** 三类 prompt(数学 / 结构化列举 / 开放式创意),每类在 temperature=0 下重复调用 20 次,比对 exact-match 率。

**运行:**
```bash
# 需配置 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL
# 本仓测试环境:open.bigmodel.cn / glm-5.2
python3 temp0-determinism-test.py
```
需 LLM API。约 1-2 分钟(60 次调用)。

**依赖:** `pip install anthropic`

**预期结论:** 开放式输出仅 70% 一致,30% 发散,极端情况相似度 0.198。温度 0 ≠ 确定性。只测了一个 provider(GLM-5.2),换 OpenAI 等大概率加强结论。

---

## 实验三:Phase Gate 形式主义(`phasegate-formalism-test.py`)

**靶断言:** Phase Gate 把"任务完成"变成"可验证的客观事实"。

**方法:** 照文章描述实现 4 种检查(script exit_code / file_exists / file_glob_count / user_confirmation),构造 8 场景(4 内容正确 + 4 内容垃圾但符合检查),看 Gate 是否无差别放行。

**运行:**
```bash
python3 phasegate-formalism-test.py
```
零外部依赖,纯本地,秒级出结果。

**预期结论:** Gate 通过率 100%,内容正确率 50%,假阳率 50%。"我是一只小鸭子""。""TODO""0 passed"全部通过——Gate 只验证"动作发生了",验证不了"结果是对的"。

---

## 实验四:Embedding 语义分离(`embedding-semantic-test.py`)

**靶断言(我自己的):** 用神经 embedding 升级词汇重叠,能更好区分"同义/同方向" vs "反义/反方向"。

**方法:** 12 组同义对 + 12 组反义对 + 12 组无关对,用 qwen3-embedding:0.6b (1024 维) 计算 cosine 相似度,统计三类分布的均值/最值/重叠度。

**运行:**
```bash
# 需先安装 Ollama: ollama pull qwen3-embedding:0.6b
python3 embedding-semantic-test.py
```
需本地 Ollama。

**预期结论:** 同义(0.766) vs 反义(0.739) 均值差仅 0.026,完全重叠。embedding 只能分"相关 vs 无关",不能分"同方向 vs 反方向"。我原本用这套方案升级靶子文章的构想被自己跑的数据证伪。

---

## Alexey 触发器实测（`alexey-trigger-yield-test.py`）

**靶断言:** 触发精度取决于 `u=P(一致∧置信≥0.9|判对)`；class list 几乎包办筛选，叠加 UHC 精度抬升≈1×。

**方法:** 先重跑三模型 `df-multiperspective-escalation.py --suffix alexey-uhc`，再离线从 JSON 实测 u/h 与四路 yield 表（无随机）。

**运行:**
```bash
python df-multiperspective-escalation.py --backend ollama --model qwen3:0.5b --suffix alexey-uhc
python df-multiperspective-escalation.py --backend ollama --model gemma3:latest --suffix alexey-uhc
python df-multiperspective-escalation.py --backend openai --model deepseek-v4-flash --suffix alexey-uhc
python alexey-trigger-yield-test.py
```

**结果:** `results-v2/alexey-trigger-yield.json`

---

## 跟帖驱动的延伸实验

读者在 dev.to 评论里提出的挑战/疑问驱动了一批延伸实验。每个脚本自带 docstring（spec + 方法 + 预期 + 证伪条件），可以独立复跑；回复只挂当次实验的链接，这一段是索引层，让读者从单条回复回到完整证据链。

| 读者 / 主题 | 脚本 | 结果 |
|-------------|------|------|
| Xiao Man — probe-cascade vs artifact-shape 路由（Part 7） | `probe-cascade-routing-test.py`、`probe-artifact-shape-routing-test.py` | `results-v2/probe-cascade-routing.json`、`results-v2/probe-artifact-shape-routing.json` |
| Xiao Man — shape-routing 第三扰动 rename_keys | `probe-shape-routing-rename-keys-test.py` | `results-v2/probe-shape-routing-rename-keys.json` |
| Xiao Man — 结构不变量锚点（position/type/cardinality） | `probe-structural-invariant-anchor-test.py` | `results-v2/probe-structural-invariant-anchor.json` |
| Xiao Man — 探针 path-passing 重设计（boundary 重画）| `probe-path-passing-redesign-test.py` | `results-v2/probe-path-passing-redesign.json` |
| Xiao Man — 声明层锚生存矩阵（8 扰动 × 4 锚）| `declaration-anchor-survival-test.py` | `results-v2/declaration-anchor-survival.json` |
| Xiao Man — fallback+日志 / 退役信号（主次分歧 × 两种流量）| `declaration-anchor-fallback-logging-test.py` | `results-v2/declaration-anchor-fallback-logging.json` |
| Tom Jones — 冻结声明把失败搬了家（归因/salvage） | `frozen-declaration-fault-attribution-test.py` | `results-v2/frozen-declaration-fault-attribution.json` |
| Tom Jones — conf_desc shuffle / HaluEval agree-set（Part 15） | `conf-desc-miss-shape-test.py`、`agree-set-halueval-probe.py` | `results-v2/conf-desc-miss-shape.json`、`results-v2/agree-set-halueval.json` |
| Tom Jones — position-adjacency 服从率（Part 15） | `position-adjacency-obedience-test.py`、`position-adjacency-obedience-v2.py` | `results-v2/position-adjacency-obedience.json`、`results-v2/position-adjacency-obedience-v2.json` |
| Tom Jones — Vinicius 拆分格 A（deepseek × BANANA） | `position-adjacency-obedience-test.py --model deepseek-v4-flash --out …` | `results-v2/position-adjacency-obedience-v1-deepseek.json` |
| Mike — HHI pair-join 经验测量 | `pair-join-empirical-test.py` | `results-v2/pair-join-empirical-{slug}.json` + `pair-join-empirical-cross-model.json` |
| Mike — unique-catch co-fire / 共现 concentration | `unique-catch-cofire-test.py`、`unique-catch-cooccur-dose-test.py`、`unique-catch-cooccur-labels-test.py`、`defect-class-concentration-histogram.py` | `results-v2/unique-catch-cofire.json`、`results-v2/unique-catch-cooccur-*.json`、`results-v2/defect-class-concentration-histogram.json` |
| Mike — joint-failure monitor live vs late | `joint-failure-monitor-test.py`、`joint-failure-monitor-duration-test.py` | `results-v2/joint-failure-monitor.json`、`results-v2/joint-failure-monitor-duration.json` |
| Mike — shadow-promote ladder（soft-couple ρ） | `joint-failure-shadow-promote-test.py` | `results-v2/joint-failure-shadow-promote.json` |
| Mike — quiet-failure fallback gap (shadow ∈ (0, enforce)) | `partial-stale-shadow-test.py`（纯数学扫描）、`partial-stale-injection-test.py`（df_proxy stress） | `results-v2/partial-stale-shadow.json`、`results-v2/partial-stale-injection.json` |
| Mike — DS4 上游设计期检查（apology 文）| `ds4-upstream-design-check-test.py`（双向 value-match 验证）| `results-v2/ds4-upstream-design-check.json` |
| Mike — 第四 size 点 cliff-vs-slope（apology 文）| 复用 `directional-failure-v2.py --model qwen2.5:1.5b` | `results-v2/qwen2-5-1-5b_summary.json` |

实验之间有依赖：`probe-shape-routing-rename-keys` 复用 `probe-artifact-shape-routing` 的 SCHEMA/probe 推论；`joint-failure-monitor-duration` 是 `joint-failure-monitor-test` 的 τ/L 扫展；`joint-failure-shadow-promote` 是 duration 的 soft-couple 晋升门（ρ=1 校准 → ρ<1 shadow）；`position-adjacency-obedience-v2` 是 v1 在二值饱和后的脱 ceiling 重跑。运行细节看各自 docstring。

---

## 如何用它打我的脸

文章结尾说"欢迎拿你自己的业务数据打脸"。具体怎么打:

- **实验一:** 把 `PAIRS` 换成你真实业务里的"用户中途插嘴"对话,保持 SAME/NEW 标注,重跑。如果你的领域误判率显著低于 50%,说明该机制在你那儿成立——告诉我,我更新结论。
- **实验二:** 换 provider/模型,或换更接近你评估器真实输出的 prompt,重跑 exact-match 率。如果某 provider 在开放输出上真的 100% 一致,那是我没测到的反例。
- **实验三:** 这是机制层面的,不太可能被打脸——4 种检查本来就不读内容。除非你能论证"检查存在性等价于检查正确性",那请务必写一篇。
- **实验四:** 换更强的 embedding 模型(E5/BGE/OpenAI text-embedding-3)重跑,如果在同话题/反向上分离度显著提升,说明我的结论在模型不足时成立、更强的模型下不成立,欢迎打脸。

打脸成功的数据,比文章本身的点击量更值钱。
