# 归源 · 账本与模型守法

对应私有文稿仓「归源」第 3 篇（宪章）、第 4–6 篇（工种）、第 7 篇（性格）、第 8 篇（扩展）、第 9 篇（现场）、第 10 篇（手册）。零外部依赖可跑账本。模型守法要密钥。

```bash
python -u charter_constitution.py
python -u role_charter.py
python -u behavior_prime.py
python -u agent_ext.py
python -u context_c.py
python -u playbook_d.py
# 可选：CHARTER_API_KEY + CHARTER_BASE_URL + CHARTER_MODEL
python -u charter_model.py
# 仅性格：CHARTER_SUITE=bp python -u charter_model.py
# 仅扩展：CHARTER_SUITE=ext python -u charter_model.py
# 仅现场：CHARTER_SUITE=c python -u charter_model.py
# 仅手册：CHARTER_SUITE=d python -u charter_model.py
# 宪章+岗位+性格+扩展+现场+手册：CHARTER_SUITE=all python -u charter_model.py
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
| `charter_constitution.py` | A 静态 + 23 条账本 |
| `role_charter.py` | B 静态 + 28 条账本 |
| `behavior_prime.py` | B′ 静态 + 20 条账本 |
| `agent_ext.py` | Ext 静态 + 18 条账本 |
| `context_c.py` | C 静态 + 21 条账本 |
| `playbook_d.py` | D 静态 + 22 条账本 |
| `charter_model.py` | 灌颁布稿，模型填 JSON，同一套 judge。无密钥 → SKIP。默认只跑 A/B；`CHARTER_SUITE=bp` / `ext` / `c` / `d` / `all` |
| `results/*.jsonl` | 最近一次运行。D 模型结果另存 `charter_model_d.jsonl`，免被 `c`/`ab` 盖掉 |

**诚实标签：** 账本全绿 = 这部法可被违反、可被判无效。不是 Agent 安全，不是现网已执行，不是模型会自觉。模型守法 N=1 不是频率。现场未开，不灌。
