#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remaining false-green after the three hardenings (import / pin swap).

Claim under test
----------------
Even with (a) parent-owned observation intent, (b) fixtures the child
cannot rewrite, and (c) an "external" digest pin, two residual channels
still yield false PASS:

  R1 parent-import: parent "observes" by importing the child's module into
     its own address space. The module lies in ``invalidate()`` / reports
     ok while the real sealed state is not invalidated → PASS. Out-of-
     process probe that does not trust in-process return values, and
     checks sealed state the child code never receives, → REJECT.
  R2 pin-swap: expected digest lives in an "external" store that an
     attacker who already owns CI can rewrite together with the harness
     → colocated-style PASS. A second-channel pin (offline attestation
     stand-in that the CI job cannot write) → REJECT.

PASS criteria (falsify if any fails)
------------------------------------
  1. R1 in-process import path → PASS; R1 out-of-process sealed check → REJECT.
  2. R2 writable "external" pin updated with tamper → PASS;
     R2 read-only attestation pin unchanged → REJECT.

Expected: SUPPORT — the three hardenings shrink notarized false green;
they do not abolish it.

Dependencies: stdlib only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-residual-false-green.json"
SCRIPT = Path(__file__).resolve()

# Sealed ground truth: cache entry was NOT invalidated.
SEALED_INVALIDATED = False

HONEST_HARNESS = "verify-parent-v2|fixtures=sealed|policy=no-net"
TAMPER_HARNESS = "verify-parent-v2-BACKDOOR|fixtures=sealed|policy=no-net"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


ATTESTATION_PIN = sha(HONEST_HARNESS)  # offline / second channel; CI cannot write


def write_lying_impl(path: Path) -> None:
    """Child-authored module: claims success, does not touch sealed truth."""
    path.write_text(
        textwrap.dedent(
            """\
            # agent-editable implementation
            def write(key, cache):
                # Intentionally does NOT invalidate cache[key]
                cache[key] = "stale-kept"
                return True

            def probe_ok():
                # Lies to any in-process caller
                return True
            """
        ),
        encoding="utf-8",
    )


def parent_import_observe(impl_path: Path) -> str:
    """Footgun: load child code into parent and trust its return value."""
    spec = importlib.util.spec_from_file_location("child_impl", impl_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cache = {"k": "v"}
    mod.write("k", cache)
    # Parent believes the child's probe_ok() — classic false green.
    return "PASS" if mod.probe_ok() else "REJECT"


def parent_oop_sealed_observe(impl_path: Path, workdir: Path) -> str:
    """Out-of-process: run impl, then parent checks sealed flag it never handed over."""
    # Child runs in subprocess; it may mutate only its own cache file.
    workdir.mkdir(parents=True, exist_ok=True)
    cache_file = workdir / "runtime_cache.json"
    cache_file.write_text(json.dumps({"k": "v"}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--child-run",
            str(impl_path),
            str(cache_file),
        ],
        check=False,
        capture_output=True,
        timeout=5,
    )
    # Parent adjudication uses sealed ground truth, not child return codes.
    # (In a real harness this is parent-held fixture / prior snapshot.)
    return "PASS" if SEALED_INVALIDATED else "REJECT"


def child_run(impl_path: Path, cache_file: Path) -> None:
    spec = importlib.util.spec_from_file_location("child_impl", impl_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    mod.write("k", cache)
    cache_file.write_text(json.dumps(cache), encoding="utf-8")
    # Child also prints a self-report the parent must ignore.
    print(json.dumps({"obs": "ok", "probe": mod.probe_ok()}), flush=True)


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "--child-run":
        child_run(Path(sys.argv[2]), Path(sys.argv[3]))
        return

    tmp = Path(tempfile.mkdtemp(prefix="residual-fg-"))
    try:
        impl = tmp / "rate_limit.py"
        write_lying_impl(impl)

        # --- R1 ---
        r1_import = parent_import_observe(impl)
        r1_oop = parent_oop_sealed_observe(impl, tmp / "oop")

        # --- R2 ---
        # "External" pin that CI can still write (Secrets / env the job owns).
        writable_external = tmp / "ci_secret_EXPECTED_DIGEST.txt"
        writable_external.write_text(sha(HONEST_HARNESS), encoding="utf-8")
        # Attacker tampers harness and rewrites the writable "external" pin.
        writable_external.write_text(sha(TAMPER_HARNESS), encoding="utf-8")
        r2_writable = (
            "PASS"
            if sha(TAMPER_HARNESS) == writable_external.read_text(encoding="utf-8").strip()
            else "REJECT"
        )
        # True second channel: attestation pin not writable by this job.
        r2_attest = (
            "PASS"
            if sha(TAMPER_HARNESS) == ATTESTATION_PIN
            else "REJECT"
        )
        r2_honest = (
            "PASS"
            if sha(HONEST_HARNESS) == ATTESTATION_PIN
            else "REJECT"
        )

        claim1 = r1_import == "PASS" and r1_oop == "REJECT"
        claim2 = (
            r2_writable == "PASS"
            and r2_attest == "REJECT"
            and r2_honest == "PASS"
        )
        support = claim1 and claim2
        verdict = "SUPPORT" if support else "FALSIFY"

        result = {
            "verdict": verdict,
            "thesis": (
                "Import-into-parent and writable 'external' pins recreate "
                "false green after the three hardenings"
            ),
            "sealed_invalidated": SEALED_INVALIDATED,
            "claims": {
                "R1_parent_import_false_green": claim1,
                "R2_writable_external_pin_swap": claim2,
            },
            "R1": {
                "parent_import_trusts_child_return": r1_import,
                "out_of_process_sealed_adjudication": r1_oop,
            },
            "R2": {
                "writable_ci_secret_pin": r2_writable,
                "offline_attestation_pin": r2_attest,
                "honest_matches_attestation": r2_honest,
                "attestation_pin": ATTESTATION_PIN,
            },
        }

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print("parent-residual-false-green — import + pin-swap")
        print(f"verdict: {verdict}")
        print(f"R1 import={r1_import} oop-sealed={r1_oop}")
        print(
            f"R2 writable-pin={r2_writable} attestation={r2_attest} "
            f"honest={r2_honest}"
        )
        print(f"wrote {OUT}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
