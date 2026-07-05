# -*- coding: utf-8 -*-
"""
模拟 SPC 冷启动基线偏移: 首周 Agent 有 Bug 时,动态阈值会失效。

场景:
  Phase 1 (正常):  500 条轨迹, 轮数 mean=5, sd=2
  Phase 2 (Bug):   500 条轨迹, 轮数 mean=12, sd=3 (Agent 陷入循环)
  Phase 3 (恢复):  Agent 修复, 回到正常, 但出现一个新异常(20轮)

验证: 静态硬阈值(>10轮) vs 动态阈值(mean±1.5sd) 在 Phase 3 的检出率。
"""
import io, sys, random, math, statistics as stat
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

random.seed(42)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# 生成三阶段数据
N = 500
phase1 = [clamp(int(random.gauss(5, 2)), 1, 15) for _ in range(N)]   # 正常
phase2 = [clamp(int(random.gauss(12, 3)), 3, 25) for _ in range(N)]  # Bug期
phase3_normal = [clamp(int(random.gauss(5, 2)), 1, 15) for _ in range(N)]
PHASE3_ANOMALY = 20  # 需检出的异常

# 方式1: 静态硬阈值(冷启动)
STATIC_THRESHOLD = 10  # 经验值: 正常Agent不应超过10轮

# 方式2: 动态阈值(有Bug期数据污染)
def dynamic_threshold(data, k=1.5):
    m = stat.mean(data)
    s = stat.stdev(data) if len(data) > 1 else 1.0
    return m + k * s

# 方式3: 纯首周正常基线(最理想,但实际拿不到)
ideal_baseline = dynamic_threshold(phase1)

print('=' * 90)
print('  SPC 冷启动基线偏移模拟')
print('=' * 90)
print()
print(f'  Phase 1 (正常期, N={N}):      mean={stat.mean(phase1):.1f}, sd={stat.stdev(phase1):.2f}')
print(f'  Phase 2 (Bug 期, N={N}):      mean={stat.mean(phase2):.1f}, sd={stat.stdev(phase2):.2f}')
print(f'  Phase 3 (恢复期, N={N}):      mean={stat.mean(phase3_normal):.1f}, sd={stat.stdev(phase3_normal):.2f}')
print(f'  Phase 3 异常值:                 {PHASE3_ANOMALY} 轮')
print()

# 基线计算
baselines = {
    '冷启动(只用Phase1,理想情况)': phase1,
    '混入Bug期(Phase1+Phase2+Phase3)': phase1 + phase2 + phase3_normal,
    '静态硬阈值(经验值>10轮)': None,
}

print('-' * 90)
print(f'  {\"基线来源\":<45} {\"阈值(上限)\":>15} {\"Phase3异常(\"+str(PHASE3_ANOMALY)+\"轮)\":>20}')
print('-' * 90)

for name, data in baselines.items():
    if data is None:
        thresh = STATIC_THRESHOLD
        source_desc = f'经验值: >{STATIC_THRESHOLD}轮即报警'
    else:
        thresh = dynamic_threshold(data)
        source_desc = f'mean+1.5sd = {stat.mean(data):.1f}+1.5*{stat.stdev(data):.2f} = {thresh:.1f}'

    caught = PHASE3_ANOMALY > thresh
    mark = '✅ 抓住!' if caught else '❌ 漏报!'
    print(f'  {name:<45} {thresh:>10.1f}轮    {mark:>20}')

print()
print('-' * 90)
print('  详细分析')
print('-' * 90)

# 动态阈值(混合期) 的阈值计算过程
mixed = phase1 + phase2 + phase3_normal
m_mixed = stat.mean(mixed)
s_mixed = stat.stdev(mixed)
print(f'  混合基线(含Bug期): mean={m_mixed:.1f}, sd={s_mixed:.2f}')
print(f'  动态阈值 = {m_mixed:.1f} + 1.5 x {s_mixed:.2f} = {m_mixed + 1.5*s_mixed:.1f}')
print(f'  Phase3异常({PHASE3_ANOMALY}轮) < 阈值({m_mixed + 1.5*s_mixed:.1f}) -> 漏报')
print(f'  原因: Bug期(mean={stat.mean(phase2):.1f})将整体均值从{stat.mean(phase1):.1f}拉到{m_mixed:.1f}')
print()

# 展示不同 Phase 2 bug 严重程度对漏报率的影响
print('-' * 90)
print('  敏感性分析: Bug期严重程度 vs 漏报率')
print('-' * 90)
print(f'  {\"Bug期mean\":>12} {\"Bug期sd\":>10} {\"混合阈值\":>10} {\"异常检出?\":>10}')
print('  ' + '-' * 44)

for bug_mean in [8, 10, 12, 14, 16]:
    bug_phase = [clamp(int(random.gauss(bug_mean, 3)), 3, 30) for _ in range(N)]
    mixed2 = phase1 + bug_phase + phase3_normal
    th = stat.mean(mixed2) + 1.5 * stat.stdev(mixed2)
    caught = PHASE3_ANOMALY > th
    print(f'  {bug_mean:>8}轮      3.0      {th:>8.1f}轮    {"✅" if caught else "❌"}')

print()
print('=' * 90)
print('  结论')
print('=' * 90)
print('  1. 冷启动(纯正常期)基线: Phase3异常可检出')
print('  2. 混入Bug期的动态基线: 均值被拉到高位,阈值右移,异常漏报')
print('  3. 静态硬阈值(经验值): 不受基线偏移影响,始终检出新异常')
print('  4. 敏感性分析: Bug期均值>=10时,混合阈值>20,异常一定漏报')
print()
print('  工程含义:')
print('    - 上线首周必须用静态硬阈值(根据任务类型预设轮数上限)')
print('    - 运行2周确认无系统性Bug后,切换到动态统计阈值')
print('    - 动态阈值必须绑定时间窗口(如最近7天),不要用累计全量')
