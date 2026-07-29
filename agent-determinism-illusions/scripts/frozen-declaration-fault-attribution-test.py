# -*- coding: utf-8 -*-
"""Frozen-declaration fault attribution — Tom Jones (done self-check thread).

Question (Tom Jones, 2026-07-30, on nexuslabzen "Is your agent's done real?"):
  Freezing the declaration out of the agent's reach is right. What it does to
  the *failure distribution* caught us: gate blocked correctly when the
  declared test file did not exist — declaration frozen, untouched, compared
  exactly. The declaration itself was wrong (named a test never written).
  Mechanism real; failure relocated, not removed; relocated into worse
  ergonomics — a spec defect wearing an agent-failure costume. Cost: 421 lines
  of correct work lost to destructive cleanup. Two guards: (1) applyable patch
  of whatever was built before destroy; (2) message names fault as spec defect
  and lists what the worker produced. After freeze, the small frozen artifact
  is the only unverified thing in the chain — cheap to review, expensive to
  get wrong.

Claim under test:
  C1  Freeze+gate blocks both agent defects and missing-declared-test (mechanism).
  C2  Naive attribution labels BOTH as agent_failed → 100% misattribution on
      spec-defect cells.
  C3  Spec-aware attribution (missing path in frozen form, worker tree present)
      labels spec_defect → misattribution 0 on those cells; agent_bad stays
      agent_failed.
  C4  Naive cleanup loses worker lines on spec-defect; salvage-before-destroy
      recovers them (patch line count == worker lines).
  C5  Agent cannot rewrite the frozen declaration (write rejected); gate still
      compares against original form.

Falsifiers:
  C2 fail → naive already distinguishes causes (then Tom's costume claim is fixture-specific).
  C3 fail → heuristic still mislabels agent_bad or misses spec_missing.
  C4 fail → salvage incomplete (lines recovered < worker lines).
  C5 fail → agent rewrite sticks and gate follows the rewritten form.

Method (offline sim, no API):
  Spec = {artifact, verify_test} frozen before dispatch.
  Worker builds a text tree of N lines (default 421, Tom's figure).
  Gate: verify_test path must exist; artifact must be non-empty.
  Policies: naive_block vs tom_guards (classify + salvage).

Run:
  python frozen-declaration-fault-attribution-test.py
  python frozen-declaration-fault-attribution-test.py --lines 421 --n 40 --seed 7
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "frozen-declaration-fault-attribution.json"


@dataclass
class Spec:
    artifact: str
    verify_test: str
    frozen: bool = True

    def fingerprint(self) -> str:
        return f"{self.artifact}|{self.verify_test}"


@dataclass
class World:
    files: dict[str, str] = field(default_factory=dict)  # path → content
    spec: Spec | None = None
    destroyed: bool = False
    salvage_patch: str | None = None
    messages: list[str] = field(default_factory=list)


def freeze_spec(artifact: str, verify_test: str) -> Spec:
    return Spec(artifact=artifact, verify_test=verify_test, frozen=True)


def try_agent_rewrite_spec(world: World, new_test: str) -> bool:
    """Agent attempts to rewrite verify_test. Returns True if rewrite stuck."""
    assert world.spec is not None
    if world.spec.frozen:
        world.messages.append("rewrite_rejected:spec_frozen")
        return False
    world.spec.verify_test = new_test
    world.messages.append("rewrite_applied")
    return True


def worker_build(world: World, n_lines: int, good: bool) -> int:
    """Build artifact (+ optional junk). Returns lines written."""
    assert world.spec is not None
    body = "\n".join(f"line_{i:04d}_ok" for i in range(n_lines))
    if not good:
        body = ""  # empty / missing work — agent defect
    world.files[world.spec.artifact] = body
    return len(body.splitlines()) if body else 0


def plant_verify_test(world: World, exists: bool) -> None:
    assert world.spec is not None
    if exists:
        world.files[world.spec.verify_test] = "def test_ok():\n    assert True\n"
    else:
        world.files.pop(world.spec.verify_test, None)


def gate_check(world: World) -> tuple[bool, str]:
    """Mechanical compare against frozen form. Returns (pass, reason)."""
    assert world.spec is not None
    spec = world.spec
    art = world.files.get(spec.artifact)
    if art is None or len(art) == 0:
        return False, "artifact_missing_or_empty"
    if spec.verify_test not in world.files:
        return False, "verify_test_missing"
    return True, "ok"


def classify_fault(world: World, gate_reason: str) -> str:
    """Tom-style: missing declared test + non-empty worker artifact → spec_defect."""
    assert world.spec is not None
    art = world.files.get(world.spec.artifact, "")
    has_work = bool(art)
    if gate_reason == "verify_test_missing" and has_work:
        return "spec_defect"
    if gate_reason == "artifact_missing_or_empty":
        return "agent_failed"
    if gate_reason == "verify_test_missing" and not has_work:
        return "ambiguous_or_both"
    return "agent_failed"


def cleanup_naive(world: World) -> None:
    world.files.clear()
    world.destroyed = True
    world.salvage_patch = None
    world.messages.append("cleanup:destroyed_no_salvage")


def cleanup_with_salvage(world: World) -> None:
    assert world.spec is not None
    art = world.files.get(world.spec.artifact, "")
    world.salvage_patch = art  # applyable patch = full artifact body
    world.files.clear()
    world.destroyed = True
    world.messages.append("cleanup:salvage_then_destroy")


def run_policy(
    policy: str,
    world: World,
    true_cause: str,
) -> dict[str, Any]:
    passed, reason = gate_check(world)
    attributed = "none"
    lines_before = 0
    if world.spec and world.spec.artifact in world.files:
        content = world.files[world.spec.artifact]
        lines_before = len(content.splitlines()) if content else 0

    if passed:
        return {
            "policy": policy,
            "true_cause": true_cause,
            "gate_pass": True,
            "gate_reason": reason,
            "attributed": "none",
            "misattributed": False,
            "lines_before": lines_before,
            "lines_salvaged": lines_before,
            "work_lost": 0,
            "message": "pass",
        }

    if policy == "naive_block":
        attributed = "agent_failed"
        msg = f"agent_failed:{reason}"
        world.messages.append(msg)
        cleanup_naive(world)
        salvaged = 0
    elif policy == "tom_guards":
        attributed = classify_fault(world, reason)
        produced = list(world.files.keys())
        msg = (
            f"{attributed}:{reason}; "
            f"human_read: declaration_wrong_or_agent; produced={produced}"
        )
        if attributed == "spec_defect":
            msg = (
                f"spec_defect:{reason}; "
                f"your_declaration_was_wrong; produced={produced}"
            )
        world.messages.append(msg)
        cleanup_with_salvage(world)
        salvaged = (
            len(world.salvage_patch.splitlines()) if world.salvage_patch else 0
        )
    else:
        raise ValueError(policy)

    mis = False
    if true_cause == "spec" and attributed != "spec_defect":
        mis = True
    if true_cause == "agent" and attributed != "agent_failed":
        mis = True

    return {
        "policy": policy,
        "true_cause": true_cause,
        "gate_pass": False,
        "gate_reason": reason,
        "attributed": attributed,
        "misattributed": mis,
        "lines_before": lines_before,
        "lines_salvaged": salvaged,
        "work_lost": max(0, lines_before - salvaged),
        "message": world.messages[-1] if world.messages else "",
    }


SCENARIOS = (
    # name, true_cause, worker_good, test_exists
    ("honest_ok", "none", True, True),
    ("agent_bad_empty", "agent", False, True),
    ("spec_missing_test", "spec", True, False),
    ("both_bad", "both", False, False),
)


def make_world(
    rng: random.Random,
    n_lines: int,
    worker_good: bool,
    test_exists: bool,
) -> World:
    suffix = rng.randint(1000, 9999)
    spec = freeze_spec(
        artifact=f"build/out_{suffix}.py",
        verify_test=f"tests/test_out_{suffix}.py",
    )
    world = World(spec=spec)
    worker_build(world, n_lines, good=worker_good)
    plant_verify_test(world, exists=test_exists)
    return world


def run_rewrite_cell(n_lines: int, seed: int) -> dict[str, Any]:
    """C5: agent tries to point verify_test at a file it will create."""
    rng = random.Random(seed)
    world = make_world(rng, n_lines, worker_good=True, test_exists=False)
    assert world.spec is not None
    original_fp = world.spec.fingerprint()
    # Agent creates a fake test path and tries to rewrite spec to it
    fake = "tests/agent_authored_easy.py"
    world.files[fake] = "def test_easy():\n    assert True\n"
    stuck = try_agent_rewrite_spec(world, fake)
    after_fp = world.spec.fingerprint()
    passed, reason = gate_check(world)
    return {
        "rewrite_stuck": stuck,
        "fingerprint_unchanged": original_fp == after_fp,
        "gate_still_blocks": not passed,
        "gate_reason": reason,
        "c5_hold": (not stuck) and original_fp == after_fp and (not passed),
    }


def aggregate(rows: list[dict[str, Any]], policy: str, cause: str) -> dict[str, Any]:
    sub = [r for r in rows if r["policy"] == policy and r["true_cause"] == cause]
    if not sub:
        return {"n": 0}
    mis = sum(1 for r in sub if r["misattributed"])
    lost = sum(r["work_lost"] for r in sub)
    salv = sum(r["lines_salvaged"] for r in sub)
    before = sum(r["lines_before"] for r in sub)
    return {
        "n": len(sub),
        "misattribution_rate": mis / len(sub),
        "mean_work_lost": lost / len(sub),
        "mean_lines_salvaged": salv / len(sub),
        "mean_lines_before": before / len(sub),
    }


def check_claims(rows: list[dict], rewrite: dict, n_lines: int) -> dict[str, Any]:
    # C1: both agent and spec cells block under both policies
    def blocked(policy: str, cause: str) -> bool:
        sub = [r for r in rows if r["policy"] == policy and r["true_cause"] == cause]
        return bool(sub) and all(not r["gate_pass"] for r in sub)

    c1 = all(
        blocked(p, c)
        for p in ("naive_block", "tom_guards")
        for c in ("agent", "spec")
    )

    naive_spec = aggregate(rows, "naive_block", "spec")
    tom_spec = aggregate(rows, "tom_guards", "spec")
    tom_agent = aggregate(rows, "tom_guards", "agent")
    naive_agent = aggregate(rows, "naive_block", "agent")

    c2 = naive_spec.get("misattribution_rate", 0) == 1.0
    c3 = (
        tom_spec.get("misattribution_rate", 1) == 0.0
        and tom_agent.get("misattribution_rate", 1) == 0.0
    )
    c4 = (
        naive_spec.get("mean_work_lost", 0) == float(n_lines)
        and tom_spec.get("mean_work_lost", 1) == 0.0
        and tom_spec.get("mean_lines_salvaged", 0) == float(n_lines)
    )
    c5 = bool(rewrite.get("c5_hold"))

    # honest always passes
    honest = [r for r in rows if r["true_cause"] == "none"]
    honest_ok = bool(honest) and all(r["gate_pass"] for r in honest)

    return {
        "C1_gate_blocks_agent_and_spec": c1,
        "C2_naive_misattributes_spec_as_agent": c2,
        "C3_tom_guards_attribute_correctly": c3,
        "C4_salvage_recovers_spec_defect_work": c4,
        "C5_freeze_blocks_agent_rewrite": c5,
        "honest_always_passes": honest_ok,
        "all_hold": all([c1, c2, c3, c4, c5, honest_ok]),
        "naive_spec": naive_spec,
        "tom_spec": tom_spec,
        "tom_agent": tom_agent,
        "naive_agent": naive_agent,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="trials per scenario×policy")
    ap.add_argument("--lines", type=int, default=421, help="worker lines (Tom's figure)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []

    for _ in range(args.n):
        for name, true_cause, worker_good, test_exists in SCENARIOS:
            for policy in ("naive_block", "tom_guards"):
                world = make_world(rng, args.lines, worker_good, test_exists)
                # deep copy isolation already via new world
                row = run_policy(policy, world, true_cause)
                row["scenario"] = name
                rows.append(row)

    rewrite = run_rewrite_cell(args.lines, seed=args.seed + 99)
    claims = check_claims(rows, rewrite, args.lines)

    print("Frozen-declaration fault attribution")
    print(f"  n={args.n} lines={args.lines} seed={args.seed}")
    print("Claims:", json.dumps(claims, indent=2))
    print("Rewrite cell:", json.dumps(rewrite, indent=2))

    # compact table
    print("\nmisattribution / mean work_lost by policy × true_cause:")
    for policy in ("naive_block", "tom_guards"):
        for cause in ("agent", "spec", "both", "none"):
            agg = aggregate(rows, policy, cause)
            if agg["n"] == 0:
                continue
            print(
                f"  {policy:<12} cause={cause:<5} "
                f"mis={agg.get('misattribution_rate', 0):.2f} "
                f"lost={agg.get('mean_work_lost', 0):.1f} "
                f"salv={agg.get('mean_lines_salvaged', 0):.1f}"
            )

    payload = {
        "claim": (
            "Tom Jones: freeze relocates failure; naive attribution costumes "
            "spec defects as agent failures; salvage+naming guards recover work "
            "and correct the message."
        ),
        "n_per_scenario_policy": args.n,
        "worker_lines": args.lines,
        "seed": args.seed,
        "scenarios": [s[0] for s in SCENARIOS],
        "policies": ["naive_block", "tom_guards"],
        "claims": claims,
        "rewrite_cell": rewrite,
        "rows_sample": rows[:8],
        "n_rows": len(rows),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
