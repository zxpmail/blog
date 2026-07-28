# CONTEXT

## 当前正在做什么
- Tom Jones Part 15：两支实验已齐；回复草稿可贴；Part 15 正文 Update / `--full` / commit 待定

## 上次停在哪个位置
- `conf-desc-miss-shape.json`：conf_desc = fixture (conf,miss) 联合；不能当安全 fallback
- `agree-set-halueval.json`：n=70 DeepSeek-v4-flash × gemma3；P(wrong|agree)=19.5% Wilson[10.2%,34.0%]；同模 temp0 100% vs 异模 78.8%
- 回复：`working-notes/reply-tom-jones-part15.md`
- DeepSeek 密钥从 `~/.cc-switch/cc-switch.db` 导出（`scripts/data/.deepseek_env.json`，已 gitignore）

## 近期关键决定
- 模型对：DeepSeek-v4-flash（cc-switch）+ Ollama gemma3:latest
- HaluEval 先 n=70 分层对齐 Tom；`--full` 可选第二档
- 二值 disagree 双错不当证据（Tom caveat）
