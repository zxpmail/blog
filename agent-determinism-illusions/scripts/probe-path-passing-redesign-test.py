# -*- coding: utf-8 -*-
"""Probe path-passing redesign — Xiao Man refinement on rename_keys (2026-07-30).

Question (Xiao Man, 2026-07-30, Part 7 thread):
  The probe should never re-find what the router already resolved. If the
  router passes the resolved path (e.g. "services is at art['components']"
  after rename), the probe stops doing key-name lookup and becomes
  rename-immune by construction.

  Mutation suite becomes: "did we accidentally put lookup responsibility
  back into the probe?"

Predecessor: probe-shape-routing-rename-keys-test.py
  Under rename_keys, current probe (hardcoded art.get("services")):
    false_reject ≈ 100% on good renamed artifacts.

This script tests two probe designs on the same rename_keys cell:
  probe_v1 (current):  hardcoded art.get("services")
  probe_v2 (refined):  takes resolved path from router; no key lookup

Method:
  Reuse SCHEMA/make_good/rename_map from probe-shape-routing-rename-keys.
  Add a declaration-aware router that knows the services field can be at
  any of {services, components, modules}. Both probes run on the same
  renamed-good population (N=40, seed=7).

Expected / falsification:
  probe_v1: false_reject ≈ 100% on rename_keys_T3 (existing finding).
  probe_v2: false_reject ≈ 0% on rename_keys_T3 IF the router resolves
            the path correctly. If probe_v2 also false_rejects high, the
            boundary redraw didn't help — the lookup must be leaking
            somewhere else (e.g., the probe still references the original
            key in a sub-route).

Caveat (explicit):
  This only verifies the probe side. The router side still has to resolve
  the path — and the router's resolution is itself a lookup. Declaration
  with a synonym list works for *known* renames; structural anchors
  (list-of-dicts-with-limits) work for arbitrary renames but fail
  decoy_nest. Probe-side fix doesn't eliminate the lookup problem; it
  relocates it.

Run:
  python probe-path-passing-redesign-test.py
"""

from __future__ import annotations

import copy
import io
import json
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "probe-path-passing-redesign.json"


# ── Schema (copied from probe-shape-routing-rename-keys for standalone run) ──

SCHEMA_T3_TEMPLATE = lambda: {
    "services": [
        {"name": "api", "port": 8080,
         "limits": {"max_connections": 10, "timeout_ms": 5000}},
        {"name": "worker", "port": 8081,
         "limits": {"max_connections": 20, "timeout_ms": 3000}},
    ]
}


def rename_recursive(obj, mapping):
    if isinstance(obj, dict):
        return {mapping.get(k, k): rename_recursive(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [rename_recursive(x, mapping) for x in obj]
    return obj


DEFAULT_RENAME = {
    "services": "components",
    "budget": "cost_limit",
    "timeout_ms": "request_timeout_ms",
    "retries": "retry_count",
    "fingerprint": "sig",
}


def make_good_t3():
    art = copy.deepcopy(SCHEMA_T3_TEMPLATE())
    art["_meta"] = {"ok": True}
    return art


# ── Probe v1: hardcoded key lookup (current design) ──

def probe_v1(art):
    """Hardcoded art.get('services'). Breaks under rename."""
    services = art.get("services")
    if not isinstance(services, list) or len(services) != 2:
        return True, "v1 missing services"
    for i, (name, port, mc, to) in enumerate(
        [("api", 8080, 10, 5000), ("worker", 8081, 20, 3000)]
    ):
        svc = services[i]
        if svc.get("name") != name:
            return True, f"v1 name[{i}]"
        if svc.get("port") != port:
            return True, f"v1 port[{i}]"
        if svc.get("limits", {}).get("max_connections") != mc:
            return True, f"v1 max_conn[{i}]"
        if svc.get("limits", {}).get("timeout_ms") != to:
            return True, f"v1 timeout[{i}]"
    return False, "v1 ok"


# ── Probe v2: path-passed by router ──

def probe_v2(art, services_path, timeout_key):
    """Takes resolved services path AND timeout key from router.
    No key-name lookup for any renamed field."""
    cur = art
    for p in services_path:
        if not isinstance(cur, dict) or p not in cur:
            return True, f"v2 path broken at {p}"
        cur = cur[p]
    if not isinstance(cur, list) or len(cur) != 2:
        return True, "v2 services not list len 2"
    for i, (name, port, mc, to) in enumerate(
        [("api", 8080, 10, 5000), ("worker", 8081, 20, 3000)]
    ):
        svc = cur[i]
        if svc.get("name") != name:
            return True, f"v2 name[{i}]"
        if svc.get("port") != port:
            return True, f"v2 port[{i}]"
        if svc.get("limits", {}).get("max_connections") != mc:
            return True, f"v2 max_conn[{i}]"
        if svc.get("limits", {}).get(timeout_key) != to:
            return True, f"v2 {timeout_key}[{i}]={svc.get('limits', {}).get(timeout_key)} want {to}"
    return False, "v2 ok"


# ── Router: declaration-aware path resolver ──

DECLARATION = {
    "services_candidates": ["services", "components", "modules"],
    "timeout_candidates": ["timeout_ms", "request_timeout_ms"],
}


def resolve_services_path(art, declaration):
    """Router resolves the services path."""
    for cand in declaration["services_candidates"]:
        if cand in art and isinstance(art[cand], list):
            return [cand]
    return None


def resolve_timeout_key(svc, declaration):
    """Router resolves which timeout key the artifact actually uses."""
    limits = svc.get("limits", {}) if isinstance(svc, dict) else {}
    for cand in declaration["timeout_candidates"]:
        if cand in limits:
            return cand
    return None


# ── Main ──

def main():
    n = 40
    seed = 7
    rng = random.Random(seed)

    # Generate good T3 artifacts (control + renamed)
    good_normal = [make_good_t3() for _ in range(n)]
    good_renamed = []
    for _ in range(n):
        art = make_good_t3()
        renamed = rename_recursive(art, DEFAULT_RENAME)
        renamed["_meta"] = {"ok": True}
        good_renamed.append(renamed)

    # Probe v1 on both populations
    v1_normal_fr = sum(1 for a in good_normal if probe_v1(a)[0]) / n
    v1_rename_fr = sum(1 for a in good_renamed if probe_v1(a)[0]) / n

    # Probe v2: router resolves services path AND per-svc timeout key
    v2_normal_fr = 0
    v2_rename_fr = 0
    v2_path_unresolved_normal = 0
    v2_path_unresolved_rename = 0
    for a in good_normal:
        path = resolve_services_path(a, DECLARATION)
        if path is None:
            v2_path_unresolved_normal += 1
            v2_normal_fr += 1
            continue
        # Peek at first svc to resolve timeout key (router-side)
        svcs = a[path[0]]
        tkey = resolve_timeout_key(svcs[0], DECLARATION)
        if tkey is None:
            v2_path_unresolved_normal += 1
            v2_normal_fr += 1
            continue
        v2_normal_fr += probe_v2(a, path, tkey)[0]
    v2_normal_fr /= n

    for a in good_renamed:
        path = resolve_services_path(a, DECLARATION)
        if path is None:
            v2_path_unresolved_rename += 1
            v2_rename_fr += 1
            continue
        svcs = a[path[0]]
        tkey = resolve_timeout_key(svcs[0], DECLARATION)
        if tkey is None:
            v2_path_unresolved_rename += 1
            v2_rename_fr += 1
            continue
        v2_rename_fr += probe_v2(a, path, tkey)[0]
    v2_rename_fr /= n

    # Adversarial rename outside declaration (probe v2 should now fail at router)
    adversarial_rename = dict(DEFAULT_RENAME)
    adversarial_rename["services"] = "instances"  # NOT in declaration
    good_adversarial = []
    for _ in range(n):
        art = make_good_t3()
        renamed = rename_recursive(art, adversarial_rename)
        renamed["_meta"] = {"ok": True}
        good_adversarial.append(renamed)
    v2_adv_path_unresolved = 0
    v2_adv_fr = 0
    for a in good_adversarial:
        path = resolve_services_path(a, DECLARATION)
        if path is None:
            v2_adv_path_unresolved += 1
            v2_adv_fr += 1
            continue
        svcs = a[path[0]]
        tkey = resolve_timeout_key(svcs[0], DECLARATION)
        if tkey is None:
            v2_adv_path_unresolved += 1
            v2_adv_fr += 1
            continue
        v2_adv_fr += probe_v2(a, path, tkey)[0]
    v2_adv_fr /= n

    print("═" * 78)
    print("  Probe path-passing redesign — Xiao Man refinement")
    print("═" * 78)
    print()
    print(f"  n = {n}, seed = {seed}")
    print()
    print("  Population: good T3 artifacts (legit)")
    print()
    print("  Probe v1 (hardcoded art.get('services')):")
    print(f"    normal T3        false_reject = {v1_normal_fr:.3f}")
    print(f"    rename_keys T3   false_reject = {v1_rename_fr:.3f}   ← known break")
    print()
    print("  Probe v2 (path passed by declaration-aware router):")
    print(f"    normal T3        false_reject = {v2_normal_fr:.3f}   "
          f"(path unresolved: {v2_path_unresolved_normal})")
    print(f"    rename_keys T3   false_reject = {v2_rename_fr:.3f}   "
          f"(path unresolved: {v2_path_unresolved_rename})   ← Xiao Man's claim")
    print()
    print("  Adversarial cell: services renamed to 'instances' (NOT in declaration):")
    print(f"    probe v2         false_reject = {v2_adv_fr:.3f}   "
          f"(path unresolved: {v2_adv_path_unresolved}/{n})   ← router-side gap")
    print()

    claim_v2_rename_immune = v2_rename_fr < 0.05
    claim_router_unresolved_adv = v2_adv_path_unresolved == n

    print("  Claims:")
    print(f"    [{'PASS' if claim_v2_rename_immune else 'FAIL'}] "
          f"v2 probe rename-immune: false_reject < 5% on rename_keys_T3")
    print(f"    [{'PASS' if claim_router_unresolved_adv else 'FAIL'}] "
          f"router declaration fails on out-of-declaration rename: "
          f"path unresolved {v2_adv_path_unresolved}/{n}")
    print()

    out = {
        "experiment": "probe-path-passing-redesign",
        "source": "Xiao Man 2026-07-30 refinement on rename_keys cell",
        "predecessor": "probe-shape-routing-rename-keys-test.py",
        "n": n,
        "seed": seed,
        "declaration_services_candidates": DECLARATION["services_candidates"],
        "default_rename_map": DEFAULT_RENAME,
        "adversarial_rename_extra": {"services": "instances"},
        "results": {
            "probe_v1_hardcoded": {
                "normal_T3_false_reject": v1_normal_fr,
                "rename_keys_T3_false_reject": v1_rename_fr,
            },
            "probe_v2_path_passed": {
                "normal_T3_false_reject": v2_normal_fr,
                "rename_keys_T3_false_reject": v2_rename_fr,
                "path_unresolved_normal": v2_path_unresolved_normal,
                "path_unresolved_rename": v2_path_unresolved_rename,
                "adversarial_false_reject": v2_adv_fr,
                "adversarial_path_unresolved": v2_adv_path_unresolved,
            },
        },
        "claims": {
            "v2_probe_rename_immune": claim_v2_rename_immune,
            "router_declaration_fails_outside_synonym_list": claim_router_unresolved_adv,
        },
        "interpretation": (
            "Probe-side fix verified: path-passed probe is rename-immune by "
            "construction. But the router-side lookup is the new failure site — "
            "declaration with synonym list works for known renames and fails on "
            "out-of-declaration ones (e.g. 'instances'). Xiao Man's boundary "
            "redraw relocates the lookup; it doesn't eliminate it. The next "
            "survival question is the router-side anchor."
        ),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {OUT}")


if __name__ == "__main__":
    main()
