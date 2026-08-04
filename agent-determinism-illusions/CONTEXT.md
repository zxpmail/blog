# CONTEXT

## 当前正在做什么
- 草稿：working-notes/reply-xiao-man-external-reference.md（P8 后续——外部探针的设计参数）
- 实验：declaration-anchor-external-reference-test.py 已跑通，三判据全 PASS（f04b839 已 push）

## 上次停在哪个位置
- 已 push f04b839（外部参照探针实验 + 回帖草稿）
- Xiao Man 新评论已到（2026-08-04）：P8 确认架构边界 + 两观察（fixture=护栏 / out-of-channel 成设计参数）
- Part 17 严苛检查：正文数字/链接/引文全部核实；survival 脚本 docstring + JSON interpretation 残留文本已修（all 6→all 8）

## 近期关键决定
- load sensor = 压力可见性，不是裁决权
- P8 双绿同错 → 传感 QUIET + 主锚仍会放行诱饵；与 unanimous miss 同形
- 外部探针的设计参数 = 参照的作者归属：同作者=重画边界 / 异作者=第二作者（可裁决）/ 无参照=tripwire（升级不裁决）
- 关键定理：P2 与 P8 对任何 matcher 观感相同（payload 都在 instances）→ 门无法从结构区分合法/对抗搬迁；P8 与 P9 对所有内部探针观感相同 → 只有外部参照能分开
