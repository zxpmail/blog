# -*- coding: utf-8 -*-
"""
实验 D：Embedding 同义/反义/无关语义分离测试

对应文章「第四刀：我也撒了谎——拆我自己」部分。
验证神经 embedding 是否能区分同义（同一任务、不同措辞）和反义（同一话题、相反操作）。

依赖：Ollama + qwen3-embedding:0.6b（运行前先 `ollama pull qwen3-embedding:0.6b`）
运行：python3 embedding-semantic-test.py

方法：
  构造 12 组同义对、12 组反义对、12 组无关对，
  用 Qwen3-embedding 计算每组 cosine 相似度，
  统计三类分布的均值/最值/重叠度。

预期结论：
  同义(0.77) 和 反义(0.74) 高度重叠，均值差 <0.03。
  embedding 能分离「相关 vs 无关」但不能分离「同方向 vs 反方向」。
"""

import json
import urllib.request
import numpy as np

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding:0.6b"

SYN = [
    ("继续写那篇循环引擎的文章", "把那篇循环引擎的文章接着写完"),
    ("修复登录 bug", "登录那个问题修一下"),
    ("优化这段代码性能", "把这段代码跑得更快些"),
    ("设计数据库表结构", "想想存储 schema 怎么建"),
    ("解析 markdown 目录", "从 md 文件提取标题树"),
    ("加上用户注册功能", "把账户注册那块做了"),
    ("继续写那篇文章", "把那篇文章接着写"),
    ("部署循环引擎服务", "把循环引擎上线"),
    ("给文件加注释", "给文件补上说明"),
    ("写一篇技术文章", "撰写一篇技术博文"),
    ("修复支付页面的 bug", "结账那页报错了你看看怎么回事"),
    ("做一个用户登录注册的功能", "加一下账户鉴权那块"),
]
ANT = [
    ("继续写那篇文章", "删掉那篇文章"),
    ("把登录功能加上", "把登录功能撤掉"),
    ("部署循环引擎服务", "下线循环引擎服务"),
    ("给文件加注释", "删掉文件的注释"),
    ("优化代码性能", "别优化代码性能"),
    ("创建这个文件", "删除这个文件"),
    ("启动这个服务", "停止这个服务"),
    ("把价格调高", "把价格调低"),
    ("允许这个操作", "禁止这个操作"),
    ("继续这个任务", "取消这个任务"),
    ("把功能加上", "把功能撤掉"),
    ("给价格涨价", "给价格降价"),
]
UNR = [
    ("继续写那篇文章", "今天中午吃什么"),
    ("修复登录 bug", "推荐一部科幻电影"),
    ("优化代码性能", "北京明天天气怎么样"),
    ("设计数据库表", "给我讲个笑话"),
    ("解析 markdown 目录", "帮我订一张机票"),
    ("加用户注册功能", "瑜伽初学者该怎么练"),
    ("继续写那篇文章", "最近有什么好电影"),
    ("部署循环引擎服务", "这首歌叫什么名字"),
    ("给文件加注释", "明天几点开会"),
    ("写技术文章", "去哪个国家旅游比较好"),
    ("修复登录 bug", "特朗普最近又说了什么"),
    ("优化代码性能", "怎么写一个 REST API"),
]


def get_embeddings(texts):
    data = json.dumps({"model": MODEL, "input": texts}).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=120)
    body = json.loads(resp.read())
    return [np.array(e) for e in body["embeddings"]]


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def run(cat, name, pairs):
    scores = [(cos(mapping[a], mapping[b]), a, b) for a, b in pairs]
    arr = np.array([s[0] for s in scores])
    print(f"\n{name} N={len(scores):>2}  mean={arr.mean():.3f}  min={arr.min():.3f}  max={arr.max():.3f}")
    for s, a, b in sorted(scores, reverse=True):
        print(f"    {s:.3f}  {a[:24]} <-> {b[:24]}")
    return arr


if __name__ == "__main__":
    all_texts = list(set(p for pair in SYN + ANT + UNR for p in pair))
    print(f"共 {len(all_texts)} 个文本,请求 {MODEL} ...")
    embs = get_embeddings(all_texts)
    mapping = {t: e for t, e in zip(all_texts, embs)}
    print(f"维度: {len(embs[0])}")

    print("\n" + "=" * 60)
    syn = run(SYN, "同义(应高)", SYN)
    ant = run(ANT, "反义(应中低)", ANT)
    unr = run(UNR, "无关(应低)", UNR)

    print("\n" + "=" * 60)
    best = max(ant.max(), unr.max())
    syn_sep = sum(s > best for s in syn) / len(syn) * 100
    print(f"非同义组最高余弦: {best:.3f}")
    print(f"同义高于此阈值的比例: {syn_sep:.0f}%")
    print(f"同义均值-反义均值差: {syn.mean() - ant.mean():.3f}")

    print(f"\n结论: ", end="")
    if syn_sep >= 80:
        print("embedding 能较好分离同义/反义")
    elif syn_sep >= 40:
        print("部分分离但交叠严重,单阈值不可靠")
    else:
        print("embedding 无法分离同义/反义 → 向量余弦在同话题/反向上无效")

    print(f"\n注意: 无关组(mean={unr.mean():.3f})显著低于同义/反义({syn.mean():.3f}/{ant.mean():.3f})")
    print("→ embedding 能区分「相关」vs「无关」,但无法区分「同方向」vs「反方向」(当话题相同时)")
