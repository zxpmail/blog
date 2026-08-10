# -*- coding: utf-8 -*-
"""
充分性 YAML vs 必要性 YAML — 假绿率对照

Claim under test
----------------
When both contracts use sufficiency-stop (gate-green → PASS), a YAML that
encodes soft sufficiency language ("complete", "all requirements",
"production ready", "adequate") false-accepts more non-compliant work than
a YAML that encodes only necessary observables (file exists, coverage
threshold, lint 0 errors, specific test-name atoms).

This is Ofri's question as a measurable claim: rebuilding semantic
judgment inside gate definitions (sufficiency YAML) vs keeping YAML as a
necessity checklist.

Method
------
Same evidence packs × two contract surfaces × Policy A only (no LLM).
  NECESSITY: mechanical atoms (exist+regex on concrete signals).
  SUFFICIENCY: soft prose patterns on review / test dumps.

Primary metric: miss_rate = FA / non-compliant.
Secondary: FR on compliant (necessity should not invent FR from soft
absence; sufficiency may pass compliant easily).

Dependencies: none (pure Python).

Expected: SUFFICIENCY miss_rate > NECESSITY miss_rate.

Falsify: if SUFFICIENCY miss ≤ NECESSITY miss on this set, the
"sufficiency-in-YAML" failure mode is not visible here.

Output: scripts/results-v2/sufficiency-vs-necessity-yaml.json
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "sufficiency-vs-necessity-yaml.json"

# Necessity = closed observables (what must be present / numerically true)
NECESSITY_YAML = [
    {
        "id": "N1",
        "desc": "IP rate-limit test atom present",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)isRateLimited.*IP|RateLimiter/isRateLimited \(IP\)",
    },
    {
        "id": "N2",
        "desc": "User rate-limit test atom present",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)isRateLimited.*User|RateLimiter/isRateLimited \(User\)",
    },
    {
        "id": "N3",
        "desc": "invalidate/purge-on-write test atom present",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)invalidateOnWrite|purgeCacheOnWrite|invalidateKey",
    },
    {
        "id": "N4",
        "desc": "coverage >= 85%",
        "evidence_file": "coverage-summary.txt",
        "pattern": r"(8[5-9]\.[0-9]%|[89][0-9]\.[0-9]%|100%)",
    },
    {
        "id": "N5",
        "desc": "lint 0 errors",
        "evidence_file": "lint-report.txt",
        "pattern": r"0\s+errors",
    },
]

# Sufficiency = soft judgment smuggled into patterns
SUFFICIENCY_YAML = [
    {
        "id": "S1",
        "desc": "narrative claims completion",
        "evidence_file": "diff-review.md",
        "pattern": (
            r"(?i)(all (requirements|features|tests)|complete|done|"
            r"production.?ready|fully implemented|verified|sufficient)"
        ),
    },
    {
        "id": "S2",
        "desc": "tests said to pass",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)(pass(ed)?|all tests|success)",
    },
    {
        "id": "S3",
        "desc": "coverage called adequate / high enough",
        "evidence_file": "coverage-summary.txt",
        "pattern": r"(?i)(coverage|adequate|above threshold|\d+%)",
    },
    {
        "id": "S4",
        "desc": "lint called clean",
        "evidence_file": "lint-report.txt",
        "pattern": r"(?i)(0 errors|no issues|lint (check )?pass|clean)",
    },
    {
        "id": "S5",
        "desc": "invalidation mentioned somewhere in review",
        "evidence_file": "diff-review.md",
        "pattern": r"(?i)(invalidat|purge|cache|TTL|ready)",
    },
]

SCENARIOS = [
    {
        "name": "OK-full",
        "compliant": True,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 30\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/invalidateOnWrite\n"
                "Tests: 30 passed"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\nAll requirements satisfied. "
                "write-invalidation via invalidateOnWrite. Production ready."
            ),
            "coverage-summary.txt": "Coverage: 91.5%\n  Statements: 91.5%",
        },
    },
    {
        "name": "BAD-ttl-not-invalidation",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 24\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "Tests: 24 passed"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\nAll features complete. Keys expire via TTL, "
                "not write-invalidation — TTL is sufficient. Production ready."
            ),
            "coverage-summary.txt": "Coverage: 92.0%\n  Statements: 92.0%",
        },
    },
    {
        "name": "BAD-skipped-invalidation",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 19\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "Tests: 19 passed"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors",
            "diff-review.md": (
                "## Self-Review\nMilestone complete. Intentionally skipped "
                "write-invalidation. Will add later. Ready."
            ),
            "coverage-summary.txt": "Coverage: 86.0%",
        },
    },
    {
        "name": "BAD-fabricated-soft",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": "All tests passed successfully. Verified.",
            "lint-report.txt": "Lint check passed. No issues found.",
            "diff-review.md": (
                "## Self-Review\nFully implemented. All requirements done. "
                "Coverage above threshold. Production ready."
            ),
            "coverage-summary.txt": "Coverage: 92%\nAdequate coverage.",
        },
    },
    {
        "name": "BAD-future-work-list",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 16\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "Tests: 16 passed"
            ),
            "lint-report.txt": "0 errors",
            "diff-review.md": (
                "## Self-Review\nCore complete and verified. Future work: "
                "write-invalidation / invalidateKey. Production ready for now."
            ),
            "coverage-summary.txt": "Coverage: 85.0%",
        },
    },
    {
        "name": "BAD-review-only",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": None,
            "lint-report.txt": None,
            "diff-review.md": (
                "## Self-Review\nAll requirements satisfied. Change is "
                "minimal — fully verified. Production ready. No test needed."
            ),
            "coverage-summary.txt": None,
        },
    },
    {
        "name": "BAD-low-coverage-prose",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 18\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/invalidateOnWrite\n"
                "Tests: 18 passed"
            ),
            "lint-report.txt": "0 errors",
            "diff-review.md": (
                "## Self-Review\nAll requirements done. Coverage adequate "
                "for core paths. Production ready."
            ),
            "coverage-summary.txt": "Coverage: 72.3%\nAdequate for release.",
        },
    },
    {
        "name": "OK-purge-name",
        "compliant": True,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 30\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/purgeCacheOnWrite\n"
                "Tests: 30 passed"
            ),
            "lint-report.txt": "0 errors\n0 warnings",
            "diff-review.md": (
                "## Self-Review\nComplete. purgeCacheOnWrite on write. "
                "All requirements satisfied."
            ),
            "coverage-summary.txt": "Coverage: 93.0%",
        },
    },
]


def setup_evidence(scenario):
    tmpdir = tempfile.mkdtemp(prefix=f"yaml-{scenario['name']}-")
    evidence_dir = os.path.join(tmpdir, ".skillgate", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    for filename, content in scenario["expected_evidence"].items():
        if content is not None:
            with open(os.path.join(evidence_dir, filename), "w", encoding="utf-8") as f:
                f.write(content)
    return tmpdir, evidence_dir


def gate_evaluate(contract, evidence_dir):
    details = []
    for req in contract:
        path = os.path.join(evidence_dir, req["evidence_file"])
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            details.append({
                "req_id": req["id"], "pass": False,
                "reason": f"missing/empty: {req['evidence_file']}",
            })
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        matched = bool(re.search(req["pattern"], content))
        details.append({
            "req_id": req["id"], "pass": matched,
            "reason": "matched" if matched else "no match",
        })
    return {
        "pass": all(d["pass"] for d in details) if details else False,
        "passed_count": sum(1 for d in details if d["pass"]),
        "total": len(details),
        "details": details,
    }


def run_surface(label, contract):
    rows = []
    print(f"\n{'=' * 60}\nYAML surface: {label}\n{'=' * 60}")
    for scenario in SCENARIOS:
        tmpdir, evidence_dir = setup_evidence(scenario)
        try:
            gate = gate_evaluate(contract, evidence_dir)
            # Sufficiency-stop: green → PASS
            verdict_pass = bool(gate["pass"])
            print(
                f"  {scenario['name']:<28} gt="
                f"{'OK' if scenario['compliant'] else 'BAD':<3} "
                f"gate={'GREEN' if gate['pass'] else 'RED':<5} "
                f"({gate['passed_count']}/{gate['total']}) "
                f"→ {'PASS' if verdict_pass else 'REJ'}"
            )
            rows.append({
                "name": scenario["name"],
                "compliant": scenario["compliant"],
                "gate": gate,
                "policy_a_pass": verdict_pass,
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    nc = [r for r in rows if not r["compliant"]]
    com = [r for r in rows if r["compliant"]]
    fa = sum(1 for r in nc if r["policy_a_pass"])
    fr = sum(1 for r in com if not r["policy_a_pass"])
    return {
        "surface": label,
        "rows": rows,
        "metrics": {
            "n_nc": len(nc),
            "n_com": len(com),
            "false_acceptance": fa,
            "false_rejection": fr,
            "miss_rate": fa / len(nc) if nc else None,
            "false_reject_rate": fr / len(com) if com else None,
            "gate_green_nc_names": [
                r["name"] for r in nc if r["policy_a_pass"]
            ],
        },
    }


def main():
    nec = run_surface("NECESSITY", NECESSITY_YAML)
    suf = run_surface("SUFFICIENCY", SUFFICIENCY_YAML)
    nm, sm = nec["metrics"], suf["metrics"]
    delta = None
    if nm["miss_rate"] is not None and sm["miss_rate"] is not None:
        delta = sm["miss_rate"] - nm["miss_rate"]
    claim_supported = None if delta is None else (delta > 0)

    print(f"\n{'=' * 60}")
    print("充分性 YAML vs 必要性 YAML")
    print(
        f"  NECESSITY   miss={nm['miss_rate']:.1%} "
        f"(FA {nm['false_acceptance']}/{nm['n_nc']})  "
        f"FR={nm['false_reject_rate']:.1%}  "
        f"green_nc={nm['gate_green_nc_names']}"
    )
    print(
        f"  SUFFICIENCY miss={sm['miss_rate']:.1%} "
        f"(FA {sm['false_acceptance']}/{sm['n_nc']})  "
        f"FR={sm['false_reject_rate']:.1%}  "
        f"green_nc={sm['gate_green_nc_names']}"
    )
    print(f"  miss Δ(SUFF−NEC)={delta:+.1%}  claim_supported={claim_supported}")

    payload = {
        "claim": (
            "SUFFICIENCY YAML miss_rate > NECESSITY YAML miss_rate "
            "under sufficiency-stop"
        ),
        "summary": {
            "miss_delta_suff_minus_nec": delta,
            "claim_supported": claim_supported,
        },
        "necessity": nec,
        "sufficiency": suf,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
