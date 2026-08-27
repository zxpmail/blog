# 归源宪章 · 账本测试

对应私有文稿仓「归源」第 3 篇（宪章稿）。零外部依赖，不调模型。

```bash
python -u charter_constitution.py
```

| 文件 | 用途 |
|------|------|
| `charter.md` | 颁布稿（进模型的四句） |
| `charter_constitution.py` | 静态一般法 + 23 条账本抵宪 |
| `results/charter_constitution.jsonl` | 最近一次运行 |

**诚实标签：** 全绿 = 这部法可被违反、可被判无效。不是 Agent 安全，不是现网已执行。
