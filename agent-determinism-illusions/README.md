# Agent Determinism Illusions — 实验库

AI Agent 工程中流行"确定性"神话的可复现实验脚本与结果。配套文章发布在 **[dev.to/zxpmail](https://dev.to/zxpmail)**（Agent Determinism Illusions 系列、Judging vs. Building essay 系列、红线法则等）。

文章正文里指向 `github.com/zxpmail/blog` 的实验链接全部落在本仓 `scripts/`。

## 目录

- `scripts/` — 实验脚本（每个脚本一个断言，独立可跑）+ `test_cases/` + `results-v2/`（结果 JSON/JSONL）
- `samples/` — 参考场景副本（供读者查阅；脚本内联自己的场景，不加载这些文件）
- 实验索引：[scripts/README.md](scripts/README.md)

## 复跑

```bash
# 零依赖实验（纯 Python）
python agent-determinism-illusions/scripts/lexical-overlap-test.py

# 需要 LLM API 的实验
export ANTHROPIC_BASE_URL=...
export ANTHROPIC_AUTH_TOKEN=...
python agent-determinism-illusions/scripts/temp0-determinism-test.py
```

每个脚本的 docstring 写明：被测断言、方法、依赖、预期结果、如何证伪。

## 协议

MIT
