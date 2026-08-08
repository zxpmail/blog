# -*- coding: utf-8 -*-
"""Dual-column dashboard — carry both numbers by default (Mike, after ρ=0.8).

Claim under test:
  Mike (follow-up on shadow-promote): the ρ=0.8 row makes the failure mode
  legible — any-alert 98% while live-catch 62%. A dashboard with only the
  forensic number would ship that as green. The promotion ladder only works
  if you already suspected the two metrics could diverge enough to build a
  live-catch column. Stronger rule: carry both numbers by default even when
  they usually agree, because the one time they do not is the one time you
  needed the second column to already exist.

Method:
  Light experiment — no re-simulation. Read
  `results-v2/joint-failure-shadow-promote.json` (interrupt ladder, τ=0.05
  L=20) and apply two dashboard promote policies at each ρ:

    single_any   — ship/promote if any_alert_rate ≥ ANY_FLOOR (default 0.90)
                   (forensic-only aggregate; the common setup Mike names)
    dual_column  — ship/promote iff live promote_ok
                   (predicted_live − realized_live ≤ promote_eps)
                   AND report any_alert alongside (both columns present)

  Also mark rows where the two dashboards *disagree* — the hide surface.

Expected (SUPPORT if all hold):
  1. ρ=1.0: both dashboards SHIP (they usually agree)
  2. ρ=0.8: single_any SHIP, dual_column HOLD — single aggregate greens the
     collapse; dual refuses
  3. At least one disagree row exists on the interrupt ladder
  4. Forensic ladder (τ=0.03) still shows a disagree row somewhere
     (second column not optional for that role either)

Falsification:
  If single_any also HOLDs at ρ=0.8, the forensic floor is not high enough
  to hide on this dump (re-tune or drop claim). If dual SHIPs at ρ=0.8,
  the upstream promote_ok definition changed.

Dependencies: stdlib; requires joint-failure-shadow-promote.json present.
Run: python dual-column-dashboard-test.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).parent
SRC = HERE / "results-v2" / "joint-failure-shadow-promote.json"
OUT = HERE / "results-v2" / "dual-column-dashboard.json"
ANY_FLOOR = 0.90


def decide(row: dict, eps: float) -> dict:
    any_r = row["any_alert_rate"]
    live_r = row["live_catch_rate"]
    gap = row["gap_vs_predicted"]
    single = "SHIP" if any_r >= ANY_FLOOR else "HOLD"
    dual = "SHIP" if gap <= eps else "HOLD"
    return {
        "rho": row["rho"],
        "live_catch_rate": live_r,
        "any_alert_rate": any_r,
        "gap_vs_predicted": gap,
        "single_any": single,
        "dual_column": dual,
        "disagree": single != dual,
    }


def main():
    if not SRC.exists():
        print(f"MISSING {SRC} — run joint-failure-shadow-promote-test.py first")
        sys.exit(2)

    blob = json.loads(SRC.read_text(encoding="utf-8"))
    eps = blob["params"]["promote_eps"]
    ladders = {L["role"]: L for L in blob["ladders"]}
    interrupt = ladders["interrupt"]
    forensic = ladders["forensic"]

    rows_i = [decide(r, eps) for r in interrupt["shadow"]]
    rows_f = [decide(r, eps) for r in forensic["shadow"]]

    by_rho_i = {r["rho"]: r for r in rows_i}
    r1 = by_rho_i[1.0]
    r08 = by_rho_i[0.8]

    checks = {
        "rho1_both_ship": r1["single_any"] == "SHIP" and r1["dual_column"] == "SHIP",
        "rho08_single_ships_dual_holds": (
            r08["single_any"] == "SHIP" and r08["dual_column"] == "HOLD"
        ),
        "interrupt_has_disagree": any(r["disagree"] for r in rows_i),
        "forensic_has_disagree": any(r["disagree"] for r in rows_f),
    }
    verdict = "SUPPORT" if all(checks.values()) else "FALSIFIED"

    print("=== dual-column-dashboard-test ===")
    print(f"source: {SRC.name}  ANY_FLOOR={ANY_FLOOR}  promote_eps={eps}")
    print()
    print("interrupt τ=0.05 L=20:")
    print(f"{'rho':>5} {'live':>6} {'any':>6} {'single':>8} {'dual':>8} {'Δ?':>4}")
    print("-" * 42)
    for r in rows_i:
        flag = "YES" if r["disagree"] else ""
        print(
            f"{r['rho']:>5.1f} {r['live_catch_rate']:>5.0%} "
            f"{r['any_alert_rate']:>5.0%} {r['single_any']:>8} "
            f"{r['dual_column']:>8} {flag:>4}"
        )
    print()
    print("forensic τ=0.03 L=20 (disagree rows only):")
    for r in rows_f:
        if r["disagree"]:
            print(
                f"  ρ={r['rho']}: live={r['live_catch_rate']:.0%} "
                f"any={r['any_alert_rate']:.0%} "
                f"single={r['single_any']} dual={r['dual_column']}"
            )
    print()
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nVERDICT: {verdict}")
    print()
    print("Mike's lock: carry both by default — the disagree row is why the")
    print("second column had to exist before ρ=0.8 showed up.")

    payload = {
        "claim": (
            "Forensic-only dashboard (any-alert ≥ floor) ships ρ=0.8 as green "
            "while dual-column (live promote_ok) holds; carry both numbers by "
            "default even when they usually agree."
        ),
        "source": str(SRC.name),
        "any_floor": ANY_FLOOR,
        "promote_eps": eps,
        "interrupt_rows": rows_i,
        "forensic_rows": rows_f,
        "checks": checks,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
