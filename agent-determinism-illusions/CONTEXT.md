# CONTEXT

## 当前正在做什么
- 待发回帖清零（2026-08-20）：Tom 修正后续 + Mike a priori validation 都已贴 DEV.to
- Part 19 EN 草稿已写（2026-08-20，未发布，zh 待补）
- classifier_disagree 隔离实验**已完成**（2026-07-22，Part 6 §4 Update en+zh 已落消融表）：CD 单独 24.9% < P6 28.4%、必要不充分、与 barely_passed 共驱；95.8% 偏 qwen——无排队实验
- 总钉：测量工具盲区清单

## 上次停在哪个位置
- round-2（U/W/I + provenance）已贴 DEV.to（2026-08-19，commit 780e15b）
- 修订已 commit+push：`stamp-partial-store-read-test.py` 删 I 格（+U/W）；JSON 同步；清单行 7 改「required 从 store 枚举非 reader 自报」
- Tom 修正后续已贴（2026-08-20）：`working-notes/reply-tom-jones-partial-store-round2.md`（撤 Intent、三谓词并列；8778579）
- Mike a priori validation 已贴（2026-08-20）：`working-notes/reply-mike-before-the-fact.md`（ρ=0.8 格 + absence-not-health 极点；7396474）

## 近期关键决定
- 撤回 Intent 一等公民：frozen-intent 目录是夹具，synthetic 撑不住仲裁锚主张
- 全收 Tom：`required` 由 reader 自报是门内盲区；fix = store 枚举
- 三条谓词并列：age / coverage / provenance（drill = stores_touched 旋到 run_kind）
- SUPPORT 仅命名谓词，不说生产已焊
