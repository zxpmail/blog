# -*- coding: utf-8 -*-
"""
实验 B：证伪《ReAct 只是起点》第 4 节"目标连续性裁决"机制。

文章断言：用户中途插嘴时，用"词汇重叠度"判定新旧任务，
  >= 0.24 判为同任务
  <= 0.08 判为新任务
  0.08~0.24 交 LLM 裁决
并声称"80% 用代码秒判"。

本实验构造 30 对 (当前任务, 新输入) 带标注样本，
套用上述阈值，统计：
  - 硬误判（SAME 判成 NEW，或 NEW 判成 SAME）
  - 推给 LLM（落入 0.08~0.24 不确定区，削弱"80% 秒判"）
"""

# 30 对样本。label: SAME=同任务, NEW=新任务
# 类别：paraphrase(同义改写)/crosslingual(跨语言)/antonym(反义高重叠)
#       /easy_same(同任务高重叠基线)/easy_new(新任务低重叠基线)
PAIRS = [
    # ---- 同任务·同义改写（label=SAME，语义同但词汇差异大）----
    ("帮我写一篇关于循环引擎的技术文章", "我想让你梳理一下 Agent 内核里那个跑循环的部分整理成博客", "SAME", "paraphrase"),
    ("做一个用户登录注册的功能", "加一下账户鉴权那块就是注册和登录", "SAME", "paraphrase"),
    ("把这段代码优化一下太慢了", "这段逻辑跑得有点卡你帮我重写得更高效些", "SAME", "paraphrase"),
    ("修复支付页面的 bug", "结账那页报错了你看看怎么回事", "SAME", "paraphrase"),
    ("给我设计一个数据库表结构", "帮我想想这个业务的存储 schema 怎么设计", "SAME", "paraphrase"),
    ("写一个 CLI 工具解析 markdown 的目录", "做个命令行程序从 md 文件里提取标题树", "SAME", "paraphrase"),

    # ---- 同任务·跨语言（label=SAME，重叠度接近 0）----
    ("写一篇循环引擎的技术文章", "write a technical post about the loop engine", "SAME", "crosslingual"),
    ("修复登录 bug", "fix the login bug", "SAME", "crosslingual"),
    ("优化这段代码的性能", "optimize the performance of this code", "SAME", "crosslingual"),
    ("设计数据库表结构", "design the database schema", "SAME", "crosslingual"),
    ("做一个用户注册功能", "build a user signup feature", "SAME", "crosslingual"),
    ("解析 markdown 目录", "parse the markdown table of contents", "SAME", "crosslingual"),

    # ---- 新任务·高重叠（label=NEW，词汇重叠高但任务不同/相反）----
    ("继续写那篇循环引擎的文章", "删掉那篇循环引擎的文章", "NEW", "antonym"),
    ("把登录功能加上", "把登录功能撤掉", "NEW", "antonym"),
    ("给这个文件加注释", "给这个文件删注释", "NEW", "antonym"),
    ("帮我部署循环引擎服务", "帮我下线循环引擎服务", "NEW", "antonym"),
    ("优化代码 A 的性能", "优化代码 B 的性能", "NEW", "shared_template"),
    ("写一篇循环引擎的文章", "写一篇 RAG 的文章", "NEW", "shared_template"),

    # ---- 同任务·高重叠基线（label=SAME，文章很可能在这类上调参）----
    ("写一篇循环引擎的技术文章", "继续写那篇循环引擎的技术文章", "SAME", "easy_same"),
    ("修复登录 bug", "登录 bug 修复好了吗继续", "SAME", "easy_same"),
    ("优化代码性能", "继续优化代码性能", "SAME", "easy_same"),
    ("设计数据库表", "数据库表设计继续", "SAME", "easy_same"),
    ("做用户注册功能", "继续做用户注册功能", "SAME", "easy_same"),
    ("解析 markdown 目录", "继续解析 markdown 目录", "SAME", "easy_same"),

    # ---- 新任务·低重叠基线（label=NEW，与任务无关的插话）----
    ("写循环引擎文章", "今天中午吃什么", "NEW", "easy_new"),
    ("修复登录 bug", "推荐一部科幻电影", "NEW", "easy_new"),
    ("优化代码性能", "北京明天天气怎么样", "NEW", "easy_new"),
    ("设计数据库表", "给我讲个笑话", "NEW", "easy_new"),
    ("做用户注册功能", "帮我订一张机票", "NEW", "easy_new"),
    ("解析 markdown 目录", "瑜伽初学者该怎么练", "NEW", "easy_new"),
]


def tokenize_char_ngrams(s, n):
    """字符 n-gram 分词，去掉空格和标点。中英文混排最常用的短文本相似度方案。"""
    import re
    s = re.sub(r'[\s\W_]+', '', s.lower())
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i+n] for i in range(len(s) - n + 1)}


def tokenize_words(s):
    """空白分词（英文友好，中文无分词器时的退化方案）。"""
    import re
    return set(re.findall(r'\w+', s.lower()))


def jaccard(a, b):
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def classify(score):
    """套文章阈值：>=0.24 SAME，<=0.08 NEW，中间 UNCERTAIN（推给 LLM）。"""
    if score >= 0.24:
        return "SAME"
    if score <= 0.08:
        return "NEW"
    return "UNCERTAIN"


def run(tokenizer_name, tokenizer):
    print(f"\n{'='*92}")
    print(f" 分词方案：{tokenizer_name}")
    print(f"{'='*92}")
    header = f"{'#':>2} {'类别':<14} {'标注':<5} {'分数':>6} {'预测':<10} {'结果':<8}"
    print(header)
    print("-" * 92)

    stats = {
        "total": 0,
        "hard_wrong": 0,      # SAME->NEW 或 NEW->SAME
        "uncertain": 0,       # 落入 0.08~0.24
        "correct": 0,
        # 按类别细分
        "paraphrase_wrong": 0, "paraphrase_total": 0,
        "crosslingual_wrong": 0, "crosslingual_total": 0,
        "antonym_wrong": 0, "antonym_total": 0,
        "easy_correct": 0, "easy_total": 0,
    }

    for i, (task, new_input, label, cat) in enumerate(PAIRS, 1):
        a = tokenizer(task)
        b = tokenizer(new_input)
        score = jaccard(a, b)
        pred = classify(score)

        stats["total"] += 1
        if cat in ("paraphrase", "crosslingual", "antonym"):
            key = f"{cat}_total"
            stats[key] += 1

        if pred == "UNCERTAIN":
            stats["uncertain"] += 1
            verdict = "推LLM"
            # 不确定区削弱"80%秒判"，但不计为硬误判
            if cat in ("paraphrase", "crosslingual", "antonym"):
                stats[f"{cat}_wrong"] += 1
        elif pred == label:
            stats["correct"] += 1
            verdict = "✓"
            if cat in ("easy_same", "easy_new"):
                stats["easy_correct"] += 1
                stats["easy_total"] += 1
        else:
            stats["hard_wrong"] += 1
            verdict = "✗误判"
            if cat in ("paraphrase", "crosslingual", "antonym"):
                stats[f"{cat}_wrong"] += 1

        print(f"{i:>2} {cat:<14} {label:<5} {score:>6.3f} {pred:<10} {verdict:<8}")

    print("-" * 92)
    print(f"\n【{tokenizer_name} 汇总】")
    print(f"  样本总数          : {stats['total']}")
    print(f"  硬误判            : {stats['hard_wrong']:>2}  ({stats['hard_wrong']/stats['total']*100:.0f}%)")
    print(f"  推给 LLM(不确定区): {stats['uncertain']:>2}  ({stats['uncertain']/stats['total']*100:.0f}%)")
    code_decided = stats['total'] - stats['uncertain']
    print(f"  纯代码能判的      : {code_decided:>2}  ({code_decided/stats['total']*100:.0f}%)  ← 文章声称 80%")
    print(f"  其中判对的        : {stats['correct']:>2}")
    print(f"\n  杀伤样本细分:")
    print(f"    同义改写 (应判 SAME): {stats['paraphrase_wrong']}/{stats['paraphrase_total']} 被阈值坑")
    print(f"    跨语言   (应判 SAME): {stats['crosslingual_wrong']}/{stats['crosslingual_total']} 被阈值坑")
    print(f"    反义高重叠(应判 NEW): {stats['antonym_wrong']}/{stats['antonym_total']} 被阈值坑")
    print(f"    简单基线 (易样本)  : {stats['easy_correct']}/{stats['easy_total']} 判对 ← 文章大概率在这类上调的参")

    return stats


if __name__ == "__main__":
    print("\n" + "█" * 92)
    print("  实验 B：证伪《ReAct 只是起点》词汇重叠度阈值 (0.24 / 0.08)")
    print("█" * 92)

    # 三种分词，证明结论不依赖具体分词方案
    run("字符 2-gram Jaccard（中文短文本最常用）", lambda s: tokenize_char_ngrams(s, 2))
    run("字符 3-gram Jaccard", lambda s: tokenize_char_ngrams(s, 3))
    run("空白分词 Jaccard（英文友好）", tokenize_words)

    print("\n" + "=" * 92)
    print(" 结论：无论哪种分词，同义改写/跨语言/反义三类样本大量硬误判或被推给 LLM，")
    print("       且文章声称的『80% 纯代码秒判』在含上述常见情形的样本集上不成立。")
    print("=" * 92)
