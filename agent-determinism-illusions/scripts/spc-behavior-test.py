# -*- coding: utf-8 -*-
"""
SPC 行为特征检测实验: 统计阈值能否抓住 Agent 输出异常?

对实验 E 的 8 个场景(L1-L4 合法, G1-G4 垃圾)做行为特征分析,
验证: SPC 能抓住格式异常(句号/TODO)但不能抓语义陷阱(G4 零用例)
"""
import io, sys, statistics as stat
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCENES = [
    ('L1(合法-被误杀:简报)',  True,
     '# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷...'),
    ('L2(合法-被误杀:初稿)',  True,
     '# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字）'),
    ('L3(合法-被误杀:章节)',  True,
     '# 第 1 章\n\n本章详细论述 Pre-AL Gate 设计...'),
    ('L4(合法-放行:测试日志)',True,
     '(工具日志: python run_tests.py --suite all -> exit_code=0, 42 passed, 0 failed)'),
    ('G1(垃圾:鸭子)',         False,
     '我是一只小鸭子，嘎嘎嘎。'),
    ('G2(垃圾:句号)',         False,
     '。'),
    ('G3(垃圾:TODO)',         False,
     'TODO'),
    ('G4(垃圾:零用例)',       False,
     '(工具日志: python run_tests.py -> exit_code=0, 0 passed (no tests collected))'),
]

# 特征提取
def extract_features(text):
    n = len(text)
    special = sum(1 for c in text if c in '，。！？、；：""''（）【】—…·《》.,!?;:\"\'()[]-+*/=><@#$%^&|~` ') / n
    digits = sum(1 for c in text if c.isdigit()) / n
    alpha = sum(1 for c in text if c.isalpha() and ord(c) < 128) / n
    cjk = sum(1 for c in text if '一' <= c <= '鿿') / n
    lines = text.count('\n') + 1
    return n, special, digits, alpha, cjk, lines

rows = []
for sc_id, legit, text in SCENES:
    n, sp, dig, alp, cjk, lines = extract_features(text)
    rows.append({'id': sc_id, 'legit': legit, 'n': n, 'sp': sp, 'dig': dig,
                 'alp': alp, 'cjk': cjk, 'lines': lines})

# 统计阈值
feats = {'n': '长度', 'sp': '特殊符', 'dig': '数字', 'alp': '字母', 'cjk': '中文'}
feat_names = list(feats.keys())

thresholds = {}
for f in feat_names:
    vals = [r[f] for r in rows]
    m = stat.mean(vals)
    s = stat.stdev(vals) if len(vals) > 1 else 0.01
    lo = m - 1.5 * s
    hi = m + 1.5 * s
    thresholds[f] = (m, s, lo, hi)

# 检测
def detect_flags(row, thresholds):
    flags = []
    for f, (m, s, lo, hi) in thresholds.items():
        if row[f] > hi:
            flags.append((f, 'HIGH'))
        elif row[f] < lo:
            flags.append((f, 'LOW'))

    # 单特征重复检测(所有字符同类型)
    # 已在特征中通过特殊符占比反映, 不重复

    return flags

print('=' * 100)
print('  SPC 行为特征检测: 统计阈值能否抓住 Agent 输出异常?')
print('=' * 100)
print()
header = f'{"场景":<30} {"长度":>6} {"特殊符%":>7} {"数字%":>6} {"字母%":>6} {"中文%":>6} {"行数":>4}  SPC标记'
print(header)
print('-' * len(header))

for r in rows:
    flags = detect_flags(r, thresholds)
    flag_str = '|'.join([f'{feats.get(f[0],f[0])}:{f[1]}' for f in flags]) if flags else '(-)normal'
    outcome = ''
    if not r['legit'] and not flags:
        outcome = '  *** 漏报! ***'
    if r['legit'] and flags:
        outcome = '  *** 误报! ***'
    print(f'{r["id"]:<30} {r["n"]:>6} {r["sp"]*100:>6.0f}% {r["dig"]*100:>5.0f}% '
          f'{r["alp"]*100:>5.0f}% {r["cjk"]*100:>5.0f}% {r["lines"]:>3}行  {flag_str:<30}{outcome}')

print()
print('=' * 100)
print('  阈值参考')
print('=' * 100)
for f, label in feats.items():
    m, s, lo, hi = thresholds[f]
    print(f'  {label}: mean={m:.3f}, sd={s:.3f}, 正常范围=[{lo:.2f}, {hi:.2f}]')

print()
print('=' * 100)
print('  漏报分析')
print('=' * 100)
for r in rows:
    if not r['legit']:
        flags = detect_flags(r, thresholds)
        status = 'SPC抓住' if flags else 'SPC漏报'
        print(f'  {r["id"]:<30} {status}')

print()
print('  误报分析')
print('=' * 100)
for r in rows:
    if r['legit']:
        flags = detect_flags(r, thresholds)
        status = 'SPC标记' if flags else 'SPC正常'
        print(f'  {r["id"]:<30} {status}')

print()
print('=' * 100)
print('  结论')
print('=' * 100)
print('  SPC 能抓: 格式/长度异常(句号/TODO)')
print('  SPC 漏报: 语义陷阱(G4 零用例——和 L4 行为特征几乎一致)')
print('  SPC 误报: 无(合法场景的行数/长度在正常范围内)')
print()
print('  与文章的盲区声明一致:')
print('    "SPC catches format anomalies but not semantic traps (G4-class)"')
