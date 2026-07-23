# -*- coding: utf-8 -*-
"""Dual-axis probe cost/catch experiment — Xiao Man question on Part 7.

Question (Xiao Man, 2026-07-23, Part 7 thread):
  Does out-of-channel probe catch rate stay stable as task complexity rises?
  Is there a complexity threshold where structural invariants become too
  expensive relative to the task itself?

Design (offline, no API — checksum-style probes only):
  Axis T  task/artifact complexity   T1..T4
  Axis P  probe depth / #invariants  P1..P4

  Domain: nested service-config JSON. Ground-truth violations are structural
  (wrong scalar, missing leaf, cross-field break). Probe pass/fail is written
  from schema + artifact only — never from a judge rationale (checksum test).

  Matched pairs: (T1,P1) (T2,P2) (T3,P3) (T4,P4)
  Under-spec:    Pj < matched depth for Ti  → expect catch drop
  Over-spec:     Pj > matched depth for Ti  → expect catch stable, cost up

Metrics per cell:
  catch_rate       = caught_bad / n_bad
  false_reject     = rejected_good / n_good
  probe_ops        = instrumented field visits + comparisons + hash steps
  task_ops         = leaf fields in schema (fixed per T) + artifact char size
  cost_ratio       = probe_ops / max(task_ops, 1)

Claims:
  C1  Matched catch stable: each matched cell catch_rate >= 0.95
  C2  Under-spec drops: mean catch of under-spec cells < 0.80
  C3  Cost grows with probe depth: mean cost_ratio(P4) > mean cost_ratio(P1)
  C4  Relative-cost threshold: report first matched Ti where cost_ratio >= 1.0
      (probe ops >= task ops). Not a falsifier — a measurement Xiao Man asked for.
  C5  Over-spec waste: for each Ti, catch(P_over) ≈ catch(matched) but
      cost_ratio(P_over) > cost_ratio(matched)

Falsifiers:
  C1 fail → catch does NOT stay stable under matched probes (answers Xiao Man
            with "no, even matched structural probes degrade").
  C2 fail → under-specified probes still catch → depth axis is not load-bearing.
  C3 fail → deeper probes are not more expensive → cost story collapses.

Run:
  python probe-complexity-dual-axis.py
  python probe-complexity-dual-axis.py --n 40 --seed 7
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "probe-complexity-dual-axis.json"

# ── Schema levels (task complexity) ─────────────────────────────────────────

SCHEMA = {
    "T1": {
        "depth": 1,
        "leaves": 1,
        "cross": 0,
        "template": lambda rng: {"max_connections": 10},
        "rules": ("max_connections == 10",),
    },
    "T2": {
        "depth": 1,
        "leaves": 3,
        "cross": 0,
        "template": lambda rng: {
            "max_connections": 10,
            "timeout_ms": 5000,
            "retries": 3,
        },
        "rules": (
            "max_connections == 10",
            "timeout_ms == 5000",
            "retries == 3",
        ),
    },
    "T3": {
        "depth": 2,
        "leaves": 8,  # 2 services × (name + port + max_conn + timeout)
        "cross": 0,
        "template": lambda rng: {
            "services": [
                {
                    "name": "api",
                    "port": 8080,
                    "limits": {"max_connections": 10, "timeout_ms": 5000},
                },
                {
                    "name": "worker",
                    "port": 8081,
                    "limits": {"max_connections": 20, "timeout_ms": 3000},
                },
            ]
        },
        "rules": (
            "services[0].limits.max_connections == 10",
            "services[1].limits.max_connections == 20",
            "services[0].port == 8080",
            "services[1].port == 8081",
        ),
    },
    "T4": {
        "depth": 3,
        "leaves": 10,  # T3 leaves + budget + fingerprint
        "cross": 2,
        "template": lambda rng: {
            "budget": 30,
            "services": [
                {
                    "name": "api",
                    "port": 8080,
                    "limits": {"max_connections": 10, "timeout_ms": 5000},
                },
                {
                    "name": "worker",
                    "port": 8081,
                    "limits": {"max_connections": 20, "timeout_ms": 3000},
                },
            ],
            "fingerprint": _fp(["api", "worker"]),
        },
        "rules": (
            "sum(max_connections) <= budget",
            "ports unique",
            "fingerprint matches sorted names",
            "leaf limits as T3",
        ),
    },
}

LEVELS = ["T1", "T2", "T3", "T4"]
PROBES = ["P1", "P2", "P3", "P4"]
MATCHED = {"T1": "P1", "T2": "P2", "T3": "P3", "T4": "P4"}
PROBE_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
TASK_RANK = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


def _fp(names: list[str]) -> str:
    raw = "|".join(sorted(names)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ── Artifact factory ────────────────────────────────────────────────────────


def make_good(level: str, rng: random.Random) -> dict:
    art = copy.deepcopy(SCHEMA[level]["template"](rng))
    # light noise that does not break rules (extra metadata only)
    art["_meta"] = {"seed": rng.randint(0, 10_000), "ok": True}
    return art


def make_bad(level: str, rng: random.Random) -> tuple[dict, str]:
    """Return (artifact, violation_kind). Violation always structural for Ti."""
    art = make_good(level, rng)
    kind = ""

    if level == "T1":
        art["max_connections"] = 50
        kind = "scalar_over_limit"

    elif level == "T2":
        pick = rng.choice(["max_connections", "timeout_ms", "retries"])
        art[pick] = art[pick] * 10 + 1
        kind = f"scalar_{pick}"

    elif level == "T3":
        mode = rng.choice(["nested_limit", "port", "drop_leaf"])
        if mode == "nested_limit":
            art["services"][0]["limits"]["max_connections"] = 999
            kind = "nested_limit"
        elif mode == "port":
            art["services"][1]["port"] = 9999
            kind = "wrong_port"
        else:
            del art["services"][0]["limits"]["timeout_ms"]
            kind = "missing_leaf"

    else:  # T4
        mode = rng.choice(["budget", "port_clash", "fingerprint", "nested"])
        if mode == "budget":
            art["services"][0]["limits"]["max_connections"] = 25
            art["services"][1]["limits"]["max_connections"] = 25
            # sum 50 > budget 30
            kind = "cross_budget"
        elif mode == "port_clash":
            art["services"][1]["port"] = art["services"][0]["port"]
            kind = "cross_port_unique"
        elif mode == "fingerprint":
            art["fingerprint"] = "deadbeefdeadbeef"
            kind = "cross_fingerprint"
        else:
            art["services"][0]["limits"]["timeout_ms"] = 1
            kind = "nested_under_t4"

    return art, kind


# ── Instrumented probes ─────────────────────────────────────────────────────


class Counter:
    def __init__(self) -> None:
        self.ops = 0

    def tick(self, n: int = 1) -> None:
        self.ops += n


def _get(d: Any, *path: str, ctr: Counter) -> Any:
    cur = d
    for p in path:
        ctr.tick(1)
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def probe(level_p: str, level_t: str, art: dict, ctr: Counter) -> tuple[bool, str]:
    """
    Return (reject, reason). reject=True → escalate (artifact fails check).
    Depth of check is controlled by level_p; schema expected by level_t.
    """
    # P1: single root / first scalar only
    if level_p == "P1":
        ctr.tick(1)
        if level_t == "T1" or level_t == "T2":
            v = _get(art, "max_connections", ctr=ctr)
            ctr.tick(1)
            if v != 10:
                return True, f"P1 max_connections={v}"
            return False, "P1 ok"
        # For T3/T4, P1 only peeks first nested max_connections — under-spec
        v = _get(art, "services", ctr=ctr)
        ctr.tick(1)
        if not isinstance(v, list) or not v:
            return True, "P1 missing services"
        mc = _get(v[0], "limits", "max_connections", ctr=ctr)
        ctr.tick(1)
        if mc != 10:
            return True, f"P1 services[0].max_connections={mc}"
        return False, "P1 nested peek ok"

    # P2: all top-level scalars (+ shallow list length)
    if level_p == "P2":
        if level_t in ("T1", "T2"):
            expect = {"max_connections": 10}
            if level_t == "T2":
                expect.update({"timeout_ms": 5000, "retries": 3})
            for k, exp in expect.items():
                got = _get(art, k, ctr=ctr)
                ctr.tick(1)
                if got != exp:
                    return True, f"P2 {k}={got} want {exp}"
            return False, "P2 ok"
        # T3/T4: check ports + names only (not nested limits, not cross)
        services = _get(art, "services", ctr=ctr)
        ctr.tick(1)
        if not isinstance(services, list) or len(services) != 2:
            return True, "P2 services length"
        expect_ports = [8080, 8081]
        expect_names = ["api", "worker"]
        for i, svc in enumerate(services):
            ctr.tick(2)
            if _get(svc, "port", ctr=ctr) != expect_ports[i]:
                return True, f"P2 port[{i}]"
            if _get(svc, "name", ctr=ctr) != expect_names[i]:
                return True, f"P2 name[{i}]"
        return False, "P2 shallow ok"

    # P3: walk all nested leaves against schema (no cross-field)
    if level_p == "P3":
        if level_t in ("T1", "T2"):
            # over-spec vs T1/T2: still check the scalars thoroughly
            return probe("P2", level_t, art, ctr)
        services = _get(art, "services", ctr=ctr)
        ctr.tick(1)
        if not isinstance(services, list) or len(services) != 2:
            return True, "P3 services"
        expect = [
            ("api", 8080, 10, 5000),
            ("worker", 8081, 20, 3000),
        ]
        for i, (name, port, mc, to) in enumerate(expect):
            svc = services[i]
            ctr.tick(4)
            if _get(svc, "name", ctr=ctr) != name:
                return True, f"P3 name[{i}]"
            if _get(svc, "port", ctr=ctr) != port:
                return True, f"P3 port[{i}]"
            if _get(svc, "limits", "max_connections", ctr=ctr) != mc:
                return True, f"P3 max_conn[{i}]"
            if _get(svc, "limits", "timeout_ms", ctr=ctr) != to:
                return True, f"P3 timeout[{i}]"
        return False, "P3 leaves ok"

    # P4: P3 + cross-field + fingerprint recompute
    # For T1–T3, still run leaf checks then any cross rules that exist on art
    reject, reason = probe("P3", level_t if level_t != "T4" else "T3", art, ctr)
    if reject:
        return True, f"P4viaP3:{reason}"

    if level_t == "T4" or "budget" in art or "fingerprint" in art:
        services = art.get("services") or []
        ctr.tick(len(services) + 2)
        total = 0
        ports = []
        names = []
        for svc in services:
            ctr.tick(3)
            lim = svc.get("limits") or {}
            total += int(lim.get("max_connections") or 0)
            ports.append(svc.get("port"))
            names.append(svc.get("name"))
        budget = art.get("budget")
        if budget is not None:
            ctr.tick(1)
            if total > budget:
                return True, f"P4 budget {total}>{budget}"
        ctr.tick(1)
        if len(ports) != len(set(ports)):
            return True, "P4 port clash"
        if "fingerprint" in art:
            ctr.tick(5)  # hash work
            want = _fp([n for n in names if n])
            if art.get("fingerprint") != want:
                return True, "P4 fingerprint"
    else:
        # over-spec on T1–T3 without cross fields: pay extra hash of dump
        ctr.tick(8)
        _ = hashlib.sha256(json.dumps(art, sort_keys=True).encode()).hexdigest()

    return False, "P4 ok"


def task_ops(level_t: str, art: dict) -> int:
    """Proxy for 'task itself' cost: schema leaves + artifact size."""
    leaves = int(SCHEMA[level_t]["leaves"])
    cross = int(SCHEMA[level_t]["cross"])
    size = len(json.dumps(art, ensure_ascii=False))
    # Normalize chars into ops-ish units so ratio is dimensionless-ish
    return leaves * 10 + cross * 20 + max(size // 20, 1)


# ── Cell runner ─────────────────────────────────────────────────────────────


def run_cell(
    level_t: str,
    level_p: str,
    n: int,
    rng: random.Random,
) -> dict:
    bad_caught = 0
    good_rejected = 0
    probe_ops_bad: list[int] = []
    probe_ops_good: list[int] = []
    task_ops_list: list[int] = []
    miss_kinds: dict[str, int] = {}

    for _ in range(n):
        art, kind = make_bad(level_t, rng)
        ctr = Counter()
        reject, _reason = probe(level_p, level_t, art, ctr)
        probe_ops_bad.append(ctr.ops)
        task_ops_list.append(task_ops(level_t, art))
        if reject:
            bad_caught += 1
        else:
            miss_kinds[kind] = miss_kinds.get(kind, 0) + 1

    for _ in range(n):
        art = make_good(level_t, rng)
        ctr = Counter()
        reject, _reason = probe(level_p, level_t, art, ctr)
        probe_ops_good.append(ctr.ops)
        if reject:
            good_rejected += 1

    mean_probe = sum(probe_ops_bad + probe_ops_good) / (2 * n)
    mean_task = sum(task_ops_list) / n
    return {
        "T": level_t,
        "P": level_p,
        "relation": _relation(level_t, level_p),
        "n_bad": n,
        "n_good": n,
        "catch_rate": bad_caught / n,
        "false_reject_rate": good_rejected / n,
        "mean_probe_ops": round(mean_probe, 2),
        "mean_task_ops": round(mean_task, 2),
        "cost_ratio": round(mean_probe / max(mean_task, 1e-9), 4),
        "miss_kinds": miss_kinds,
        "schema": {
            "depth": SCHEMA[level_t]["depth"],
            "leaves": SCHEMA[level_t]["leaves"],
            "cross": SCHEMA[level_t]["cross"],
        },
    }


def _relation(level_t: str, level_p: str) -> str:
    m = MATCHED[level_t]
    if level_p == m:
        return "matched"
    if PROBE_RANK[level_p] < PROBE_RANK[m]:
        return "under_spec"
    return "over_spec"


# ── Claims ──────────────────────────────────────────────────────────────────


def evaluate_claims(grid: list[dict]) -> dict:
    by = {(c["T"], c["P"]): c for c in grid}
    matched = [by[(t, MATCHED[t])] for t in LEVELS]
    under = [c for c in grid if c["relation"] == "under_spec"]
    over = [c for c in grid if c["relation"] == "over_spec"]

    c1_ok = all(c["catch_rate"] >= 0.95 for c in matched)
    c2_ok = (sum(c["catch_rate"] for c in under) / len(under)) < 0.80 if under else False
    mean_p1 = sum(by[(t, "P1")]["cost_ratio"] for t in LEVELS) / 4
    mean_p4 = sum(by[(t, "P4")]["cost_ratio"] for t in LEVELS) / 4
    c3_ok = mean_p4 > mean_p1

    threshold_t = None
    for t in LEVELS:
        if by[(t, MATCHED[t])]["cost_ratio"] >= 1.0:
            threshold_t = t
            break

    c5_details = []
    c5_ok = True
    for t in LEVELS:
        m = by[(t, MATCHED[t])]
        overs = [c for c in over if c["T"] == t]
        if not overs:
            continue
        # pick deepest over-spec
        o = max(overs, key=lambda x: PROBE_RANK[x["P"]])
        catch_close = abs(o["catch_rate"] - m["catch_rate"]) <= 0.05
        cost_higher = o["cost_ratio"] > m["cost_ratio"]
        cell_ok = catch_close and cost_higher
        c5_ok = c5_ok and cell_ok
        c5_details.append(
            {
                "T": t,
                "matched_P": m["P"],
                "over_P": o["P"],
                "catch_matched": m["catch_rate"],
                "catch_over": o["catch_rate"],
                "cost_matched": m["cost_ratio"],
                "cost_over": o["cost_ratio"],
                "ok": cell_ok,
            }
        )

    matched_catch = {c["T"]: c["catch_rate"] for c in matched}
    matched_cost = {c["T"]: c["cost_ratio"] for c in matched}

    return {
        "C1_matched_catch_stable": {
            "pass": c1_ok,
            "threshold": 0.95,
            "matched_catch": matched_catch,
            "detail": "each matched (Ti,Pi) catch_rate >= 0.95",
        },
        "C2_under_spec_drops_catch": {
            "pass": c2_ok,
            "mean_under_catch": round(sum(c["catch_rate"] for c in under) / len(under), 4)
            if under
            else None,
            "detail": "mean under-spec catch < 0.80",
        },
        "C3_deeper_probe_costs_more": {
            "pass": c3_ok,
            "mean_cost_ratio_P1": round(mean_p1, 4),
            "mean_cost_ratio_P4": round(mean_p4, 4),
            "detail": "mean cost_ratio(P4) > mean cost_ratio(P1)",
        },
        "C4_relative_cost_threshold": {
            "pass": True,  # measurement, not falsifier
            "first_matched_cost_ratio_ge_1": threshold_t,
            "matched_cost_ratio": matched_cost,
            "detail": "first matched Ti where probe_ops >= task_ops (ratio>=1)",
        },
        "C5_over_spec_waste": {
            "pass": c5_ok,
            "cells": c5_details,
            "detail": "over-spec keeps catch ≈ matched but raises cost_ratio",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="bad/good samples per cell")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    grid: list[dict] = []
    for t in LEVELS:
        for p in PROBES:
            grid.append(run_cell(t, p, args.n, rng))

    claims = evaluate_claims(grid)

    # Compact matrices for humans
    catch_matrix = {t: {} for t in LEVELS}
    cost_matrix = {t: {} for t in LEVELS}
    for c in grid:
        catch_matrix[c["T"]][c["P"]] = c["catch_rate"]
        cost_matrix[c["T"]][c["P"]] = c["cost_ratio"]

    out = {
        "question": (
            "Does out-of-channel probe catch rate stay stable as task complexity "
            "increases? Is there a threshold where structural invariants become "
            "too expensive relative to the task?"
        ),
        "source": "Xiao Man comment on Part 7 (2026-07-23)",
        "n_per_cell": args.n,
        "seed": args.seed,
        "axes": {
            "T": {k: {"depth": v["depth"], "leaves": v["leaves"], "cross": v["cross"]} for k, v in SCHEMA.items()},
            "P": {
                "P1": "single scalar / first nested peek",
                "P2": "all top-level / shallow ports+names",
                "P3": "full nested leaf walk",
                "P4": "P3 + cross-field + fingerprint",
            },
        },
        "catch_matrix": catch_matrix,
        "cost_ratio_matrix": cost_matrix,
        "grid": grid,
        "claims": claims,
        "answer_for_xiao_man": _answer_blurb(claims, catch_matrix, cost_matrix),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary
    print("══ probe-complexity dual-axis ══")
    print(f"n={args.n} seed={args.seed} → {OUT}")
    print("\nCatch matrix (rows=T, cols=P):")
    print(f"{'':4} " + " ".join(f"{p:>6}" for p in PROBES))
    for t in LEVELS:
        row = " ".join(f"{catch_matrix[t][p]:6.2f}" for p in PROBES)
        print(f"{t:4} {row}")
    print("\nCost-ratio matrix:")
    print(f"{'':4} " + " ".join(f"{p:>6}" for p in PROBES))
    for t in LEVELS:
        row = " ".join(f"{cost_matrix[t][p]:6.2f}" for p in PROBES)
        print(f"{t:4} {row}")
    print("\nClaims:")
    for k, v in claims.items():
        flag = "PASS" if v["pass"] else "FAIL"
        print(f"  [{flag}] {k}: {v.get('detail')}")
    thr = claims["C4_relative_cost_threshold"]["first_matched_cost_ratio_ge_1"]
    print(f"\nC4 threshold (matched cost_ratio>=1): {thr}")
    print("\nAnswer blurb:")
    print(out["answer_for_xiao_man"])
    return 0


def _answer_blurb(claims: dict, catch_m: dict, cost_m: dict) -> str:
    matched_catch = [catch_m[t][MATCHED[t]] for t in LEVELS]
    matched_cost = [cost_m[t][MATCHED[t]] for t in LEVELS]
    thr = claims["C4_relative_cost_threshold"]["first_matched_cost_ratio_ge_1"]
    parts = []
    if claims["C1_matched_catch_stable"]["pass"]:
        parts.append(
            f"On matched probes, catch stayed high across T1–T4 "
            f"({', '.join(f'{x:.0%}' for x in matched_catch)})."
        )
    else:
        parts.append(
            f"Matched catch did NOT stay stable "
            f"({', '.join(f'{x:.0%}' for x in matched_catch)})."
        )
    if claims["C2_under_spec_drops_catch"]["pass"]:
        parts.append(
            "Under-specified probes lost catch — depth must track the schema, "
            "not just 'have a checksum'."
        )
    if thr:
        parts.append(
            f"Relative-cost threshold: matched cost_ratio first crosses ≥1 at {thr} "
            f"(matched ratios={', '.join(f'{x:.2f}' for x in matched_cost)})."
        )
    else:
        parts.append(
            f"No matched cell hit cost_ratio≥1 "
            f"(ratios={', '.join(f'{x:.2f}' for x in matched_cost)}); "
            "threshold not crossed under this cost model."
        )
    parts.append(
        "Caveat: fixture demonstration with instrumented ops, not production timings; "
        "structural half of novelty bar only."
    )
    return " ".join(parts)


if __name__ == "__main__":
    sys.exit(main())
