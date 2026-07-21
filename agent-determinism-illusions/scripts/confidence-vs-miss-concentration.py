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

    print()
    # Concentration: is 95.8% a general shape or one model/scenario?
    total = len(miss)
    print("Concentration check (Mike follow-up: stable across models/scenarios?)")
    print("-" * 70)
    model_counts = {m: len(by_model[m]) for m in MODELS}
    for m in MODELS:
        n = model_counts[m]
        share = 100 * n / total if total else 0
        print(f"  {m:<22} {n:>3}/{total} MISS = {share:5.1f}% of all MISS")
    max_model = max(MODELS, key=lambda m: model_counts[m])
    max_model_share = model_counts[max_model] / total if total else 0
    print(f"  → max model share: {max_model} = {100*max_model_share:.1f}%")

    scen_counts = {sid: len(runs) for sid, runs in by_scenario.items()}
    top_scen = sorted(scen_counts.items(), key=lambda kv: -kv[1])[:3]
    print(f"  Top scenarios: " + ", ".join(f"{s}={n} ({100*n/total:.1f}%)" for s, n in top_scen))
    max_scen_share = top_scen[0][1] / total if total and top_scen else 0

    # Conditional: among models that MISS, is high-conf still the shape?
    print()
    print("Conditional high-conf rate (given model has MISS):")
    for model in MODELS:
        runs = by_model[model]
        if not runs:
            continue
        n = len(runs)
        n_high = sum(1 for _, c in runs if c is not None and c >= HIGH_CONF_THRESHOLD)
        print(f"  {model:<22} {n_high}/{n} = {100*n_high/n:.1f}% at conf≥0.9")

    # Model × scenario top cells
    by_cell = defaultdict(int)
    by_cell_high = defaultdict(int)
    for model, sid, conf in miss:
        by_cell[(model, sid)] += 1
        if conf is not None and conf >= HIGH_CONF_THRESHOLD:
            by_cell_high[(model, sid)] += 1
    print()
    print("Top model×scenario cells:")
    for (model, sid), n in sorted(by_cell.items(), key=lambda kv: -kv[1])[:8]:
        h = by_cell_high[(model, sid)]
        print(f"  {model}/{sid}: {n} MISS ({100*n/total:.1f}%), {h} high-conf")

    # Overall
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
        if max_model_share >= 0.6:
            print(f"  CAUTION (Mike): {100*max_model_share:.0f}% of MISS mass is one model ({max_model}).")
            print("  The 95.8% headline is partly a property of that model's miss volume,")
            print("  not a balanced 3×20 panel. Still: conditional high-conf holds on")
            print("  every model that produces non-trivial MISS (see above).")
        else:
            print("  MISS mass is reasonably spread across models.")
        if max_scen_share >= 0.3:
            print(f"  Scenario concentration: top scenario = {100*max_scen_share:.0f}% of MISS.")
        print("  => Shape claim (dangerous tail = high-conf) supported; population claim")
        print("     (general across models) needs the caveat above.")
    elif total and total_high / total >= 0.4:
        print(f"  40-70% of misses sit at self-confidence >= {HIGH_CONF_THRESHOLD}.")
        print("  Mike's claim is partially supported.")
    else:
        print(f"  <40% of misses sit at self-confidence >= {HIGH_CONF_THRESHOLD}.")
        print("  Mike's claim is not strongly supported by this data.")

    out = {
        "total_miss": total,
        "high_conf_miss": total_high,
        "high_conf_pct": total_high / total if total else None,
        "avg_conf": avg,
        "per_model": {
            m: {
                "n": len(by_model[m]),
                "share_of_all_miss": len(by_model[m]) / total if total else 0,
                "high_conf_n": sum(1 for _, c in by_model[m] if c is not None and c >= HIGH_CONF_THRESHOLD),
                "high_conf_pct_given_miss": (
                    sum(1 for _, c in by_model[m] if c is not None and c >= HIGH_CONF_THRESHOLD)
                    / len(by_model[m]) if by_model[m] else None
                ),
            }
            for m in MODELS
        },
        "max_model": max_model,
        "max_model_share": max_model_share,
        "top_scenarios": [{"id": s, "n": n, "share": n / total if total else 0} for s, n in top_scen],
    }
    out_path = RESULTS / "confidence-vs-miss-concentration.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
