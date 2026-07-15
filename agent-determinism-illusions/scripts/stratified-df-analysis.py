"""
Experiment: Stratified analysis of existing DF v2 data — ANP2's test on real data

Falsifiable claim:
    ANP2 Network's discrimination-vs-calibration test applied to the existing
    directional-failure v2 data. The 20 scenarios split naturally into four
    subtlety strata:
      - explicit_df (DF1-DF6):    reversal stated openly with contradicting keywords
      - subtle_df  (DS1-DS10):    reversal hidden behind a rationalization
      - valid_ctrl (V1-V2):       legitimate output (should always pass)
      - garbage_ctrl (G1-G2):     non-output (should always reject)

    Claim: per-stratum miss rates pull apart sharply across the three model
    tiers (qwen3-0.5b / gemma3-4.3b / deepseek-v4-flash). The aggregate "wall"
    hides this — within each stratum, the pattern is either discrimination
    (high miss rate scales with model capability — capability-bound) or
    calibration (high miss rate is uniform across models — true wall).

    Specifically:
    - explicit_df: should be ~0% miss for all three tiers (easy stratum)
    - subtle_df: should scale sharply with capability (gradient stratum)
    - DS4 specifically: the "no-change-needed" rationalization should be the
      hardest case, with weak models at ~100% miss and strong models
      showing uncertainty (PARSE_FAIL) rather than confident miss.

    Falsification: if miss rates are uniform across model tiers within each
    stratum, the gradient is not capability-driven — the wall is structural.

Method:
    Reads existing JSONL files in results-v2/ (no new API calls).
    For each (model, scenario), aggregates per-run verdicts into:
      - miss_rate: P(judge says passes | defective)
      - parse_fail_rate: P(no parseable verdict)
      - confidence_when_miss: mean confidence on wrong verdicts

    Per-stratum summary by subtlety tier. Three-model comparison.

Dependencies: existing DF v2 JSONL files in results-v2/.
"""

import json
import sys
import io
import math
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Configuration ───────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results-v2"

MODELS = [
    ("qwen3:0.5b",        "qwen3-0-5b.jsonl",        "weak (0.5B)"),
    ("gemma3:latest",     "gemma3-latest.jsonl",     "mid (4.3B)"),
    ("deepseek-v4-flash", "deepseek-v4-flash.jsonl", "strong (~200B)"),
]

# Strata definitions
STRATA = {
    "explicit_df": {
        "ids": ["DF1", "DF2", "DF3", "DF4", "DF5", "DF6"],
        "kind": "defective",  # ground truth: should be REJECTED
        "label": "Explicit reversal (keywords contradict task)",
    },
    "subtle_df": {
        "ids": [f"DS{i}" for i in range(1, 11)],
        "kind": "defective",
        "label": "Subtle reversal (rationalization hides direction)",
    },
    "valid_ctrl": {
        "ids": ["V1", "V2"],
        "kind": "valid",  # ground truth: should PASS
        "label": "Valid control (legitimate output)",
    },
    "garbage_ctrl": {
        "ids": ["G1", "G2"],
        "kind": "defective",
        "label": "Garbage control (non-output)",
    },
}


# ─── Data loading ────────────────────────────────────────────────────────────

def load_jsonl(path):
    """Load a JSONL file. Returns list of dicts."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def aggregate_scenario(record):
    """Aggregate a scenario record's per-run verdicts.

    Returns dict with: n, miss_rate, parse_fail_rate, false_reject_rate,
    confidence_when_wrong, confidence_when_right.
    """
    verdicts = record.get("run_verdicts", [])
    n = len(verdicts)
    is_legit = record.get("is_legit", False)

    misses = 0       # defective wrongly passes
    false_rejects = 0  # valid wrongly rejected
    parse_fails = 0
    conf_wrong = []
    conf_right = []

    for v in verdicts:
        passes = v.get("passes")
        conf = v.get("confidence")
        err = v.get("error_type", "")

        if passes is None or err == "PARSE_FAIL":
            parse_fails += 1
            continue

        if is_legit:
            # Valid output: correct = passes=True
            if passes:
                conf_right.append(conf if conf is not None else 0)
            else:
                false_rejects += 1
                conf_wrong.append(conf if conf is not None else 0)
        else:
            # Defective output: correct = passes=False
            if not passes:
                conf_right.append(conf if conf is not None else 0)
            else:
                misses += 1
                conf_wrong.append(conf if conf is not None else 0)

    n_judged = n - parse_fails
    return {
        "n": n,
        "n_judged": n_judged,
        "miss_rate": misses / n_judged if (not is_legit and n_judged > 0) else None,
        "false_reject_rate": false_rejects / n_judged if (is_legit and n_judged > 0) else None,
        "parse_fail_rate": parse_fails / n if n > 0 else 0,
        "confidence_when_wrong": (sum(conf_wrong) / len(conf_wrong)) if conf_wrong else None,
        "confidence_when_right": (sum(conf_right) / len(conf_right)) if conf_right else None,
    }


# ─── SDT analysis ────────────────────────────────────────────────────────────

def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def d_prime_from_hit_fa(hit_rate, fa_rate):
    """Compute d' from hit and false-alarm rates.

    hit_rate: P(say defective | defective) = 1 - miss_rate
    fa_rate:  P(say defective | valid)     = false_reject_rate (for valid controls)

    d' = z(hit) - z(fa)
    """
    # Clamp to avoid infinite z-scores
    hit = min(max(hit_rate, 0.01), 0.99)
    fa = min(max(fa_rate, 0.01), 0.99)
    z_hit = _ppf(hit)
    z_fa = _ppf(fa)
    return z_hit - z_fa


def _ppf(p):
    """Inverse normal CDF (Beasley-Springer-Moro)."""
    if p <= 0:
        return float("-inf")
    if p >= 1:
        return float("inf")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    elif p <= phigh:
        q = p - 0.5
        r = q*q
        x = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
            (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    else:
        q = math.sqrt(-2 * math.log(1-p))
        x = -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    return x


# ─── Main analysis ───────────────────────────────────────────────────────────

def print_table(rows, headers):
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    print()


def main():
    print("=" * 80)
    print("Stratified Analysis of DF v2 Data — ANP2's discrimination vs calibration test")
    print("=" * 80)
    print()

    # Load all model data
    model_data = {}
    for model_name, fname, tier in MODELS:
        path = RESULTS_DIR / fname
        if not path.exists():
            print(f"WARNING: {path} not found, skipping {model_name}")
            continue
        records = load_jsonl(path)
        model_data[model_name] = {
            "tier": tier,
            "records": {r["id"]: aggregate_scenario(r) for r in records},
        }
        print(f"Loaded {model_name} ({tier}): {len(records)} scenarios")

    if len(model_data) < 2:
        print("\nERROR: need at least 2 models for stratified comparison")
        return

    print()

    # ─── Sweep 1: Per-stratum miss rate by model tier ──────────────────
    print("─" * 80)
    print("SWEEP 1: Per-stratum miss rate by model tier")
    print("(miss rate = P(judge says 'passes' | defective))")
    print("─" * 80)

    rows = []
    for stratum_name, stratum_cfg in STRATA.items():
        if stratum_cfg["kind"] != "defective":
            continue
        row = [stratum_name]
        for model_name, _, _ in MODELS:
            if model_name not in model_data:
                row.append("—")
                continue
            records = model_data[model_name]["records"]
            misses = []
            for sid in stratum_cfg["ids"]:
                if sid in records and records[sid]["miss_rate"] is not None:
                    misses.append(records[sid]["miss_rate"])
            if misses:
                # Weight by n_judged
                total_miss = sum(records[sid]["miss_rate"] * records[sid]["n_judged"]
                                 for sid in stratum_cfg["ids"]
                                 if sid in records and records[sid]["miss_rate"] is not None)
                total_n = sum(records[sid]["n_judged"]
                              for sid in stratum_cfg["ids"]
                              if sid in records and records[sid]["miss_rate"] is not None)
                weighted = total_miss / total_n if total_n > 0 else 0
                row.append(f"{weighted:.1%} ({len(misses)} scn)")
            else:
                row.append("—")
        rows.append(row)
    print_table(rows, ["Stratum"] + [m[0] for m in MODELS])

    # ─── Sweep 2: Per-scenario detail (subtle_df only — where the action is) ─
    print("─" * 80)
    print("SWEEP 2: Per-scenario miss rate within subtle_df (the gradient stratum)")
    print("─" * 80)

    rows = []
    for sid in STRATA["subtle_df"]["ids"]:
        row = [sid]
        for model_name, _, _ in MODELS:
            if model_name not in model_data:
                row.append("—")
                continue
            rec = model_data[model_name]["records"].get(sid)
            if rec and rec["miss_rate"] is not None:
                row.append(f"{rec['miss_rate']:.0%}")
            else:
                row.append("—")
        rows.append(row)
    print_table(rows, ["Scenario"] + [m[2] for m in MODELS])

    # ─── Sweep 3: Pull-apart Δ — does stratification reveal heterogeneity? ─
    print("─" * 80)
    print("SWEEP 3: Pull-apart — does stratification reveal heterogeneity?")
    print("─" * 80)
    print("If per-stratum miss rates differ substantially, the aggregate wall hides")
    print("heterogeneity (collapsed operating points). If uniform, it's discrimination.")
    print()

    rows = []
    for model_name, _, tier in MODELS:
        if model_name not in model_data:
            continue
        records = model_data[model_name]["records"]

        # Aggregate defective miss rate
        all_defective = [sid for sname, scfg in STRATA.items()
                         if scfg["kind"] == "defective"
                         for sid in scfg["ids"]
                         if sid in records and records[sid]["miss_rate"] is not None]
        total_n = sum(records[sid]["n_judged"] for sid in all_defective)
        total_miss = sum(records[sid]["miss_rate"] * records[sid]["n_judged"] for sid in all_defective)
        agg = total_miss / total_n if total_n > 0 else 0

        # Per-stratum
        explicit_ids = [s for s in STRATA["explicit_df"]["ids"] if s in records and records[s]["miss_rate"] is not None]
        subtle_ids = [s for s in STRATA["subtle_df"]["ids"] if s in records and records[s]["miss_rate"] is not None]
        garbage_ids = [s for s in STRATA["garbage_ctrl"]["ids"] if s in records and records[s]["miss_rate"] is not None]

        def wmiss(ids):
            tn = sum(records[s]["n_judged"] for s in ids)
            tm = sum(records[s]["miss_rate"] * records[s]["n_judged"] for s in ids)
            return tm / tn if tn > 0 else 0

        rows.append([
            f"{tier}",
            f"{agg:.1%}",
            f"{wmiss(explicit_ids):.1%}",
            f"{wmiss(subtle_ids):.1%}",
            f"{wmiss(garbage_ids):.1%}",
            f"{wmiss(subtle_ids) - wmiss(explicit_ids):+.1%}",
        ])
    print_table(rows, ["Model tier", "Aggregate", "Explicit", "Subtle", "Garbage",
                       "Δ (subtle - explicit)"])

    # ─── Sweep 4: d' estimate per stratum (using valid_ctrl as FA reference) ──
    print("─" * 80)
    print("SWEEP 4: Estimated d' per model (using valid_ctrl false-reject as FA proxy)")
    print("─" * 80)
    print("Note: d' computed from hit (1 - miss_rate) on defective stratum vs FA on valid.")
    print("This is approximate — valid_ctrl has only 2 scenarios, FA estimate is noisy.")
    print()

    rows = []
    for model_name, _, tier in MODELS:
        if model_name not in model_data:
            continue
        records = model_data[model_name]["records"]

        # Hit rate = 1 - miss_rate on subtle_df (the interesting stratum)
        subtle_ids = [s for s in STRATA["subtle_df"]["ids"] if s in records and records[s]["miss_rate"] is not None]
        if not subtle_ids:
            continue
        total_n = sum(records[s]["n_judged"] for s in subtle_ids)
        total_miss = sum(records[s]["miss_rate"] * records[s]["n_judged"] for s in subtle_ids)
        hit_rate = 1 - (total_miss / total_n if total_n > 0 else 0)

        # FA rate on valid_ctrl
        valid_ids = [s for s in STRATA["valid_ctrl"]["ids"] if s in records]
        fa_rate = None
        if valid_ids:
            fa_n = sum(records[s]["n_judged"] for s in valid_ids)
            fa_total = sum((records[s]["false_reject_rate"] or 0) * records[s]["n_judged"]
                           for s in valid_ids
                           if records[s]["false_reject_rate"] is not None)
            fa_rate = fa_total / fa_n if fa_n > 0 else 0

        if fa_rate is not None:
            dp = d_prime_from_hit_fa(hit_rate, fa_rate)
            rows.append([
                tier,
                f"{hit_rate:.1%}",
                f"{fa_rate:.1%}",
                f"{dp:.2f}",
                ("real discrimination" if dp >= 1.0
                 else "weak discrimination" if dp >= 0.5
                 else "near-zero discrimination"),
            ])
        else:
            rows.append([tier, f"{hit_rate:.1%}", "—", "—", "insufficient FA data"])
    print_table(rows, ["Model tier", "Hit Rate (subtle)", "FA Rate (valid)", "d' est.", "Diagnosis"])

    # ─── Sweep 5: DS4 specifically — the "no-change" rationalization ────
    print("─" * 80)
    print("SWEEP 5: DS4 (no-change-needed rationalization) — the hardest case")
    print("─" * 80)

    rows = []
    for model_name, _, tier in MODELS:
        if model_name not in model_data:
            continue
        rec = model_data[model_name]["records"].get("DS4")
        if not rec:
            continue
        rows.append([
            tier,
            f"{rec['miss_rate']:.0%}" if rec['miss_rate'] is not None else "—",
            f"{rec['parse_fail_rate']:.0%}",
            f"{rec['confidence_when_wrong']:.2f}" if rec['confidence_when_wrong'] is not None else "—",
        ])
    print_table(rows, ["Model tier", "Miss Rate", "Parse Fail Rate", "Confidence When Wrong"])

    print("Interpretation:")
    print("  - Weak model: confidently wrong (high miss, high confidence) — classic wall")
    print("  - Strong model: high uncertainty (PARSE_FAIL) — capability gradient, not wall")
    print("  - If strong model were confidently wrong like weak model, that would be a")
    print("    true discrimination ceiling. PARSE_FAIL is the escape signal — the model")
    print("    knows it doesn't know, which stratification can leverage.")

    # ─── Claims check ───────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("CLAIMS CHECK — ANP2's test on real DF v2 data")
    print("=" * 80)

    # Compute per-stratum miss rate variance across models
    print("\nPer-stratum miss rate across model tiers:")
    for stratum_name, stratum_cfg in STRATA.items():
        if stratum_cfg["kind"] != "defective":
            continue
        rates = []
        for model_name, _, _ in MODELS:
            if model_name not in model_data:
                continue
            records = model_data[model_name]["records"]
            ids = [s for s in stratum_cfg["ids"] if s in records and records[s]["miss_rate"] is not None]
            if not ids:
                continue
            tn = sum(records[s]["n_judged"] for s in ids)
            tm = sum(records[s]["miss_rate"] * records[s]["n_judged"] for s in ids)
            rates.append(tm / tn if tn > 0 else 0)
        if len(rates) >= 2:
            spread = max(rates) - min(rates)
            verdict = ("CAPABILITY GRADIENT (not wall)"
                       if spread >= 0.30
                       else "MODERATE GRADIENT"
                       if spread >= 0.10
                       else "UNIFORM (potential wall)")
            print(f"  {stratum_name:15} — min={min(rates):.1%}, max={max(rates):.1%}, "
                  f"spread={spread:.1%} → {verdict}")

    # ─── Write results ──────────────────────────────────────────────────
    out = {
        "parameters": {
            "models": [{"name": m[0], "file": m[1], "tier": m[2]} for m in MODELS],
            "strata": {k: {"ids": v["ids"], "kind": v["kind"]} for k, v in STRATA.items()},
        },
        "per_scenario": {},
        "per_stratum": {},
    }

    for model_name, _, _ in MODELS:
        if model_name not in model_data:
            continue
        out["per_scenario"][model_name] = model_data[model_name]["records"]
        out["per_stratum"][model_name] = {}
        for stratum_name, stratum_cfg in STRATA.items():
            ids = [s for s in stratum_cfg["ids"]
                   if s in model_data[model_name]["records"]
                   and model_data[model_name]["records"][s]["miss_rate"] is not None]
            if not ids:
                continue
            tn = sum(model_data[model_name]["records"][s]["n_judged"] for s in ids)
            tm = sum(model_data[model_name]["records"][s]["miss_rate"] * model_data[model_name]["records"][s]["n_judged"] for s in ids)
            out["per_stratum"][model_name][stratum_name] = tm / tn if tn > 0 else 0

    out_path = RESULTS_DIR / "stratified-df-analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {out_path}")


if __name__ == "__main__":
    main()
