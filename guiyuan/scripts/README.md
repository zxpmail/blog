# 归源 · 账本与模型守法

对应私有文稿仓「归源」第 3 篇（宪章）、第 4–6 篇（工种）、第 7 篇（性格）、第 8 篇（扩展）、第 9 篇（现场）、第 10 篇（手册）、第 11 篇（闸门）、第 12 篇（装卸）、第 13 篇（地图）、第 14 篇（投毒）、第 15 篇（混淆）、第 16 篇（对账）、第 17 篇（边界，无新账本）。零外部依赖可跑账本。模型守法要密钥。闸门和装卸不调模型。

```bash
python -u charter_constitution.py
python -u role_charter.py
python -u behavior_prime.py
python -u agent_ext.py
python -u context_c.py
python -u playbook_d.py
python -u gate_g.py
python -u loader.py
# 整体：先八账本，后模型（无密钥自 SKIP）
python -u charter_ag.py
# 可选：CHARTER_API_KEY + CHARTER_BASE_URL + CHARTER_MODEL
python -u charter_model.py
# 仅性格：CHARTER_SUITE=bp python -u charter_model.py
# 仅扩展：CHARTER_SUITE=ext python -u charter_model.py
# 仅现场：CHARTER_SUITE=c python -u charter_model.py
# 仅手册：CHARTER_SUITE=d python -u charter_model.py
# 宪章+岗位+性格+扩展+现场+手册：CHARTER_SUITE=all python -u charter_model.py
# 不要用 all 当整体。问模型改没改栈，实验就错了。
```

| 文件 | 用途 |
|------|------|
| `charter.md` | A 颁布稿（四句） |
| `role.md` | B 颁布稿（两段岗位） |
| `behavior.md` | B′ 性格方案（进模型） |
| `ext.md` | Ext 任务扩展方案 |
| `context.md` | C 现场方案 |
| `operations.md` | D 手册方案 |
| `D/` | D 目标提示词（按入口） |
| `C/` | C 目标提示词（按入口，事实稿） |
| `gate.md` | G 闸门方案（不进模型）。含两刀刀形、注入旗、终态对账、旁路收口 |
| `loader.md` | 装卸方案（不进模型） |
| `charter_constitution.py` | A 静态 + 30 条账本 |
| `role_charter.py` | B 静态 + 29 条账本 |
| `behavior_prime.py` | B′ 静态 + 20 条账本 |
| `agent_ext.py` | Ext 静态 + 18 条账本 |
| `context_c.py` | C 静态 + 21 条账本 |
| `playbook_d.py` | D 静态 + 29 条账本（含终态对账判栈位） |
| `gate_g.py` | G 静态 + 30 判例 + 93 刀形 + 40 止意语料。不调模型 |
| `loader.py` | 装卸账本，25 判例。不调模型 |
| `charter_ag.py` | 整体：先八账本后模型。G 不进 system |
| `charter_model.py` | 灌颁布稿，模型填 JSON，同一套 judge。无密钥 → SKIP。默认只跑 A/B；`CHARTER_SUITE=bp` / `ext` / `c` / `d` / `all`。`all` 仍是分层薄装，不是整体 |
| `results/*.jsonl` | 最近一次运行。D 模型结果另存 `charter_model_d.jsonl`，免被 `c`/`ab` 盖掉 |

**诚实标签：** 账本全绿 = 这部法可被违反、可被判无效。不是 Agent 安全，不是现网已执行，不是模型会自觉。模型守法 N=1 不是频率。闸门和装卸不调模型。问模型卸没卸、闸过没过，实验就错了。
