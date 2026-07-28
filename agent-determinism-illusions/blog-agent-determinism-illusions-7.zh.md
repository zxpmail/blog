<!--
  ─────────────────────────────────────────────────────────────────
  微信 / 知乎标题备选:
  分歧升级捞错了人：全票一致的漏放才是自动通过的主犯
  ─────────────────────────────────────────────────────────────────
-->

# 分歧升级捞错了人：全票一致的漏放才是自动通过的主犯

**Agent Determinism Illusions（第 7 篇）**

> **本文在系列中的位置：** 本篇**不**延续第 13 篇的 probe-vs-prose。它回到 [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) 的 L2→L3 升级规则——Dipankar 把投票分歧当作转人工信号。Alexey Spinov 的跟评说：这个信号对准了错误的人群。两档实验检验他是否说对，以及 tripwire 该换成什么。

第 6 篇画的是这条控制流：

```
L2 多视角投票
        │
   全票一致 ──────────► 自动通过 / 自动拒绝
        │
   分歧（如 2–1） ────► L3 人工
```

正文里已有 caveat：分歧测的是不确定性，修不了全票一致的系统性偏见。Alexey 更锋利——这是**路由**问题，不是再补一段 caveat。

---

## 1. Alexey 的人口错配

在第 6 篇评论区，[Alexey Spinov](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f) 的要点（压缩）：

> 危险失败是高自信、同向的——系统性的。系统偏差跨 prompt 共享，不是各视角各错各的（你自己的 P3：多数决修不了）。所以三视角往往会在**恰恰那些案子上一致**。分歧→人工于是把人审指到「安全地暧昧」的样本，把「自信且错」的自动放行。升级信号对准了错误人群。

他给了两刀便宜改法：

1. **T1** — 已知反转类上的确定性 tripwire（不管是否一致都升级）  
2. **T2** — 「历史上易反转的类 × 全票高自信」→ 升级——与「高自信自动过」**反过来**

要测的不是「分歧没用」，而是「对你已经量过的失败模式，分歧不该当唯一主 tripwire」。

---

## 2. 实验 A — DF v2 离线代理（不新烧 API）

第 6 篇 Mike Update 已报：96 次 MISS 里 **95.8%** 自报自信 ≥0.9（均值 0.969）。该质量是集中的——第 6 篇亦报约 **80%** MISS 来自 qwen3:0.5b——所以 headline 是集中度事实，不是三模型通律。P2（同 prompt N=10；此处无冻结 `results-v2` 落盘）显示同输入几乎 0 分歧。故第一刀：

- `conf ≥ 0.9` ≈ *同信道全票代理* → 按第 6 篇规则会**自动过**  
- `conf < 0.9` ≈ *分歧代理* → 会**升级**

在「判官 PASS 且实际是 MISS」的集合里，丢掉 **2** 条 deepseek DS4、`confidence: null` 的 run（策略表需要标量 conf）。下表分母因此是 **n=94**，不是第 6 篇 headline 的 n=96：

| 分歧代理下的桶 | 占 MISS（n=94） |
|----------------|-----------------|
| 会自动过（conf≥0.9） | **97.9%**（92/94） |
| 会升级（conf<0.9） | 2.1%（2/94） |

| 策略 | MISS 捞到% | MISS 仍自动过% |
|------|------------|----------------|
| **D**（只升低自信） | 2.1% | **97.9%** |
| T1（升所有 DF*/DS* 类） | 100%† | 0% |
| T2（反转类 ∩ conf≥0.9） | 97.9% | 2.1% |
| **D+T2** | **100%** | **0%** |

†**T1 在本 fixture 上是类清单上界，不是独立发现。** DF v2 每一次 MISS 的 sid 都已是 DF*/DS*；「凡反转类即升」对 MISS 抓 100% 由定义保证。把 T1 当 oracle 天花板读；可部署主张是 **D+T2**。

脚本：`scripts/escalation-population-mismatch.py`。  
代理口径（针对 D vs D+T2，不单独吹 T1）：**SUPPORT**。

代理不是真三视角。下一节去掉这个借口。

---

## 3. 实验 B — DF 集上真跑 Strict / Balanced / Lenient

同一套 20 个 DF v2 场景，与 P3 相同的三人格，每场景每视角 1 次（每模型 60 次调用）。策略用**真实投票模式**：

- **D** — 仅 `split` 升级  
- **T1** — 接受路径上且为已知反转类  
- **T2** — 反转类 **且** `unanimous_pass`  
- **D+T2** — 并集  

### deepseek-v4-flash — 测不到这主张的底物

坏场景几乎全票拒绝。**0 个 dangerous accept**（多数票放过坏输出）。在几乎不漏放的模型上，测不到「全票错却自动过」。空结果，不是证伪。

### gemma3:latest — 另一种形状

Strict/Balanced 拒、Lenient 过 → 几乎全是 `split`，多数仍拒坏案 → **0 dangerous accept**。分歧会把大量接受路径（含真通过）送去人审。也不是 Alexey 点名的那一桶。

### qwen3:0.5b — 对得上主张的底物

**6** 个 dangerous accept。其中：

| 模式 | 数量 | 占比 |
|------|-----:|-----:|
| `unanimous_pass` | 4 | **66.7%** |
| `split` | 2 | 33.3% |

| 策略 | MISS 捞到% | MISS 仍自动过% | 真通过被升级% |
|------|------------|----------------|---------------|
| **D** | 33.3% | **66.7%** | 0% |
| T1 | 100%† | 0% | 0% |
| T2 | 66.7% | 33.3% | 0% |
| **D+T2** | **100%** | **0%** | 0% |

†同 §2：六个 dangerous accept 全在反转类 sid 上，T1 的 100% 是类清单天花板。承重行是 **D+T2**。

脚本：`scripts/df-multiperspective-escalation.py`  
结果：`results-v2/df-multiperspective-qwen3-0.5b.json`（另有 deepseek / gemma 落盘）

在真会产生该失败模式的模型上：**PARTIAL → SUPPORT**。危险放过里约三分之二是全票，按第 6 篇规则会自动过；分歧只捞到另外三分之一。**D+T2** 六个全捞到，且本 run 未误升真通过。DeepSeek/Gemma 空结果意味着这是**底物条件**结果（会系统性漏放的法官），不是对所有模型的通律。

---

## 4. 管线改口

第 6 篇的图仍用于**真暧昧**。它不再是 L2→L3 的**唯一**触发器。

```
L2 投票
   │
   ├─ 已知反转类 tripwire（T1）──────────► L3 / 硬拒路径
   ├─ 易反转类上的全票通过（T2）──────► L3   ← 与自动过相反
   ├─ 分歧（Dipankar）─────────────────► L3
   └─ 其余全票 ────────────────────────► 自动执行
```

把「一致」读成「可信」是 bug。一致落在你以前错过的类上，正是相关错误躲藏处——Alexey 的原话，qwen 的票印证了。

Mike 的第 6 篇 Update 从**审计抽样**打同一条尾（别用 1/confidence 加权）；本篇从**升级触发器**打。同一人群，不同旋钮。

---

## 5. 边界（钉在正文）

- DeepSeek / Gemma 空结果：强法官或古怪分裂形状不压测此主张；主张针对**会系统性漏放的法官**。  
- qwen 为每视角 N=1（60 次）。够否定「分歧就够」；不够当生产费率卡。  
- T1 需要维护类清单；无历史的冷启动类仍回退到 D，并继承 D 的盲区。  
- forge-verify 的 `content-verify.mjs` 今天仍是分歧→UNCLEAR / 多数自动。这些 tripwire 是**设计 + 博文证据**，本稿未声称已产品化。

### Update (2026-07-22)：双臂——复发 vs 新奇（Mike）

Mike Czerwinski 对反向扳机：

> 它只在你**已经**抓错过的类上开火。「历史上易反转」靠历史堆出来，所以你还没见过的反转类……会全票高自信、无 tripwire……这不是反对扳机……而是主张它只是双臂设计的一臂……已知反转 tripwire 抓**复发**。抓新系统偏差的**首次**出现，更接近……真正独立的第二读——不需要历史也能和错答案分歧……「已知反转类上的全票高自信」是对的增量。它不是「自信且错、且从未被抓过」的修复。

第二种人在本线有了名字：**confidently-wrong-and-never-caught-before**（新奇系统偏差）。T1/T2 是**复发臂**——便宜、依赖历史、必要。它们不是新奇臂。

Mike 希望新奇臂可能由单独的 `classifier_disagree` 承担（不共享模型先验的独立第二读）。我们在第 6 篇采样 fixture 上跑过消融（`external-signal-ablation.json`）：**`classifier_disagree` 单独捕获 25.1% < Part 6 的 28.4%**——外部单信号里最好，仍不够当新奇捕手。和 `barely_passed` 捆绑才抬升；单独过不了线。所以新奇臂**不是**「把 CD 单独塞进 tripwire 就当首次出现已解决」。

本系列反复落到的分叉：

| 臂 | 信号形状 | 抓住 | 成本 |
|----|----------|------|------|
| **复发** | T1 / T2——失败历史、已知反转类 | 已烧过的模式重来 | 便宜 |
| **新奇** | **不**共享法官先验的源（出信道 probe、独立模态——见第 13 篇 probe-vs-prose；不是同文本信道里再加一个 prompt） | 新系统偏差的首次出现 | 贵 |

两臂都要。错在指望便宜臂干贵臂的活。D+T2 仍是第 6 篇管线图的正确增量。它关不上 confidently-wrong-and-never-caught-before。

### Update (2026-07-23)：「出信道」到底指什么（Mike）

动手做新奇臂 probe 之前，Mike 钉死了买独立性的性质——不是外观：

> 若 probe 仍是另一个 LLM 用文本推理「这说法看起来对不对」，即便换 priming、甚至被要求唱反调，仍算同信道。真正买到独立的，是答案来自**原主张从未走过的路径上重推导事实**——另一数据源、结构不变量、重计算，而不是对同一证据的第二次阅读换个 prompt。
>
> 可操作地：事先写明 probe **错**意味着什么，且**不依赖原主张说了什么**——像 checksum 可以错，不管文件自称装了什么。若评价 probe 输出的唯一办法是拿它和原主张的推理比对，它仍在信道内，只是管线更靠后。语义新奇难，正因为多数第二意见继承同一证据和同一推理基底……不继承的更稀、且常领域相关——所以复发臂今天可建，新奇臂仍开着。

**Checksum 检验（可操作）：** 能否在**不引用主张说理**的前提下写出 probe 的过/不过准则？不能 → 仍同信道（戴帽子的第五个 prompt）。能 → 出信道候选。

| 检验不过（同信道） | 检验过（出信道） |
|-------------------|-----------------|
| Strict/Balanced/Lenient、「和上一法官唱反调」、辩论团 | 从源数据重算；结构不变量（schema / 类型 / checksum）；执行一条输出可证伪主张的命令（第 13 篇 probe） |
| 仍在同一产物上读故事的 `classifier_disagree`（L2 文本） | 从不读 LLM 叙事的 L0/L1 形状/合约检查——且其判决不需要主张散文才可解释 |

因此：复发臂今天可建（T1/T2）。新奇臂**故意**仍开着——不是因为还没加一个 prompt，而是因为真独立稀缺且常按领域长成。第 13 篇 probe-vs-prose 是最近的既有线；Mike 的 checksum 检验是任何自称坐在该臂上的验收条件。

### Update (2026-07-23)：结构独立 ≠ 因果独立（Mike）

Mike 对 checksum 门槛的跟评：

> Checksum framing sets the right bar, because it's falsifiable independent of the story. A probe that can only be scored by comparing it to the original reasoning is grading agreement, not correctness.
>
> One case worth naming explicitly…: "other data" that's structurally different but still downstream of the **same collection pipeline**. Two signals can pass the same-channel test and still share a common cause upstream — a sensor outage or schema change that corrupts both the claim and the probe's input at once. **Structural independence and causal independence aren't the same property**, and the recurrence-buildable-today case might be quietly assuming the second while only checking the first.

两刀，不是一刀：

| 检验 | 问的是 | 过关当… | 仍会挂当… |
|------|--------|---------|-----------|
| **Checksum / 同信道** | 能否不靠主张的*故事*给 probe 打分？ | 过/不过准则可不引用说理写出来 | probe 仍是对同一证据的第二次文本阅读 |
| **因果 / 共因** | 主张与 probe 是否共享上游失效模式？ | probe 输入不在同一采集/导出/schema 路径下游 | 「看起来独立」的其他数据，却被同一传感器中断、schema 变更或坏导出一起污染 |

Checksum 仍是正确的第一道门槛——拦住「打一致性分」。它**不是**共因护盾。点名第二种失效，免得「出信道」把结构不同偷偷升格成因果独立。

这收紧了不对称主张：**「复发今天可建」**说的是已烧过类上的 T1/T2——依赖历史，**不要求独立性**。下面的 hold-out probe 只测了新奇门槛的**结构**半边（可不引用主张说理写出过/不过）。它**没有**对共享上游失效做因果独立背书。领域稀缺现在有两层：找到过 checksum 的 probe，*以及*找到输入路径不与主张共因的那一个。操作后续（测得到的盖章；其余靠尖峰报警）：[联合失败监视 Update](#joint-failure-monitor-mike)。

<a id="joint-failure-monitor-mike"></a>

### Update (2026-07-27)：联合失败监视——发现你其实没有因果独立（Mike）

Mike 在结构≠因果之后的下一刀：实践修法不是更强的独立性*定义*——是**监视器**。跟踪主张与 probe 的联合失败率；把相关失败尖峰当成独立告警。

操作收口（比「事先绝对无法盖章」更窄）：**测得到的上游事先盖章**（血缘、对已点名共因路径做混沌注入）。**别假装**那枚章盖住了未点名的共因——那些剩余，联合失败尖峰*就是*可跑的检查。

离线仿真（[`joint-failure-monitor-test.py`](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/joint-failure-monitor-test.py) → [`joint-failure-monitor.json`](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/joint-failure-monitor.json)）：`(claim_fail, probe_fail)` 流；滚动窗 W=200 **excess** = ĵ − ĉ·p̂；excess ≥ τ 连续 K=3 窗则告警。两体制——纯独立（p_c=0.12, p_p=0.10）vs 同基线加日程化共因停电窗（双强制失败；传感器中断形）。Checksum 仍只打结构过/不过；监视器从不看主张说理。

| τ | 独立体制误报率 | 共因检出率 | 首次停电后平均延迟 |
|---|---------------|------------|-------------------|
| 0.03 | **2%** | **99%** | **~9** 步 |
| 0.05 | **0%** | **100%** | **~15** 步 |

本网格工作点：τ=0.03（FAR≤5% 且检出≥90%，再取最小延迟）。

**结论：** checksum / 已测上游 = 事先章；联合失败 excess = 剩余告警。监视器不制造因果独立，也不替代已经能跑的上游测试——它让尚未盖章的那截变得可听见。寿命 vs 延迟（对活停电是否太慢）：[准确 vs 延迟 Update](#joint-failure-monitor-duration-mike)。

<a id="joint-failure-monitor-duration-mike"></a>

### Update (2026-07-27)：准确 vs 延迟——停电寿命对抗检测延迟（Mike）

Mike 对 τ 表的跟进：通常抬阈值是用检出换误报。这里 τ=0.03→0.05 时 FAR 降、检出升——共因尖峰离独立噪声底很远——真正代价是延迟（≈9 → ≈15）。旋钮是**准确 vs 延迟**，不是准确 vs 噪声。操作问题：这延迟相对一次传感器中断能撑多久够不够短？短命停电可能在告警过线前就结束。

离线扫（[`joint-failure-monitor-duration-test.py`](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/joint-failure-monitor-duration-test.py) → [`joint-failure-monitor-duration.json`](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/joint-failure-monitor-duration.json)）：同 W=200 / K=3；单次长度 L 的停电；**live_catch** = 停电仍在时首次告警；**late_only** = 结束后才告警（残渣仍在滚动窗里）；**miss** = 无告警。

| τ | 父实验平均延迟 | live≥90% 的 L | any≥90% 的 L | L ≈ 延迟时 |
|---|----------------|---------------|--------------|------------|
| 0.03 | ≈9 | **15** | **9** | L=9 → live **25%** / late **65%** / miss 6% |
| 0.05 | ≈15 | **20** | **15** | L=15 → live **37%** / late **62%** / miss 1% |

**结论：** 停电寿命 ≤ 检测延迟时，监视器常在*活*故障期间沉默，只在窗残渣上事后响——法医有用，拦不住进行中的中断。对 live 捕获，有用下限是 L ≳ delay（要 ≥90% live 还得略高于平均延迟），不是「任何最终能推动 excess 的 L」。上一则监视 Update：[盖章 / 剩余告警](#joint-failure-monitor-mike)。

### Update (2026-07-23)：hold-out 实验——分叉可测

最小离线实验（`novelty-arm-holdout-test.py` → `results-v2/novelty-arm-holdout.json`，冻结为 `--holdout DS4`）。从已知反转登记里 **hold-out DS4**（跨模型 31 次高置信 MISS）。三臂打这批「首次」质量：

| 臂 | DS4 高置信 MISS 捕获 |
|----|----------------------|
| **A 复发**（D+T2，登记表无 DS4） | **0/31（0%）** |
| **B 同信道**（同 model×sid 其他 run 是否拒过） | **1/31（3%）** |
| **B′ 同信道**（qwen Strict/Balanced/Lenient） | **unanimous_pass → 不捕获** |
| **C 出信道 probe**（任务+产物 checksum；不读法官说理） | **31/31（100%）‡** |

‡**Arm C 是 fixture 演示，不是盲测泛化。** `probe_fail()` 按 sid / 任务约束编码规则（含 DS4）；hold-out 只从*复发登记表*去掉 DS4，probe 仍认识产物形状。把 31/31 读成「checksum 式准则*可以*在无类历史条目时抓住首次」，不是「我们没看过失败就发现了 probe」。`--holdout DS9` 同形（重跑会覆盖 JSON；默认冻结为 DS4）。

对照：非 hold-out 高置信 MISS 上复发臂 **61/61（100%）**——类已知时历史管用。V1/V2 合法产物 probe 无误拒。判决：**SUPPORT** 不对称形状（A 漏新奇 / B 塌陷 / C 在 oracle 规则下可抓）；**不**声称 Arm C 已可上生产或已因果独立。

因此 Mike 的分叉不只是定义。在本 fixture：便宜复发臂漏从未烧过的类；同信道第二读跟 miss 一起塌；checksum 式 probe 在你*已经会写准则*时可无登记表抓首次。新奇臂仍按领域长成；稀缺主张保留。请与上一则 Update 合读：本跑支持新奇门槛的**结构**半边；不声称对同管道共因已有因果独立。

### Update (2026-07-24)：复杂度升高时的捕获率与相对成本（Xiao Man）

Xiao Man 在 T1/T2 vs 新奇、以及出信道 checksum 之后追问：

> 我一直把它想成廉价复发检测 vs 昂贵新奇检测……不需要说理可解释的 checksum/结构探针——才是真边界。问题：有没有测过，出信道探针的捕获率在任务复杂度升高时是否仍稳定？我在想有没有一个复杂度阈值，连结构不变量相对任务本身都算太贵。

双轴离线实验（`probe-complexity-dual-axis.py` → `results-v2/probe-complexity-dual-axis.json`，每格 n=40，seed=7）。行 = 任务/产物深度 T1–T4；列 = 探针深度 P1–P4。仅 checksum 式（过/不过只看 schema+产物，从不看法官说理）。匹配对：(T1,P1)…(T4,P4)。

**捕获矩阵（坏产物被拒比例）：**

|  | P1 | P2 | P3 | P4 |
|--|----|----|----|-----|
| T1 | 1.00 | 1.00 | 1.00 | 1.00 |
| T2 | 0.48 | **1.00** | 1.00 | 1.00 |
| T3 | 0.45 | 0.35 | **1.00** | 1.00 |
| T4 | 0.23 | 0.30 | 0.70 | **1.00** |

（粗体 = 匹配深度。）

**成本比矩阵**（探针操作数 ÷ 任务操作数；任务侧 = schema 叶子 + 产物体积）：

|  | P1 | P2 | P3 | P4 |
|--|----|----|----|-----|
| T1 | 0.23 | 0.15 | 0.15 | 0.46 |
| T2 | 0.09 | 0.14 | 0.15 | 0.26 |
| T3 | 0.07 | 0.11 | 0.20 | 0.24 |
| T4 | 0.04 | 0.06 | 0.12 | 0.19 |

读法：

1. **匹配时捕获率稳定**——T1–T4 全 100%。在本 fixture，任务变深本身不会让出信道捕获掉下来。
2. **悬崖在欠规格，不在任务体量**——同一批 T4 坏样本：P1 23% → P2 30% → P3 70% → P4 100%。漏掉的正是浅探针从不看的嵌套/跨字段规则。「有个 checksum」≠ 盖住失败面。
3. **本执行成本模型下未跨相对成本阈值**——匹配格 cost_ratio 全程 <1（约 0.23 / 0.14 / 0.20 / 0.19）。更深探针更贵（均值 P4 > P1）；过规格保持捕获但抬高成本（浪费，不是更安全）。若给「写不变量」或「整任务重跑」定价，会更早跨线；这里量的是**执行**成本。

与 hold-out 同族 caveat：fixture 演示；只覆盖新奇门槛的结构半边；非生产墙钟；非因果独立。Xiao Man 的问题拆得很干净：捕获稳不稳是匹配问题；贵不贵是成本模型问题——在执行成本下，这里没跨线。

### Update (2026-07-27)：固定深度 vs 失败信号 vs 产物形状（Xiao Man）

Xiao Man 在 P1→P4 悬崖与「过规格 = 浪费不是安全」之后追问：

> P1→P4 那一段最戳我。23% → 30% → 70% → 100%——不是渐变，是特定 schema 覆盖阈值上的相变。「过规格 = 浪费不是安全」很锋利……想问探针怎么选：你们是按任务类型固定 P 级，还是按产物特征动态升级？有没有廉价预检，只在 P1/P2 提示可能有跨字段问题时才上 P3/P4？

同一 checksum fixture 上两支离线后续（n=40，seed=7）。

**1. 级联 / 失败信号路由**（`probe-cascade-routing-test.py` → `results-v2/probe-cascade-routing.json`）

同一批产物上三种策略：

| 策略 | 规则 | T4 捕获 | T4 cost_ratio |
|------|------|---------|---------------|
| `fixed_matched` | 已知 Ti → 跑匹配 Pi | **1.00** | 0.19 |
| `fail_escalate` | P1 通过 → 放行；P1 失败 → 跳到匹配 Pi | **0.23** | **0.05** |
| `schema_cap` | 即使通过，也升到匹配 Pi | **1.00** | 0.36 |

`fail_escalate` 就是那条廉价预检。T4 上捕获掉到双轴的 P1 地板（23%）；跨字段漏 **22/31**。预算 / 端口唯一 / 指纹类破坏，浅探针常常直接*通过*，级联根本不触发。它还*看起来*更便宜（约 7 vs 约 30 ops）——这是陷阱，不是胜利。`schema_cap` 能找回捕获，但天花板仍是 schema 匹配深度：换皮的固定匹配，不是省钱策略。

**2. 按产物形状路由**（`probe-artifact-shape-routing-test.py` → `results-v2/probe-artifact-shape-routing.json`）

只凭字段推断 `(T̂, P̂)`：有 `budget` → T4/P4；有 `services[]` → T3/P3；有 `timeout_ms`/`retries` → T2/P2；否则 T1/P1。（指纹是 P4 的*载荷*检查，不是路由线索。）

| 人群 | 固定捕获 | 形状捕获 | 说明 |
|------|----------|----------|------|
| 正常 T1–T4 | 1.00 | **1.00** | 诚实线索 ≈ 任务标签 |
| 删线索（去掉 `budget`，留下错误指纹） | 1.00 | **0.82** | 欠规格；漏 P4 专属项 |
| 诱饵嵌套（T2 + 装饰性 `services[]`） | 1.00 | **0.00** | 误路由；5 → 24 ops |

因此：产物特征*可以*设定 P 级——当它们编码的是 schema 深度且保持诚实时——那仍是换了标签源的匹配深度路由，不是「P1/P2 失败才加深」的替代品。删掉深度线索，或塞进诱饵嵌套，形状路由就会欠规格或查错层。

同族 caveat：fixture；只覆盖结构半边；仪器化 ops，非墙钟。直接回答：**本设置里 P 级由 schema 深度固定**（任务类型，或诚实的形状代理）。**按失败信号动态加深，不是通往 P3/P4 以抓住跨字段问题的廉价路径**——那些问题正是廉价预检不会报警的那批。

---

## 收束

第 6 篇停掉「把分裂多数决成假共识」是对的；把补集——全票——当作对 DF v2 已测失败模式的安全自动执行，是错的。Alexey 点名了人口错配；DF 三视角重跑给了数字。Mike 点名了复发臂看不见的残余人口，钉死了动手前「出信道」必须意味着什么，并把该门槛拆成结构独立 vs 因果独立。Xiao Man 先问捕获与相对成本是否扛得住复杂度升高，再问 P 深度能否靠失败信号或产物形状级联；匹配深度站得住，失败才加深站不住，形状路由只在诚实 schema 代理时成立。

**分歧留下。T1/T2 加入。它们都不是新奇臂。第五个 prompt 也不是。过 checksum 的「其他数据」probe 也不自动是共因护盾。匹配深度保住捕获；欠规格才是悬崖；失败才加深不是绕开悬崖的捷径。**

### Update (2026-07-27)：谁进门 ≠ 谁被看见（指针）

第 6 篇线程里 Alexey/Mike 把问题从 tripwire 选择推到 floor volume 与硬预算下的 rank-inside-stream。那是 D+T2 之后的下一控制面——不是又一个 novelty 臂 prompt。离线套件 + 双线运维形态：**[第 15 篇](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/blog-agent-determinism-illusions-15.zh.md)**（《D+T2 只决定谁进门；预算决定谁被看见》——仓库草稿）。编号跳到 15，为保住第 8–14 篇其他弧；本论证线发布顺序是 7 → 15。

---

**系列：** Agent Determinism Illusions · 脚本：[GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**上一篇：** [第 6 篇](https://dev.to/zxpmail/five-comments-that-redesigned-my-llm-verification-pipeline-388f)  
**本弧下一篇：** [第 15 篇 — D+T2 只决定谁进门；预算决定谁被看见](https://dev.to/zxpmail/dt2-names-who-enters-budget-names-who-gets-seen-4f9g)
