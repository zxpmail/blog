# CONTEXT

## 当前正在做什么
- Tom partial-store round-2 回帖待发（U/W/I + provenance）
- **Intent 一等公民**：门控仲裁锚，否则 U 假绿 / W 假红

## 上次停在哪个位置
- round-2 草稿：`reply-tom-jones-partial-store-round2.md`（含 Intent 段）
- 脚本：`stamp-partial-store-read-test.py`（+I 格）；`stamp-provenance-drill-test.py`
- 四谓词：age / coverage / provenance / **intent**

## 近期关键决定
- Intent 运行前冻结（非 reader 事后自报），仲裁 required
- ops_complete → REJECT partial；archive_base → PASS partial；W 对 archive 是假红
- SUPPORT 命名谓词，不说生产已焊
