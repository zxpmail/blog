# CONTEXT

## 当前正在做什么
DAF 架构文（中英双稿就绪）：中文终版 `articles/agents-propose-pipeline-decides.md`、英文初稿 `articles/agents-propose-pipeline-decides.en.md`（published: false，tags: ai/architecture/agents/lowcode）。发布前 6 项核实 2026-11-17 作者逐条确认属实（dogfood/语义卡/例外审批/回滚互锁/评审口径/对比表两行）；:101 交叉引用由"第五节"改指第三节末证据表（生产验证整列未验证），中英同步；英文另润三处（verified-to-be-blocked / cloud-services path / DAF 行）。剩余：作者通读 EN → 贴 dev.to → 回填 canonical_url。

## 上次停在哪个位置
- 「AI 算法是人造的」：中文已落盘，英文 .en.md 待出（走 dev.to）。
- agent-memory / ai-language-ceiling 两篇英文稿：发布前检查已过（数字 per-trial 下钻全对、blob 链接 200、4 tags；memory 文脚注半引已补全为 "prefer memory / don't change what isn't broken"），仍 `published: false` 待贴。
- memory 文一处待用户定夺：EN 第 28 行 "a state machine might — and only under stated sensors" 为 EN 编辑性增写，zh 无对应句。
- 两篇英文稿修正未提交。

旁线：EVE 中英已在远程；`look-is-not-draw-ui.md` 仍待定。

## 近期关键决定
- 记忆文定位：有边界的机制草案；实验只示意惯性
- n=3 为脚手架占位；信号缺失则自动降级不可用
- 「AI 算法是人造的」不挂 ADI 系列（无实验锚点，独立评论文）；定稿要点：先验决定"能找到哪类规律"而非"能不能找到"；无言理解可属于自己，跨文本通道交付的理解才要求可问责
- DAF 文同不挂 ADI 系列；修正版要点：插槽死亡谷升独立小节、"七成"改诚实口径、回滚×数据前进互锁写成开放问题、对比表补 Frappe/Odoo + Salesforce/ServiceNow 两行、证据表测试列去 ✅ 改文字+脚注、veto 放行粒度缺口点名。DAF 代码库/演练日志不在本机（C:\work 全盘扫零命中 AssemblyStudio），机时等数字拿不到就按"不报数"发
