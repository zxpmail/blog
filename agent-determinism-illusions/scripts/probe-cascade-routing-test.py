# -*- coding: utf-8 -*-
"""Cascade / adaptive P-depth routing experiment — Xiao Man follow-up on Part 7.

Question (Xiao Man, 2026-07-26, Part 7 thread):
  In your setup, is the P-level fixed per task type, or do you escalate
  dynamically based on artifact characteristics? Wondering if there's a cheap
  pre-check that routes to P3/P4 only when P1/P2 signal potential cross-field
  issues.

Predecessor: probe-complexity-dual-axis.py showed under-spec catch cliff
  (T4: P1 23% → P2 30% → P3 70% → P4 100%) and over-spec = waste not safety.
  That grid always ran a *fixed* (T,P) cell. This script asks whether a
  fail-driven cascade can recover catch without paying matched depth up front.

Design (offline, no API — same checksum-style domain as dual-axis):
  Reuse T1–T4 schemas + P1–P4 probes (inlined; one-script-per-claim).
  Three policies on the same artifact stream:

  A  fixed_matched   — know Ti, run Pi once (baseline from dual-axis)
  B  fail_escalate   — P1 pre-check; PASS → accept; FAIL → jump to matched Pi
                       (Xiao Man's "cheap pre-check routes deeper only on signal")
  C  schema_cap      — start P1; even on PASS, continue up to matched Pi
                       (cascade bounded by schema depth, not by failure signal)

Metrics per (T, policy):
  catch_rate, false_reject_rate, mean_probe_ops, cost_ratio,
  mean_stop_rank (how deep the policy ran), cross_miss (T4 cross-field misses)

Claims:
  C1  B under-catches on T4 vs A: catch(B,T4) < catch(A,T4) - 0.15
      (fail-signal routing misses cross-field population shallow probes never see)
  C2  C recovers catch: catch(C,T4) >= 0.95  (same bar as matched)
  C3  B mean_probe_ops < A on T4  (B is cheaper — the trap looks attractive)
  C4  C catch ≈ A catch on every Ti (|Δ| <= 0.05); C cost between shallow and always-P4

Falsifiers:
  C1 fail → fail_escalate somehow catches cross-field without shallow signal
            (would revise the "don't escalate only on fail" answer).
  C2 fail → schema_cap cascade broken / probe composition bug.
  C3 fail → B not even cheaper → no cost temptation to discuss.

Run:
  python probe-cascade-routing-test.py
  python probe-cascade-routing-test.py --n 40 --seed 7
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import random
import sys
from pathlib import Path
from typing import Any

# Windows UTF-8 stdout (script prints Chinese in summary path; keep contract)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "probe-cascade-routing.json"

# ── Schema / probe (inlined from probe-complexity-dual-axis.py) ─────────────

SCHEMA = {
    "T1": {
        "depth": 1,
        "leaves": 1,
        "cross": 0,
        "template": lambda rng: {"max_connections": 10},
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
    },
    "T3": {
        "depth": 2,
        "leaves": 8,
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
    },
    "T4": {
        "depth": 3,
        "leaves": 10,
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
    },
}

LEVELS = ["T1", "T2", "T3", "T4"]
PROBES = ["P1", "P2", "P3", "P4"]
MATCHED = {"T1": "P1", "T2": "P2", "T3": "P3", "T4": "P4"}
PROBE_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
RANK_PROBE = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
CROSS_KINDS = frozenset({"cross_budget", "cross_port_unique", "cross_fingerprint"})
POLICIES = ("fixed_matched", "fail_escalate", "schema_cap")


def _fp(names: list[str]) -> str:
    raw = "|".join(sorted(names)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def make_good(level: str, rng: random.Random) -> dict:
    art = copy.deepcopy(SCHEMA[level]["template"](rng))
    art["_meta"] = {"seed": rng.randint(0, 10_000), "ok": True}
    return art


def make_bad(level: str, rng: random.Random) -> tuple[dict, str]:
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
    """Return (reject, reason). reject=True → artifact fails check."""
    if level_p == "P1":
        ctr.tick(1)
        if level_t in ("T1", "T2"):
            v = _get(art, "max_connections", ctr=ctr)
            ctr.tick(1)
            if v != 10:
                return True, f"P1 max_connections={v}"
            return False, "P1 ok"
        v = _get(art, "services", ctr=ctr)
        ctr.tick(1)
        if not isinstance(v, list) or not v:
            return True, "P1 missing services"
        mc = _get(v[0], "limits", "max_connections", ctr=ctr)
        ctr.tick(1)
        if mc != 10:
            return True, f"P1 services[0].max_connections={mc}"
        return False, "P1 nested peek ok"

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

    if level_p == "P3":
        if level_t in ("T1", "T2"):
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

    # P4
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
            ctr.tick(5)
            want = _fp([n for n in names if n])
            if art.get("fingerprint") != want:
                return True, "P4 fingerprint"
    else:
        ctr.tick(8)
        _ = hashlib.sha256(json.dumps(art, sort_keys=True).encode()).hexdigest()

    return False, "P4 ok"


def task_ops(level_t: str, art: dict) -> int:
    leaves = int(SCHEMA[level_t]["leaves"])
    cross = int(SCHEMA[level_t]["cross"])
    size = len(json.dumps(art, ensure_ascii=False))
    return leaves * 10 + cross * 20 + max(size // 20, 1)


# ── Policies ────────────────────────────────────────────────────────────────


def run_policy(
    policy: str,
    level_t: str,
    art: dict,
    ctr: Counter,
) -> tuple[bool, str, int]:
    """
    Return (reject, stop_P, stop_rank).
    reject=True means artifact fails (escalate / block).
    """
    matched = MATCHED[level_t]
    matched_rank = PROBE_RANK[matched]

    if policy == "fixed_matched":
        reject, _ = probe(matched, level_t, art, ctr)
        return reject, matched, matched_rank

    if policy == "fail_escalate":
        # Cheap P1 pre-check. No signal (PASS) → accept.
        # Signal (FAIL) → authoritative matched Pi (not step-by-step deepen:
        # an intermediate under-spec Pj must not clear a P1 fail).
        # Trap: cross-field bugs often PASS P1, so deep probe never runs.
        reject1, _ = probe("P1", level_t, art, ctr)
        if not reject1:
            return False, "P1", 1
        reject, _ = probe(matched, level_t, art, ctr)
        return reject, matched, matched_rank

    if policy == "schema_cap":
        # Even on PASS, continue up to matched Pi. Never past schema match.
        last_p = matched
        for rank in range(1, matched_rank + 1):
            p = RANK_PROBE[rank]
            last_p = p
            reject, _ = probe(p, level_t, art, ctr)
            if reject:
                return True, p, rank
        return False, last_p, matched_rank

    raise ValueError(f"unknown policy: {policy}")


def evaluate_claims(cells: list[dict]) -> dict:
    by = {(c["T"], c["policy"]): c for c in cells}
    a_t4 = by[("T4", "fixed_matched")]
    b_t4 = by[("T4", "fail_escalate")]
    c_t4 = by[("T4", "schema_cap")]

    c1_ok = b_t4["catch_rate"] < (a_t4["catch_rate"] - 0.15)
    c2_ok = c_t4["catch_rate"] >= 0.95
    c3_ok = b_t4["mean_probe_ops"] < a_t4["mean_probe_ops"]

    c4_details = []
    c4_ok = True
    for t in LEVELS:
        a = by[(t, "fixed_matched")]
        c = by[(t, "schema_cap")]
        catch_close = abs(c["catch_rate"] - a["catch_rate"]) <= 0.05
        # schema_cap reruns shallow prefixes → cost >= fixed on same Ti
        cost_ge = c["mean_probe_ops"] >= a["mean_probe_ops"] * 0.95
        cell_ok = catch_close and cost_ge
        c4_ok = c4_ok and cell_ok
        c4_details.append(
            {
                "T": t,
                "catch_A": a["catch_rate"],
                "catch_C": c["catch_rate"],
                "ops_A": a["mean_probe_ops"],
                "ops_C": c["mean_probe_ops"],
                "ok": cell_ok,
            }
        )

    return {
        "C1_fail_escalate_undercatches_T4": {
            "pass": c1_ok,
            "catch_A_T4": a_t4["catch_rate"],
            "catch_B_T4": b_t4["catch_rate"],
            "cross_miss_B_T4": b_t4["cross_field_miss"],
            "cross_total_B_T4": b_t4["cross_field_total"],
            "detail": "fail_escalate catch on T4 < fixed_matched - 0.15",
        },
        "C2_schema_cap_recovers_catch": {
            "pass": c2_ok,
            "catch_C_T4": c_t4["catch_rate"],
            "detail": "schema_cap catch on T4 >= 0.95",
        },
        "C3_fail_escalate_looks_cheaper": {
            "pass": c3_ok,
            "ops_A_T4": a_t4["mean_probe_ops"],
            "ops_B_T4": b_t4["mean_probe_ops"],
            "detail": "fail_escalate mean_probe_ops < fixed_matched on T4",
        },
        "C4_schema_cap_matches_fixed_catch": {
            "pass": c4_ok,
            "cells": c4_details,
            "detail": "schema_cap catch ≈ fixed_matched on every Ti; cost ≥ fixed",
        },
    }


def _answer_blurb(claims: dict, by: dict) -> str:
    a = by[("T4", "fixed_matched")]
    b = by[("T4", "fail_escalate")]
    c = by[("T4", "schema_cap")]
    parts = []
    parts.append(
        f"On T4, fixed_matched catch={a['catch_rate']:.0%}, "
        f"fail_escalate={b['catch_rate']:.0%} "
        f"(cross-field miss {b['cross_field_miss']}/{b['cross_field_total']}), "
        f"schema_cap={c['catch_rate']:.0%}."
    )
    if claims["C1_fail_escalate_undercatches_T4"]["pass"]:
        parts.append(
            "Cheap pre-check that deepens only on P1/P2 fail misses the "
            "cross-field population — those artifacts pass shallow probes, "
            "so the cascade never fires."
        )
    if claims["C2_schema_cap_recovers_catch"]["pass"] and claims[
        "C4_schema_cap_matches_fixed_catch"
    ]["pass"]:
        parts.append(
            "Cascade is fine if the ceiling is schema-matched depth "
            "(continue on pass up to Pi), not failure-signal-driven."
        )
    if claims["C3_fail_escalate_looks_cheaper"]["pass"]:
        parts.append(
            f"fail_escalate looks cheaper ({b['mean_probe_ops']:.1f} vs "
            f"{a['mean_probe_ops']:.1f} ops) — that is the trap, not the win."
        )
    parts.append(
        "Answer: P-level is fixed by task/schema type in this setup; "
        "dynamic deepen-on-fail is not a substitute for matched depth. "
        "Fixture + instrumented ops, same caveats as dual-axis."
    )
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="bad/good samples per (T, policy)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    # Shared artifact streams so A/B/C compare on identical samples per Ti
    cells: list[dict] = []
    for t in LEVELS:
        shared_bad: list[tuple[dict, str]] = []
        shared_good: list[dict] = []
        rng = random.Random(args.seed * 17 + LEVELS.index(t))
        for _ in range(args.n):
            shared_bad.append(make_bad(t, rng))
        for _ in range(args.n):
            shared_good.append(make_good(t, rng))

        for policy in POLICIES:
            bad_caught = 0
            good_rejected = 0
            probe_ops_all: list[int] = []
            task_ops_list: list[int] = []
            stop_ranks: list[int] = []
            miss_kinds: dict[str, int] = {}
            cross_miss = 0
            cross_total = 0
            for art, kind in shared_bad:
                ctr = Counter()
                reject, _, stop_rank = run_policy(policy, t, art, ctr)
                probe_ops_all.append(ctr.ops)
                task_ops_list.append(task_ops(t, art))
                stop_ranks.append(stop_rank)
                if kind in CROSS_KINDS:
                    cross_total += 1
                if reject:
                    bad_caught += 1
                else:
                    miss_kinds[kind] = miss_kinds.get(kind, 0) + 1
                    if kind in CROSS_KINDS:
                        cross_miss += 1
            for art in shared_good:
                ctr = Counter()
                reject, _, stop_rank = run_policy(policy, t, art, ctr)
                probe_ops_all.append(ctr.ops)
                stop_ranks.append(stop_rank)
                if reject:
                    good_rejected += 1
            mean_probe = sum(probe_ops_all) / (2 * args.n)
            mean_task = sum(task_ops_list) / args.n
            cells.append(
                {
                    "T": t,
                    "policy": policy,
                    "n_bad": args.n,
                    "n_good": args.n,
                    "catch_rate": bad_caught / args.n,
                    "false_reject_rate": good_rejected / args.n,
                    "mean_probe_ops": round(mean_probe, 2),
                    "mean_task_ops": round(mean_task, 2),
                    "cost_ratio": round(mean_probe / max(mean_task, 1e-9), 4),
                    "mean_stop_rank": round(sum(stop_ranks) / len(stop_ranks), 3),
                    "miss_kinds": miss_kinds,
                    "cross_field_total": cross_total,
                    "cross_field_miss": cross_miss,
                    "cross_field_miss_rate": round(cross_miss / cross_total, 4)
                    if cross_total
                    else None,
                    "matched_P": MATCHED[t],
                    "paired": True,
                }
            )

    claims = evaluate_claims(cells)
    by = {(c["T"], c["policy"]): c for c in cells}

    catch_table = {t: {} for t in LEVELS}
    cost_table = {t: {} for t in LEVELS}
    stop_table = {t: {} for t in LEVELS}
    for c in cells:
        catch_table[c["T"]][c["policy"]] = c["catch_rate"]
        cost_table[c["T"]][c["policy"]] = c["cost_ratio"]
        stop_table[c["T"]][c["policy"]] = c["mean_stop_rank"]

    out = {
        "question": (
            "Is P-level fixed per task type, or escalate dynamically? "
            "Can a cheap P1/P2 pre-check route to P3/P4 only when shallow "
            "probes signal potential cross-field issues?"
        ),
        "source": "Xiao Man comment on Part 7 (2026-07-26)",
        "predecessor": "probe-complexity-dual-axis.py",
        "n_per_cell": args.n,
        "seed": args.seed,
        "policies": {
            "fixed_matched": "know Ti → run matched Pi once",
            "fail_escalate": "P1 pre-check; PASS→accept; FAIL→jump to matched Pi",
            "schema_cap": "P1→… continue on PASS up to matched Pi",
        },
        "catch_table": catch_table,
        "cost_ratio_table": cost_table,
        "mean_stop_rank_table": stop_table,
        "cells": cells,
        "claims": claims,
        "answer_for_xiao_man": _answer_blurb(claims, by),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("══ probe-cascade-routing ══")
    print(f"n={args.n} seed={args.seed} → {OUT}")
    print("\nCatch (rows=T, cols=policy):")
    hdr = " ".join(f"{p:>16}" for p in POLICIES)
    print(f"{'':4} {hdr}")
    for t in LEVELS:
        row = " ".join(f"{catch_table[t][p]:16.2f}" for p in POLICIES)
        print(f"{t:4} {row}")
    print("\nCost-ratio:")
    print(f"{'':4} {hdr}")
    for t in LEVELS:
        row = " ".join(f"{cost_table[t][p]:16.4f}" for p in POLICIES)
        print(f"{t:4} {row}")
    print("\nMean stop rank (1=P1 … 4=P4):")
    print(f"{'':4} {hdr}")
    for t in LEVELS:
        row = " ".join(f"{stop_table[t][p]:16.2f}" for p in POLICIES)
        print(f"{t:4} {row}")

    b4 = by[("T4", "fail_escalate")]
    print(
        f"\nT4 fail_escalate cross-field miss: "
        f"{b4['cross_field_miss']}/{b4['cross_field_total']}"
    )
    print("\nClaims:")
    for k, v in claims.items():
        flag = "PASS" if v["pass"] else "FAIL"
        print(f"  [{flag}] {k}: {v.get('detail')}")
    print("\nAnswer blurb:")
    print(out["answer_for_xiao_man"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
