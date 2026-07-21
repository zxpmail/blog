"""Confidence vs miss concentration — does confidence-weighting under-sample the dangerous tail?

Claim under test (Mike Czerwinski, dev.to comment on Part 6, 2026-07-21):
    "Confidence-weighted sampling concentrates audits where the model is unsure.
     But the long-tail directional failure is the confident-and-wrong case.
     Weighting on confidence samples that region least, because high confidence
     drives the rate down. The 5.6x efficiency is partly bought by sampling less
     exactly where the failure you were hunting lives."

Article (Part 6) defines "confidence" as cross-prompt divergence, not self-reported
confidence. Mike's critique still applies to that definition if three LLM prompts
share the same channel blindness on confident-and-wrong cases — they all see the
same plausible-sounding rationalization.

Method:
    Read scripts/results-v2/{qwen3-0-5b,gemma3-latest,deepseek-v4-flash}.jsonl.
    For each MISS run (passes=true on is_legit=False scenario), record confidence.
    Compute: what fraction of MISS mass sits at confidence >= 0.9?

    If most misses sit at high self-reported confidence, then:
      (a) self-confidence weighting directly under-samples the dangerous region;
      (b) cross-prompt divergence is likely to collapse there too, because the
          models are highly consistent (P2 showed 0 divergence on identical input).

Expected result (from earlier inspection):
    DS4 on gemma3: avg_confidence 0.95, accuracy 0.0 — all 15 runs miss at high conf.
    DS4 on deepseek: avg_confidence 0.93, 13% accuracy.
    Suggests miss mass concentrates at high confidence.

Dependencies: none (pure Python).
Falsifier: if MISS cases distribute roughly uniformly across confidence bins,
Mike's claim is empirically weaker than it sounds.

Run:
    python agent-determinism-illusions/scripts/confidence-vs-miss-concentration.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

RESULTS = Path(__file__).parent / "results-v2"
MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
HIGH_CONF_THRESHOLD = 0.9


def load_jsonl(model_slug):
    path = RESULTS / f"{model_slug}.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def collect_miss_confidences():
    """Yield (model, scenario_id, confidence) for each MISS run.

    MISS = passes=true on is_legit=False scenario (judge accepted a bad output).
    """
    out = []
    for model in MODELS:
        rows = load_jsonl(model)
        for row in rows:
            if row.get("is_legit"):
                continue  # MISS only counts on bad outputs
            sid = row["id"]
            for v in row.get("run_verdicts", []):
                if v.get("passes") and v.get("error_type") == "MISS":
                    out.append((model, sid, v.get("confidence")))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    miss = collect_miss_confidences()
    print(f"Total MISS runs across 3 models: {len(miss)}\n")

    # Per-model breakdown
    by_model = defaultdict(list)
    for model, sid, conf in miss:
        by_model[model].append((sid, conf))

    print(f"{'Model':<22} {'Total MISS':>11} {'Conf>=0.9':>10} {'% high-conf':>13} {'Avg conf':>10}")
    print("-" * 70)
    for model in MODELS:
        runs = by_model[model]
        if not runs:
            print(f"{model:<22} {'0':>11} {'0':>10} {'-':>13} {'-':>10}")
            continue
        n = len(runs)
        n_high = sum(1 for _, c in runs if c is not None and c >= HIGH_CONF_THRESHOLD)
        confs = [c for _, c in runs if c is not None]
        avg = sum(confs) / len(confs) if confs else float("nan")
        print(f"{model:<22} {n:>11} {n_high:>10} {100*n_high/n:>12.1f}% {avg:>10.3f}")

    print()
    # Per-scenario breakdown for the worst case
    by_scenario = defaultdict(list)
    for model, sid, conf in miss:
        by_scenario[sid].append((model, conf))

    print("Per-scenario MISS concentration (sorted by count):")
    print(f"{'Scenario':<10} {'N miss':>7} {'Conf>=0.9':>10} {'% high-conf':>13}")
    print("-" * 45)
    for sid, runs in sorted(by_scenario.items(), key=lambda kv: -len(kv[1])):
        n = len(runs)
        n_high = sum(1 for _, c in runs if c is not None and c >= HIGH_CONF_THRESHOLD)
        pct = 100 * n_high / n if n else 0
        print(f"{sid:<10} {n:>7} {n_high:>10} {pct:>12.1f}%")

    # Overall
    total = len(miss)
    total_high = sum(1 for _, _, c in miss if c is not None and c >= HIGH_CONF_THRESHOLD)
    confs = [c for _, _, c in miss if c is not None]
    avg = sum(confs) / len(confs) if confs else float("nan")
    print()
    print(f"Overall: {total} MISS runs, {total_high} at confidence >= {HIGH_CONF_THRESHOLD} "
          f"({100*total_high/total:.1f}%), avg confidence {avg:.3f}")
    print()
    print("Interpretation:")
    if total and total_high / total >= 0.7:
        print(f"  >=70% of misses sit at self-confidence >= {HIGH_CONF_THRESHOLD}.")
        print("  Self-confidence weighting (audit_rate ~ 1/confidence^k) samples this region least.")
        print("  Cross-prompt divergence is also likely to collapse here, because P2 showed")
        print("  LLM judgments on identical input are highly consistent (0 divergence, N=10).")
        print("  => Mike's claim is empirically supported by DF v2 data.")
    elif total and total_high / total >= 0.4:
        print(f"  40-70% of misses sit at self-confidence >= {HIGH_CONF_THRESHOLD}.")
        print("  Mike's claim is partially supported.")
    else:
        print(f"  <40% of misses sit at self-confidence >= {HIGH_CONF_THRESHOLD}.")
        print("  Mike's claim is not strongly supported by this data.")


if __name__ == "__main__":
    main()
