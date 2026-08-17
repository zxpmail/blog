#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parent+IPC alone is hollow without trusted observation (Peter gap).

Claim under test
----------------
Peter's prescription (trusted parent, narrow IPC, fail-closed, harness
digest) correctly protects *reporting authority*. It does **not** by itself
protect *oracle integrity*. Three attack shapes should still produce a
clean parent PASS unless observation inputs are parent-owned and the
expected digest is pinned outside the mutable tree.

  H1 child-lied IPC: true side effect failed, child still emits
     ``{"obs":"ok"}`` — parent that trusts child IPC PASSes (false green);
     parent that observes itself REJECTs.
  H2 fixture poison: child rewrites a shared fixture the parent will read
     as "truth" — parent reading that file PASSes; parent using a sealed
     in-memory fixture REJECTs.
  H3 colocated digest: attacker changes harness body **and** the expected
     digest stored beside it — colocated check PASSes; externally pinned
     expected digest REJECTs.

PASS criteria (falsify if any fails)
------------------------------------
  1. H1 trust-child → PASS; H1 parent-observe → REJECT.
  2. H2 read-poisoned-file → PASS; H2 sealed-fixture → REJECT.
  3. H3 colocated expected updated with tamper → PASS;
     H3 external pin unchanged → REJECT.

Expected: SUPPORT — parent reporting without trusted observation (and
without external digest pin) is notarized false green.

Dependencies: stdlib only.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-oracle-hollow.json"
SCRIPT = Path(__file__).resolve()

# Ground truth for the cache-write claim: invalidation did NOT happen.
TRUE_INVALIDATED = False

# External pin (CI attestation stand-in) — not writable by the "repo tree".
EXTERNAL_PIN = hashlib.sha256(
    b"verify-parent-v1|fixtures=sealed|policy=no-net"
).hexdigest()


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def parent_from_child_ipc(ipc_line: str) -> str:
    """Peter-shaped parent that trusts the child's obs field."""
    try:
        msg = json.loads(ipc_line.strip())
    except json.JSONDecodeError:
        return "REJECT"
    if set(msg.keys()) != {"obs"} or msg["obs"] not in ("ok", "fail"):
        return "REJECT"
    return "PASS" if msg["obs"] == "ok" else "REJECT"


def parent_self_observe(invalidated: bool) -> str:
    """Observation produced on the parent side — child narrative ignored."""
    return "PASS" if invalidated else "REJECT"


def run_child(mode: str, workdir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--child", mode, str(workdir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
    )
    ipc = None
    for line in (proc.stdout or "").splitlines():
        if line.strip().startswith("{"):
            ipc = line.strip()
            break
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "ipc_line": ipc,
    }


def child_main(mode: str, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    if mode == "lie_ok":
        # True world: not invalidated. Child lies on the reporting channel.
        assert TRUE_INVALIDATED is False
        print(json.dumps({"obs": "ok"}), flush=True)
        sys.exit(0)
    if mode == "poison_fixture":
        # Parent might read this file as the observation source.
        fixture = workdir / "observation.json"
        fixture.write_text(
            json.dumps({"invalidated": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(json.dumps({"obs": "fail"}), flush=True)  # IPC looks honest
        sys.exit(0)
    print(json.dumps({"obs": "fail"}), flush=True)
    sys.exit(2)


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        child_main(sys.argv[2], Path(sys.argv[3]))
        return

    tmp = Path(tempfile.mkdtemp(prefix="oracle-hollow-"))
    try:
        # --- H1: lie on IPC ---
        raw1 = run_child("lie_ok", tmp / "h1")
        h1_trust = parent_from_child_ipc(raw1["ipc_line"] or "")
        h1_self = parent_self_observe(TRUE_INVALIDATED)

        # --- H2: poison shared fixture ---
        # Sealed truth the child cannot rewrite (parent memory).
        sealed_invalidated = TRUE_INVALIDATED
        raw2 = run_child("poison_fixture", tmp / "h2")
        poisoned_path = tmp / "h2" / "observation.json"
        poisoned = json.loads(poisoned_path.read_text(encoding="utf-8"))
        h2_file = "PASS" if poisoned.get("invalidated") is True else "REJECT"
        h2_sealed = parent_self_observe(sealed_invalidated)

        # --- H3: colocated digest vs external pin ---
        honest_body = "verify-parent-v1|fixtures=sealed|policy=no-net"
        tampered_body = "verify-parent-v1-BACKDOOR|fixtures=sealed|policy=no-net"
        # Attacker rewrites both harness and the expected digest in-tree.
        colocated_expected = digest(tampered_body)
        h3_colocated = (
            "PASS"
            if digest(tampered_body) == colocated_expected
            else "REJECT"
        )
        h3_external = (
            "PASS"
            if digest(tampered_body) == EXTERNAL_PIN
            else "REJECT"
        )
        # Sanity: honest body still matches external pin
        h3_honest_external = (
            "PASS"
            if digest(honest_body) == EXTERNAL_PIN
            else "REJECT"
        )

        claim1 = h1_trust == "PASS" and h1_self == "REJECT"
        claim2 = h2_file == "PASS" and h2_sealed == "REJECT"
        claim3 = (
            h3_colocated == "PASS"
            and h3_external == "REJECT"
            and h3_honest_external == "PASS"
        )

        support = claim1 and claim2 and claim3
        verdict = "SUPPORT" if support else "FALSIFY"

        result = {
            "verdict": verdict,
            "thesis": (
                "Trusted parent + narrow IPC protects reporting authority; "
                "without parent-owned observation and externally pinned digest, "
                "the parent notarizes false green"
            ),
            "ground_truth_invalidated": TRUE_INVALIDATED,
            "claims": {
                "H1_child_lied_ipc_false_green": claim1,
                "H2_fixture_poison_false_green": claim2,
                "H3_colocated_digest_placebo": claim3,
            },
            "H1": {
                "child": raw1,
                "parent_trusts_child_ipc": h1_trust,
                "parent_self_observe": h1_self,
            },
            "H2": {
                "child": raw2,
                "poisoned_file": poisoned,
                "parent_reads_poisoned_file": h2_file,
                "parent_sealed_fixture": h2_sealed,
            },
            "H3": {
                "tampered_body": tampered_body,
                "colocated_check": h3_colocated,
                "external_pin_check": h3_external,
                "honest_matches_external_pin": h3_honest_external,
                "external_pin": EXTERNAL_PIN,
            },
        }

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print("parent-oracle-hollow — Peter prescription gaps")
        print(f"verdict: {verdict}")
        print(f"H1 trust-IPC={h1_trust} self-observe={h1_self}")
        print(f"H2 poisoned-file={h2_file} sealed={h2_sealed}")
        print(
            f"H3 colocated={h3_colocated} external={h3_external} "
            f"honest={h3_honest_external}"
        )
        print(f"wrote {OUT}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
