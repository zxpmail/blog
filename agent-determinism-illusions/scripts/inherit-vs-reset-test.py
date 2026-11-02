# -*- coding: utf-8 -*-
"""继承经验 vs 重置经验：在合成多峰地形上扫描环境漂移速度。

对应公开仓文章《Keep the Gate, Downgrade the Recursion》留下的开放问题
（继承经验是否优于每轮重置），以及源文《基于RSI 架构的淘宝闪购店铺装修
选品Agent 实践》§7 自己给出的实验方案：两组使用相同的数据窗口、评估器、
起点规则和预算，仅改变历史反馈的使用方式。不读这两个文件。

主张（被测的结构性条件，来自文章原句）：
  外循环长期是否有价值，取决于「反馈能可靠改变下一批候选」且
  「环境真的在漂移」。把这句话变成可测形式：继承优势应依赖漂移
  速度——中等漂移下最大，漂移大到经验过期时应被侵蚀。
  这是机制类比，不是淘宝业务实验的复现：没有 A/B 门、没有真实
  业务噪声，经验=搜索分布+精英档案，地形=高斯多峰之和。

方法：
  地形：D=6 维盒 [-1,1]，12 个高斯包（幅度 0.8–1.0，宽度 0.18），
  适应度=包的最大值。每个种子一套地形。
  漂移：每轮边界，各包中心沿种子固定的单位方向走 δ，越界反射。
  搜索：(μ,λ)-ES，λ=12、μ=4 精英，1/5 规则调 σ。每轮预算 48 次评估，
  共 6 轮。三个臂（同种子同地形同漂移轨迹，第 1 轮完全相同）：
    inherit — 第 k>1 轮从上一轮的最终分布出发；档案 top-6 先在当前
      地形下重评（源文：历史分数不可原样复用），重评计入本轮预算
    reset   — 每轮从初始分布出发，不带任何历史反馈
    longrun — 参照臂：搜索状态不设轮边界，连搜 288 次；漂移照常发生
  每档 δ 跑 100 个种子，配对差做 bootstrap 95% 区间。
  交接非空检查：inherit 第 k>1 轮起点离初始分布的距离（交接必须
  真的改变了采样分布，否则继承是构造上的空转）。

预期：
  优势曲线（inherit − reset）随 δ 非单调：中等漂移下最大；
  δ=0.48 时过期经验把优势拖低。inherit 相对 longrun 的差
  主要由重评开销构成。

怎么证伪：
  ① 优势对 δ 平坦且区间全含零——「环境真的在漂」这个条件在本
     类比里测不出来，文章那句话的机制不成立；
  ② 高漂移下优势反而最大且显著——过期经验无害，漂移窗口不存在；
  ③ inherit 处处显著劣于 reset——暖启动从头吃亏，与预期相反。
  任一发生都以跑出的曲线为准，更新文章措辞。

依赖：仅 Python 标准库。运行：python inherit-vs-reset-test.py
"""

import io
import json
import math
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

D = 6                 # 维数
K = 12                # 高斯包个数
BOX = 1.0             # 盒 [-BOX, BOX]
WIDTH = 0.18          # 包宽度
LAM = 12              # 每代子代数
MU = 4                # 精英数
ROUNDS = 6            # 轮数（外循环轮）
BUDGET = 48           # 每轮评估预算
ARCHIVE_KEEP = 20     # 档案容量
ARCHIVE_REEVAL = 6    # inherit 每轮开局重评的档案条数
SIGMA0 = 0.35
SIGMA_MIN, SIGMA_MAX = 0.02, 0.5
DELTA_LIST = [0.0, 0.04, 0.16, 0.48]
SEEDS = 100
BOOT = 2000


def reflect(x, lo, hi):
    """越界反射，保持漂移不贴墙。"""
    span = hi - lo
    x = (x - lo) % (2 * span)
    if x < 0.0:
        x += 2 * span
    if x > span:
        x = 2 * span - x
    return x + lo


def gauss(rng):
    """Box-Muller，避免引入依赖。"""
    u1 = rng.random()
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1 or 1e-12)) * math.cos(2 * math.pi * u2)


def make_landscape(seed):
    """一套地形 + 一条固定的漂移方向。每种子同 seed 可复现。"""
    r = random.Random(seed)
    centers = [tuple(r.uniform(-BOX, BOX) for _ in range(D)) for _ in range(K)]
    amps = [r.uniform(0.8, 1.0) for _ in range(K)]
    dirs = []
    for _ in range(K):
        v = [gauss(r) for _ in range(D)]
        norm = math.sqrt(sum(t * t for t in v)) or 1e-12
        dirs.append(tuple(t / norm for t in v))
    return {"centers": centers, "amps": amps, "dirs": dirs}


def drift(land, delta):
    """把包中心沿各自固定方向推 δ，反射回盒内。返回新中心列表。"""
    if delta == 0.0:
        return land["centers"]
    out = []
    for c, u in zip(land["centers"], land["dirs"]):
        out.append(tuple(reflect(ci + delta * ui, -BOX, BOX) for ci, ui in zip(c, u)))
    return out


def fitness(land, centers, x):
    """max_j a_j·exp(-‖x-c_j‖²/2s²)。纯标准库，热循环。"""
    best = -1e18
    half_inv = 1.0 / (2 * WIDTH * WIDTH)
    for c, a in zip(centers, land["amps"]):
        s = 0.0
        for xi, ci in zip(x, c):
            d = xi - ci
            s += d * d
        v = a * math.exp(-s * half_inv)
        if v > best:
            best = v
    return best


def clip(x):
    return tuple(max(-BOX, min(BOX, xi)) for xi in x)


def es_generation(land, centers, state, rng, results):
    """一代：λ 个子代 + 1/5 规则调 σ。state 含 m/sigma/f_parent。"""
    m, sigma, f_parent = state["m"], state["sigma"], state["f"]
    children = []
    for _ in range(LAM):
        x = clip(tuple(mi + sigma * gauss(rng) for mi in m))
        children.append((fitness(land, centers, x), x))
    children.sort(key=lambda t: -t[0])
    rate = sum(1 for f, _ in children if f > f_parent) / LAM
    sigma *= 1.3 if rate > 0.2 else (1.0 / 1.3)
    sigma = max(SIGMA_MIN, min(SIGMA_MAX, sigma))
    top = children[:MU]
    if top[0][0] > f_parent:
        nm = [0.0] * D
        for _, x in top:
            for i in range(D):
                nm[i] += x[i] / MU
        state["m"], state["f"] = tuple(nm), top[0][0]
    state["sigma"] = sigma
    results.extend(children)


def run_arm(land, arm, delta, seed):
    """一个臂在一条漂移轨迹上的完整搜索。返回逐轮 best-so-far 与统计。"""
    rng = random.Random(seed * 1000 + 7)
    centers = drift(land, 0.0)
    m0 = tuple(0.0 for _ in range(D))
    state = {"m": m0, "sigma": SIGMA0, "f": fitness(land, centers, m0)}
    archive = []            # (score, x) 当前地形下的新鲜分
    best = -1e18
    per_round = []
    handoff_dists = []
    reeval_used = 0
    for rnd in range(ROUNDS):
        if rnd > 0:
            centers = drift(land, delta * rnd)
        budget = BUDGET
        if arm == "inherit" and rnd > 0:
            handoff_dists.append(math.sqrt(sum((a - b) ** 2 for a, b in zip(state["m"], m0))))
            stale = sorted(archive, key=lambda t: -t[0])[:ARCHIVE_REEVAL]
            archive = []
            for _, x in stale:
                f = fitness(land, centers, x)
                archive.append((f, x))
                best = max(best, f)
            reeval_used += len(stale)
            budget -= len(stale)
        if arm == "reset" and rnd > 0:
            state = {"m": m0, "sigma": SIGMA0, "f": fitness(land, centers, m0)}
            archive = []
        gen = 0
        while gen * LAM < budget:
            results_buf = []
            es_generation(land, centers, state, rng, results_buf)
            archive.extend(results_buf)
            archive.sort(key=lambda t: -t[0])
            del archive[ARCHIVE_KEEP:]
            best = max(best, max(f for f, _ in results_buf))
            gen += 1
        per_round.append(best)
    return {
        "final_best": best,
        "per_round": per_round,
        "handoff_dists": handoff_dists,
        "reeval_evals": reeval_used,
    }


def bootstrap_ci(diffs, rng):
    """配对差的 bootstrap 95% 百分位区间。"""
    means = []
    n = len(diffs)
    for _ in range(BOOT):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT)]


def main():
    arms = ("inherit", "reset", "longrun")
    per_delta = []
    boot_rng = random.Random(20261103)
    for delta in DELTA_LIST:
        finals = {a: [] for a in arms}
        rounds_sum = {a: [0.0] * ROUNDS for a in arms}
        handoff_sum, handoff_n = 0.0, 0
        reeval_sum = 0
        pair_ir, pair_li = [], []
        for seed in range(SEEDS):
            land = make_landscape(seed)
            res = {a: run_arm(land, a, delta, seed) for a in arms}
            for a in arms:
                finals[a].append(res[a]["final_best"])
                for i, b in enumerate(res[a]["per_round"]):
                    rounds_sum[a][i] += b
            for a in ("inherit",):
                handoff_sum += sum(res[a]["handoff_dists"])
                handoff_n += len(res[a]["handoff_dists"])
                reeval_sum += res[a]["reeval_evals"]
            pair_ir.append(res["inherit"]["final_best"] - res["reset"]["final_best"])
            pair_li.append(res["longrun"]["final_best"] - res["inherit"]["final_best"])
        lo_ir, hi_ir = bootstrap_ci(pair_ir, boot_rng)
        lo_li, hi_li = bootstrap_ci(pair_li, boot_rng)
        per_delta.append({
            "delta": delta,
            "mean_final": {a: sum(finals[a]) / SEEDS for a in arms},
            "mean_per_round": {a: [v / SEEDS for v in rounds_sum[a]] for a in arms},
            "inherit_minus_reset": {
                "mean": sum(pair_ir) / SEEDS, "ci95": [lo_ir, hi_ir],
                "per_seed": pair_ir,
            },
            "longrun_minus_inherit": {
                "mean": sum(pair_li) / SEEDS, "ci95": [lo_li, hi_li],
            },
            "handoff_mean_dist": handoff_sum / handoff_n if handoff_n else 0.0,
            "reeval_evals_per_seed": reeval_sum / SEEDS,
        })

    adv = [row["inherit_minus_reset"]["mean"] for row in per_delta]
    crosses_zero = any(row["inherit_minus_reset"]["ci95"][0] > 0 or row["inherit_minus_reset"]["ci95"][1] < 0
                       for row in per_delta)
    falls_at_high_drift = adv[-1] < adv[0]
    verdict = {
        "advantage_curve": dict(zip((str(d) for d in DELTA_LIST), adv)),
        "some_ci_excludes_zero": crosses_zero,
        "advantage_falls_at_high_drift": falls_at_high_drift,
        "handoff_nonvacuous": per_delta[-1]["handoff_mean_dist"] > 0.05,
        "pass": bool(crosses_zero and falls_at_high_drift and per_delta[-1]["handoff_mean_dist"] > 0.05),
    }
    out = {
        "claim": "继承优势依赖漂移速度：中等漂移最大，大漂移被过期经验侵蚀（机制类比，非业务实验）",
        "simulator": "gaussian_bumps_max_es",
        "not_a_business_measurement": True,
        "config": {
            "D": D, "K": K, "bump_width": WIDTH, "lam": LAM, "mu": MU,
            "rounds": ROUNDS, "budget_per_round": BUDGET,
            "archive_keep": ARCHIVE_KEEP, "archive_reeval": ARCHIVE_REEVAL,
            "sigma0": SIGMA0, "deltas": DELTA_LIST, "seeds": SEEDS,
        },
        "per_delta": per_delta,
        "verdict": verdict,
    }
    dest = Path(__file__).parent / "results-v2" / "inherit-vs-reset.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"地形：D={D}，{K} 个高斯包（宽 {WIDTH}），盒 [-{BOX},{BOX}]")
    print(f"预算：每轮 {BUDGET} 次评估 × {ROUNDS} 轮；λ={LAM} μ={MU}；{SEEDS} 种子/档")
    print(f"inherit 每轮开局重评档案 top-{ARCHIVE_REEVAL}（计入预算），reset 全部丢弃历史")
    print()
    print(f"{'δ':>6} {'inherit':>9} {'reset':>9} {'longrun':>9} {'差(I−R)':>9} {'95%区间':>18} {'交接距离':>8}")
    for row in per_delta:
        ir = row["inherit_minus_reset"]
        print(f"{row['delta']:>6.2f} "
              f"{row['mean_final']['inherit']:>9.4f} "
              f"{row['mean_final']['reset']:>9.4f} "
              f"{row['mean_final']['longrun']:>9.4f} "
              f"{ir['mean']:>+9.4f} "
              f"[{ir['ci95'][0]:>+7.4f},{ir['ci95'][1]:>+7.4f}] "
              f"{row['handoff_mean_dist']:>8.3f}")
    print()
    print(f"判定：{'PASS' if verdict['pass'] else 'FAIL'}"
          f"（优势随漂移回落={falls_at_high_drift}，某档区间不含零={crosses_zero}，"
          f"交接非空={verdict['handoff_nonvacuous']}）")
    print(f"结果：{dest}")


if __name__ == "__main__":
    main()
