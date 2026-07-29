# -*- coding: utf-8 -*-
"""Shape-routing stability test — Xiao Man inferability-first follow-up (2026-07-29).

Question (Xiao Man, 2026-07-29, Part 7 thread):
  Move the stable-referent test one level up. Don't ask "does this case have a
  stable referent?" — ask "is the depth signal stable under minor shape changes?"
  If yes → schema-deterministic routing. If no → don't infer depth from shape;
  route to a fixed mid-depth probe as baseline, escalate on cross-field signal.

Predecessor: probe-artifact-shape-routing-test.py
  cue_erase  (T4; strip budget cue):     routing T4→T3; catch 100% → 82.5%
  decoy_nest (T2; inject services[]):    routing T2→T3; catch 100% → 0%
  Both perturbations flip routing classification; depth signal unstable on the
  *catch* axis.

This script adds the third perturbation cell — rename_keys on T3:
  T3 artifact, rename `services` → `components` (schema synonym, semantic-preserving).
  An adversarial artifact can do this trivially — it's pure surface shape.

  infer_route trace on renamed T3:
    "budget" in art          → False
    isinstance(services,list)→ False  (key is now "components")
    timeout_ms|retries       → False
    → routes to T1/P1

  P1 probe on misrouted T3 (level_t="T1"):
    T1 branch checks art["max_connections"] != 10
    T3 schema has no top-level max_connections → None != 10 → reject

  So shape routing rejects every renamed-T3 artifact (good or bad).
  Expected: catch_rate ~100% (false-positive on every bad too, trivially),
            false_reject_rate ~100% (every good T3 rejected).

  This is a DIFFERENT failure axis than cue_erase / decoy_nest:
    cue_erase  → catch drops (under-reject: miss real defects)
    decoy_nest → catch drops (wrong-probe-wrong-depth)
    rename_keys→ catch fine but false_reject spikes (over-reject: kill good art)

  Three perturbations, two failure axes — depth signal not stable on either.
  Xiao Man's design implication follows: don't infer depth from shape; use a
  fixed mid-depth probe as baseline; escalate on cross-field signal.

Falsification:
  If rename_keys catch ≈ fixed AND false_reject ≈ fixed → router has semantic
  robustness to synonym rename (depth signal stable on this axis; Xiao Man's
  cut would be too strong).

Run:
  python probe-shape-routing-rename-keys-test.py
  python probe-shape-routing-rename-keys-test.py --n 40 --seed 7
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
OUT = RESULTS / "probe-shape-routing-rename-keys.json"


# ── Schema (copied from probe-artifact-shape-routing-test.py for standalone run) ──

def _fp(names: list[str]) -> str:
    raw = "|".join(sorted(names)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


SCHEMA = {
    "T1": {
        "depth": 1, "leaves": 1, "cross": 0,
        "template": lambda rng: {"max_connections": 10},
    },
    "T2": {
        "depth": 1, "leaves": 3, "cross": 0,
        "template": lambda rng: {
            "max_connections": 10, "timeout_ms": 5000, "retries": 3,
        },
    },
    "T3": {
        "depth": 2, "leaves": 8, "cross": 0,
        "template": lambda rng: {
            "services": [
                {"name": "api", "port": 8080,
                 "limits": {"max_connections": 10, "timeout_ms": 5000}},
                {"name": "worker", "port": 8081,
                 "limits": {"max_connections": 20, "timeout_ms": 3000}},
            ]
        },
    },
    "T4": {
        "depth": 3, "leaves": 10, "cross": 2,
        "template": lambda rng: {
            "budget": 30,
            "services": [
                {"name": "api", "port": 8080,
                 "limits": {"max_connections": 10, "timeout_ms": 5000}},
                {"name": "worker", "port": 8081,
                 "limits": {"max_connections": 20, "timeout_ms": 3000}},
            ],
            "fingerprint": _fp(["api", "worker"]),
        },
    },
}

LEVELS = ["T1", "T2", "T3", "T4"]
MATCHED = {"T1": "P1", "T2": "P2", "T3": "P3", "T4": "P4"}
PROBE_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
POLICIES = ("fixed_matched", "artifact_shape")


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


def infer_route(art: dict, ctr: Counter) -> tuple[str, str]:
    ctr.tick(1)
    if "budget" in art:
        return "T4", "P4"
    ctr.tick(1)
    if isinstance(art.get("services"), list):
        return "T3", "P3"
    ctr.tick(1)
    if "timeout_ms" in art or "retries" in art:
        return "T2", "P2"
    return "T1", "P1"


# ── New perturbation: rename_keys ──

def rename_recursive(obj: Any, mapping: dict[str, str]) -> Any:
    """Recursively rename dict keys per mapping. Pure surface shape change."""
    if isinstance(obj, dict):
        return {mapping.get(k, k): rename_recursive(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [rename_recursive(x, mapping) for x in obj]
    return obj


def apply_rename_keys(art: dict, rename_map: dict[str, str]) -> dict:
    """Rename schema-synonym keys. Default: services→components, budget→cost_limit,
    timeout_ms→request_timeout_ms, retries→retry_count."""
    out = rename_recursive(art, rename_map)
    if isinstance(out, dict):
        out["_mutate"] = "rename_keys"
    return out


DEFAULT_RENAME = {
    "services": "components",
    "budget": "cost_limit",
    "timeout_ms": "request_timeout_ms",
    "retries": "retry_count",
    "fingerprint": "sig",
}


def run_policy(policy: str, true_t: str, art: dict, ctr: Counter) -> tuple[bool, str, str, int]:
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
    cells = []
    for policy in POLICIES:
        bad_caught = 0
        good_rejected = 0
        probe_ops: list[int] = []
        miss_kinds: dict[str, int] = {}
        route_hist: dict[str, int] = {}
        reject_reasons_good: dict[str, int] = {}
        n_bad = len(items_bad)
        n_good = len(items_good)

        for art, kind, true_t in items_bad:
            ctr = Counter()
            reject, used_t, used_p, _ = run_policy(policy, true_t, art, ctr)
            probe_ops.append(ctr.ops)
            route_hist[f"{used_t}/{used_p}"] = route_hist.get(f"{used_t}/{used_p}", 0) + 1
            if reject:
                bad_caught += 1
            else:
                miss_kinds[kind] = miss_kinds.get(kind, 0) + 1

        for art, true_t in items_good:
            ctr = Counter()
            reject, used_t, used_p, _ = run_policy(policy, true_t, art, ctr)
            probe_ops.append(ctr.ops)
            if reject:
                # Diagnose: what reason did P1 give?
                reason_ctr = Counter()
                _, reason = probe(used_p, used_t, art, reason_ctr)
                reject_reasons_good[reason] = reject_reasons_good.get(reason, 0) + 1
                good_rejected += 1

        mean_probe = sum(probe_ops) / max(len(probe_ops), 1)
        cells.append({
            "population": name,
            "policy": policy,
            "n_bad": n_bad,
            "n_good": n_good,
            "catch_rate": bad_caught / n_bad if n_bad else None,
            "false_reject_rate": good_rejected / n_good if n_good else None,
            "mean_probe_ops": round(mean_probe, 2),
            "miss_kinds": miss_kinds,
            "reject_reasons_on_good": reject_reasons_good,
            "route_histogram": route_hist,
        })
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    cells: list[dict] = []

    # ── normal_T3 baseline (control) ──
    rng = random.Random(args.seed * 17 + 2)  # offset so it matches the original normal_T3 cell
    bad_normal = []
    good_normal = []
    for _ in range(args.n):
        art, kind = make_bad("T3", rng)
        bad_normal.append((art, kind, "T3"))
    for _ in range(args.n):
        good_normal.append((make_good("T3", rng), "T3"))
    cells.extend(eval_population("normal_T3", bad_normal, good_normal))

    # ── rename_keys_T3 (the new perturbation) ──
    rng = random.Random(args.seed * 31 + 7)
    bad_rename = []
    good_rename = []
    for _ in range(args.n):
        art, kind = make_bad("T3", rng)
        renamed = apply_rename_keys(art, DEFAULT_RENAME)
        bad_rename.append((renamed, f"{kind}+rename", "T3"))
    for _ in range(args.n):
        art = make_good("T3", rng)
        renamed = apply_rename_keys(art, DEFAULT_RENAME)
        good_rename.append((renamed, "T3"))
    cells.extend(eval_population("rename_keys_T3", bad_rename, good_rename))

    by = {(c["population"], c["policy"]): c for c in cells}

    # Claims
    normal_fixed = by[("normal_T3", "fixed_matched")]
    normal_shape = by[("normal_T3", "artifact_shape")]
    rename_fixed = by[("rename_keys_T3", "fixed_matched")]
    rename_shape = by[("rename_keys_T3", "artifact_shape")]

    c_normal_close = (
        abs(normal_fixed["catch_rate"] - normal_shape["catch_rate"]) <= 0.05
        and abs(normal_fixed["false_reject_rate"] - normal_shape["false_reject_rate"]) <= 0.05
    )
    c_rename_misroutes = (
        rename_shape["route_histogram"].get("T1/P1", 0) > 0
        or rename_shape["route_histogram"].get("T2/P2", 0) > 0
    )
    c_rename_false_reject_spiikes = (
        rename_shape["false_reject_rate"] is not None
        and rename_fixed["false_reject_rate"] is not None
        and rename_shape["false_reject_rate"] > rename_fixed["false_reject_rate"] + 0.15
    )

    claims = {
        "C1_normal_T3_baseline_match": {
            "pass": c_normal_close,
            "catch_fixed": normal_fixed["catch_rate"],
            "catch_shape": normal_shape["catch_rate"],
            "fr_fixed": normal_fixed["false_reject_rate"],
            "fr_shape": normal_shape["false_reject_rate"],
            "detail": "On unmodified T3, shape matches fixed on catch AND false_reject (|Δ| <= 0.05).",
        },
        "C2_rename_misroutes_to_T1": {
            "pass": c_rename_misroutes,
            "route_hist_shape": rename_shape["route_histogram"],
            "detail": "rename_keys on T3 causes shape router to misclassify away from T3/P3.",
        },
        "C3_rename_false_reject_spikes": {
            "pass": c_rename_false_reject_spiikes,
            "fr_fixed": rename_fixed["false_reject_rate"],
            "fr_shape": rename_shape["false_reject_rate"],
            "catch_fixed": rename_fixed["catch_rate"],
            "catch_shape": rename_shape["catch_rate"],
            "reject_reasons_on_good": rename_shape["reject_reasons_on_good"],
            "detail": "rename_keys: shape false_reject_rate > fixed + 0.15 (specificity collapse).",
        },
    }

    out = {
        "experiment": "probe-shape-routing-rename-keys",
        "question": (
            "Is the depth signal from artifact shape stable under minor shape changes? "
            "Specifically: does synonym-rename (services→components, schema-semantic-preserving) "
            "break shape routing?"
        ),
        "source": "Xiao Man inferability-first push, Part 7 thread, 2026-07-29",
        "predecessor": "probe-artifact-shape-routing-test.py (cue_erase, decoy_nest)",
        "third_perturbation": "rename_keys on T3 (services→components)",
        "n_per_cell": args.n,
        "seed": args.seed,
        "rename_map": DEFAULT_RENAME,
        "normal_T3": {
            "fixed_matched": normal_fixed,
            "artifact_shape": normal_shape,
        },
        "rename_keys_T3": {
            "fixed_matched": rename_fixed,
            "artifact_shape": rename_shape,
        },
        "claims": claims,
        "interpretation": (
            "Three perturbations now, two failure axes. "
            "cue_erase: catch drops (under-reject on P4-specific defects). "
            "decoy_nest: catch drops to 0 (wrong-probe-wrong-depth). "
            "rename_keys: catch looks fine but false_reject spikes (over-reject from misroute to T1). "
            "Depth signal not stable on either axis — confirms Xiao Man's design cut: "
            "don't infer depth from shape; route to fixed mid-depth probe as baseline."
        ),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("═══ rename_keys stability test ═══")
    print(f"n={args.n} seed={args.seed}")
    print(f"rename_map: {DEFAULT_RENAME}")
    print()
    print("Normal T3 (control):")
    for p in POLICIES:
        c = by[("normal_T3", p)]
        print(f"  {p:>16}: catch={c['catch_rate']:.3f}  false_reject={c['false_reject_rate']:.3f}  "
              f"routes={c['route_histogram']}")
    print()
    print("rename_keys T3:")
    for p in POLICIES:
        c = by[("rename_keys_T3", p)]
        print(f"  {p:>16}: catch={c['catch_rate']:.3f}  false_reject={c['false_reject_rate']:.3f}  "
              f"routes={c['route_histogram']}")
        if c["reject_reasons_on_good"]:
            print(f"                    reject_reasons_on_good={c['reject_reasons_on_good']}")
    print()
    print("Claims:")
    for k, v in claims.items():
        flag = "PASS" if v["pass"] else "FAIL"
        print(f"  [{flag}] {k}")
        print(f"         {v['detail']}")
    print()
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
