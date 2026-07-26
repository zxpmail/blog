# -*- coding: utf-8 -*-
"""Artifact-shape P-depth routing experiment — Xiao Man Part 7 follow-up.

Question (Xiao Man, 2026-07-26, Part 7 thread):
  …is the P-level fixed per task type, or do you escalate dynamically based
  on artifact characteristics?

Predecessor:
  probe-cascade-routing-test.py showed fail-signal routing under-catches.
  This script asks the other fork: route by *artifact shape* (fields / nesting)
  without a task-type label Ti.

Design (offline, no API — same checksum domain as dual-axis):
  Infer (T_hat, P_hat) from artifact keys only:

    budget key present         → (T4, P4)   # sole T4 routing cue
    services list              → (T3, P3)
    timeout_ms|retries         → (T2, P2)
    else                       → (T1, P1)

  Fingerprint is a P4 *payload* check, not a routing cue — so cue erasure
  can strip budget while leaving a wrong fingerprint as residual evidence
  that only T4/P4 looks at (P3 leaf walk will miss it).

  Policies:
    A  fixed_matched  — true Ti → matched Pi (oracle task label)
    B  artifact_shape — (T_hat, P_hat) from artifact only

  Populations (paired A/B on identical artifacts):
    normal     — unmodified T1–T4 good/bad
    cue_erase  — T4; strip budget cue; force wrong fingerprint residual
    decoy_nest — T2 bad/good; inject decorative services[] → shape thinks T3

Claims:
  C1  Normal: shape catch ≈ fixed on every Ti (|Δ| <= 0.05)
      → shape is a viable *proxy for schema* when cues stay honest
  C2  Cue-erase: shape catch on T4 < fixed - 0.15
      → deleting depth cues under-specs the router (blind spot)
  C3  Decoy: shape mean_probe_ops > fixed on T2, AND shape catch < fixed - 0.15
      → decoy nesting is not just waste; it can misroute and miss

Falsifiers:
  C1 fail → even honest shapes don't track schema (inference rule wrong)
  C2 fail → cue erasure doesn't hurt shape (router has other signals)
  C3 fail → decoys only cost extra without catch loss on this fixture

Run:
  python probe-artifact-shape-routing-test.py
  python probe-artifact-shape-routing-test.py --n 40 --seed 7
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "probe-artifact-shape-routing.json"

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
MATCHED = {"T1": "P1", "T2": "P2", "T3": "P3", "T4": "P4"}
PROBE_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
POLICIES = ("fixed_matched", "artifact_shape")
DECOY_SERVICES = [
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
    else:
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


def infer_route(art: dict, ctr: Counter) -> tuple[str, str]:
    """Infer (T_hat, P_hat) from artifact shape only. Ticks cheap cue reads."""
    ctr.tick(1)  # budget cue
    if "budget" in art:
        return "T4", "P4"
    ctr.tick(1)
    if isinstance(art.get("services"), list):
        return "T3", "P3"
    ctr.tick(1)
    if "timeout_ms" in art or "retries" in art:
        return "T2", "P2"
    return "T1", "P1"


def apply_cue_erase(art: dict) -> dict:
    """Strip T4 routing cue (budget); force fingerprint residual for P4-only catch."""
    out = copy.deepcopy(art)
    out.pop("budget", None)
    out["fingerprint"] = "deadbeefdeadbeef"
    out["_mutate"] = "cue_erase"
    return out


def apply_decoy_nest(art: dict) -> dict:
    """Inject T3-shaped services so shape router overshoots to P3."""
    out = copy.deepcopy(art)
    out["services"] = copy.deepcopy(DECOY_SERVICES)
    out["_mutate"] = "decoy_nest"
    return out


def run_policy(
    policy: str,
    true_t: str,
    art: dict,
    ctr: Counter,
) -> tuple[bool, str, str, int]:
    """Return (reject, used_T, used_P, stop_rank)."""
    if policy == "fixed_matched":
        p = MATCHED[true_t]
        reject, _ = probe(p, true_t, art, ctr)
        return reject, true_t, p, PROBE_RANK[p]

    if policy == "artifact_shape":
        t_hat, p_hat = infer_route(art, ctr)
        reject, _ = probe(p_hat, t_hat, art, ctr)
        return reject, t_hat, p_hat, PROBE_RANK[p_hat]

    raise ValueError(policy)


def eval_population(
    name: str,
    items_bad: list[tuple[dict, str, str]],
    items_good: list[tuple[dict, str]],
) -> list[dict]:
    """items_bad: (art, kind, true_t); items_good: (art, true_t)."""
    cells = []
    for policy in POLICIES:
        bad_caught = 0
        good_rejected = 0
        probe_ops: list[int] = []
        task_ops_list: list[int] = []
        miss_kinds: dict[str, int] = {}
        route_hist: dict[str, int] = {}
        n_bad = len(items_bad)
        n_good = len(items_good)

        for art, kind, true_t in items_bad:
            ctr = Counter()
            reject, used_t, used_p, _rank = run_policy(policy, true_t, art, ctr)
            probe_ops.append(ctr.ops)
            task_ops_list.append(task_ops(true_t, art))
            route_hist[f"{used_t}/{used_p}"] = route_hist.get(f"{used_t}/{used_p}", 0) + 1
            if reject:
                bad_caught += 1
            else:
                miss_kinds[kind] = miss_kinds.get(kind, 0) + 1

        for art, true_t in items_good:
            ctr = Counter()
            reject, used_t, used_p, _rank = run_policy(policy, true_t, art, ctr)
            probe_ops.append(ctr.ops)
            route_hist[f"{used_t}/{used_p}"] = route_hist.get(f"{used_t}/{used_p}", 0) + 1
            if reject:
                good_rejected += 1

        mean_probe = sum(probe_ops) / max(len(probe_ops), 1)
        mean_task = sum(task_ops_list) / max(len(task_ops_list), 1) if task_ops_list else 0
        cells.append(
            {
                "population": name,
                "policy": policy,
                "n_bad": n_bad,
                "n_good": n_good,
                "catch_rate": bad_caught / n_bad if n_bad else None,
                "false_reject_rate": good_rejected / n_good if n_good else None,
                "mean_probe_ops": round(mean_probe, 2),
                "mean_task_ops": round(mean_task, 2),
                "cost_ratio": round(mean_probe / max(mean_task, 1e-9), 4) if task_ops_list else None,
                "miss_kinds": miss_kinds,
                "route_histogram": route_hist,
            }
        )
    return cells


def evaluate_claims(cells: list[dict], normal_by_t: dict) -> dict:
    by = {(c["population"], c["policy"]): c for c in cells}

    # C1: normal per-Ti catch close — use normal_by_t cells
    c1_details = []
    c1_ok = True
    for t in LEVELS:
        a = normal_by_t[(t, "fixed_matched")]
        b = normal_by_t[(t, "artifact_shape")]
        close = abs(a["catch_rate"] - b["catch_rate"]) <= 0.05
        c1_ok = c1_ok and close
        c1_details.append(
            {
                "T": t,
                "catch_fixed": a["catch_rate"],
                "catch_shape": b["catch_rate"],
                "ok": close,
            }
        )

    erase_a = by[("cue_erase", "fixed_matched")]
    erase_b = by[("cue_erase", "artifact_shape")]
    c2_ok = erase_b["catch_rate"] < (erase_a["catch_rate"] - 0.15)

    decoy_a = by[("decoy_nest", "fixed_matched")]
    decoy_b = by[("decoy_nest", "artifact_shape")]
    c3_cost = decoy_b["mean_probe_ops"] > decoy_a["mean_probe_ops"]
    c3_catch = decoy_b["catch_rate"] < (decoy_a["catch_rate"] - 0.15)
    c3_ok = c3_cost and c3_catch

    return {
        "C1_shape_matches_fixed_on_honest_cues": {
            "pass": c1_ok,
            "cells": c1_details,
            "detail": "normal population: |catch_shape - catch_fixed| <= 0.05 per Ti",
        },
        "C2_cue_erase_undercatches": {
            "pass": c2_ok,
            "catch_fixed": erase_a["catch_rate"],
            "catch_shape": erase_b["catch_rate"],
            "miss_kinds_shape": erase_b["miss_kinds"],
            "detail": "cue_erase: shape catch < fixed - 0.15",
        },
        "C3_decoy_misroutes": {
            "pass": c3_ok,
            "ops_fixed": decoy_a["mean_probe_ops"],
            "ops_shape": decoy_b["mean_probe_ops"],
            "catch_fixed": decoy_a["catch_rate"],
            "catch_shape": decoy_b["catch_rate"],
            "miss_kinds_shape": decoy_b["miss_kinds"],
            "detail": "decoy_nest on T2: shape costs more AND catch drops > 0.15",
        },
    }


def _answer_blurb(claims: dict, by: dict) -> str:
    parts = []
    if claims["C1_shape_matches_fixed_on_honest_cues"]["pass"]:
        parts.append(
            "When routing cues stay honest, artifact-shape routing matches "
            "fixed task-type depth on catch — shape is a schema proxy, not a "
            "failure-signal cascade."
        )
    else:
        parts.append("Even on honest artifacts, shape routing diverged from fixed.")

    e_f = by[("cue_erase", "fixed_matched")]["catch_rate"]
    e_s = by[("cue_erase", "artifact_shape")]["catch_rate"]
    parts.append(
        f"Cue erasure (strip budget cue, wrong fingerprint residual): "
        f"fixed={e_f:.0%} vs shape={e_s:.0%} — depth cues are load-bearing."
    )

    d_f = by[("decoy_nest", "fixed_matched")]["catch_rate"]
    d_s = by[("decoy_nest", "artifact_shape")]["catch_rate"]
    o_f = by[("decoy_nest", "fixed_matched")]["mean_probe_ops"]
    o_s = by[("decoy_nest", "artifact_shape")]["mean_probe_ops"]
    parts.append(
        f"Decoy nesting on T2: fixed catch={d_f:.0%} ({o_f:.1f} ops) vs "
        f"shape catch={d_s:.0%} ({o_s:.1f} ops) — misroute, not just waste."
    )
    parts.append(
        "Answer fork: artifact characteristics can set P-level *if they encode "
        "schema depth and are not agent-writable escape hatches*. That is still "
        "matched-depth routing, not 'cheap pre-check on P1/P2 fail'."
    )
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    cells: list[dict] = []
    normal_by_t: dict = {}

    # ── normal: per Ti, paired policies ──
    for t in LEVELS:
        rng = random.Random(args.seed * 17 + LEVELS.index(t))
        bad_items: list[tuple[dict, str, str]] = []
        good_items: list[tuple[dict, str]] = []
        for _ in range(args.n):
            art, kind = make_bad(t, rng)
            bad_items.append((art, kind, t))
        for _ in range(args.n):
            good_items.append((make_good(t, rng), t))

        pop_cells = eval_population(f"normal_{t}", bad_items, good_items)
        for c in pop_cells:
            normal_by_t[(t, c["policy"])] = c
            c["population"] = "normal"
            c["T"] = t
            cells.append(c)

    # ── cue_erase: T4 only ──
    rng = random.Random(args.seed * 31 + 4)
    bad_erase = []
    good_erase = []
    for _ in range(args.n):
        art, kind = make_bad("T4", rng)
        bad_erase.append((apply_cue_erase(art), f"{kind}+cue_erase", "T4"))
    for _ in range(args.n):
        good_erase.append((apply_cue_erase(make_good("T4", rng)), "T4"))
    cells.extend(eval_population("cue_erase", bad_erase, good_erase))

    # ── decoy_nest: T2 only ──
    rng = random.Random(args.seed * 43 + 2)
    bad_decoy = []
    good_decoy = []
    for _ in range(args.n):
        art, kind = make_bad("T2", rng)
        bad_decoy.append((apply_decoy_nest(art), f"{kind}+decoy", "T2"))
    for _ in range(args.n):
        good_decoy.append((apply_decoy_nest(make_good("T2", rng)), "T2"))
    cells.extend(eval_population("decoy_nest", bad_decoy, good_decoy))

    claims = evaluate_claims(cells, normal_by_t)
    by = {(c["population"], c["policy"]): c for c in cells}

    # Compact tables
    normal_catch = {t: {} for t in LEVELS}
    for t in LEVELS:
        for p in POLICIES:
            normal_catch[t][p] = normal_by_t[(t, p)]["catch_rate"]

    out = {
        "question": (
            "Can P-level be chosen from artifact characteristics (shape) "
            "instead of a fixed task-type label?"
        ),
        "source": "Xiao Man comment on Part 7 (2026-07-26) — artifact-characteristics fork",
        "predecessor": "probe-cascade-routing-test.py",
        "n_per_cell": args.n,
        "seed": args.seed,
        "shape_rule": {
            "T4/P4": "budget key present (fingerprint is payload, not cue)",
            "T3/P3": "services list present",
            "T2/P2": "timeout_ms or retries present",
            "T1/P1": "else",
        },
        "populations": {
            "normal": "unmodified T1–T4",
            "cue_erase": "T4; strip budget cue; force wrong fingerprint residual",
            "decoy_nest": "T2; inject decorative services[]",
        },
        "normal_catch_table": normal_catch,
        "cue_erase": {
            "fixed_matched": by[("cue_erase", "fixed_matched")],
            "artifact_shape": by[("cue_erase", "artifact_shape")],
        },
        "decoy_nest": {
            "fixed_matched": by[("decoy_nest", "fixed_matched")],
            "artifact_shape": by[("decoy_nest", "artifact_shape")],
        },
        "cells": cells,
        "claims": claims,
        "answer_for_xiao_man": _answer_blurb(claims, by),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("══ probe-artifact-shape-routing ══")
    print(f"n={args.n} seed={args.seed} → {OUT}")
    print("\nNormal catch (rows=T, cols=policy):")
    print(f"{'':4} " + " ".join(f"{p:>16}" for p in POLICIES))
    for t in LEVELS:
        row = " ".join(f"{normal_catch[t][p]:16.2f}" for p in POLICIES)
        print(f"{t:4} {row}")

    print("\nCue-erase (T4):")
    for p in POLICIES:
        c = by[("cue_erase", p)]
        print(
            f"  {p}: catch={c['catch_rate']:.2f} ops={c['mean_probe_ops']} "
            f"routes={c['route_histogram']} miss={c['miss_kinds']}"
        )

    print("\nDecoy-nest (T2):")
    for p in POLICIES:
        c = by[("decoy_nest", p)]
        print(
            f"  {p}: catch={c['catch_rate']:.2f} ops={c['mean_probe_ops']} "
            f"routes={c['route_histogram']} miss={c['miss_kinds']}"
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
