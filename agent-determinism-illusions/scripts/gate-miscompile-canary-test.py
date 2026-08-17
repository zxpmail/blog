# -*- coding: utf-8 -*-
"""Gate miscompile — fail-green without path-execution evidence (Tom Jones, Part 8).

Claim under test:
  A deterministic command gate can be silently miscompiled: asserts keep their
  indentation, land after `return`, never execute; exit code 0; the gate
  reports verified having checked nothing. This is neither channel blindness
  nor Goodhart. Alongside those, a third failure class: fail-green from a
  dead check path. Cheap countermeasure (Tom): keep a known-wrong
  implementation and require the suite to fail against it in CI — green must
  carry evidence that the check *path* executed, not merely an exit-0 slip.

Method:
  Stdlib only. Materialize a tiny function (add) + correct/wrong impls + a
  caller assert file. Two compilers of the same asserts into a runnable suite:
    correct_compile  — asserts run against the impl
    miscompile       — Tom's bug: nested asserts kept indented after `return`
                       (valid Python, never executed)
  Two gates on each (compiler × impl) cell:
    exit_only        — subprocess exit code == 0 → green
    +known_wrong     — exit_only on the candidate, AND the same suite must
                       fail (non-zero exit) against the known-wrong impl
                       (path-execution evidence / mutation canary)

Expected (SUPPORT if all hold):
  1. miscompile + exit_only: wrong impl is GREEN (fail-green; checked nothing)
  2. correct_compile + exit_only: wrong RED, correct GREEN
  3. miscompile + known_wrong canary: gate REJECTS (canary does not go red)
  4. correct_compile + known_wrong: correct GREEN, wrong RED (canary armed)

Falsification:
  If miscompile+exit_only rejects the wrong impl, the indentation bug does
  not produce Tom's fail-green. If the canary still greens miscompile, the
  known-wrong check does not detect a dead path.

Dependencies: stdlib only (subprocess + tempfile).
Run: python gate-miscompile-canary-test.py
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "gate-miscompile-canary.json"

# caller 提供的断言（原始缩进保留 → miscompile 的饵）
CALLER_ASSERTS = [
    "    assert add(1, 1) == 2",
    "    assert add(2, 3) == 5",
    "    assert add(0, 0) == 0",
]

CORRECT_IMPL = textwrap.dedent(
    """\
    def add(a, b):
        return a + b
    """
)

WRONG_IMPL = textwrap.dedent(
    """\
    def add(a, b):
        return a * b  # deliberately wrong
    """
)


def compile_correct(impl_src: str, asserts: list[str]) -> str:
    """正确编译：断言在测试函数里真的执行。"""
    body = "\n".join(asserts)
    return (
        impl_src
        + "\n\ndef test_add():\n"
        + body
        + "\n\nif __name__ == '__main__':\n"
        + "    test_add()\n"
        + "    print('OK')\n"
    )


def compile_miscompile(impl_src: str, asserts: list[str]) -> str:
    """Tom 的 bug：保留原缩进，断言落在 return 之后，合法 Python，从不执行。"""
    dead = "\n".join(asserts)  # 已带 4 空格缩进
    return (
        impl_src
        + "\n\ndef test_add():\n"
        + "    return True  # extractor finished early\n"
        + dead
        + "\n\nif __name__ == '__main__':\n"
        + "    test_add()\n"
        + "    print('OK')\n"
    )


def run_suite(src: str, work: Path) -> dict:
    """写入临时文件并用当前解释器执行，返回 exit / stdout / stderr。"""
    path = work / "suite.py"
    path.write_text(src, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip()[:400],
    }


def gate_exit_only(run: dict) -> str:
    return "GREEN" if run["exit_code"] == 0 else "RED"


def gate_with_canary(run_candidate: dict, run_wrong: dict) -> str:
    """绿 = 候选 exit 0 且已知错误实现必须非 0（路径确曾执行）。"""
    if run_candidate["exit_code"] != 0:
        return "RED"
    if run_wrong["exit_code"] == 0:
        # canary 没红 → 检查路径死了或套件不分辨对错
        return "REJECT_DEAD_PATH"
    return "GREEN"


def main():
    compilers = {
        "correct_compile": compile_correct,
        "miscompile": compile_miscompile,
    }
    cells = []

    with tempfile.TemporaryDirectory(prefix="gate-miscompile-") as tmp:
        root = Path(tmp)
        for cname, cfn in compilers.items():
            d = root / cname
            d.mkdir()
            src_correct = cfn(CORRECT_IMPL, CALLER_ASSERTS)
            src_wrong = cfn(WRONG_IMPL, CALLER_ASSERTS)
            (d / "on_correct").mkdir()
            run_c = run_suite(src_correct, d / "on_correct")
            (d / "on_wrong").mkdir()
            run_w = run_suite(src_wrong, d / "on_wrong")

            exit_on_correct = gate_exit_only(run_c)
            exit_on_wrong = gate_exit_only(run_w)
            canary_on_correct = gate_with_canary(run_c, run_w)
            # 对错误候选：候选跑 wrong；canary 仍是「同一套件对 known-wrong」
            # 这里 known-wrong 就是 WRONG_IMPL 本身 → run_w 对 miscompile 也是 0
            canary_on_wrong = gate_with_canary(run_w, run_w)

            cells.append({
                "compiler": cname,
                "run_on_correct": run_c,
                "run_on_wrong": run_w,
                "exit_only": {
                    "correct_impl": exit_on_correct,
                    "wrong_impl": exit_on_wrong,
                },
                "known_wrong_canary": {
                    "correct_impl": canary_on_correct,
                    # wrong impl as candidate: exit_only would green under miscompile;
                    # canary against known-wrong (same suite on WRONG) still dead
                    "wrong_impl": canary_on_wrong,
                },
                "suite_preview_miscompile_tail": (
                    src_wrong.split("def test_add():", 1)[-1][:200]
                    if cname == "miscompile"
                    else None
                ),
            })

    by = {c["compiler"]: c for c in cells}
    mis = by["miscompile"]
    ok = by["correct_compile"]

    checks = {
        "miscompile_exit_only_fail_green_on_wrong": (
            mis["exit_only"]["wrong_impl"] == "GREEN"
        ),
        "correct_exit_only_separates": (
            ok["exit_only"]["correct_impl"] == "GREEN"
            and ok["exit_only"]["wrong_impl"] == "RED"
        ),
        "miscompile_canary_rejects_dead_path": (
            mis["known_wrong_canary"]["correct_impl"] == "REJECT_DEAD_PATH"
        ),
        "correct_canary_armed": (
            ok["known_wrong_canary"]["correct_impl"] == "GREEN"
            and ok["exit_only"]["wrong_impl"] == "RED"
        ),
    }
    verdict = "SUPPORT" if all(checks.values()) else "FALSIFIED"

    print("=== gate-miscompile-canary-test ===")
    print("(real subprocess runs; stdlib only)")
    print()
    print(f"{'compiler':<18} {'exit@correct':>12} {'exit@wrong':>12} "
          f"{'canary@correct':>16}")
    print("-" * 62)
    for c in cells:
        print(
            f"{c['compiler']:<18} "
            f"{c['exit_only']['correct_impl']:>12} "
            f"{c['exit_only']['wrong_impl']:>12} "
            f"{c['known_wrong_canary']['correct_impl']:>16}"
        )
    print()
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nVERDICT: {verdict}")
    print()
    print("Tom's line: a gate you have only ever watched pass is not a gate,")
    print("it is a habit. Known-wrong must go RED — that is path-execution evidence.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "claim": (
            "Miscompiled command gate fail-greens on wrong impl (exit 0, "
            "asserts after return); known-wrong canary rejects dead path. "
            "Green needs path-execution evidence, not an exit-0 slip."
        ),
        "cells": cells,
        "checks": checks,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
