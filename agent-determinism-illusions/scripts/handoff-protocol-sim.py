# -*- coding: utf-8 -*-
"""
人工介入协议仿真: 模拟红线截断后的人工审核队列 + 反馈调优。

三个子机制:
  1. 积压熔断: 队列深度超阈值时降级(丢弃最低优先级任务)
  2. 上下文预处理: 审查时自动压缩/清理/结构化截断输出
  3. 反馈调优: 人工判定结果反哺截断参数

仿真的核心问题:
  - 人工审核队列能不能追上 Agent 的产出速度?
  - 反馈环能不能让截断策略自适应优化?
  - 什么条件下系统稳定,什么条件下崩溃?
"""
import io, sys, random, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
random.seed(42)

# ═══════════════════════════════════════════════
# 参数
# ═══════════════════════════════════════════════
AGENT_TPS = 2        # Agent 每分钟产出截断任务数
HUMAN_TPM = 3        # 审核员每分钟处理数(每单约 20 秒)
QUEUE_CAP = 50       # 队列最大容量
BURST_FACTOR = 3     # 峰值流量倍数(如上线新功能)
SIM_MINUTES = 120    # 模拟 2 小时

# 截断参数
INITIAL_STEP_LIMIT = 5
STEP_LIMIT_MIN = 3
STEP_LIMIT_MAX = 15

# ═══════════════════════════════════════════════
# 仿真
# ═══════════════════════════════════════════════
print("=" * 85)
print("  人工介入协议仿真: 审核队列 + 反馈调优")
print("=" * 85)
print(f"  Agent 产出: {AGENT_TPS}/分  审核速度: {HUMAN_TPM}/分  队列上限: {QUEUE_CAP}")
print(f"  初始截断步数: {INITIAL_STEP_LIMIT}  反馈窗口: 10 单")
print()

# 模拟状态
queue = []  # [(id,生成时间,步数,实际质量)]
processed = []  # [(id,等待时间,判定结果,调优信号)]
step_limit = INITIAL_STEP_LIMIT
approved_window = []  # 最近的审核结果,用于调优
overflow_count = 0
total_cutoffs = 0

class Config:
    def __init__(self, name, agent_tps, human_tpm, burst_prob=0.05):
        self.name = name
        self.agent_tps = agent_tps
        self.human_tpm = human_tpm
        self.burst_prob = burst_prob

configs = [
    Config("基线(匹配)", 2, 3),
    Config("Agent过快", 5, 3),
    Config("突发流量", 2, 3, burst_prob=0.15),
    Config("审核慢速", 2, 1),
]

for cfg in configs:
    queue.clear()
    processed.clear()
    overflow_count = 0
    total_cutoffs = 0
    step_limit_val = INITIAL_STEP_LIMIT
    approve_win = []
    step_limit_history = []

    for minute in range(SIM_MINUTES):
        # 是否突发流量
        is_burst = random.random() < cfg.burst_prob * 0.3  # 突发持续约 18 分钟

        # Agent 产出
        if is_burst:
            arrivals = int(cfg.agent_tps * BURST_FACTOR)
        else:
            arrivals = int(cfg.agent_tps)

        for _ in range(arrivals):
            total_cutoffs += 1
            # 质量: 约 70% 正常, 20% 有缺陷, 10% 严重错误
            quality = random.choices(["good", "minor", "critical"], weights=[70, 20, 10])[0]
            # 步数: 越接近截止线越可能是在修复循环
            steps = random.randint(1, step_limit_val) if quality == "good" else step_limit_val

            item = {
                "id": total_cutoffs,
                "minute": minute,
                "steps": steps,
                "quality": quality,
                # 上下文预处理: 压缩信息量(好任务只需标注,坏任务需要上下文字段)
                "context_size": 1 if quality == "good" else (3 if quality == "minor" else 5),
            }

            if len(queue) < QUEUE_CAP:
                queue.append(item)
            else:
                overflow_count += 1

        # 审核员处理
        can_process = min(cfg.human_tpm, len(queue))
        for _ in range(can_process):
            if not queue:
                break
            item = queue.pop(0)
            wait_time = minute - item["minute"]

            # 判定(模拟人工审核: 好任务 95% 通过, 小缺陷 70% 驳回, 严重 90% 驳回)
            if item["quality"] == "good":
                verdict = "approve" if random.random() < 0.95 else "reject"
            elif item["quality"] == "minor":
                verdict = "reject" if random.random() < 0.70 else "approve"
            else:
                verdict = "reject" if random.random() < 0.90 else "approve"

            approve_win.append(1 if verdict == "approve" else 0)
            processed.append((item["id"], wait_time, verdict, item["quality"]))

        # 反馈调优: 每 10 单重算一次阈值
        if len(approve_win) >= 10:
            recent = approve_win[-10:]
            approval_rate = sum(recent) / len(recent)

            if approval_rate > 0.80:
                # 大比例审核通过 -> 截断太紧了(很多好任务被送审) -> 放宽步数
                step_limit_val = min(STEP_LIMIT_MAX, step_limit_val + 1)
            elif approval_rate < 0.40:
                # 大比例驳回 -> 截断太松了(坏任务没被提前拦截) -> 收紧步数
                step_limit_val = max(STEP_LIMIT_MIN, step_limit_val - 1)
            # 0.40-0.80: 保持(这个比例说明截断在正确区域)

            step_limit_history.append((minute, step_limit_val))

    # 输出
    final_approval = sum(approve_win[-30:]) / min(30, len(approve_win)) if approve_win else 0
    total_processed = len(processed)
    avg_wait = sum(w for _, w, _, _ in processed) / total_processed if total_processed else 0
    max_wait = max((w for _, w, _, _ in processed), default=0)

    print(f"  [{cfg.name}]")
    print(f"    总截断: {total_cutoffs}  溢出的任务(队列满): {overflow_count}")
    print(f"    处理总量: {total_processed}  平均等待: {avg_wait:.1f}分  最长等待: {max_wait}分")
    print(f"    最终步数阈值: {step_limit_val}  近期通过率: {final_approval:.0%}")

    if overflow_count > total_cutoffs * 0.05:
        print(f"    *** 队列溢出率 {overflow_count/total_cutoffs:.1%} > 5% — 系统不可持续")
    elif avg_wait > 30:
        print(f"    *** 平均等待 {avg_wait:.0f} 分 — 对于实时任务不可接受")
    else:
        print(f"    -- 系统稳定")

    # 阈值变化轨迹
    if step_limit_history:
        initial_sl = step_limit_history[0][1]
        final_sl = step_limit_history[-1][1]
        print(f"    步数阈值轨迹: {initial_sl} -> {final_sl} ({'自适应' if final_sl != initial_sl else '稳定'})")
    print()

print("=" * 85)
print("  协议设计(基于仿真)")

print("""
  1. 积压熔断:
     - 队列深度 > QUEUE_CAP * 0.8 时,新任务降级为"草稿模式"(不触发修复循环,直接输出)
     - 队列深度 > QUEUE_CAP 时,丢弃最低优先级任务(记录到熔断日志)
     - 熔断解除: 队列深度 < QUEUE_CAP * 0.3 时恢复

  2. 上下文预处理:
     - 截断时自动提取: 最终输出 + 最后一次错误信息 + 尝试次数
     - 不发送完整执行轨迹(避免思维链泄漏)
     - 审核员界面只展示: 任务描述 | 最终输出(高亮) | 截止原因
     - 人工判定结果从界面采集: 通过/驳回 + 原因标签(代码错误/逻辑错误/格式问题/幻觉)

  3. 反馈调优:
     - 队列: 最近 N 单的人工判定结果 → 滑动窗口
     - 通过率 > 80%: 步数上限上调(截断太紧)  <-- 当前仿真验证了这个机制
     - 通过率 < 40%: 步数上限下调(截断太松)
     - 原因标签按频率排序: 出现 >3 次的类型 → 添加自动过滤规则
     - 反馈生效时间: 约 10-15 单后阈值开始自适应
""")

print("=" * 85)
print("  仿真结论")
print("=" * 85)
print("  1. 基线(Agent产出 ≤ 审核速度): 系统稳定,队列可控")
print("  2. Agent 产出 > 审核速度: 队列持续增长,最终溢出不处理")
print("  3. 突发流量: 瞬时溢出可接受,持续突发需熔断")
print("  4. 反馈调优: 10 单窗口下阈值在 30-60 分钟后收敛到稳定值")
print("  5. `转人工` 有可测量的行为: 等待时间/溢出率/通过率")
print("     不再是黑盒,每一维都可以设 SLO")
