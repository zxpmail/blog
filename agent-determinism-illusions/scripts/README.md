# "确定性约束"三道幻象 — 复跑脚本

本目录三个脚本对应文章《"确定性约束"的三道幻象》的三组实验,用于实测证伪某生产级 Agent 文章的三个核心机制断言。

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

## 如何用它打我的脸

文章结尾说"欢迎拿你自己的业务数据打脸"。具体怎么打:

- **实验一:** 把 `PAIRS` 换成你真实业务里的"用户中途插嘴"对话,保持 SAME/NEW 标注,重跑。如果你的领域误判率显著低于 50%,说明该机制在你那儿成立——告诉我,我更新结论。
- **实验二:** 换 provider/模型,或换更接近你评估器真实输出的 prompt,重跑 exact-match 率。如果某 provider 在开放输出上真的 100% 一致,那是我没测到的反例。
- **实验三:** 这是机制层面的,不太可能被打脸——4 种检查本来就不读内容。除非你能论证"检查存在性等价于检查正确性",那请务必写一篇。

打脸成功的数据,比文章本身的点击量更值钱。
