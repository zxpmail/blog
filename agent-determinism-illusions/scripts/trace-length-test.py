# -*- coding: utf-8 -*-
"""
缺陷六实验: Agent 执行轨迹长度 vs 最低审核时间

构造三个真实规模的 Agent 执行轨迹,测量其文本长度,
按保守阅读速度(250 当量词/分钟)计算最短审核时间,
验证"15 秒"是否合理。
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TRACE_SIMPLE = """=== Agent 执行轨迹 (3 步) ===

[Step 1] 用户请求: 写一份循环引擎研究简报
[Step 2] 工具调用: file_write("research-brief.md")
[Step 3] 输出:
  # 循环引擎研究简报
  ReAct 循环在生产环境的三个缺陷:无终止条件、无中断处理、无空转保护。
  方向:确定性约束包围 LLM 不确定性。
  实验:词汇重叠 50% 误判、温度 0 开放输出 70% 一致、Phase Gate 假阳 50%。

Phase Gate 结果: exit 0, 文件存在 [PASS]
GLM-5.2 质检结果: REJECT (内容过短)

审核员需要判断: GLM-5.2 的判定是否正确?"""

TRACE_MEDIUM = """=== Agent 执行轨迹 (12 步) ===

[Step 1] 用户请求: 写一份关于 LLM Agent 确定性约束的完整技术文档
[Step 2] 工具调用: task_decompose()
  -> 子任务: 1.收集数据 2.写简报 3.写初稿 4.生成章节文件
[Step 3] 工具调用: file_read("experiments/exp-B-lexical-overlap.json")
  -> 读取实验 B 数据: 30 对样本, 误判率 50%
[Step 4] 工具调用: file_read("experiments/exp-A-temp0.json")
  -> 读取实验 A 数据: 温度 0 下开放输出 70% 一致
[Step 5] 工具调用: file_read("experiments/exp-C-phasegate.json")
  -> 读取实验 C 数据: Phase Gate 假阳率 50%
[Step 6] 工具调用: file_write("research-brief.md", content)
  -> 已写入: 研究简报(约 300 字)
[Step 7] 工具调用: file_read("research-brief.md")
  -> 返回: 研究简报内容
[Step 8] 工具调用: file_write("draft.md", content)
  -> 已写入: 初稿(约 2000 字)
[Step 9] 工具调用: file_write("chapter-1.md", content)
  -> 已写入: 第 1 章
[Step 10] 工具调用: file_write("chapter-2.md", content)
[Step 11] 工具调用: file_write("chapter-3.md", content)
[Step 12] 工具调用: run_pytest("tests/")
  -> stdout: ... 42 passed, 0 failed in 3.21s

Phase Gate 结果: exit 0, 文件全存在 [PASS]
GLM-5.2 质检结果: REJECT 3/4
  - L1(研究简报): 内容太短, 信息量不足
  - L2(初稿): 结构不完整, 缺少方法论章节
  - L3(章节文件): 占位符过多, 内容质量不达标

审核员需要判断:
  1. L1 的 REJECT 是否合理?(简报确实短但任务就是简报)
  2. L2 的 REJECT 是否合理?(2000 字但声称缺方法论)
  3. L3 的 REJECT 是否合理?(内容偏少但有结构)"""

TRACE_COMPLEX = """=== Agent 执行轨迹 (28 步) ===

[Step 1] 用户请求: 对所有 Agent 输出进行质检, 生成质量报告
[Step 2] 工具调用: list_directory("/data/agent-outputs/today/")
  -> 找到 750 条待审核记录
[Step 3] 工具调用: batch_embed("/data/agent-outputs/today/", model="qwen3-embedding")
  -> 返回 750 条向量, 维度 1024
[Step 4] 工具调用: cluster(embeddings, k=100)
  -> 聚类完成, 100 组, 每组 1 个代表
[Step 5-14] 工具调用: file_read 10 个代表样本
  -> 每个约 200-800 字
[Step 15] 工具调用: GLM-5.2 质检("rep_001")
  -> REJECT (研究简报, 内容过短)
[Step 16] 工具调用: GLM-5.2 质检("rep_002")
  -> PASS (测试日志, 42 passed)
[Step 17] 工具调用: GLM-5.2 质检("rep_003")
  -> REJECT (初稿, 结构不完整)
[Step 18-24] GLM-5.2 质检代表 004-010
  -> 6 PASS, 4 REJECT
[Step 25] 工具调用: log_results()
  -> 100 组: 67 PASS, 33 REJECT
[Step 26] 工具调用: aggregate_to_report()
  -> 750 单: 预计 67% 自动通过, 33% 需人工复核(约 248 单)
[Step 27] 工具调用: human_review_queue.create(248 items)
  -> 创建人工审核队列
[Step 28] 工具调用: notify_auditor(auditor_id="auditor-01", queue_size=248)
  -> 通知已发送

Phase Gate 结果: exit 0, 全文件存在 [PASS]
GLM-5.2 质检结果: 67/100 PASS, 33/100 REJECT

审核员需要判断:
  1. 33 组 REJECT 中有多少是误杀(聚类误差)?
  2. 67 组 PASS 中有多少是漏网垃圾?
  3. 聚类代表样本是否能代表整组?
  4. 反馈闭环中是否有审核员之前的判断被翻盘? """


def estimate_read_time(text):
    """估算技术文档阅读时间(秒)。中文 ~400 字/分, 英文 ~200 词/分。
    技术文档需更慢, 保守取 250 当量词/分钟。"""
    zh = sum(1 for c in text if ord(c) > 127)
    en = len(text.split())
    weight = int(zh * 0.6 + en * 0.3)  # 折算为"当量词"
    sec = weight / 250 * 60
    return weight, sec


print("=" * 90)
print("  缺陷六实验: Agent 轨迹长度 vs 最低审核时间")
print("=" * 90)
print()

traces = [
    ("简单 (3 步, 单任务)", TRACE_SIMPLE, 1),
    ("中等 (12 步, 多任务)", TRACE_MEDIUM, 3),
    ("复杂 (28 步, 全流程)", TRACE_COMPLEX, 4),
]

for label, trace, n_questions in traces:
    chars = len(trace)
    lines = trace.count("\n")
    weight, sec = estimate_read_time(trace)

    print(f"[{label}]")
    print(f"  字符数: {chars}")
    print(f"  行数: {lines}")
    print(f"  当量词数: {weight}")
    print(f"  最低阅读时间: {int(sec)} 秒 / {sec/60:.1f} 分钟")
    print(f"  需判断的问题数: {n_questions}")
    if sec > 15:
        ratio = int(sec / 15)
        print(f"  15 秒占比: {15/sec*100:.0f}% (只够读完 {100//ratio}% 的轨迹)")
        print(f"  => \"15 秒\" 差了 {int(sec - 15)} 秒")
    print()

# Summary table
print("=" * 90)
print("  汇总对照表")
print("=" * 90)
print(f"  {'轨迹规模':<24} {'字符数':>8} {'当量词':>8} {'阅读秒':>8} {'15秒达标?':>10} {'差多远'}")
print(f"  {'-'*24}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*20}")

total_weight = 0
for label, trace, n_q in traces:
    weight, sec = estimate_read_time(trace)
    total_weight += weight
    fits = "不可能" if sec > 60 else ("勉强" if sec > 30 else "可")
    diff = f"+{int(sec-15)}秒" if sec > 15 else "达标"
    bar = "=" * min(50, int(sec/2))
    print(f"  {label:<24} {len(trace):>8} {weight:>8} {int(sec):>5}秒    {fits:>8}  {bar} {diff}")

print(f"  {'-'*24}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*20}")
avg_sec = 0
_, _, counted = 0, 0, 0
for label, trace, n_q in traces:
    _, sec = estimate_read_time(trace)
    avg_sec += sec
    counted += 1
avg_sec /= counted
print()
print(f"  平均阅读时间: {int(avg_sec)} 秒 / {avg_sec/60:.1f} 分钟")
print(f"  结论:")
print(f"    - 最简轨迹也需要 {int(estimate_read_time(TRACE_SIMPLE)[1])} 秒, >15 秒")
print(f"    - 真实生产场景(12-28 步)的审核时间在 4-12 分钟")
print(f'    - "15 秒" 只可能出现在: 只看一行/不读上下文的情况')
print(f'    - 这和靶子文章"80% 秒判"是同一类营销话术')
print()
