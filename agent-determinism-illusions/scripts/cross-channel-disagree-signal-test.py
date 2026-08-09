# -*- coding: utf-8 -*-
"""Cross-channel disagreement as review signal (AI Explore, Part 8).

Claim under test:
  AI Explore: track disagreement between the text channel (A) and the
  filesystem channel (B) as its own signal. When they diverge on the same
  requirement, that is not noise — it is a flag where evasion (or a broken
  check) lives. Agreement is boring; spend review minutes on divergence.

Method:
  Light experiment — no re-sim / no API. Read
  `results-v2/channel-comparison.json` (Part 8 Phase 1, 12 scenarios).
  For each scenario classify the (A_pass, B_pass) cell:

    agree_pass   — both PASS
    agree_reject — both REJECT
    disagree     — XOR (exactly one PASS)

  Metrics:
    1. Every complementary catch (non-compliant, exactly one channel
       rejects) sits in disagree.
    2. Precision of "escalate on disagree": P(non-compliant | disagree) = 1.
    3. Density: P(non-compliant | disagree) > P(non-compliant | agree_pass)
       — spend minutes on diverge beats spending them on dual-green.
    4. Scope lock: ≥1 shared miss in agree_pass (SC10-type) — "agreement
       is boring" is false for dual-green; disagree does not replace DPI.

  Note: agree_reject (both REJECT) is already caught without a conflict
  signal — not counted against the disagree spend rule.

Expected SUPPORT if 1–4 all hold.

Falsification:
  If a compliant scenario lands in disagree (precision < 1), disagreement
  is noisier than claimed. If density(disagree) ≤ density(agree_pass),
  the spend rule has no edge on this dump. If no single-channel catches,
  no complementary mass to validate.

Dependencies: stdlib; requires channel-comparison.json.
Run: python cross-channel-disagree-signal-test.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).parent
SRC = HERE / "results-v2" / "channel-comparison.json"
OUT = HERE / "results-v2" / "cross-channel-disagree-signal.json"


def cell(a_pass: bool, b_pass: bool) -> str:
    if a_pass and b_pass:
        return "agree_pass"
    if (not a_pass) and (not b_pass):
        return "agree_reject"
    return "disagree"


def main():
    if not SRC.exists():
        print(f"MISSING {SRC} — run channel-comparison-test.py first")
        sys.exit(2)

    blob = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for s in blob["per_scenario"]:
        a = bool(s["channel_a"]["pass"])
        b = bool(s["channel_b"]["pass"])
        c = cell(a, b)
        comp = bool(s["compliant"])
        single_catch = (not comp) and (a != b)  # exactly one channel rejects
        both_miss = (not comp) and a and b
        rows.append({
            "name": s["name"],
            "compliant": comp,
            "a_pass": a,
            "b_pass": b,
            "cell": c,
            "single_channel_catch": single_catch,
            "shared_miss": both_miss,
        })

    disagree = [r for r in rows if r["cell"] == "disagree"]
    agree_pass = [r for r in rows if r["cell"] == "agree_pass"]
    agree_reject = [r for r in rows if r["cell"] == "agree_reject"]
    noncomp = [r for r in rows if not r["compliant"]]
    single_catches = [r for r in noncomp if r["single_channel_catch"]]
    shared_misses = [r for r in noncomp if r["shared_miss"]]
    recoverable = [r for r in noncomp if not r["shared_miss"]]

    # 1. all single-channel catches in disagree
    c1 = all(r["cell"] == "disagree" for r in single_catches) and len(single_catches) > 0

    # 2. precision of disagree escalate
    prec = (
        sum(1 for r in disagree if not r["compliant"]) / len(disagree)
        if disagree else None
    )
    c2 = prec == 1.0

    # 3. density edge vs agree_pass (dual-green)
    dens_dis = prec  # same as precision when defined
    dens_ap = (
        sum(1 for r in agree_pass if not r["compliant"]) / len(agree_pass)
        if agree_pass else None
    )
    c3 = dens_dis is not None and dens_ap is not None and dens_dis > dens_ap

    # 4. scope: shared miss exists in agree_pass
    c4_scope = len(shared_misses) >= 1 and all(
        r["cell"] == "agree_pass" for r in shared_misses
    )

    checks = {
        "single_catches_all_in_disagree": c1,
        "disagree_precision_1": c2,
        "disagree_denser_than_agree_pass": c3,
        "shared_miss_in_agree_pass_scope": c4_scope,
    }
    verdict = "SUPPORT" if all(checks.values()) else "FALSIFIED"

    print("=== cross-channel-disagree-signal-test ===")
    print(f"source: {SRC.name}  n={len(rows)}")
    print()
    print(f"{'scenario':<28} {'comp':>4} {'A':>4} {'B':>4} {'cell':<14} note")
    print("-" * 72)
    for r in rows:
        note = ""
        if r["single_channel_catch"]:
            note = "single-ch catch"
        elif r["shared_miss"]:
            note = "SHARED MISS"
        print(
            f"{r['name']:<28} {'Y' if r['compliant'] else 'N':>4} "
            f"{'P' if r['a_pass'] else 'R':>4} "
            f"{'P' if r['b_pass'] else 'R':>4} "
            f"{r['cell']:<14} {note}"
        )
    print()
    print(
        f"disagree={len(disagree)}  agree_pass={len(agree_pass)}  "
        f"agree_reject={len(agree_reject)}"
    )
    print(
        f"single-channel catches={len(single_catches)}  "
        f"shared misses={len(shared_misses)}  "
        f"disagree precision={prec}"
    )
    print(
        f"density non-comp | disagree={dens_dis}  agree_pass={dens_ap}  "
        f"agree_reject="
        f"{sum(1 for r in agree_reject if not r['compliant'])/len(agree_reject) if agree_reject else None}"
    )
    print()
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nVERDICT: {verdict}")
    print()
    print("AI Explore lock: spend review minutes on disagree (complementary).")
    print("Scope: agree_pass still holds shared miss — dual-green is not boring.")

    payload = {
        "claim": (
            "Cross-channel disagreement is a high-precision escalate signal "
            "for complementary A/B failures; denser than agree_pass; "
            "agree_pass still holds shared miss."
        ),
        "source": SRC.name,
        "rows": rows,
        "counts": {
            "disagree": len(disagree),
            "agree_pass": len(agree_pass),
            "agree_reject": len(agree_reject),
            "single_channel_catches": len(single_catches),
            "shared_misses": len(shared_misses),
            "disagree_precision": prec,
            "density_disagree": dens_dis,
            "density_agree_pass": dens_ap,
            "recoverable_total": len(recoverable),
        },
        "checks": checks,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
