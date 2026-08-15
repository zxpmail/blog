#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trusted parent owns PASS/REJECT; child cannot convert rejection (Peter).

Claim under test
----------------
Part 10's C3 5/5 shows synonym-immune *behavioral* observation. Peter
(DEV.to on ``the-third-predicate-argument-space-verification-tested-3gfh``)
separates a second claim: the **reporting channel** must terminate outside
the evaluated process.

  - Trusted parent launches a restricted child, reads a narrow IPC line,
    decides PASS/REJECT in the parent.
  - Child may exit 0, hang, or emit malformed data — it must not replace
    the parent's exit function or turn a rejection into success.
  - Timeouts / protocol violations fail closed.
  - Bind the result to a digest of parent harness (+ fixtures/policy
    stand-in); else isolation can be sound while CI runs a modified
    verifier.

Method
------
Same script acts as parent and ``--child`` worker (stdlib subprocess).

  A1 in-process adversary: observation is fail, but the evaluated process
     prints/returns PASS (reporting authority inside the subject).
  A2 parent+IPC: same fail observation; child also exits 0 and prints a
     fake ``PASS`` banner — parent ignores banner/exit, decides from IPC.
  A3 child hang past timeout → parent REJECT (fail closed).
  A4 malformed IPC → parent REJECT.
  A5 digest mismatch (modified harness) → REJECT even if IPC says ok.
  A6 honest child + matching digest + ok observation → PASS.

PASS criteria (falsify if any fails)
------------------------------------
  1. A1 yields PASS on a failing observation (authority conflation).
  2. A2 yields REJECT despite child exit 0 + fake PASS text.
  3. A3 and A4 yield REJECT.
  4. A5 yields REJECT; A6 yields PASS.

Expected: SUPPORT — randomized/behavioral oracle ≠ reporting authority;
external supervisor + digest protect the latter.

Dependencies: stdlib only.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-reporting-authority.json"
SCRIPT = Path(__file__).resolve()

# Stand-in for "parent harness + fixtures + sandbox policy"
HARNESS_BODY = "verify-parent-v1|fixtures=cache-write|policy=no-net"
EXPECTED_DIGEST = hashlib.sha256(HARNESS_BODY.encode("utf-8")).hexdigest()
MODIFIED_HARNESS = "verify-parent-v1-TAMPERED|fixtures=cache-write|policy=no-net"
TIMEOUT_S = 0.8


def harness_digest(body: str) -> str:
    """Digest binding for the supervisor itself."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def in_process_report(observation_ok: bool, adversary: bool) -> str:
    """Reporting decided inside the evaluated process (conflated channel)."""
    if adversary:
        return "PASS"  # convert rejection into success
    return "PASS" if observation_ok else "REJECT"


def parent_decide(
    ipc_line: str | None,
    *,
    timed_out: bool,
    exit_code: int | None,
    digest: str,
    expected_digest: str,
) -> str:
    """Parent-only verdict. Never trusts child exit code or free-text PASS."""
    if digest != expected_digest:
        return "REJECT"
    if timed_out:
        return "REJECT"
    if exit_code is None:
        return "REJECT"
    # Signal-style failure (POSIX); on Windows rare — still fail closed if set.
    if exit_code < 0:
        return "REJECT"
    if ipc_line is None or not ipc_line.strip():
        return "REJECT"
    # Narrow protocol: one JSON object, key "obs" in {"ok", "fail"} only.
    # Extra keys / banners / "PASS" strings are protocol violations.
    try:
        msg = json.loads(ipc_line.strip().splitlines()[0])
    except json.JSONDecodeError:
        return "REJECT"
    if not isinstance(msg, dict) or set(msg.keys()) != {"obs"}:
        return "REJECT"
    if msg["obs"] not in ("ok", "fail"):
        return "REJECT"
    return "PASS" if msg["obs"] == "ok" else "REJECT"


def run_child(mode: str, timeout: float = TIMEOUT_S) -> dict:
    """Launch restricted child; collect IPC + exit; parent decides."""
    cmd = [sys.executable, str(SCRIPT), "--child", mode]
    timed_out = False
    stdout = ""
    exit_code: int | None = None
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        stdout = proc.stdout or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        exit_code = None
    elapsed = time.perf_counter() - t0

    # First non-empty line that looks like JSON is the IPC; rest is noise.
    ipc_line = None
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("{"):
            ipc_line = s
            break

    return {
        "mode": mode,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout": stdout,
        "ipc_line": ipc_line,
        "elapsed_s": round(elapsed, 3),
    }


def child_main(mode: str) -> None:
    """Child: may emit IPC, banners, hang, or malformed data."""
    if mode == "honest_ok":
        print(json.dumps({"obs": "ok"}), flush=True)
        sys.exit(0)
    if mode == "fail_obs_fake_pass":
        # True behavioral fail, but tries to steal reporting authority.
        print(json.dumps({"obs": "fail"}), flush=True)
        print("PASS", flush=True)  # banner the parent must ignore
        sys.exit(0)  # success exit must not convert rejection
    if mode == "hang":
        time.sleep(30.0)
        print(json.dumps({"obs": "ok"}), flush=True)
        sys.exit(0)
    if mode == "malformed":
        print('{"obs": "ok", "extra": true}', flush=True)  # protocol violation
        sys.exit(0)
    if mode == "non_json":
        print("PASS", flush=True)
        sys.exit(0)
    print(json.dumps({"obs": "fail", "error": f"unknown mode {mode}"}), flush=True)
    sys.exit(2)


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--child":
        child_main(sys.argv[2])
        return

    # A1 — conflated reporting inside the subject
    a1 = in_process_report(observation_ok=False, adversary=True)

    # A2 — parent decides; child fakes PASS + exit 0
    raw2 = run_child("fail_obs_fake_pass")
    a2 = parent_decide(
        raw2["ipc_line"],
        timed_out=raw2["timed_out"],
        exit_code=raw2["exit_code"],
        digest=EXPECTED_DIGEST,
        expected_digest=EXPECTED_DIGEST,
    )

    # A3 — hang
    raw3 = run_child("hang", timeout=TIMEOUT_S)
    a3 = parent_decide(
        raw3["ipc_line"],
        timed_out=raw3["timed_out"],
        exit_code=raw3["exit_code"],
        digest=EXPECTED_DIGEST,
        expected_digest=EXPECTED_DIGEST,
    )

    # A4 — malformed protocol
    raw4 = run_child("malformed")
    a4 = parent_decide(
        raw4["ipc_line"],
        timed_out=raw4["timed_out"],
        exit_code=raw4["exit_code"],
        digest=EXPECTED_DIGEST,
        expected_digest=EXPECTED_DIGEST,
    )

    # A5 — modified verifier digest (CI quietly swapped harness)
    raw5 = run_child("honest_ok")
    a5 = parent_decide(
        raw5["ipc_line"],
        timed_out=raw5["timed_out"],
        exit_code=raw5["exit_code"],
        digest=harness_digest(MODIFIED_HARNESS),
        expected_digest=EXPECTED_DIGEST,
    )

    # A6 — honest path
    raw6 = run_child("honest_ok")
    a6 = parent_decide(
        raw6["ipc_line"],
        timed_out=raw6["timed_out"],
        exit_code=raw6["exit_code"],
        digest=EXPECTED_DIGEST,
        expected_digest=EXPECTED_DIGEST,
    )

    claim1 = a1 == "PASS"
    claim2 = a2 == "REJECT"
    claim3 = a3 == "REJECT" and raw3["timed_out"] is True
    claim4 = a4 == "REJECT"
    claim5 = a5 == "REJECT"
    claim6 = a6 == "PASS"

    support = all([claim1, claim2, claim3, claim4, claim5, claim6])
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "peter_split": {
            "behavioral_oracle": "randomized/argument-space probes (Part 10 C3)",
            "reporting_authority": "trusted parent + narrow IPC + digest",
        },
        "expected_digest": EXPECTED_DIGEST,
        "claims": {
            "A1_in_process_adversary_converts_reject": claim1,
            "A2_parent_ignores_child_exit_and_PASS_banner": claim2,
            "A3_hang_fail_closed": claim3,
            "A4_malformed_fail_closed": claim4,
            "A5_digest_mismatch_reject": claim5,
            "A6_honest_pass": claim6,
        },
        "runs": {
            "A1_in_process": {"observation_ok": False, "verdict": a1},
            "A2": {**raw2, "parent_verdict": a2},
            "A3": {**raw3, "parent_verdict": a3},
            "A4": {**raw4, "parent_verdict": a4},
            "A5": {**raw5, "parent_verdict": a5, "digest_ok": False},
            "A6": {**raw6, "parent_verdict": a6, "digest_ok": True},
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("parent-reporting-authority — Peter / Part 10 follow-up")
    print(f"verdict: {verdict}")
    print(f"A1 in-process adversary: {a1} (expect PASS conversion)")
    print(f"A2 parent vs fake PASS: {a2} (expect REJECT)")
    print(f"A3 hang timeout: {a3} timed_out={raw3['timed_out']}")
    print(f"A4 malformed: {a4}")
    print(f"A5 digest mismatch: {a5}")
    print(f"A6 honest: {a6}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
