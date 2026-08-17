#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pin rollback: digest authenticity ≠ freshness (Peter, Part 10 follow-up).

Claim under test
----------------
An external digest proves that a verifier was *approved*, not that it is the
*newest acceptable* verifier. If CI may select any still-matching digest from
an approval set, it can resurrect an older verifier with a known false-green
channel without modifying that artifact — only by choosing which pin to use.

Peter's prescription under test: bind attestation to a monotonic
harness/policy version, reject anything older than the repository's recorded
minimum, and require an independently authorized forward transition (the
minimum itself must not be CI-writable).

Method
------
Two *executable* harnesses (not string labels). Ground truth observation is
FAILING (cache not invalidated). Adjudication:

  v1 harness — ignores observation, always returns PASS (false-green channel)
  v2 harness — returns REJECT on failing observation (repaired)

Approval history records both digests + versions. Repo minimum has advanced
to 2. Pipeline = admit(pin) then, if admitted, run harness on failing obs.

Cells
-----
  A digest-only allowlist
    select v1 → admit PASS → adjudicate PASS  (rollback false green)
    select v2 → admit PASS → adjudicate REJECT (honest)
  B digest + sealed minimum (=2)
    select v1 → admit REJECT (never runs)
    select v2 → admit PASS → adjudicate REJECT
  C selection ≠ rewrite (negative control)
    rewrite: mutate v1 bytes → digest leaves approval set → admit REJECT
    select:  unchanged v1 bytes → digest-only admit PASS
  D minimum writability residual
    CI-writable minimum lowered to 1 + select v1 → admit PASS → false green
    sealed minimum stays 2 + select v1 → admit REJECT

PASS criteria (falsify if any fails)
------------------------------------
  1. A: v1 path ends CI-green on failing obs; v2 path ends CI-red
  2. B: v1 admit REJECT; v2 admit PASS and adjudicate REJECT
  3. C: rewritten v1 rejected by digest check; unmodified v1 admitted
     under digest-only (proves resurrection without content rewrite)
  4. D: writable-minimum rollback false-greens; sealed-minimum blocks it

Expected: SUPPORT — digest pin lacks rollback resistance; sealed monotonic
minimum closes selection-rollback; a CI-writable minimum reopens it.

Dependencies: stdlib only.
How to falsify: digest-only refuses older-approved pins; sealed minimum
still admits v1; rewritten bytes still match approval; or writable-minimum
path fails to false-green while sealed path does.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-pin-rollback.json"

# 观测真相：未失效 → 诚实 harness 必须 REJECT
OBS_FAILING = {"invalidated": False}

V1_VERSION = 1
V2_VERSION = 2
SEALED_MINIMUM = 2  # 已轮换；独立信道，本 CI job 写不了


def sha(s: str) -> str:
    """内容摘要：只证明「是这份批准过的产物」。"""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def harness_v1_adjudicate(obs: dict) -> str:
    """已知假绿通道：无视观测，永远 PASS。"""
    _ = obs
    return "PASS"


def harness_v2_adjudicate(obs: dict) -> str:
    """修复版：观测未失效则 REJECT。"""
    return "PASS" if obs.get("invalidated") else "REJECT"


# 批准时冻结的 artifact 字节（之后不再改写）
V1_SOURCE = (
    "def adjudicate(obs):\n"
    "    return 'PASS'  # BACKDOOR: ignore observation\n"
)
V2_SOURCE = (
    "def adjudicate(obs):\n"
    "    return 'PASS' if obs.get('invalidated') else 'REJECT'\n"
)

# 运行时用函数表模拟「装载该 artifact」；digest 绑的是源码字节
HARNESS_RUN = {
    sha(V1_SOURCE): harness_v1_adjudicate,
    sha(V2_SOURCE): harness_v2_adjudicate,
}


def digest_only_admit(body: str, approved_digests: set[str]) -> str:
    """策略 A：批准集 digest 匹配即放行。"""
    return "PASS" if sha(body) in approved_digests else "REJECT"


def digest_plus_minimum_admit(
    body: str,
    version: int,
    approved_digests: set[str],
    repo_minimum: int,
) -> str:
    """策略 B：digest 匹配且 version ≥ repo_minimum。"""
    if sha(body) not in approved_digests:
        return "REJECT"
    if version < repo_minimum:
        return "REJECT"
    return "PASS"


def run_pipeline(admit: str, body: str, obs: dict) -> dict:
    """准入后才裁决；拒入则不跑 harness。"""
    if admit != "PASS":
        return {
            "admit": admit,
            "adjudicate": None,
            "ci_green": False,
        }
    fn = HARNESS_RUN[sha(body)]
    verdict = fn(obs)
    return {
        "admit": admit,
        "adjudicate": verdict,
        "ci_green": verdict == "PASS",
    }


def main() -> None:
    approved_digests = {sha(V1_SOURCE), sha(V2_SOURCE)}

    # --- A：仅 digest ---
    a_v1_admit = digest_only_admit(V1_SOURCE, approved_digests)
    a_v2_admit = digest_only_admit(V2_SOURCE, approved_digests)
    a_v1 = run_pipeline(a_v1_admit, V1_SOURCE, OBS_FAILING)
    a_v2 = run_pipeline(a_v2_admit, V2_SOURCE, OBS_FAILING)

    # --- B：digest + 密封最低版本 ---
    b_v1_admit = digest_plus_minimum_admit(
        V1_SOURCE, V1_VERSION, approved_digests, SEALED_MINIMUM
    )
    b_v2_admit = digest_plus_minimum_admit(
        V2_SOURCE, V2_VERSION, approved_digests, SEALED_MINIMUM
    )
    b_v1 = run_pipeline(b_v1_admit, V1_SOURCE, OBS_FAILING)
    b_v2 = run_pipeline(b_v2_admit, V2_SOURCE, OBS_FAILING)

    # --- C：选型 ≠ 改写 ---
    rewritten_v1 = V1_SOURCE + "# mutated\n"
    c_rewrite_admit = digest_only_admit(rewritten_v1, approved_digests)
    c_select_admit = digest_only_admit(V1_SOURCE, approved_digests)

    # --- D：最低版本可写残差 ---
    ci_writable_minimum = 1  # 攻击者把 minimum 降回 1
    d_writable_admit = digest_plus_minimum_admit(
        V1_SOURCE, V1_VERSION, approved_digests, ci_writable_minimum
    )
    d_sealed_admit = digest_plus_minimum_admit(
        V1_SOURCE, V1_VERSION, approved_digests, SEALED_MINIMUM
    )
    d_writable = run_pipeline(d_writable_admit, V1_SOURCE, OBS_FAILING)
    d_sealed = run_pipeline(d_sealed_admit, V1_SOURCE, OBS_FAILING)

    claim_a = (
        a_v1["ci_green"] is True
        and a_v1["adjudicate"] == "PASS"
        and a_v2["ci_green"] is False
        and a_v2["adjudicate"] == "REJECT"
    )
    claim_b = (
        b_v1["admit"] == "REJECT"
        and b_v1["adjudicate"] is None
        and b_v2["admit"] == "PASS"
        and b_v2["adjudicate"] == "REJECT"
        and b_v2["ci_green"] is False
    )
    claim_c = c_rewrite_admit == "REJECT" and c_select_admit == "PASS"
    claim_d = (
        d_writable["ci_green"] is True
        and d_writable["adjudicate"] == "PASS"
        and d_sealed["admit"] == "REJECT"
        and d_sealed["ci_green"] is False
    )
    support = claim_a and claim_b and claim_c and claim_d
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Digest authenticity admits rollback selection of an older "
            "approved false-green harness; sealed monotonic minimum blocks "
            "selection; a CI-writable minimum reopens the same channel"
        ),
        "source": (
            "Peter DEV.to follow-up on Part 10 reporting-authority thread "
            "(rollback / authorization history)"
        ),
        "observation": OBS_FAILING,
        "sealed_minimum": SEALED_MINIMUM,
        "approval_history": [
            {
                "label": "v1",
                "version": V1_VERSION,
                "digest": sha(V1_SOURCE),
                "false_green_channel": True,
            },
            {
                "label": "v2",
                "version": V2_VERSION,
                "digest": sha(V2_SOURCE),
                "false_green_channel": False,
            },
        ],
        "claims": {
            "A_digest_only_rollback_false_green": claim_a,
            "B_sealed_minimum_blocks_v1": claim_b,
            "C_selection_not_rewrite": claim_c,
            "D_writable_minimum_reopens_rollback": claim_d,
        },
        "cell_A_digest_only": {"select_v1": a_v1, "select_v2": a_v2},
        "cell_B_sealed_minimum": {"select_v1": b_v1, "select_v2": b_v2},
        "cell_C_selection_vs_rewrite": {
            "rewrite_v1_bytes_admit": c_rewrite_admit,
            "select_unmodified_v1_admit": c_select_admit,
        },
        "cell_D_minimum_writability": {
            "ci_writable_minimum": ci_writable_minimum,
            "writable_min_select_v1": d_writable,
            "sealed_min_select_v1": d_sealed,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("parent-pin-rollback — authenticity vs freshness (hardened)")
    print(f"verdict: {verdict}")
    print(
        f"A digest-only: v1 ci_green={a_v1['ci_green']} "
        f"adj={a_v1['adjudicate']} | v2 ci_green={a_v2['ci_green']} "
        f"adj={a_v2['adjudicate']}"
    )
    print(
        f"B sealed min≥{SEALED_MINIMUM}: v1 admit={b_v1['admit']} | "
        f"v2 adj={b_v2['adjudicate']}"
    )
    print(
        f"C rewrite admit={c_rewrite_admit} select admit={c_select_admit}"
    )
    print(
        f"D writable-min ci_green={d_writable['ci_green']} "
        f"sealed admit={d_sealed['admit']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
