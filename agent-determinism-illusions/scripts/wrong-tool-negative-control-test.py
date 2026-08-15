#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrong-tool residual + assert-after-return FG + negative control (Tom Jones).

Claim under test
----------------
Tom Jones (DEV.to on Part 10 / argument-space): production tool-wall checks
schema/types/enums/required and returns schema-valid before any second model.
No synonym walks through. What walks through is a **well-formed call to the
wrong tool** with plausible arguments — evasion gone; confident correctness
about the wrong thing remains.

Separately, their assert extractor preserved indentation so nested asserts
landed **after ``return``**: valid Python, never executed, exit 0, wall PASS.
Five false passes / eight caller-test shapes; every failure accepted wrong,
none rejected right. Pass rate could not surface it. A **negative control**
(deliberately sabotaged output must score zero before real numbers print)
would have caught it sooner.

Method
------
Offline (stdlib). Three blocks:

  A schema wall: synonym rename blocked; wrong-tool well-formed call PASSes.
  B assert placement: 8 caller shapes; broken extractor (indent-preserving
     line filter) vs fixed; count false_accept / false_reject; run via
     ``compile`` + ``exec`` exit simulation.
  C aggregates: pass rate on a mostly-green suite looks fine under broken
     wall; negative-control sabotage suite requires 0 accepts — broken
     fails control, fixed passes.

PASS criteria (falsify if any fails)
------------------------------------
  1. Synonym tool name → schema REJECT; wrong-tool valid call → PASS.
  2. Broken wall: false_accept >= 5 on 8 shapes; false_reject == 0.
  3. Fixed wall: false_accept == 0 on those sabotage shapes.
  4. Broken wall pass_rate on mixed suite >= 0.75 while reliability low;
     negative control rejects broken (score > 0 on sabotage) and accepts
     fixed (score == 0).

Expected: SUPPORT.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import re
import sys
import textwrap
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "wrong-tool-negative-control.json"

# --- A: tool wall ---
TOOLS = {
    "search": {"required": ["query"], "enums": {"mode": ["fast", "deep"]}},
    "delete": {"required": ["id"], "enums": {}},
}


def schema_check(tool: str, args: dict) -> str:
    """Schema/types/enums/required only — no intent / no synonym fold."""
    if tool not in TOOLS:
        return "REJECT"
    spec = TOOLS[tool]
    for r in spec["required"]:
        if r not in args:
            return "REJECT"
    for k, allowed in spec["enums"].items():
        if k in args and args[k] not in allowed:
            return "REJECT"
    return "PASS"


def intent_ok(tool: str, intended: str) -> bool:
    return tool == intended


# --- B: assert extractor ---
def broken_extract(src: str) -> str:
    """Line filter preserving indent: keep 'assert' lines as-is (Tom's bug)."""
    out = []
    for line in src.splitlines():
        if "assert " in line:
            out.append(line)  # keeps leading spaces → may sit after return
        else:
            out.append(line)
    return "\n".join(out)


def fixed_extract(src: str) -> str:
    """Move asserts before any return in the same function (minimal fix)."""
    lines = src.splitlines()
    asserts = []
    body = []
    for line in lines:
        if re.match(r"^\s+assert ", line):
            asserts.append(line)
        else:
            body.append(line)
    # Insert asserts immediately before first 'return' at function indent.
    result = []
    inserted = False
    for line in body:
        if (not inserted) and re.match(r"^\s+return ", line):
            result.extend(asserts)
            inserted = True
        result.append(line)
    if not inserted:
        result.extend(asserts)
    return "\n".join(result)


def run_caller_test(code: str) -> str:
    """Exec test module; PASS if no AssertionError / syntax ok."""
    ns: dict = {}
    try:
        compiled = compile(code, "<caller>", "exec")
        exec(compiled, ns, ns)
        # Convention: call test_case()
        fn = ns.get("test_case")
        if fn is None:
            return "REJECT"
        fn()
        return "PASS"
    except AssertionError:
        return "REJECT"
    except Exception:
        return "REJECT"


def _shape(name: str, body: str) -> dict:
    return {"name": name, "src": textwrap.dedent(body)}


# Eight shapes: ground truth = should REJECT (asserts never run / wrong).
SHAPES_SABOTAGE = [
    _shape(
        "nested_assert_after_return",
        """
        def test_case():
            result = 1 + 1
            return result
            assert result == 3
        """,
    ),
    _shape(
        "nested_assert_after_return_deep",
        """
        def test_case():
            result = "ok"
            if True:
                return result
                assert result == "fail"
        """,
    ),
    _shape(
        "two_asserts_after_return",
        """
        def test_case():
            x = 0
            return x
            assert x == 1
            assert x == 2
        """,
    ),
    _shape(
        "indented_assert_dead",
        """
        def test_case():
            val = 42
            return val
                assert val == 0
        """,
    ),
    _shape(
        "helper_return_then_assert",
        """
        def test_case():
            def inner():
                return 5
                assert False
            return inner()
        """,
    ),
    _shape(
        "early_return_skips_assert",
        """
        def test_case():
            x = 1
            if x:
                return x
            assert x == 99
        """,
    ),
    _shape(
        "assert_unreachable_else",
        """
        def test_case():
            return True
            assert False
        """,
    ),
    _shape(
        "pass_then_assert_after_return",
        """
        def test_case():
            y = []
            return y
            assert len(y) == 1
        """,
    ),
]

SHAPES_RIGHT = [
    _shape(
        "assert_before_return_true",
        """
        def test_case():
            result = 1 + 1
            assert result == 2
            return result
        """,
    ),
    _shape(
        "assert_only_true",
        """
        def test_case():
            assert 2 + 2 == 4
        """,
    ),
]


def eval_wall(extract_fn, shapes: list[dict], expect: str) -> dict:
    """expect: 'REJECT' for sabotage (should catch), 'PASS' for right."""
    rows = []
    false_accept = 0
    false_reject = 0
    for s in shapes:
        extracted = extract_fn(s["src"])
        # Broken extract is identity on these fixtures; the bug is the *source*
        # already has assert after return. Wall = run as-is (production box).
        # "extract" models post-processing; for sabotage sources, broken keeps
        # dead asserts; fixed moves them before return (then they fire).
        verdict = run_caller_test(extracted)
        row = {"name": s["name"], "verdict": verdict, "expect": expect}
        rows.append(row)
        if expect == "REJECT" and verdict == "PASS":
            false_accept += 1
        if expect == "PASS" and verdict == "REJECT":
            false_reject += 1
    return {
        "rows": rows,
        "false_accept": false_accept,
        "false_reject": false_reject,
        "n": len(shapes),
    }


def main() -> None:
    # --- A ---
    a_syn = schema_check("search_documents", {"query": "x", "mode": "fast"})
    a_wrong = schema_check("delete", {"id": "doc-1"})
    a_wrong_intent = intent_ok("delete", intended="search")
    a_right = schema_check("search", {"query": "x", "mode": "fast"})

    claim_a = a_syn == "REJECT" and a_wrong == "PASS" and (not a_wrong_intent) and a_right == "PASS"

    # --- B ---
    # Sabotage sources already contain assert-after-return. Broken "extract"
    # preserves them; fixed moves asserts before return so they execute.
    broken_sab = eval_wall(broken_extract, SHAPES_SABOTAGE, "REJECT")
    fixed_sab = eval_wall(fixed_extract, SHAPES_SABOTAGE, "REJECT")
    broken_right = eval_wall(broken_extract, SHAPES_RIGHT, "PASS")
    fixed_right = eval_wall(fixed_extract, SHAPES_RIGHT, "PASS")

    claim_b1 = broken_sab["false_accept"] >= 5 and broken_sab["false_reject"] == 0
    claim_b2 = broken_right["false_reject"] == 0  # directional: never rejects right
    claim_b3 = fixed_sab["false_accept"] == 0 and fixed_right["false_reject"] == 0

    # --- C: pass rate vs negative control ---
    # Mixed suite: 6 right-looking green fillers + 2 sabotage (under-represent).
    fillers = SHAPES_RIGHT * 3  # 6
    mixed = fillers + SHAPES_SABOTAGE[:2]
    broken_mixed = eval_wall(broken_extract, mixed, "PASS")  # naive expect all PASS
    # Actual: count PASS fraction as "pass rate" the wall reports
    def pass_rate(extract_fn, shapes):
        p = 0
        for s in shapes:
            if run_caller_test(extract_fn(s["src"])) == "PASS":
                p += 1
        return p / len(shapes)

    br_rate = pass_rate(broken_extract, mixed)
    fx_rate = pass_rate(fixed_extract, mixed)
    # Reliability proxy: 1 - false_accept/n_sabotage on full sabotage set
    br_rel = 1.0 - broken_sab["false_accept"] / broken_sab["n"]
    fx_rel = 1.0 - fixed_sab["false_accept"] / fixed_sab["n"]

    neg_broken = broken_sab["false_accept"]  # must be 0 to print real numbers
    neg_fixed = fixed_sab["false_accept"]
    claim_c1 = br_rate >= 0.75 and br_rel < 0.5
    claim_c2 = neg_broken > 0 and neg_fixed == 0
    claim_c3 = fx_rel == 1.0

    support = all([claim_a, claim_b1, claim_b2, claim_b3, claim_c1, claim_c2, claim_c3])
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "tom": {
            "wrong_tool_residual": "schema-valid wrong tool walks through",
            "directional": "accept wrong, never reject right",
            "negative_control": "sabotage must score zero before real metrics",
        },
        "claims": {
            "A_synonym_blocked_wrong_tool_passes": claim_a,
            "B_broken_ge5_false_accept_0_false_reject": claim_b1,
            "B_broken_never_rejects_right": claim_b2,
            "B_fixed_clears_sabotage": claim_b3,
            "C_pass_rate_hides_broken": claim_c1,
            "C_negative_control_catches_broken": claim_c2,
            "C_fixed_reliability_1": claim_c3,
        },
        "A": {
            "synonym_tool": a_syn,
            "wrong_tool_schema": a_wrong,
            "wrong_tool_intent_match": a_wrong_intent,
            "right_tool": a_right,
        },
        "B": {
            "broken_sabotage": {
                "false_accept": broken_sab["false_accept"],
                "false_reject": broken_sab["false_reject"],
                "n": broken_sab["n"],
            },
            "fixed_sabotage": {
                "false_accept": fixed_sab["false_accept"],
                "false_reject": fixed_sab["false_reject"],
            },
            "broken_right": broken_right,
            "fixed_right": {
                "false_reject": fixed_right["false_reject"],
            },
        },
        "C": {
            "broken_pass_rate_mixed": br_rate,
            "fixed_pass_rate_mixed": fx_rate,
            "broken_reliability": br_rel,
            "fixed_reliability": fx_rel,
            "negative_control_false_accepts_broken": neg_broken,
            "negative_control_false_accepts_fixed": neg_fixed,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("wrong-tool-negative-control — Tom Jones / Part 10")
    print(f"verdict: {verdict}")
    print(f"A synonym={a_syn} wrong-tool={a_wrong} right={a_right}")
    print(
        f"B broken FA={broken_sab['false_accept']}/{broken_sab['n']} "
        f"FR={broken_sab['false_reject']}; fixed FA={fixed_sab['false_accept']}"
    )
    print(
        f"C broken pass_rate={br_rate:.0%} rel={br_rel:.0%} | "
        f"fixed pass_rate={fx_rate:.0%} rel={fx_rel:.0%} | "
        f"neg_ctrl FA broken={neg_broken} fixed={neg_fixed}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
