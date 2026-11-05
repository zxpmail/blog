# -*- coding: utf-8 -*-
"""朴素棘轮归因：轮间仪表读数能否把「搜索进步」和「环境顺风」拆开。

对应《Keep the Gate, Downgrade the Recursion》评论区的公开承诺（读者
nullandvoid_ 3jp4j 催更；作者 3jphi 明确「下一篇由下一个实验挣出来」），
以及作者回复 3joc8 结尾的反问：在线上怎么装仪表，把「经验帮了忙」和
「环境恰好朝我们这边动」分开。本脚本是那个测量的机制类比设计验证：
在一个真值已知的合成世界里，检查拆分恒等式是否成立、没有仪表时朴素
棘轮的错觉率有多大。不读那两个文件。

主张（被测结构）：
  轮间仪表读数 naive_t = f(T_t, x_t) − f(T_{t−1}, x_{t−1})——当前部署
  候选在当前地形上的读数之差——可精确拆成
    env_t    = f(T_t, x_{t−1}) − f(T_{t−1}, x_{t−1})   世界动、点不动
    search_t = f(T_t, x_t) − f(T_t, x_{t−1})           点动、世界定格
  恒等式 naive_t = env_t + search_t 构造成立。线上成本 = 每轮把上轮
  交付的候选在当前评估器下重评 1 次，外加一路冻结候选的持续读数。
  没有这两个读数时，仪表的符号不是学习证据：
    顺风型错觉 wind_up   = naive_total>0 且 env_total>search_total
                          ——涨的是风，循环自己没贡献多少；
    逆风型错觉 wind_down = naive_total<0 且 search_total>0
                          ——循环学到了，仪表却在跌。
  机制类比，非业务实验：没有 A/B 门、没有业务噪声，经验 = ES 状态
  跨轮连续，地形 = 高斯多峰之和，「部署」= 每轮把更优者晋升为现役。

方法：
  地形/ES 与 inherit-vs-reset-test.py 同族：D=6，12 个高斯包（宽
  0.18），(μ,λ)=(4,12)，1/5 规则，每轮预算 48，共 6 轮，100 种子。
  预算逐次计费（不足一代按实际子代数做选择与 1/5 规则）：
    search 臂第 t>1 轮 = 1 次现役重评（就是仪表）+ 47 次新采样
    reset 臂第 t>1 轮 = 1 次重置初始评估 + 47 次新采样（起始读数
      对起始读数，两臂对称，各付一次「开局评估」）
    static 臂第 1 轮搜索后冻结交付候选，此后只读数、不花搜索预算
  第 1 轮三臂完全相同（同 rng 流，1 次初始评估 + 48 次新采样）；
  第 1 轮最优 = 交付候选 x_1。
  风向轴（第 2 轮起每轮边界各包中心沿单位方向走 δ，越界反射，
  轨迹三臂共享；方向在第 1 次边界定死后不再变）：
    favorable — 朝 x_1（市场向已交付候选靠拢）
    adverse   — 背向 x_1
    null      — 种子固定的随机单位方向（与前脚本一致）
  δ∈{0, 0.04, 0.16, 0.48}；δ=0 时风向折叠为同一格。
  判定量（每格 100 种子，bootstrap 95% 百分位区间）：
    static_peak    = max_t S_t − S_1（冻结候选读数的窗口内峰值，纯环境项）
    naive/env/search_total（search 臂逐轮分解的总和）
    wind_up 率、wind_down 率（逐种子指示变量）
    memory_value = search 臂末轮读数 − reset 臂末轮读数（配对差）

预期（预注册）：
  P1 δ=0.48 favorable：static_peak 均值 > 0 且区间不含零——环境
     自己就能把冻结候选的仪表推高，窗口内没有任何搜索。
  P2 δ=0.48：wind_up 率 favorable > adverse 且 wind_down 率
     adverse > favorable，两组逐种子配对差的区间都不含零——
     朴素棘轮的错觉方向跟着风向走。
  P3 全部格子恒等式残差 < 1e-9（实现自检）。
  P4 δ=0：env_total、static 峰值变化逐种子精确为 0，naive_total
     ≡ search_total（容差 1e-12，无风世界无错觉）。
  P5（软预期，不判 PASS/FAIL）：null 风向格 wind_up 率非零——
     随机风向碰巧顺布就足以制造错觉，不需要故意设计。

怎么证伪：
  ① P1 不成立（顺风下冻结候选读数不涨）——「环境顺风自己能把仪表
     推高」在此类比里测不出，错觉指控落空，文章降级为记账恒等式；
  ② P2 不成立（错觉率与风向无关）——朴素棘轮的偏差不是风向驱动的，
     「环境恰好朝我们这边动」的混淆在这个类比里不成立；
  ③ P3/P4 破——实现错误或浮点问题，先修实现再谈结论。
  任一发生以跑出的数据为准，更新文章措辞。

依赖：仅 Python 标准库。运行：python ratchet-attribution-test.py
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
BUDGET = 48           # 每轮评估预算（严格逐次计费）
SIGMA0 = 0.35
SIGMA_MIN, SIGMA_MAX = 0.02, 0.5
DELTA_LIST = [0.0, 0.04, 0.16, 0.48]
WINDS = ["adverse", "null", "favorable"]
SEEDS = 100
BOOT = 2000
IDENT_TOL = 1e-9
ZERO_TOL = 1e-12


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
    """一套地形 + 一组随机单位方向（null 风向用）。每种子可复现。"""
    r = random.Random(seed)
    centers = [tuple(r.uniform(-BOX, BOX) for _ in range(D)) for _ in range(K)]
    amps = [r.uniform(0.8, 1.0) for _ in range(K)]
    dirs = []
    for _ in range(K):
        v = [gauss(r) for _ in range(D)]
        n = math.sqrt(sum(t * t for t in v)) or 1e-12
        dirs.append(tuple(t / n for t in v))
    return {"centers": centers, "amps": amps, "dirs": dirs}


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


def unit(v):
    n = math.sqrt(sum(t * t for t in v)) or 1e-12
    return tuple(t / n for t in v)


def es_generation(land, centers, state, rng, max_evals):
    """最多 max_evals 个子代；不足一代也做选择与 1/5 规则（按实际数量）。
    返回本批 (best_f, best_x, n)。预算逐次计费的关键。"""
    m, sigma, f_parent = state["m"], state["sigma"], state["f"]
    children = []
    for _ in range(max_evals):
        x = clip(tuple(mi + sigma * gauss(rng) for mi in m))
        children.append((fitness(land, centers, x), x))
    children.sort(key=lambda t: -t[0])
    rate = sum(1 for f, _ in children if f > f_parent) / len(children)
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
    return children[0][0], children[0][1], len(children)


def fresh_search(land, centers, state, rng, fresh):
    """恰好 fresh 次新采样，返回本批 (best_f, best_x)。"""
    bf, bx, n = -1e18, None, 0
    while n < fresh:
        f, x, k = es_generation(land, centers, state, rng, min(LAM, fresh - n))
        if f > bf:
            bf, bx = f, x
        n += k
    return bf, bx


def wind_dirs(land, x1, wind):
    """每个包的漂移单位方向。favorable/adverse 以交付候选 x_1 为参照，
    第 1 次边界定死后不再变。null 用地形自带的随机方向。"""
    if wind in ("null", "none"):
        return list(land["dirs"])
    sign = 1.0 if wind == "favorable" else -1.0
    return [unit([sign * (xi - ci) for xi, ci in zip(x1, c)])
            for c in land["centers"]]


def centers_at(land, dirs, delta, t):
    """第 t 轮包中心：第 1 轮不漂；第 t≥2 轮沿 dirs 走 δ·(t−1)，反射回盒。"""
    if delta == 0.0 or t == 1:
        return land["centers"]
    return [tuple(reflect(ci + delta * (t - 1) * ui, -BOX, BOX)
                  for ci, ui in zip(c, u))
            for c, u in zip(land["centers"], dirs)]


def round1(land, seed):
    """三臂共享的第 1 轮：1 次初始评估 + 48 次新采样。返回续跑上下文。"""
    rng = random.Random(seed * 1000 + 7)
    centers = land["centers"]
    m0 = tuple(0.0 for _ in range(D))
    state = {"m": m0, "sigma": SIGMA0, "f": fitness(land, centers, m0)}
    bf, bx = fresh_search(land, centers, state, rng, BUDGET)
    x1, f1 = bx, bf
    # 注意：state["m"] 是精英均值、state["f"] 是最优子代的分数，两者不是
    # 同一个点。交付候选只取评估过的最优点 (bx, bf)，不碰 ES 内部簿记。
    return {
        "rng_state": rng.getstate(),
        "state": {"m": state["m"], "sigma": state["sigma"], "f": state["f"]},
        "x1": x1, "f1": f1,
    }


def run_arms(land, r1, wind, delta):
    """同一个世界（一条共享漂移轨迹）里的三个臂。返回逐轮序列与汇总。"""
    dirs = wind_dirs(land, r1["x1"], wind)
    x1, f1 = r1["x1"], r1["f1"]

    # search 臂：ES 状态跨轮连续（经验 = 分布），现役候选晋升制
    rng = random.Random()
    rng.setstate(r1["rng_state"])
    state = dict(r1["state"])
    x_cur, f_prev = x1, f1
    seq_naive, seq_env, seq_search = [], [], []
    for t in range(2, ROUNDS + 1):
        centers = centers_at(land, dirs, delta, t)
        f_inc = fitness(land, centers, x_cur)            # 现役重评 = 仪表（计预算）
        bf, bx = fresh_search(land, centers, state, rng, BUDGET - 1)
        if bf > f_inc:
            x_new, f_new = bx, bf
        else:
            x_new, f_new = x_cur, f_inc
        seq_naive.append(f_new - f_prev)
        seq_env.append(f_inc - f_prev)
        seq_search.append(f_new - f_inc)
        x_cur, f_prev = x_new, f_new
    x6_search = f_prev

    # reset 臂：每轮重置，同预算（1 次初始评估 + 47 次新采样）
    rng = random.Random()
    rng.setstate(r1["rng_state"])
    x6_reset = None
    for t in range(2, ROUNDS + 1):
        centers = centers_at(land, dirs, delta, t)
        m0 = tuple(0.0 for _ in range(D))
        state_r = {"m": m0, "sigma": SIGMA0, "f": fitness(land, centers, m0)}
        bf, bx = fresh_search(land, centers, state_r, rng, BUDGET - 1)
        x6_reset = bf   # 该轮部署候选 = 本轮评估过的最优点（ES 簿记分数不参与部署）

    # static 臂：冻结交付候选，只读数（读数不花搜索预算）
    S = [f1]
    for t in range(2, ROUNDS + 1):
        centers = centers_at(land, dirs, delta, t)
        S.append(fitness(land, centers, x1))

    naive_total = sum(seq_naive)
    env_total = sum(seq_env)
    search_total = sum(seq_search)
    resid = max(abs(a - b - c) for a, b, c in zip(seq_naive, seq_env, seq_search))
    return {
        "seq_naive": seq_naive, "seq_env": seq_env, "seq_search": seq_search,
        "S": S,
        "naive_total": naive_total, "env_total": env_total,
        "search_total": search_total,
        "static_peak": max(S) - S[0],
        "static_ratchet": S[-1] - S[0],
        "wind_up": bool(naive_total > 0.0 and env_total > search_total),
        "wind_down": bool(naive_total < 0.0 and search_total > 0.0),
        "memory_value": x6_search - x6_reset,
        "identity_residual": resid,
    }


def bootstrap_ci(vals, rng):
    """bootstrap 95% 百分位区间。"""
    means = []
    n = len(vals)
    for _ in range(BOOT):
        s = 0.0
        for _ in range(n):
            s += vals[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT)]


def rate_ci(flags, rng):
    return bootstrap_ci([1.0 if f else 0.0 for f in flags], rng)


def mean(v):
    return sum(v) / len(v)


def main():
    cells = [("none", 0.0)] + [(w, d) for d in DELTA_LIST[1:] for w in WINDS]
    boot_rng = random.Random(20261105)
    out_cells = []
    for wind, delta in cells:
        rows = []
        for seed in range(SEEDS):
            land = make_landscape(seed)
            r1 = round1(land, seed)
            rows.append(run_arms(land, r1, wind, delta))
        ups = [r["wind_up"] for r in rows]
        downs = [r["wind_down"] for r in rows]
        cell = {
            "wind": wind, "delta": delta, "n_seeds": SEEDS,
            "mean_static_peak": mean([r["static_peak"] for r in rows]),
            "ci_static_peak": bootstrap_ci([r["static_peak"] for r in rows], boot_rng),
            "mean_static_ratchet": mean([r["static_ratchet"] for r in rows]),
            "ci_static_ratchet": bootstrap_ci([r["static_ratchet"] for r in rows], boot_rng),
            "mean_naive_total": mean([r["naive_total"] for r in rows]),
            "ci_naive_total": bootstrap_ci([r["naive_total"] for r in rows], boot_rng),
            "mean_env_total": mean([r["env_total"] for r in rows]),
            "ci_env_total": bootstrap_ci([r["env_total"] for r in rows], boot_rng),
            "mean_search_total": mean([r["search_total"] for r in rows]),
            "ci_search_total": bootstrap_ci([r["search_total"] for r in rows], boot_rng),
            "wind_up_rate": mean([1.0 if f else 0.0 for f in ups]),
            "ci_wind_up": rate_ci(ups, boot_rng),
            "wind_down_rate": mean([1.0 if f else 0.0 for f in downs]),
            "ci_wind_down": rate_ci(downs, boot_rng),
            "mean_memory_value": mean([r["memory_value"] for r in rows]),
            "ci_memory_value": bootstrap_ci([r["memory_value"] for r in rows], boot_rng),
            "mean_per_round": {
                "naive": [mean([r["seq_naive"][i] for r in rows]) for i in range(ROUNDS - 1)],
                "env": [mean([r["seq_env"][i] for r in rows]) for i in range(ROUNDS - 1)],
                "search": [mean([r["seq_search"][i] for r in rows]) for i in range(ROUNDS - 1)],
            },
            "identity_residual_max": max(r["identity_residual"] for r in rows),
            "per_seed": {
                "static_peak": [r["static_peak"] for r in rows],
                "static_ratchet": [r["static_ratchet"] for r in rows],
                "naive_total": [r["naive_total"] for r in rows],
                "env_total": [r["env_total"] for r in rows],
                "search_total": [r["search_total"] for r in rows],
                "wind_up": [1 if r["wind_up"] else 0 for r in rows],
                "wind_down": [1 if r["wind_down"] else 0 for r in rows],
                "memory_value": [r["memory_value"] for r in rows],
            },
        }
        out_cells.append(cell)
        print(f"δ={delta:.2f} wind={wind:<10} 完成"
              f"（static_peak {cell['mean_static_peak']:+.4f}，"
              f"wind_up {cell['wind_up_rate']:.0%}，"
              f"wind_down {cell['wind_down_rate']:.0%}）")

    def find(wind, delta):
        return next(c for c in out_cells if c["wind"] == wind and c["delta"] == delta)

    fav48 = find("favorable", 0.48)
    adv48 = find("adverse", 0.48)
    diff_up = [a - b for a, b in zip(fav48["per_seed"]["wind_up"], adv48["per_seed"]["wind_up"])]
    diff_down = [a - b for a, b in zip(adv48["per_seed"]["wind_down"], fav48["per_seed"]["wind_down"])]
    lo_up, hi_up = bootstrap_ci(diff_up, boot_rng)
    lo_dn, hi_dn = bootstrap_ci(diff_down, boot_rng)

    base = find("none", 0.0)
    p1 = bool(fav48["mean_static_peak"] > 0 and fav48["ci_static_peak"][0] > 0)
    p2a = bool(lo_up > 0)
    p2b = bool(lo_dn > 0)
    p3 = bool(max(c["identity_residual_max"] for c in out_cells) < IDENT_TOL)
    p4 = bool(abs(base["mean_env_total"]) < ZERO_TOL
              and abs(base["mean_static_peak"]) < ZERO_TOL
              and abs(base["mean_static_ratchet"]) < ZERO_TOL
              and max(abs(a - b) for a, b in zip(base["per_seed"]["naive_total"],
                                                 base["per_seed"]["search_total"])) < ZERO_TOL)
    null_up_any = any(c["wind"] == "null" and c["wind_up_rate"] > 0 for c in out_cells)
    verdict = {
        "P1_favorable_static_peak": {
            "mean": fav48["mean_static_peak"], "ci95": fav48["ci_static_peak"], "hold": p1},
        "P2_wind_up_favorable_gt_adverse": {
            "mean_diff": mean(diff_up), "ci95": [lo_up, hi_up], "hold": p2a},
        "P2b_wind_down_adverse_gt_favorable": {
            "mean_diff": mean(diff_down), "ci95": [lo_dn, hi_dn], "hold": p2b},
        "P3_identity_residual": {
            "max": max(c["identity_residual_max"] for c in out_cells),
            "tol": IDENT_TOL, "hold": p3},
        "P4_zero_drift_exact_zero": {"hold": p4},
        "P5_soft_null_wind_up_nonzero": {"hold": bool(null_up_any)},
        "pass": bool(p1 and p2a and p2b and p3 and p4),
    }

    out = {
        "claim": "轮间仪表读数可精确拆成环境步+搜索步；没有该拆分时朴素棘轮的错觉方向跟着风向走（机制类比，非业务实验）",
        "simulator": "gaussian_bumps_max_es_incumbent_promotion",
        "not_a_business_measurement": True,
        "config": {
            "D": D, "K": K, "bump_width": WIDTH, "lam": LAM, "mu": MU,
            "rounds": ROUNDS, "budget_per_round": BUDGET,
            "budget_accounting": "exact_per_eval",
            "sigma0": SIGMA0, "deltas": DELTA_LIST, "winds": WINDS,
            "seeds": SEEDS,
            "arms": {
                "search": "ES 状态跨轮连续 + 现役晋升；每轮 1 次现役重评（仪表）+ 47 次新采样",
                "reset": "每轮重置；每轮 1 次初始评估 + 47 次新采样",
                "static": "第 1 轮后冻结交付候选，只读数",
            },
            "wind": "favorable/adverse = 朝/背交付候选 x_1 的单位方向，第 1 次边界定死；null = 种子固定随机方向；轨迹三臂共享",
        },
        "per_cell": out_cells,
        "verdict": verdict,
    }
    dest = Path(__file__).parent / "results-v2" / "ratchet-attribution.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    hdr = (f"{'δ':>6} {'风向':<10} {'static峰值':>10} {'naive总':>9} {'env总':>9} "
           f"{'search总':>9} {'wind_up率':>16} {'wind_down率':>16} {'记忆差':>9}")
    print(hdr)
    for c in out_cells:
        print(f"{c['delta']:>6.2f} {c['wind']:<10} "
              f"{c['mean_static_peak']:>+10.4f} "
              f"{c['mean_naive_total']:>+9.4f} "
              f"{c['mean_env_total']:>+9.4f} "
              f"{c['mean_search_total']:>+9.4f} "
              f"{c['wind_up_rate']:>7.0%} [{c['ci_wind_up'][0]:>5.2f},{c['ci_wind_up'][1]:>4.2f}] "
              f"{c['wind_down_rate']:>7.0%} [{c['ci_wind_down'][0]:>5.2f},{c['ci_wind_down'][1]:>4.2f}] "
              f"{c['mean_memory_value']:>+9.4f}")
    print()
    print("预注册判定：")
    print(f"  P1 顺风 static_peak>0 且区间不含零：{'成立' if p1 else '不成立'}"
          f"（均值 {fav48['mean_static_peak']:+.4f}，区间 [{fav48['ci_static_peak'][0]:+.4f},{fav48['ci_static_peak'][1]:+.4f}]）")
    print(f"  P2 wind_up 顺风>逆风（配对差区间 [{lo_up:+.4f},{hi_up:+.4f}]）：{'成立' if p2a else '不成立'}")
    print(f"  P2b wind_down 逆风>顺风（配对差区间 [{lo_dn:+.4f},{hi_dn:+.4f}]）：{'成立' if p2b else '不成立'}")
    print(f"  P3 恒等式残差 < 1e-9：{'成立' if p3 else '不成立'}"
          f"（最大 {verdict['P3_identity_residual']['max']:.2e}）")
    print(f"  P4 零漂移精确为零：{'成立' if p4 else '不成立'}")
    print(f"  P5（软）null 风向格出现 wind_up：{'是' if null_up_any else '否'}（不判 PASS/FAIL）")
    print(f"总判定：{'PASS' if verdict['pass'] else 'FAIL'}")
    print(f"结果：{dest}")


if __name__ == "__main__":
    main()
