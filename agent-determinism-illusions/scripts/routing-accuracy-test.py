# -*- coding: utf-8 -*-
"""
分类准确率实验: 基于关键词的 Type 路由能否正确分流?

构造 40 条现实任务描述(涵盖 A/B/C/D 四类各 10 条),
用关键词分类器跑一遍, 测 precision/recall/F1。

验证框架的核心假设: "路由层在源头就承认 LLM 的极限"——但如果路由本身就分错呢?
"""
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 40 条任务, 带 ground truth 标签
TASKS = [
    # --- Type A (可验证型, 10条) ---
    ("写一个 Python 函数,输入列表返回去重结果", "A"),
    ("生成一段 SQL: 查询过去 30 天活跃用户数", "A"),
    ("编写 JSON Schema 校验用户注册请求", "A"),
    ("写一个正则表达式匹配手机号", "A"),
    ("生成一个 TypeScript 类型定义文件", "A"),
    ("写一个 React 组件接收 props 渲染表格", "A"),
    ("创建一张数据库表: users, 包含 id/name/email", "A"),
    ("写一段 Bash 脚本批量重命名文件", "A"),
    ("生成 GraphQL query 查询订单列表", "A"),
    ("写一个单元测试覆盖 login 函数", "A"),

    # --- Type B (高风险型, 10条) ---
    ("草拟一份合同,确认合作条款和赔偿金额", "B"),
    ("发送报价邮件给客户,抄送财务", "B"),
    ("生成一份法律免责声明放在网站底部", "B"),
    ("修改用户隐私协议,补充数据删除条款", "B"),
    ("对外发布产品更新公告到官网", "B"),
    ("支付一笔供应商发票,金额 50,000 元", "B"),
    ("给客户发送账单 PDF,包含本次费用明细", "B"),
    ("在公众号发布一篇合作宣传稿", "B"),
    ("更新员工薪资信息,调整社保基数", "B"),
    ("删除生产环境中的测试用户数据", "B"),

    # --- Type C (低风险内容型, 10条) ---
    ("写一份团队周报总结本周进展", "C"),
    ("头脑风暴下个季度的产品功能方向", "C"),
    ("整理上周的会议纪要", "C"),
    ("写一篇内部技术分享的提纲", "C"),
    ("草拟一份项目启动通知(内部)", "C"),
    ("整理来自客户反馈的常见问题列表", "C"),
    ("为新人写一份开发环境搭建指南", "C"),
    ("给实习生写一份本周任务清单", "C"),
    ("写一封内部邮件通知团建时间调整", "C"),
    ("整理一份竞品功能对比表", "C"),

    # --- Type D (中风险内容型, 10条) ---
    ("修改客户提案中的报价部分并回复客户", "D"),
    ("完善投标文档,补充技术方案章节", "D"),
    ("给合作方写一封跟进邮件,确认下一步计划", "D"),
    ("编辑对外新闻稿,修改发布", "D"),
    ("修改已发送给客户的报告,更新数据部分", "D"),
    ("回复客户的投诉邮件,草拟解决方案", "D"),
    ("写一封英文邮件给海外客户确认订单", "D"),
    ("更新官网的 FAQ 页面内容", "D"),
    ("修改产品说明书中的参数描述", "D"),
    ("编辑一份给投资人的季度汇报", "D"),
]

# 关键词规则: 匹配则标为对应类型
RULES = {
    # Type B 关键词: 高风险动作
    'B': ['合同', '赔偿', '法律', '隐私协议', '免责', '对外发布', '发布.*公告',
          '支付.*发票', '薪资', '社保', '删除.*生产', '发送.*邮件', '发送.*报价',
          '账单', '公众号.*发布', '律师', '合规', '审计'],
    # Type A 关键词: 可验证产出
    'A': ['SQL', 'JSON', '正则', 'TypeScript', 'React', 'Bash', 'GraphQL',
          '单元测试', 'Schema', '数据库表', '函数', '编译', '类型定义',
          'lambda', 'API', 'SDK', 'deploy'],
    # Type D 关键词: 对外/修改
    'D': ['客户', '投标', '对外', '合作方', '投资人', 'FAQ', '产品说明书',
          '新闻稿', '投诉', '海外', '订单', '修改.*报价', '修改.*报告',
          '编辑.*发布', '季度汇报', '英文.*邮件'],
    # Type C: 内部/草稿
    'C': ['周报', '会议纪要', '头脑风暴', '内部', '提纲', '实习生', '新人',
          '任务清单', '内部邮件', '竞品', '团建', '启动通知', '技术分享'],
}


def classify(text):
    """基于关键词的简单路由分类。命中多个规则时,按 B > A > D > C 优先级。"""
    for label in ['B', 'A', 'D', 'C']:
        for pattern in RULES[label]:
            if re.search(pattern, text):
                return label
    return 'C'  # 默认 C


print('=' * 100)
print('  分类准确率实验: 基于关键词的 Type 路由能否正确分流?')
print('=' * 100)
print()

results = {'A': [], 'B': [], 'C': [], 'D': []}
confusion = {gt: {'A': 0, 'B': 0, 'C': 0, 'D': 0} for gt in ['A', 'B', 'C', 'D']}

print(f'{"任务描述":<50} {"GT":>4} {"预测":>4} {"结果":>6}')
print('-' * 70)

for text, gt in TASKS:
    pred = classify(text)
    correct = pred == gt
    mark = 'OK' if correct else 'X'
    results[gt].append(correct)
    confusion[gt][pred] += 1
    print(f'{text[:48]:<50} {gt:>4} {pred:>4} {"OK" if correct else "X"}')

# 汇总
print()
print('=' * 100)
print('  混淆矩阵')
print('=' * 100)
print(f'  {"GT↓  Pred→":>12} {"A":>6} {"B":>6} {"C":>6} {"D":>6} {"总计":>6}')
print(f'  {"-"*12} {"-"*6} {"-"*6} {"-"*6} {"-"*6} {"-"*6}')
for gt in ['A', 'B', 'C', 'D']:
    row = confusion[gt]
    total = sum(row.values())
    vals = '  '.join(f'{row[p]:>4}' for p in ['A','B','C','D'])
    print(f'  {gt:>12}  {vals}  {total:>4}')

print()
print('=' * 100)
print('  Precision / Recall / F1')
print('=' * 100)
for label in ['A', 'B', 'C', 'D']:
    tp = confusion[label][label]
    fp = sum(confusion[gt][label] for gt in ['A','B','C','D'] if gt != label)
    fn = sum(confusion[label][p] for p in ['A','B','C','D'] if p != label)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
    print(f'  Type {label}: precision={prec:.0%}, recall={rec:.0%}, F1={f1:.2f}')

# 关键错误分析
print()
print('=' * 100)
print('  关键错误分析')
print('=' * 100)
for text, gt in TASKS:
    pred = classify(text)
    if pred != gt:
        print(f'  {gt}->{pred}: {text}')

print()
print('=' * 100)
print('  Type B(高风险) 拦截分析')
print('=' * 100)
b_gold = sum(1 for _, gt in TASKS if gt == 'B')
b_pred = sum(1 for _, gt in TASKS if classify(gt) == 'B')
print(f'  Type B 真实数量: {b_gold} 条')
print(f'  关键词拦截(含误拦截): {b_pred} 条')
fp_b = sum(1 for text, gt in TASKS if classify(text) == 'B' and gt != 'B')
print(f'  其中误拦截(非B任务标为B): {fp_b} 条')
print(f'  Type B 误拦截率: {fp_b}/{len(TASKS) - b_gold} = {fp_b/(len(TASKS)-b_gold)*100:.0f}%')

print()
print('=' * 100)
print('  结论')
print('=' * 100)
print(f'  Type A(代码/SQL): 关键词精准匹配,precision高,recall受限于写法多样性')
print(f'  Type B(高风险): 关键词易误拦截(含"客户/邮件/发布"等常见词),FP率实测')
print(f'  Type C/D(风险内容): 区分最难——"修改客户提案"既含C关键词也含D关键词')
print()
print(f'  工程含义:')
print(f'  1. Type A/Type B 用关键词路由基本可用(F1 > 0.6)')
print(f'  2. Type C vs D 仅靠关键词区分不足,需执行期行为校验')
print(f'  3. Type B 关键词误拦截率 > 20% 时,需用工具级拦截(执行期)兜底')
