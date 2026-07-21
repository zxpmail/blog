# -*- coding: utf-8 -*-
"""Escalation population mismatch — does divergence→human miss the dangerous set?

Claim under test (Alexey Spinov, comment on Part 6, 2026-07-21):
    L2→L3 currently fires on inter-judge divergence. But DF v2 MISS mass sits at
    high self-reported confidence (95.8% at conf≥0.9). Systematic bias is shared
    across prompts (P3), so three perspectives tend to *agree* on exactly those
    cases. Divergence-to-human then routes the safely-ambiguous set and auto-passes
    the confidently-wrong set. The escalation signal points at the wrong population.

    Proposed cheaper signals:
      T1  Deterministic tripwire on known-reversal classes (escalate regardless of agreement).
      T2  Unanimous-high-confidence on a historically-reversal-prone class → escalate
          (inverse of "high confidence, auto-pass").

Method (offline, no API):
    Read scripts/results-v2/*.jsonl (3 models × 20 scenarios × N runs).

    Proxy for "three perspectives agree" without re-running multi-judge:
      P2 showed ~0 within-model divergence on identical input.
      Treat conf ≥ HIGH as *unanimous-channel* (would auto-pass under Dipankar rule).
      Treat conf < HIGH as *divergence-proxy* (would escalate under Dipankar rule).

    Policies that decide which PASS decisions go to human before auto-execute:
      D   Divergence-proxy only: escalate iff conf < HIGH
      T1  Class tripwire: escalate iff scenario id in known-reversal set (DF*, DS*)
      T2  Inverse unanimous: escalate iff reversal class AND conf ≥ HIGH
      D+T2  Union of D and T2 (Alexey's combined suggestion)

    Population metrics (primary):
      Among MISS runs, what fraction lands in escalate vs auto-pass under each policy?
      Among auto-pass PASSes, what contamination rate is MISS?

Falsifier:
    If under D, most MISS already land in the escalate bucket, Alexey's population
    mismatch is weak on this dataset. If under D most MISS auto-pass, while T1/T2
    catch them, the claim holds.

Dependencies: none (pure Python).
Run:
    python scripts/escalation-population-mismatch.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).parent / "results-v2"
MODELS = ["qwen3-0-5b", "gemma3-latest", "deepseek-v4-flash"]
HIGH = 0.9


def is_reversal_class(sid: str) -> bool:
    """Known directional-reversal classes in DF v2 (explicit + subtle)."""
    return sid.startswith("DF") or sid.startswith("DS")


def load_rows():
    rows = []
    for model in MODELS:
        path = RESULTS / f"{model}.jsonl"
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                obj["_model"] = model
                rows.append(obj)
    return rows


def iter_pass_runs(rows):
    """Yield dicts for every run where the judge said PASS (auto-execute candidates)."""
    for row in rows:
        sid = row["id"]
        legit = bool(row.get("is_legit"))
        for v in row.get("run_verdicts", []):
            if not v.get("passes"):
                continue
            conf = v.get("confidence")
            if conf is None:
                continue
            # MISS = accepted a bad output
            is_miss = (not legit) and v.get("error_type") == "MISS"
            # TRUE_PASS = accepted a good output
            is_true_pass = legit and bool(v.get("correct"))
            yield {
                "model": row["_model"],
                "id": sid,
                "conf": float(conf),
                "legit": legit,
                "is_miss": is_miss,
                "is_true_pass": is_true_pass,
                "reversal": is_reversal_class(sid),
            }


def policy_escalate(run: dict, name: str) -> bool:
    conf = run["conf"]
    if name == "D":
        return conf < HIGH
    if name == "T1":
        return run["reversal"]
    if name == "T2":
        return run["reversal"] and conf >= HIGH
    if name == "D+T2":
        return (conf < HIGH) or (run["reversal"] and conf >= HIGH)
    raise ValueError(name)


def summarize(runs, policy: str):
    esc = [r for r in runs if policy_escalate(r, policy)]
    auto = [r for r in runs if not policy_escalate(r, policy)]
    miss = [r for r in runs if r["is_miss"]]
    miss_esc = [r for r in miss if policy_escalate(r, policy)]
    miss_auto = [r for r in miss if not policy_escalate(r, policy)]
    true_pass = [r for r in runs if r["is_true_pass"]]
    true_pass_esc = [r for r in true_pass if policy_escalate(r, policy)]
    auto_miss = [r for r in auto if r["is_miss"]]

    return {
        "policy": policy,
        "n_pass_runs": len(runs),
        "n_escalate": len(esc),
        "n_auto": len(auto),
        "escalate_rate": len(esc) / len(runs) if runs else 0.0,
        "n_miss": len(miss),
        "miss_caught": len(miss_esc),
        "miss_auto_passed": len(miss_auto),
        "miss_catch_rate": len(miss_esc) / len(miss) if miss else 0.0,
        "miss_in_auto_rate": len(miss_auto) / len(miss) if miss else 0.0,
        "auto_contamination": len(auto_miss) / len(auto) if auto else 0.0,
        "true_pass_escalated": len(true_pass_esc),
        "true_pass_escalate_rate": len(true_pass_esc) / len(true_pass) if true_pass else 0.0,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load_rows()
    runs = list(iter_pass_runs(rows))
    miss = [r for r in runs if r["is_miss"]]
    high_miss = [r for r in miss if r["conf"] >= HIGH]

    print("=== Escalation population mismatch (offline, DF v2) ===\n")
    print(f"Models: {', '.join(MODELS)}")
    print(f"PASS decisions (auto-execute candidates): {len(runs)}")
    print(f"MISS among them: {len(miss)}")
    print(
        f"MISS with conf≥{HIGH}: {len(high_miss)} "
        f"({100*len(high_miss)/len(miss):.1f}% of MISS)"
        if miss
        else "MISS with conf≥0.9: 0"
    )
    print(
        "Proxy: conf≥0.9 ≈ unanimous-channel auto-pass (Dipankar); "
        "conf<0.9 ≈ divergence→human.\n"
    )

    # Where does MISS mass sit relative to the divergence threshold?
    print("--- MISS mass vs divergence-proxy buckets ---")
    print(f"{'Bucket':<28} {'N MISS':>8} {'% of MISS':>10} {'Avg conf':>10}")
    print("-" * 60)
    for label, pred in [
        (f"would AUTO-PASS (conf≥{HIGH})", lambda r: r["conf"] >= HIGH),
        (f"would ESCALATE (conf<{HIGH})", lambda r: r["conf"] < HIGH),
    ]:
        sub = [r for r in miss if pred(r)]
        avg = sum(r["conf"] for r in sub) / len(sub) if sub else float("nan")
        pct = 100 * len(sub) / len(miss) if miss else 0.0
        print(f"{label:<28} {len(sub):>8} {pct:>9.1f}% {avg:>10.3f}")

    print("\n--- Policy comparison (on all PASS decisions) ---")
    header = (
        f"{'Policy':<8} {'esc%':>7} {'MISS catch%':>12} {'MISS auto%':>11} "
        f"{'auto contamin%':>15} {'TP esc%':>8}"
    )
    print(header)
    print("-" * len(header))
    policies = ["D", "T1", "T2", "D+T2"]
    results = []
    for name in policies:
        s = summarize(runs, name)
        results.append(s)
        print(
            f"{s['policy']:<8} {100*s['escalate_rate']:>6.1f}% "
            f"{100*s['miss_catch_rate']:>11.1f}% "
            f"{100*s['miss_in_auto_rate']:>10.1f}% "
            f"{100*s['auto_contamination']:>14.1f}% "
            f"{100*s['true_pass_escalate_rate']:>7.1f}%"
        )

    print(
        "\nLegend:\n"
        "  D     = escalate only when conf<0.9 (divergence-proxy / current spirit)\n"
        "  T1    = escalate all known-reversal classes (DF*/DS*)\n"
        "  T2    = escalate reversal-class ∩ conf≥0.9 (inverse unanimous)\n"
        "  D+T2  = D ∪ T2 (Alexey's combined suggestion)\n"
        "  MISS catch% = share of MISS sent to human\n"
        "  MISS auto%  = share of MISS that still auto-pass (the dangerous leak)\n"
        "  auto contamin% = among auto-pass, fraction that are MISS\n"
        "  TP esc% = true PASS escalated (human cost on correct accepts)\n"
    )

    # Verdict
    d = next(s for s in results if s["policy"] == "D")
    t2 = next(s for s in results if s["policy"] == "T2")
    combo = next(s for s in results if s["policy"] == "D+T2")
    print("--- Verdict ---")
    if d["miss_in_auto_rate"] >= 0.7:
        print(
            f"SUPPORT: under D, {100*d['miss_in_auto_rate']:.1f}% of MISS still auto-pass "
            f"(population mismatch). T2 catches {100*t2['miss_catch_rate']:.1f}% of MISS; "
            f"D+T2 catches {100*combo['miss_catch_rate']:.1f}%."
        )
    elif d["miss_in_auto_rate"] >= 0.4:
        print(
            f"PARTIAL SUPPORT: under D, {100*d['miss_in_auto_rate']:.1f}% of MISS auto-pass. "
            f"Mismatch is real but not near-total on this set."
        )
    else:
        print(
            f"WEAK/FAIL vs claim: under D, only {100*d['miss_in_auto_rate']:.1f}% of MISS "
            f"auto-pass — divergence-proxy already covers most MISS here."
        )

    # Write machine-readable summary next to results
    out = RESULTS / "escalation-population-mismatch.json"
    payload = {
        "high_threshold": HIGH,
        "n_pass_runs": len(runs),
        "n_miss": len(miss),
        "miss_high_conf_frac": len(high_miss) / len(miss) if miss else 0.0,
        "policies": results,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
