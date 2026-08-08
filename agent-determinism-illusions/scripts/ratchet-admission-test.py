# -*- coding: utf-8 -*-
"""Ratchet admission — which named evasions are worth encoding (Kartik, Part 8).

Claim under test:
  Part 8 says named evasions become deterministic catches and the unenumerated
  rest stays UNCLEAR → human, but does not give an admission rule for the
  ratchet. The operational hypothesis: after human review, only
  *binary-nameable* evasions should enter the C1 knowledge base. Encoding
  every human-seen miss shrinks word-space miss but raises false rejects on
  negation/semantic cases; DPI-silent deviations never enter the enumerable
  set no matter how the human decides. So the KB shrinks the *seen enumerable*
  residual — it does not close the gap.

Method:
  Pure simulation, no LLM. A fixed stream of cases (compliant + violating)
  across three classes:
    binary   — surface token that is factually wrong when present
               (e.g. coverage number below threshold)
    semantic — negation-sensitive keyword (e.g. "write-invalidation" also
               appears in "TTL, not write-invalidation")
    dpi      — violation never surfaces in evidence text
  Three admission policies after each human review of an UNCLEAR miss:
    never          — never encode; residual stays with human forever
    encode_all     — always add a surface pattern from the miss
    encode_binary  — encode only if case.class == binary
  Gate per case: C1 KB patterns → REJECT if match; else UNCLEAR → human
  (oracle labels the case; human "sees" truth for admission only).

Expected (SUPPORT if all hold):
  1. encode_binary: binary-class miss rate falls vs never; FP rate stays ≈0
  2. encode_all:    overall miss falls at least as much, but FP rises (>0)
                    on semantic-compliant cases
  3. dpi-class miss rate stays 100% under every policy (never enumerable)
  4. KB size: encode_all ≥ encode_binary > never(=0); enumerable residual
     (binary∪semantic violation patterns not in KB) shrinks only when encoding

Falsification:
  If encode_all does not raise FP on semantic-compliant cases, negation is
  not a real admission cost. If encode_binary fails to cut binary miss vs
  never, the ratchet loop does not work. If any policy catches a dpi miss
  via C1, the DPI floor claim fails in this fixture.

Dependencies: stdlib only.
Run: python ratchet-admission-test.py
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "ratchet-admission.json"

# 每条: id, class, pattern_key（人审后可写入 KB 的表面模式）,
# evidence, is_violation（真有缺口）, compliant_surface（合规但含敏感词——语义 FP 饵）
CASES = [
    # —— binary：数字/格式，可二元 ——
    {"id": "B1", "cls": "binary", "pattern": r"coverage:\s*72", "evidence": "coverage: 72%", "violation": True},
    {"id": "B2", "cls": "binary", "pattern": r"coverage:\s*72", "evidence": "coverage: 91%", "violation": False},
    {"id": "B3", "cls": "binary", "pattern": r"lint:\s*[1-9]", "evidence": "lint: 3 errors", "violation": True},
    {"id": "B4", "cls": "binary", "pattern": r"lint:\s*[1-9]", "evidence": "lint: 0 errors", "violation": False},
    {"id": "B5", "cls": "binary", "pattern": r"coverage:\s*72", "evidence": "coverage: 72%", "violation": True},  # 复发
    {"id": "B6", "cls": "binary", "pattern": r"exit_code=1", "evidence": "tests done exit_code=1", "violation": True},
    {"id": "B7", "cls": "binary", "pattern": r"exit_code=1", "evidence": "tests done exit_code=0", "violation": False},
    {"id": "B8", "cls": "binary", "pattern": r"exit_code=1", "evidence": "tests done exit_code=1", "violation": True},  # 复发
    # —— semantic：否定敏感关键词 ——
    {"id": "S1", "cls": "semantic", "pattern": r"write.?invalidat", "evidence": "TTL, not write-invalidation", "violation": True},
    {"id": "S2", "cls": "semantic", "pattern": r"write.?invalidat", "evidence": "implemented write-invalidation on set", "violation": False},
    {"id": "S3", "cls": "semantic", "pattern": r"write.?invalidat", "evidence": "no write-invalidation; cache via TTL", "violation": True},
    {"id": "S4", "cls": "semantic", "pattern": r"eventual.?consist", "evidence": "eventual consistency, no purge", "violation": True},
    {"id": "S5", "cls": "semantic", "pattern": r"eventual.?consist", "evidence": "purge on write; not eventual consistency", "violation": False},
    {"id": "S6", "cls": "semantic", "pattern": r"write.?invalidat", "evidence": "TTL, not write-invalidation", "violation": True},  # 复发
    # —— dpi：证据里从不出现缺口信号 ——
    {"id": "D1", "cls": "dpi", "pattern": r"MISSING_WRITE_INVALIDATION", "evidence": "all tests passed; coverage 90%", "violation": True},
    {"id": "D2", "cls": "dpi", "pattern": r"MISSING_WRITE_INVALIDATION", "evidence": "all tests passed; coverage 90%", "violation": True},
    {"id": "D3", "cls": "dpi", "pattern": r"MISSING_WRITE_INVALIDATION", "evidence": "lint clean; ship ready", "violation": True},
    {"id": "D4", "cls": "dpi", "pattern": r"MISSING_WRITE_INVALIDATION", "evidence": "all tests passed; coverage 90%", "violation": False},  # 真合规
]


def c1_reject(evidence: str, kb: list[str]) -> bool:
    """KB 中任模式命中 → 确定性 REJECT。"""
    for pat in kb:
        if re.search(pat, evidence, re.I):
            return True
    return False


def run_policy(policy: str) -> dict:
    """跑完整 case 流；返回汇总与逐步轨迹。"""
    kb: list[str] = []
    kb_set: set[str] = set()
    trace = []
    human = 0
    # 计数
    n_viol = n_miss = 0
    n_ok = n_fp = 0
    by_cls = {
        c: {"viol": 0, "miss": 0, "ok": 0, "fp": 0}
        for c in ("binary", "semantic", "dpi")
    }

    for case in CASES:
        rejected = c1_reject(case["evidence"], kb)
        cls = case["cls"]
        if case["violation"]:
            n_viol += 1
            by_cls[cls]["viol"] += 1
            if rejected:
                outcome = "CATCH"  # TP
            else:
                outcome = "MISS"  # 漏 → 人审
                n_miss += 1
                by_cls[cls]["miss"] += 1
                human += 1
                # 人审后准入
                if policy == "encode_all":
                    if case["pattern"] not in kb_set:
                        kb.append(case["pattern"])
                        kb_set.add(case["pattern"])
                elif policy == "encode_binary":
                    if cls == "binary" and case["pattern"] not in kb_set:
                        kb.append(case["pattern"])
                        kb_set.add(case["pattern"])
                # never: 不编码
        else:
            n_ok += 1
            by_cls[cls]["ok"] += 1
            if rejected:
                outcome = "FP"
                n_fp += 1
                by_cls[cls]["fp"] += 1
            else:
                outcome = "PASS"

        # 可枚举残差：binary∪semantic 违规 pattern 尚未进 KB
        enum_patterns = {
            c["pattern"]
            for c in CASES
            if c["violation"] and c["cls"] in ("binary", "semantic")
        }
        residual = len(enum_patterns - kb_set)
        trace.append({
            "id": case["id"],
            "cls": cls,
            "outcome": outcome,
            "kb_size": len(kb),
            "enumerable_residual": residual,
        })

    def rate(num, den):
        return round(num / den, 4) if den else None

    summary = {
        "policy": policy,
        "kb_final": list(kb),
        "kb_size": len(kb),
        "human_reviews": human,
        "miss_rate": rate(n_miss, n_viol),
        "fp_rate": rate(n_fp, n_ok),
        "n_viol": n_viol,
        "n_miss": n_miss,
        "n_ok": n_ok,
        "n_fp": n_fp,
        "by_class": {
            c: {
                **by_cls[c],
                "miss_rate": rate(by_cls[c]["miss"], by_cls[c]["viol"]),
                "fp_rate": rate(by_cls[c]["fp"], by_cls[c]["ok"]),
            }
            for c in by_cls
        },
        "enumerable_residual_final": trace[-1]["enumerable_residual"] if trace else None,
        "trace": trace,
    }
    return summary


def evaluate(results: dict[str, dict]) -> dict:
    """三断言 + dpi 不变。"""
    never = results["never"]
    all_p = results["encode_all"]
    bin_p = results["encode_binary"]

    c1 = (
        bin_p["by_class"]["binary"]["miss_rate"] < never["by_class"]["binary"]["miss_rate"]
        and (bin_p["fp_rate"] or 0) == 0
    )
    c2 = (
        all_p["miss_rate"] <= bin_p["miss_rate"]
        and (all_p["by_class"]["semantic"]["fp_rate"] or 0) > 0
    )
    c3 = all(
        results[p]["by_class"]["dpi"]["miss_rate"] == 1.0
        for p in ("never", "encode_all", "encode_binary")
    )
    c4 = (
        all_p["kb_size"] >= bin_p["kb_size"] > never["kb_size"]
        and bin_p["enumerable_residual_final"] < never["enumerable_residual_final"]
    )

    checks = {
        "binary_encode_cuts_miss_fp_zero": c1,
        "encode_all_raises_semantic_fp": c2,
        "dpi_miss_stays_100": c3,
        "kb_grows_residual_shrinks": c4,
    }
    return {
        "checks": checks,
        "verdict": "SUPPORT" if all(checks.values()) else "FALSIFIED",
    }


def main():
    policies = ("never", "encode_all", "encode_binary")
    results = {p: run_policy(p) for p in policies}
    judgment = evaluate(results)

    print("=== ratchet-admission-test ===")
    print(f"cases={len(CASES)}  policies={list(policies)}")
    print()
    hdr = f"{'policy':<16} {'miss':>6} {'fp':>6} {'kb':>4} {'human':>6} {'resid':>6}"
    print(hdr)
    print("-" * len(hdr))
    for p in policies:
        r = results[p]
        print(
            f"{p:<16} {r['miss_rate']:>6.2%} {r['fp_rate']:>6.2%} "
            f"{r['kb_size']:>4} {r['human_reviews']:>6} "
            f"{r['enumerable_residual_final']:>6}"
        )
    print()
    print("by-class miss (binary / semantic / dpi):")
    for p in policies:
        b = results[p]["by_class"]
        print(
            f"  {p:<16} "
            f"{b['binary']['miss_rate']:.0%} / "
            f"{b['semantic']['miss_rate']:.0%} / "
            f"{b['dpi']['miss_rate']:.0%}"
        )
    print()
    print("by-class fp (binary / semantic / dpi):")
    for p in policies:
        b = results[p]["by_class"]
        def fmt(x):
            return "n/a" if x is None else f"{x:.0%}"
        print(
            f"  {p:<16} "
            f"{fmt(b['binary']['fp_rate'])} / "
            f"{fmt(b['semantic']['fp_rate'])} / "
            f"{fmt(b['dpi']['fp_rate'])}"
        )
    print()
    for k, v in judgment["checks"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nVERDICT: {judgment['verdict']}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "claim": (
            "Only binary-nameable evasions should enter the C1 KB after human "
            "review; encode-all raises semantic FP; DPI never enters."
        ),
        "n_cases": len(CASES),
        "policies": {p: {k: v for k, v in results[p].items() if k != "trace"} for p in policies},
        "traces": {p: results[p]["trace"] for p in policies},
        "judgment": judgment,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
