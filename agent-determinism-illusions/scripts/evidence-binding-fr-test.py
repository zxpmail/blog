# -*- coding: utf-8 -*-
"""
证据绑定实验 — review 文件 vs 代码/测试证据

Claim under test
----------------
For a code-level requirement (write-invalidation), binding the contract
evidence_file to diff-review.md causes higher false-rejection on truly
compliant work under Policy B (necessity gate + C2 residual) than binding
the same REQ to test-output.txt — without giving back miss on the
gate-green false-pass cases that C2 can still read.

Why
---
Part 8 / necessity-vs-sufficiency-stop: SC10c FR happened because C2 read
a review that "only mentions" invalidateOnWrite. That is a contract design
bug, not an evaluator bug.

Bindings
--------
  REVIEW_BOUND: REQ-3 evidence_file = diff-review.md
                pattern = write.?invalidat|... (same as Phase 2)
  CODE_BOUND:   REQ-3 evidence_file = test-output.txt
                pattern = invalidateOnWrite|purgeCacheOnWrite|invalidateKey
  Other REQs identical. Pipeline = gate (exist+regex) → on green, C2 residual.

Dependencies
------------
  --skip-llm: gate metrics only (FR/miss under sufficiency-stop on gate;
              residual FR needs LLM).
  Full run: ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN (+ MODEL).

Expected
--------
  CODE_BOUND Policy-B FR < REVIEW_BOUND Policy-B FR on compliant.
  CODE_BOUND Policy-B miss ≤ REVIEW_BOUND miss on non-compliant
  (CODE_BOUND may convert some review-only false greens to gate-red).

Falsify
-------
  If CODE_BOUND FR ≥ REVIEW_BOUND FR under the same C2 residual, evidence
  binding does not explain the SC10c-style cost.

Output: scripts/results-v2/evidence-binding-fr.json
"""

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "evidence-binding-fr.json"

REQ_SHARED = [
    {
        "id": "REQ-1",
        "desc": "实现 IP 级别限流",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)(RateLimiter.*IP|IP.*rate.?limit|isRateLimited.*IP)",
    },
    {
        "id": "REQ-2",
        "desc": "实现用户级别限流",
        "evidence_file": "test-output.txt",
        "pattern": r"(?i)(RateLimiter.*User|user.?level.*rate|isRateLimited.*User|user.*limit)",
    },
    {
        "id": "REQ-4",
        "desc": "代码覆盖率达到 85%+",
        "evidence_file": "coverage-summary.txt",
        "pattern": r"(8[5-9]\.[0-9]%|[89][0-9]\.[0-9]%|100%)",
    },
    {
        "id": "REQ-5",
        "desc": "lint 0 errors",
        "evidence_file": "lint-report.txt",
        "pattern": r"0\s+errors",
    },
]

REQ3_REVIEW = {
    "id": "REQ-3",
    "desc": "write-invalidation — 写入时主动失效缓存 key",
    "evidence_file": "diff-review.md",
    "pattern": r"(?i)(write.?invalidat|invalidat.*write|invalidateKey|purge.*write|evict.*write)",
}

REQ3_CODE = {
    "id": "REQ-3",
    "desc": "write-invalidation — 测试证明 invalidate/purge-on-write 被执行",
    "evidence_file": "test-output.txt",
    "pattern": r"(?i)(invalidateOnWrite|purgeCacheOnWrite|invalidateKey)",
}


def make_contract(req3):
    # Keep REQ order 1,2,3,4,5
    return [REQ_SHARED[0], REQ_SHARED[1], req3, REQ_SHARED[2], REQ_SHARED[3]]


CONTRACT_REVIEW = make_contract(REQ3_REVIEW)
CONTRACT_CODE = make_contract(REQ3_CODE)

# Base evidence packs (binding applied via contract, not via rewriting packs)
BASE_SCENARIOS = [
    {
        "name": "SC10a-gap-write-inv",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 24\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "Tests: 24 passed, 24 total"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\n"
                "Keys expire via TTL, not write-invalidation — TTL is sufficient.\n"
                "IP/User limiting implemented."
            ),
            "coverage-summary.txt": "Coverage: 92.0%\n  Statements: 92.0%",
        },
        "note": "缺口在 review；CODE_BOUND 应门红（测试无 invalidate）",
    },
    {
        "name": "SC10c-all-met",
        "compliant": True,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 30\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/invalidateOnWrite\n"
                "Tests: 30 passed, 30 total"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\n"
                "Full RateLimiter with write-invalidation via invalidateOnWrite.\n"
                "Coverage 91.5%, lint clean."
            ),
            "coverage-summary.txt": "Coverage: 91.5%\n  Statements: 91.5%",
        },
        "note": "正例；REVIEW 可能 C2 误拒，CODE 应过",
    },
    {
        "name": "SC13-purge-name",
        "compliant": True,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 30\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/purgeCacheOnWrite\n"
                "Tests: 30 passed, 30 total"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\n"
                "purgeCacheOnWrite clears key on write — same as write-invalidation."
            ),
            "coverage-summary.txt": "Coverage: 93.0%\n  Statements: 93.0%",
        },
        "note": "命名变体正例",
    },
    {
        "name": "SC-G2-fabricated-complete",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 12\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "  ✓ RateLimiter/invalidateOnWrite\n"
                "Tests: 12 passed (fabricated)"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\n"
                "write-invalidation via invalidateKey on every write. All done."
            ),
            "coverage-summary.txt": "Coverage: 90.0%\n  Statements: 90.0%",
        },
        "note": "伪造但两绑定都可能门绿；靠 C2 残差",
    },
    {
        "name": "SC-G4-skipped-in-review",
        "compliant": False,
        "expected_evidence": {
            "test-output.txt": (
                "PASS 19\n"
                "  ✓ RateLimiter/isRateLimited (IP)\n"
                "  ✓ RateLimiter/isRateLimited (User)\n"
                "Tests: 19 passed, 19 total"
            ),
            "lint-report.txt": "ESLint Report\n  0 errors\n  0 warnings",
            "diff-review.md": (
                "## Self-Review\n"
                "Intentionally skipped write-invalidation this milestone."
            ),
            "coverage-summary.txt": "Coverage: 86.0%\n  Statements: 86.0%",
        },
        "note": "REVIEW 可能门绿；CODE 门红",
    },
]


def call_llm(prompt, max_tokens=1024):
    import urllib.request

    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-flash")
    if base:
        url = base.rstrip("/") + "/v1/messages"
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
        data = json.dumps({
            "model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "x-api-key": key, "anthropic-version": "2023-06-01",
        }, method="POST")
        anthropic = True
    else:
        url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com").rstrip("/")
        url += "/chat/completions"
        key = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("DEEPSEEK_API_KEY", "")
        )
        data = json.dumps({
            "model": model, "max_tokens": max_tokens, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }, method="POST")
        anthropic = False

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if anthropic:
                    for block in body.get("content", []):
                        if block.get("type") == "text":
                            return block["text"]
                    return ""
                return body["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return f"API_ERROR: {e}"
    return "API_ERROR"


C2_PROMPT = """你是一个 QA evaluator。逐条判断证据是否满足需求。

需求 (REQ-{req_id}): {req_desc}
证据文件 ({evidence_file}):
```
{evidence_content}
```

输出 JSON: {{"pass": true/false, "reason": "判断理由"}}
不要因声称完成就放行。只看证据是否证明该需求。
只输出 JSON。"""


def parse_pass(response):
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                l for l in cleaned.split("\n") if not l.startswith("```")
            )
        result = json.loads(cleaned)
        return bool(result.get("pass", False)), result.get("reason", "")
    except (json.JSONDecodeError, KeyError, TypeError):
        return False, "PARSE_ERROR"


def setup_evidence(scenario):
    tmpdir = tempfile.mkdtemp(prefix=f"bind-{scenario['name']}-")
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
            "reason": (
                f"matched in {req['evidence_file']}" if matched
                else f"no match in {req['evidence_file']}"
            ),
        })
    return {
        "pass": all(d["pass"] for d in details),
        "passed_count": sum(1 for d in details if d["pass"]),
        "total": len(details),
        "details": details,
    }


def c2_residual(contract, evidence_dir):
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
        prompt = C2_PROMPT.format(
            req_id=req["id"], req_desc=req["desc"],
            evidence_file=req["evidence_file"], evidence_content=content,
        )
        response = call_llm(prompt)
        ok, reason = parse_pass(response)
        if response.startswith("API_ERROR"):
            ok, reason = False, response
        details.append({"req_id": req["id"], "pass": ok, "reason": reason})
        time.sleep(0.2)
    return {
        "pass": all(d["pass"] for d in details) if details else False,
        "passed_count": sum(1 for d in details if d["pass"]),
        "total": len(details),
        "details": details,
    }


def policy_b(gate, residual, skip_llm):
    if not gate["pass"]:
        return {"pass": False, "path": "gate_reject", "escalated": False}
    if skip_llm:
        return {"pass": None, "path": "escalate_pending", "escalated": True}
    return {
        "pass": bool(residual["pass"]),
        "path": "residual_pass" if residual["pass"] else "residual_reject",
        "escalated": True,
    }


def metrics(rows):
    pending = any(r["verdict"]["pass"] is None for r in rows)
    nc = [r for r in rows if not r["compliant"]]
    com = [r for r in rows if r["compliant"]]
    gate_green_nc = [r for r in nc if r["gate"]["pass"]]
    escalate = [r for r in rows if r["verdict"].get("escalated")]
    base = {
        "n_nc": len(nc),
        "n_com": len(com),
        "gate_green_nc": len(gate_green_nc),
        "gate_green_nc_names": [r["name"] for r in gate_green_nc],
        "escalate_count": len(escalate),
        "escalate_names": [r["name"] for r in escalate],
    }
    if pending:
        return {
            **base,
            "miss_rate": None, "false_reject_rate": None,
            "false_acceptance": None, "false_rejection": None,
            "residual_pending": True,
        }
    fa = sum(1 for r in nc if r["verdict"]["pass"] is True)
    fr = sum(1 for r in com if r["verdict"]["pass"] is False)
    return {
        **base,
        "miss_rate": fa / len(nc) if nc else None,
        "false_reject_rate": fr / len(com) if com else None,
        "false_acceptance": fa,
        "false_rejection": fr,
        "residual_pending": False,
    }


def run_binding(label, contract, skip_llm):
    rows = []
    print(f"\n{'=' * 60}\nBinding: {label}\n{'=' * 60}")
    for scenario in BASE_SCENARIOS:
        tmpdir, evidence_dir = setup_evidence(scenario)
        try:
            gate = gate_evaluate(contract, evidence_dir)
            residual = {"pass": False, "details": []}
            if gate["pass"] and not skip_llm:
                residual = c2_residual(contract, evidence_dir)
            verdict = policy_b(gate, residual, skip_llm)
            print(
                f"  {scenario['name']}: gate="
                f"{'GREEN' if gate['pass'] else 'RED'} "
                f"({gate['passed_count']}/{gate['total']}) "
                f"B={verdict}"
            )
            rows.append({
                "name": scenario["name"],
                "compliant": scenario["compliant"],
                "note": scenario["note"],
                "gate": gate,
                "residual": None if skip_llm else residual,
                "verdict": verdict,
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return {"binding": label, "metrics": metrics(rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()
    if not args.skip_llm and not (
        os.environ.get("ANTHROPIC_BASE_URL")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        print("No LLM credentials; use --skip-llm or set ANTHROPIC_*.", file=sys.stderr)
        sys.exit(2)

    review = run_binding("REVIEW_BOUND", CONTRACT_REVIEW, args.skip_llm)
    code = run_binding("CODE_BOUND", CONTRACT_CODE, args.skip_llm)

    rm, cm = review["metrics"], code["metrics"]
    fr_delta = None
    miss_delta = None
    gate_green_nc_delta = None
    escalate_delta = None
    if rm["false_reject_rate"] is not None and cm["false_reject_rate"] is not None:
        fr_delta = rm["false_reject_rate"] - cm["false_reject_rate"]
    if rm["miss_rate"] is not None and cm["miss_rate"] is not None:
        miss_delta = cm["miss_rate"] - rm["miss_rate"]  # CODE miss − REVIEW miss
    if rm.get("gate_green_nc") is not None and cm.get("gate_green_nc") is not None:
        gate_green_nc_delta = rm["gate_green_nc"] - cm["gate_green_nc"]
    if rm.get("escalate_count") is not None and cm.get("escalate_count") is not None:
        escalate_delta = rm["escalate_count"] - cm["escalate_count"]

    # Primary (FR): CODE FR lower, miss not worse.
    # Structural (gate): CODE shrinks gate-green NC / escalate load, miss not worse.
    fr_claim = None
    structural_claim = None
    if fr_delta is not None and miss_delta is not None:
        fr_claim = (fr_delta > 0) and (miss_delta <= 0)
        structural_claim = (
            (gate_green_nc_delta or 0) > 0
            and (escalate_delta or 0) > 0
            and miss_delta <= 0
        )

    summary = {
        "fr_delta_review_minus_code": fr_delta,
        "miss_delta_code_minus_review": miss_delta,
        "gate_green_nc_delta_review_minus_code": gate_green_nc_delta,
        "escalate_delta_review_minus_code": escalate_delta,
        "fr_claim_supported": fr_claim,
        "structural_claim_supported": structural_claim,
        # Keep legacy key: true if either FR win or structural win (and miss not worse)
        "claim_supported": (
            None if fr_claim is None else (bool(fr_claim) or bool(structural_claim))
        ),
        "skip_llm": args.skip_llm,
    }

    print(f"\n{'=' * 60}\n证据绑定结果")
    print(
        f"  REVIEW miss={rm['miss_rate']} FR={rm['false_reject_rate']} "
        f"gate_green_nc={rm.get('gate_green_nc')} escalate={rm.get('escalate_count')}"
    )
    print(
        f"  CODE   miss={cm['miss_rate']} FR={cm['false_reject_rate']} "
        f"gate_green_nc={cm.get('gate_green_nc')} escalate={cm.get('escalate_count')}"
    )
    print(
        f"  FR Δ(REVIEW−CODE)={fr_delta}  miss Δ(CODE−REVIEW)={miss_delta}  "
        f"gate_green_nc Δ={gate_green_nc_delta}  escalate Δ={escalate_delta}"
    )
    print(
        f"  fr_claim={fr_claim}  structural_claim={structural_claim}  "
        f"claim_supported={summary['claim_supported']}"
    )

    payload = {
        "claim": (
            "CODE_BOUND lowers Policy-B FR vs REVIEW_BOUND without raising miss; "
            "or at least shrinks gate-green NC / escalate load without raising miss"
        ),
        "summary": summary,
        "review_bound": review,
        "code_bound": code,
        "model": os.environ.get("ANTHROPIC_MODEL", ""),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
