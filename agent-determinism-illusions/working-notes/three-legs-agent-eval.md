# 可靠智能体评估的三条腿（命题笔记）

Date: 2026-08-16  
Status: working-note（可引用；尚未升格为正式 Part）  
Triggers: Tom（手写负对照 / 语料基率）+ Peter（密封底 / 一致性 / 报告权）

## 命题

构建可靠的智能体评估系统，不能只靠「写用例」和「算准确率」。它需要三条腿同时支撑——并且有一条**先验**：

0. **信号信道对齐（先验）** — 对照与仪器必须约定同一信道（exit / stdout / JSON 字段 / 副作用），否则所有统计在测对照本身。  
1. **统计基线** — 必须在真实分布（或诚实的合成分布）上测量，不能只看手工用例。  
2. **双向约束** — 既要有阴性对照防假绿（误接受），也要有自然样本防漏报/滥报（总体不能近乎全打一）。  
3. **版本治理** — 对验证器与报告通道做防回滚、防分叉、防篡改（单调底、跨检查点一致性、job 写不掉的权威/旧头）。

缺先验信道，三腿的「绿/红」都可以是对照的幻觉。缺任何一条腿，另外两条给出的「绿」都可以是局部幻觉。

## 每条腿管什么、不管什么

| 腿 | 挡住的失败 | 单独够不够 |
|---|---|---|
| 统计基线 | 手写套件绿、基率上规则已烂（Tom 中档 99% 形） | 不够：没有破坏样仍可能系统性假绿 |
| 双向约束 | 假绿（破坏必须打零）与滥报（自然总体不能全一） | 不够：验证器版本可被选型回滚或双视图分叉 |
| 版本治理 | 旧假绿复活、权威双视图、可写报告通道 | 不够：治理正确的坏规则在基率上仍可滥报 |

## 和已跑实验的对应（索引，非安全证明）

**腿 2 为主、腿 1 补半边**

- `wrong-tool-negative-control-test.py` — 破坏样必须打零；通过率可掩盖可靠度  
- `supersession-hand-vs-corpus-test.py` — 手写五格三规则全绿；合成语料上 cue+一锚滥报，修好后压下  
- `absence-not-health-test.py` — 重放门/对账零/accept-only 同构「无信号≠健康」；§9 ESCALATE  
- `control-channel-mismatch-test.py` — 对照读错信道 → 假 BROKEN；注册绿 ≠ 开火  

**腿 3**

- `parent-reporting-authority-test.py` 及后续 hollow / residual — 报告权  
- `parent-pin-rollback-test.py` — 密封 minimum 关选型回滚  
- `parent-pin-equivocation-test.py` — 密封底 ≠ 跨检查点一致性；旧头可写 / 私有旧头不对照再开双绿  
- `parent-pin-witness-freshness-test.py` — 两首次 job 无见证双绿；见证阈值外检分叉；单调进度堵冻结  
- `parent-pin-byzantine-quorum-test.py` — 双签下 2/3 双绿；3/4 交点挡住；见证集可写残差  

**落地挂点（ReqForge，非博客玩具）**

- `ReqForge/scripts/forge-smoke/policy-witness-quorum.mjs` — CI `pnpm forge-smoke`：缺 3/4 收据则挡绿  
- 政策：`ReqForge/.forge/policy-version.json` + `witness-receipts/`（DEV HMAC，见 `POLICY-WITNESS.md`）

## 认识论尺子

- 合成 SUPPORT = 命名形状成立，≠ 现场发生率，≠ 密码学安全证明。  
- 腿 3 的「密码学级别」在文中指**目标形态**（不可伪造检查点、一致性、不可写旧头）；玩具 HMAC/CT-lite 只是形状演示。  
- 见证/法定人数抬升 minimum 等仍是残差。

## 回帖挂钩

- Tom：`working-notes/reply-tom-jones-hand-suite-base-rate.md`（收束句用本命题）  
- Peter：`working-notes/reply-peter-equivocation.md`（治理腿）  

## 升格条件（何时写成正式文）

同时满足再考虑发 Part：三条腿各至少一篇已发正文引用；读者第二次追问「整图在哪」；且不与未发 Part 编号冲突。
