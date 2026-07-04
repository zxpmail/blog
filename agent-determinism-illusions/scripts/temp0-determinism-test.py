# -*- coding: utf-8 -*-
"""
实验 A：证伪《ReAct 只是起点》"评估器温度设为 0.0，「输出「几乎完全确定」」" 的断言。

方法：对同一 prompt，在 temperature=0 下重复调用 N 次，
     比对每次输出是否完全一致（exact-match），并量化差异。

判定：
  exact-match 率 < 100%  → "「几乎完全确定」" 断言证伪
  exact-match 率 = 100%  → 该 provider 该模型在测试样本上确定（但仍不能推广为普适断言）

注意：本环境只有 GLM-5.2（经 open.bigmodel.cn Anthropic 兼容接口）。
     OpenAI / 原生 Anthropic / 国产其他模型需另配 key 补测。
     但文章断言是普遍化的，单 provider 出现非确定即证伪其普遍性。
"""

import os
import sys
import io
import time
import difflib
import statistics
from anthropic import Anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 从环境读 BigModel 兼容配置
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "glm-5.2"

if not BASE_URL or not TOKEN:
    print("缺少 ANTHROPIC_BASE_URL 或 token，无法测试")
    sys.exit(1)

client = Anthropic(base_url=BASE_URL, api_key=TOKEN)

N = 20  # 每个 prompt 重复次数

# 三类 prompt，覆盖"最稳定→最有发散空间"
PROMPTS = [
    ("数学事实（理论最稳定）",
     "What is 17 multiplied by 23? Reply with only the final number, no explanation."),

    ("结构化列举（中等发散）",
     "List exactly 5 adjectives that describe rain, one per line, no numbering, no extra text."),

    ("开放式创意（最易发散）",
     "Write one single concise tagline (under 12 words) for a specialty coffee shop named 'Northbound'."),
]


def call_once(prompt):
    """temperature=0，单次调用，返回纯文本输出。"""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=256,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    # 提取文本
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    )
    return text.strip()


def similarity(a, b):
    """字符级相似度（difflib Ratio），1.0 = 完全一致。"""
    return difflib.SequenceMatcher(None, a, b).ratio()


def run_prompt(label, prompt, n):
    print(f"\n{'─'*88}")
    print(f" Prompt 类别: {label}")
    print(f" Prompt: {prompt[:90]}")
    print(f" 重复 N={n} 次，temperature=0.0，model={MODEL}")
    print(f"{'─'*88}")

    outputs = []
    for i in range(n):
        try:
            out = call_once(prompt)
        except Exception as e:
            print(f"  第 {i+1} 次调用失败: {e}")
            outputs.append(f"<ERROR: {e}>")
            continue
        outputs.append(out)
        # 只打印前几次的预览，避免刷屏
        if i < 3:
            preview = out.replace("\n", " ⏎ ")[:70]
            print(f"  [{i+1:>2}] {preview}")
        time.sleep(0.2)  # 礼貌限速

    if len(outputs) < 2:
        print("  有效输出不足 2 条，跳过")
        return None

    # 以第一次为基准
    base = outputs[0]
    exact = sum(1 for o in outputs if o == base)
    sims = [similarity(base, o) for o in outputs]

    distinct = len(set(outputs))
    sim_min = min(sims)
    sim_mean = statistics.mean(sims)

    print(f"\n  【结果】")
    print(f"    完全一致(exact-match): {exact}/{len(outputs)}  ({exact/len(outputs)*100:.0f}%)")
    print(f"    互异版本数          : {distinct}  (1=完全确定)")
    print(f"    字符相似度 min      : {sim_min:.3f}")
    print(f"    字符相似度 mean     : {sim_mean:.3f}")

    # 展示分歧样本（若不唯一）
    if distinct > 1:
        print(f"\n  【分歧样本（取与首条差异最大的）】")
        max_idx = sims.index(min(sims))
        print(f"    首条  : {base.replace(chr(10),' ⏎ ')[:120]}")
        print(f"    第{max_idx+1}条: {outputs[max_idx].replace(chr(10),' ⏎ ')[:120]}")

    return {
        "label": label,
        "exact_match_pct": exact / len(outputs) * 100,
        "distinct": distinct,
        "sim_min": sim_min,
    }


def main():
    print("█" * 88)
    print("  实验 A：temperature=0 确定性测试")
    print(f"  Provider: {BASE_URL}  |  Model: {MODEL}  |  N={N}/prompt")
    print("  断言：评估器温度 0.0 → 「输出几乎完全确定」（出自《ReAct 只是起点》）")
    print("█" * 88)

    results = []
    for label, prompt in PROMPTS:
        r = run_prompt(label, prompt, N)
        if r:
            results.append(r)

    print("\n" + "=" * 88)
    print(" 【跨 prompt 汇总】")
    print("=" * 88)
    print(f"  {'Prompt 类别':<26} {'exact-match':>14} {'互异版本':>10} {'最低相似度':>12}")
    for r in results:
        print(f"  {r['label']:<24} {r['exact_match_pct']:>13.0f}% {r['distinct']:>10} {r['sim_min']:>12.3f}")

    fully_deterministic = all(r["exact_match_pct"] == 100 for r in results)
    print("\n  判定：")
    if fully_deterministic:
        print(f"    本 provider({MODEL})在本测试样本上 100% 确定。")
        print(f"    但这不支持文章的普遍断言——温度0的确定性与 provider/后端实现强相关：")
        print(f"    OpenAI temp=0 已知不保证一致；分布式后端、 batching、采样的浮点抖动")
        print(f"    都可能破坏一致性。文章用「几乎完全确定」作为生产级评估的基石，是过度陈述。")
    else:
        n_fail = sum(1 for r in results if r["exact_match_pct"] < 100)
        print(f"    {n_fail}/{len(results)} 类 prompt 在 temp=0 下出现非确定输出 → 「几乎完全确定」证伪。")
        print(f"    生产级评估器若依赖此假设，同一观察包可能得到不同 done/phase_done 判断，")
        print(f"    评估结果不一致——文章「同一输入评估结果必须尽可能一致」的设计目标不成立。")
    print("=" * 88)


if __name__ == "__main__":
    main()
