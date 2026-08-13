#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multirun wrapper — 跑 argument-space-test.py 的 run_experiment() N 次，记录每次
每个场景的 C2 (glm-5.2) 判定，量化 §6 的 judge variance。

文章 §6 现状："C2 的 S3 判定在两次跑之间翻转"——轶事 (N=2)。
本实验产出：每个场景在 N=10 次跑中的 PASS/REJECT 分布，以及"翻转率"。

期待发现：S3（synonym 命名）是预期的 wobble 重灾区；S1（自爆 "NOT IMPLEMENTED"）
应当稳定 REJECT；S0、S4 在 §3 主表里也翻转过，N=10 可给出真实分布。

Usage:
  python argument-space-multirun.py --runs 10 --save
"""
import sys, os, io, json, argparse, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results-v2"

# import the sibling script as a module
import importlib.util
spec = importlib.util.spec_from_file_location("arg_space", HERE / "argument-space-test.py")
arg_space = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arg_space)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "glm-5.2"))
    args = parser.parse_args()

    # minimal args namespace for run_experiment
    class A:
        pass
    A.with_c2 = True
    A.model = args.model
    A.simplified_desc = False

    runs = []
    for i in range(args.runs):
        print(f"\n=== run {i+1}/{args.runs} ===", flush=True)
        t0 = time.time()
        results = arg_space.run_experiment(A)
        elapsed = time.time() - t0
        # extract just the C2 verdict per scenario
        verdicts = {}
        for r in results:
            sc = r["scenario"]
            c2 = r.get("c2_req3", {})
            verdicts[sc] = {
                "pass": c2.get("pass"),
                "reason": (c2.get("reason") or "")[:140],
            }
        run_row = {"run": i + 1, "elapsed_sec": round(elapsed, 1), "verdicts": verdicts}
        runs.append(run_row)
        print(f"  verdicts:", flush=True)
        for sc, v in verdicts.items():
            print(f"    {sc:<28} C2={v['pass']}", flush=True)

    # aggregate per-scenario C2 distribution
    scenarios = list(runs[0]["verdicts"].keys())
    distribution = {}
    for sc in scenarios:
        passes = sum(1 for r in runs if r["verdicts"][sc]["pass"] is True)
        rejects = sum(1 for r in runs if r["verdicts"][sc]["pass"] is False)
        nones = sum(1 for r in runs if r["verdicts"][sc]["pass"] is None)
        # ground truth from the script's SCENARIOS
        gt = next((s["compliant"] for s in arg_space.SCENARIOS if s["name"] == sc), None)
        distribution[sc] = {
            "ground_truth": "comply" if gt else "evade",
            "pass_count": passes,
            "reject_count": rejects,
            "none_count": nones,
            "wobble": passes > 0 and rejects > 0,
            "wobble_rate": round((min(passes, rejects) / (passes + rejects)) if (passes + rejects) > 0 else 0, 3),
        }

    # correctness rate per run
    run_correctness = []
    for r in runs:
        correct = 0
        for sc, v in r["verdicts"].items():
            gt = next((s["compliant"] for s in arg_space.SCENARIOS if s["name"] == sc), None)
            if v["pass"] == gt:
                correct += 1
        run_correctness.append({"run": r["run"], "correct": correct, "rate": round(correct / len(scenarios), 3)})

    print("\n" + "=" * 70)
    print(f"MULTIRUN summary — N={args.runs} runs, judge={args.model}")
    print("=" * 70)
    print(f"{'scenario':<30} {'truth':<8} {'PASS':<6} {'REJECT':<7} {'wobble?'}")
    for sc, d in distribution.items():
        wobble_str = f"YES ({d['wobble_rate']})" if d["wobble"] else "no"
        print(f"{sc:<30} {d['ground_truth']:<8} {d['pass_count']:<6} {d['reject_count']:<7} {wobble_str}")
    print()
    print(f"C2 correctness per run: {[r['correct'] for r in run_correctness]}/{len(scenarios)} "
          f"(mean={sum(r['correct'] for r in run_correctness)/len(run_correctness):.1f})")
    print("=" * 70)

    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        out = {
            "experiment": "argument-space-multirun",
            "n_runs": args.runs,
            "judge_model": args.model,
            "scenarios": scenarios,
            "distribution": distribution,
            "run_correctness": run_correctness,
            "runs": runs,
        }
        fpath = RESULTS_DIR / "argument-space-multirun.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n✓ saved -> {fpath}")


if __name__ == "__main__":
    main()
