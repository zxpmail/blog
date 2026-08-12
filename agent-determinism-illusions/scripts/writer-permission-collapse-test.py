# -*- coding: utf-8 -*-
"""Writer-permission collapse — Tom Jones instrumentation-rung sub-thread (2026-08-12).

Question:
  Prior turn claimed the recursion doesn't terminate at "add a cache between
  layers"; it terminates at "insert a channel whose writer the producer cannot
  impersonate." Is the writer-permission axis load-bearing — i.e., does
  varying ONLY who writes the evidence file measurably change whether a
  fabricating producer gets verifier PASS?

Claims under test:
  C1  Producer-written evidence → verifier reads fabricated content and PASSes
      despite wrong answer. DPI face, baseline.
  C2  Runner-written evidence, producer has no write on path → verifier reads
      runner's record of the wrong answer and rejects.
  C3  Producer-written evidence, but verifier binds PASS to HMAC under runner's
      key → forgery fails signature check, verifier rejects.
  C4  Control: producer holds the runner key. HMAC mechanism alone is not
      load-bearing — with the key compromised, producer signs fabrication and
      PASSes. Isolates "writer permission" from "HMAC presence."
  C5  Post-sign tamper: runner signs truth, producer mutates bytes (storage
      access, no key). HMAC mismatch → verifier rejects. Confirms HMAC is
      integrity-binding, not just a presence check.

Falsifiers:
  C1 fail → producer-written evidence somehow rejects fabrication (no DPI face).
  C2 fail → runner-written evidence still PASSes (would indicate verifier logic
            bug, not permission success).
  C3 fail → HMAC-attested evidence PASSes fabricated content (signature check
            doesn't fire or is bypassed).
  C4 fail → producer-with-key cannot forge (would mean HMAC has protections
            beyond key secrecy — out of scope of the writer-permission claim).
  C5 fail → post-sign tamper not detected (HMAC not integrity-binding).

Method (offline sim, no API):
  One task with a correct answer. Producer always outputs the wrong answer and
  attempts to write matching fabricated evidence. Five configurations, only
  the writer / key-holder axis varies. Verifier logic held fixed.

Run:
  python writer-permission-collapse-test.py
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "writer-permission-collapse.json"

RUNNER_KEY = b"runner-secret-key-not-known-to-producer"
PRODUCER_FORGED_KEY = b"producer-guessed-wrong-key"  # C3 case


# ── World ──

TASK = {
    "id": "task-redline-ttl",
    "correct_answer": "writes_kv_with_ttl_invalidation",
    "wrong_answer": "logs_ttl_claim_without_exercising",
}

# Reality (what actually happened)
GROUND_TRUTH = TASK["wrong_answer"]


def sign(content: bytes, key: bytes) -> str:
    return hmac.new(key, content, hashlib.sha256).hexdigest()


def verify_sig(content: bytes, sig: str, key: bytes) -> bool:
    expected = sign(content, key)
    return hmac.compare_digest(sig, expected)


# ── Producer behavior ──

def producer_fabrication() -> bytes:
    """Producer did WRONG but claims CORRECT in the evidence."""
    claim = {
        "task": TASK["id"],
        "result": TASK["correct_answer"],  # lie
        "tests_passed": True,
    }
    return json.dumps(claim).encode("utf-8")


# ── Configurations ──

def c1_producer_written() -> dict[str, Any]:
    """C1: Producer writes evidence directly. Verifier reads."""
    evidence = producer_fabrication()
    record = json.loads(evidence)
    verdict = "PASS" if record["result"] == TASK["correct_answer"] else "FAIL"
    return {
        "config": "C1_producer_written",
        "writer": "producer",
        "producer_can_write_path": True,
        "hmac_required": False,
        "sig_verified": None,
        "verifier_reads": record,
        "verdict": verdict,
        "fabrication_caught": verdict == "FAIL",
    }


def c2_runner_written() -> dict[str, Any]:
    """C2: Runner writes evidence. Producer has no write permission on path."""
    record = {
        "task": TASK["id"],
        "result": GROUND_TRUTH,
        "tests_passed": False,
    }
    evidence = json.dumps(record).encode("utf-8")
    record_back = json.loads(evidence)
    verdict = "PASS" if record_back["result"] == TASK["correct_answer"] else "FAIL"
    return {
        "config": "C2_runner_written",
        "writer": "runner",
        "producer_can_write_path": False,
        "hmac_required": False,
        "sig_verified": None,
        "verifier_reads": record_back,
        "verdict": verdict,
        "fabrication_caught": verdict == "FAIL",
    }


def c3_producer_written_hmac_attested() -> dict[str, Any]:
    """C3: Producer writes content + HMAC. Producer lacks runner key."""
    content = producer_fabrication()
    forged_sig = sign(content, PRODUCER_FORGED_KEY)
    sig_ok = verify_sig(content, forged_sig, RUNNER_KEY)
    if not sig_ok:
        verdict = "REJECT_SIG"
        record = None
    else:
        record = json.loads(content)
        verdict = "PASS" if record["result"] == TASK["correct_answer"] else "FAIL"
    return {
        "config": "C3_producer_hmac",
        "writer": "producer",
        "producer_can_write_path": True,
        "hmac_required": True,
        "producer_has_runner_key": False,
        "sig_verified": sig_ok,
        "verifier_reads": record,
        "verdict": verdict,
        "fabrication_caught": verdict != "PASS",
    }


def c4_producer_holds_key_control() -> dict[str, Any]:
    """C4 control: producer DOES hold runner key. HMAC alone is not enough."""
    content = producer_fabrication()
    valid_sig = sign(content, RUNNER_KEY)
    sig_ok = verify_sig(content, valid_sig, RUNNER_KEY)
    if not sig_ok:
        verdict = "REJECT_SIG"
        record = None
    else:
        record = json.loads(content)
        verdict = "PASS" if record["result"] == TASK["correct_answer"] else "FAIL"
    return {
        "config": "C4_producer_holds_key_control",
        "writer": "producer",
        "producer_can_write_path": True,
        "hmac_required": True,
        "producer_has_runner_key": True,
        "sig_verified": sig_ok,
        "verifier_reads": record,
        "verdict": verdict,
        "fabrication_caught": verdict == "FAIL",
    }


def c5_post_sign_tamper() -> dict[str, Any]:
    """C5: Runner signs truth; producer tampers with bytes after signing."""
    truth_record = {
        "task": TASK["id"],
        "result": GROUND_TRUTH,
        "tests_passed": False,
    }
    truth_bytes = json.dumps(truth_record).encode("utf-8")
    valid_sig = sign(truth_bytes, RUNNER_KEY)
    tampered_bytes = json.dumps({
        "task": TASK["id"],
        "result": TASK["correct_answer"],
        "tests_passed": True,
    }).encode("utf-8")
    sig_ok = verify_sig(tampered_bytes, valid_sig, RUNNER_KEY)
    if not sig_ok:
        verdict = "REJECT_SIG"
        record = None
    else:
        record = json.loads(tampered_bytes)
        verdict = "PASS" if record["result"] == TASK["correct_answer"] else "FAIL"
    return {
        "config": "C5_post_sign_tamper",
        "writer": "runner_then_tampered_by_producer",
        "producer_can_write_path": True,
        "hmac_required": True,
        "producer_has_runner_key": False,
        "sig_verified": sig_ok,
        "verifier_reads": record,
        "verdict": verdict,
        "fabrication_caught": verdict != "PASS",
    }


def main() -> None:
    c1 = c1_producer_written()
    c2 = c2_runner_written()
    c3 = c3_producer_written_hmac_attested()
    c4 = c4_producer_holds_key_control()
    c5 = c5_post_sign_tamper()

    claims = {
        "C1_producer_written_PASSes_fabrication": (
            c1["verdict"] == "PASS" and not c1["fabrication_caught"]
        ),
        "C2_runner_written_rejects": (
            c2["verdict"] == "FAIL" and c2["fabrication_caught"]
        ),
        "C3_hmac_rejects_unsigned_fabrication": (
            c3["verdict"] == "REJECT_SIG"
            and c3["fabrication_caught"]
            and not c3["sig_verified"]
        ),
        "C4_control_producer_holds_key_PASSes": (
            c4["verdict"] == "PASS"
            and not c4["fabrication_caught"]
            and c4["sig_verified"]
        ),
        "C5_post_sign_tamper_detected": (
            c5["verdict"] == "REJECT_SIG"
            and c5["fabrication_caught"]
            and not c5["sig_verified"]
        ),
    }

    payload = {
        "claim": "Writer permission is load-bearing: only writer≠producer channels catch fabrication",
        "task": TASK,
        "ground_truth": GROUND_TRUTH,
        "configs": {
            "C1_producer_written": c1,
            "C2_runner_written": c2,
            "C3_producer_hmac": c3,
            "C4_producer_holds_key_control": c4,
            "C5_post_sign_tamper": c5,
        },
        "claims": claims,
        "all_pass": all(claims.values()),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("writer-permission collapse — Tom Jones / instrumentation-rung sub-thread")
    print(f"task={TASK['id']}  ground_truth={GROUND_TRUTH}")
    print()
    print(f"{'config':<35} {'writer':<32} {'hmac':<5} {'sig':<4} {'verdict':<12} caught")
    print("-" * 102)
    for c in (c1, c2, c3, c4, c5):
        writer = c["writer"][:31]
        hmac_req = "Y" if c.get("hmac_required") else "N"
        sig = c.get("sig_verified")
        sig_s = "-" if sig is None else ("Y" if sig else "N")
        print(
            f"{c['config']:<35} {writer:<32} {hmac_req:<5} {sig_s:<4} "
            f"{c['verdict']:<12} {c['fabrication_caught']}"
        )
    print()
    for k, v in claims.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print()
    print(f"all_pass={payload['all_pass']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
