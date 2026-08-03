# -*- coding: utf-8 -*-
"""External reference — what actually escapes the P8 mute cell (Xiao Man, 2026-08-04).

Claim under test:
  P2 (legit relocation, payload moved to `instances`) and P8 (agree-wrong,
  payload also at `instances` but bait at `modules` grabbed by both anchors)
  are observationally identical to any *matcher*: in both cells the payload
  sits where the synonym list doesn't cover. Therefore no matching probe —
  any substrate, any canonical hash — can catch P8 without also flagging P2.
  What escapes is a probe whose *reference* the producer didn't author:
  (b') a different-author canonical/live state (second author), or
  (c)  change detection against a baseline (tripwire), which catches P8 by
       noticing the agreed location moved — but only as an advisory flag.

Method:
  Same T3 fixture + P2/P6/P8 cells from declaration-anchor-agree-wrong-
  silence-test.py, plus a new P9 cell (legit relocation to `modules`, both
  anchors correct). Three candidate probe arms:
    static_canonical — payload must sit at declared key 'services'
                       (option-b structural hash, same-author reference).
    consensus_drift  — when anchors disagree, the load sensor already fires
                       (redundant); when they agree, fire iff the agreed
                       location differs from the baseline ('services')
                       (option-c tripwire).
    content_size     — key-free substrate: resolve the largest list-of-dicts
                       subtree by total nested key count, tie → first in
                       insertion order (option-a different substrate).

Readouts per cell × arm: fire status + oracle_correct (vs truth, oracle only).

Expected:
  static_canonical — quiet on base/P6; fires on P2 (FP), P8 (TP), P9 (FP).
                     P2 and P8 fire identically → cannot separate a legit
                     relocation from an adversarial one.
  consensus_drift  — quiet on base; fires on P8 (TP) and P9 (advisory: a
                     legit relocation still "moved", which is worth human
                     eyes); P2/P6 already fire via disagreement. Never
                     claims a verdict, only "location changed".
  content_size     — correct on base/P2/P6/P9; P8's bait ties the payload on
                     key count and wins the insertion-order tie → agree-wrong
                     again. A different substrate is a re-drawn boundary.

Falsification:
  If static_canonical separates P2 from P8 (fires on exactly one), the
  identity claim fails. If consensus_drift stays quiet on P8, change
  detection does not close the mute cell. If content_size resolves P8
  correctly, a key-free substrate escapes the bait.

Dependencies: stdlib only.
Run: python declaration-anchor-external-reference-test.py
"""

from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "declaration-anchor-external-reference.json"

BASELINE = "services"  # last-known-good agreed payload location


def base_good_t3() -> dict:
    return {
        "services": [
            {"name": "api", "port": 8080,
             "limits": {"max_connections": 10, "timeout_ms": 5000}},
            {"name": "worker", "port": 8081,
             "limits": {"max_connections": 20, "timeout_ms": 3000}},
        ],
        "_meta": {"ok": True},
    }


def p2_rename_outside_decl(art):
    a = copy.deepcopy(art)
    a["instances"] = a.pop("services")
    return a


def p6_decoy_with_limits(art):
    a = {"connections": [{"limits": {"x": 1}}, {"limits": {"x": 2}}]}
    for k, v in art.items():
        a[k] = copy.deepcopy(v)
    return a


def p8_agree_wrong(art):
    """真载荷挪出同义词表；同义词+外形诱饵 modules 抢先被两边命中。"""
    a = {}
    a["modules"] = [
        {"name": "bait", "port": 1,
         "limits": {"max_connections": 1, "timeout_ms": 1}},
        {"name": "bait2", "port": 2,
         "limits": {"max_connections": 1, "timeout_ms": 1}},
    ]
    a["instances"] = copy.deepcopy(art["services"])
    for k, v in art.items():
        if k == "services":
            continue
        a[k] = copy.deepcopy(v)
    return a


def p9_agree_right(art):
    """合法搬迁：载荷真在 modules，双锚都对该落点。"""
    a = {}
    a["modules"] = copy.deepcopy(art["services"])
    for k, v in art.items():
        if k == "services":
            continue
        a[k] = copy.deepcopy(v)
    return a


CELLS = [
    ("base", lambda base: copy.deepcopy(base), "services"),
    ("P2_rename_outside_decl", p2_rename_outside_decl, "instances"),
    ("P6_decoy_with_limits", p6_decoy_with_limits, "services"),
    ("P8_agree_wrong", p8_agree_wrong, "instances"),
    ("P9_agree_right", p9_agree_right, "modules"),
]


def _is_list_of_dicts(v) -> bool:
    return isinstance(v, list) and len(v) > 0 and all(isinstance(x, dict) for x in v)


def anchor_synonym_list(art: dict) -> str | None:
    for cand in ["services", "components", "modules"]:
        v = art.get(cand)
        if isinstance(v, list):
            return cand
    return None


def anchor_structural(art: dict) -> str | None:
    for k, v in art.items():
        if not _is_list_of_dicts(v):
            continue
        if all("limits" in d for d in v):
            return k
    return None


def anchor_content_size(art: dict) -> str | None:
    """无键名基质：取 list-of-dicts 里嵌套键总数最大者，并列取插入序第一。"""
    best, best_size = None, -1
    for k, v in art.items():
        if not _is_list_of_dicts(v):
            continue
        size = sum(len(d) for d in v)
        if size > best_size:
            best_size = size
            best = k
    return best


def arm_static_canonical(art: dict) -> bool:
    """载荷必须落在声明键 services —— 同作者 canonical 哈希。"""
    v = art.get(BASELINE)
    return not _is_list_of_dicts(v)


def arm_consensus_drift(primary: str | None, secondary: str | None) -> str | bool:
    """分歧格已由负载传感器亮；一致时若落点离开基线则触发。"""
    if primary != secondary:
        return "sensor(disagree)"
    return (primary != BASELINE) and (primary is not None)


def eval_cell(name: str, fn, truth: str, base: dict) -> dict:
    art = fn(base)
    primary = anchor_synonym_list(art)
    secondary = anchor_structural(art)
    agree = primary == secondary
    cs = anchor_content_size(art)
    row = {
        "perturbation": name,
        "truth": truth,
        "primary": primary,
        "secondary": secondary,
        "agree": agree,
        "content_size_resolved": cs,
        "content_size_ok": cs == truth,
        "sensor_fires": not agree,
        "static_canonical_fire": arm_static_canonical(art),
        "static_canonical_ok": (not arm_static_canonical(art)) == (truth == BASELINE),
        "consensus_drift": arm_consensus_drift(primary, secondary),
    }
    return row


def main():
    base = base_good_t3()
    print("═" * 72)
    print("  External reference — what escapes the P8 mute cell")
    print("  primary=synonym_list  secondary=structural  baseline=%s" % BASELINE)
    print("═" * 72)

    rows = []
    for name, fn, truth in CELLS:
        r = eval_cell(name, fn, truth, base)
        rows.append(r)
        fire = "FIRE" if r["sensor_fires"] else "QUIET"
        canon = "FIRE" if r["static_canonical_fire"] else "quiet"
        drift = r["consensus_drift"]
        drift_s = "FIRE" if drift is True else ("quiet" if drift is False else "sensor")
        print(
            f"  {name:<26} sensor={fire:<5} truth={r['truth']:<9} "
            f"canonical={canon:<5} drift={drift_s:<6} "
            f"content={r['content_size_resolved'] or 'None':<10} "
            f"content_ok={r['content_size_ok']}"
        )

    by = {r["perturbation"]: r for r in rows}
    p2, p6, p8, p9 = by["P2_rename_outside_decl"], by["P6_decoy_with_limits"], by["P8_agree_wrong"], by["P9_agree_right"]

    identity = (
        p2["static_canonical_fire"] and p8["static_canonical_fire"]
        and (not p6["static_canonical_fire"]) and (not by["base"]["static_canonical_fire"])
    )
    drift_ok = (
        p8["consensus_drift"] is True
        and by["base"]["consensus_drift"] is False
        and p9["consensus_drift"] is True  # advisory flag on legit relocation
    )
    substrate_trapped = p8["content_size_ok"] is False and p8["agree"] is True

    print("\n  Verdicts:")
    print(f"    P2/P8 identity to canonical-location probe:     {'PASS' if identity else 'FAIL'}")
    print(f"    consensus-drift catches P8 (+advisory on P9):   {'PASS' if drift_ok else 'FAIL'}")
    print(f"    key-free substrate still trapped by P8 bait:    {'PASS' if substrate_trapped else 'FAIL'}")
    print(f"    Overall:                                        {'PASS' if identity and drift_ok and substrate_trapped else 'FAIL'}")

    out = {
        "experiment": "declaration-anchor-external-reference",
        "question": (
            "Xiao Man 2026-08-04: the repeated need for an external probe "
            "becomes a design parameter — what does the probe look like in "
            "practice (different substrate / structural hash / shape-change)?"
        ),
        "cells": rows,
        "interpretation": (
            "A matching probe (canonical-location hash, option b as same-author "
            "reference) fires identically on P2 and P8 — it cannot separate a "
            "legit relocation from an adversarial one, because the two cells "
            "differ only in external intent, not artifact structure. A key-free "
            "substrate (option a) is still trapped by P8's bait (tie on key "
            "count, insertion order decides) — a re-drawn boundary, same "
            "species. Only the baseline tripwire (option c) closes the mute "
            "cell, by flagging 'agreed location moved' rather than judging — "
            "and it flags a legit relocation (P9) too, so it is advisory "
            "(route to human), never a gate."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {OUT}")
    return 0 if identity and drift_ok and substrate_trapped else 1


if __name__ == "__main__":
    raise SystemExit(main())
