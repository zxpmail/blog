# CONTEXT

## 当前正在做什么
- Tom round-2 修正后续待发：撤 Intent 第四谓词（仲裁锚 overclaim），全收 required 盲区，三谓词并列
- 总钉：测量工具盲区清单

## 上次停在哪个位置
- round-2（U/W/I + provenance）已贴 DEV.to（2026-08-19，commit 780e15b）
- 修订已 commit+push：`stamp-partial-store-read-test.py` 删 I 格（+U/W）；JSON 同步；清单行 7 改「required 从 store 枚举非 reader 自报」
- 修正后续草稿：`working-notes/reply-tom-jones-partial-store-round2.md`

## 近期关键决定
- 撤回 Intent 一等公民：frozen-intent 目录是夹具，synthetic 撑不住仲裁锚主张
- 全收 Tom：`required` 由 reader 自报是门内盲区；fix = store 枚举
- 三条谓词并列：age / coverage / provenance（drill = stores_touched 旋到 run_kind）
- SUPPORT 仅命名谓词，不说生产已焊
