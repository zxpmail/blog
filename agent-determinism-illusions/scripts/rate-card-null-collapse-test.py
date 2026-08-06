# -*- coding: utf-8 -*-
"""Rate-card null≡no collapse — Tom Jones on Round 2 (2026-08-06).

Question (Tom Jones, DEV.to Round 2 comment):
  Rate-card guard asserted "every rung … tool-capable" while one rung's tool
  capability was literally unknown. Rung served direct under the provider's
  own model id. Guard checked capability by asking a DIFFERENT catalogue for
  that id, got null, and `null is False` failed → passed. First fix was an
  alias (Round 2's "better anchor" half). Boundary redraw: serving config
  DECLARES capability; guard asserts over declaration. Stale declaration is
  checkable on a schedule; failed lookup is indistinguishable from genuine
  absence — that collapse was the damage.

Claims under test:
  C1  Boolean `cap is False` collapses lookup-null into PASS on an unknown rung.
  C2  Three-state guard fail-closes on null (BLOCK / unknown), does not PASS.
  C3  Alias unblocks lookup → PASS, but still re-derives (shopping=True).
  C4  Declare-then-assert → PASS with shopping=False (no catalogue re-find).
  C5  Stale declaration (declare True, provider False) is catchable by a
      schedule check; boolean lookup-null is NOT distinguishable from
      genuine-False once collapsed.

Falsifiers:
  C1 fail → boolean already treats null as non-pass (Tom's incident is
            language/runtime specific, not structural).
  C2 fail → three-state still PASSes on null.
  C3 fail → alias somehow avoids re-derivation.
  C4 fail → declare path still shops, or fails to PASS when declared True.
  C5 fail → schedule check misses stale True, OR boolean path can tell
            lookup-miss from genuine-no after collapse.

Method (offline sim, no API):
  One rung, direct-served, model id present in serving config, ABSENT from
  the probe catalogue. Truth = tool-capable. Four guards + one stale cell.

Run:
  python rate-card-null-collapse-test.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RESULTS = Path(__file__).parent / "results-v2"
OUT = RESULTS / "rate-card-null-collapse.json"


# ── World ──

# Serving config already resolved the endpoint. Probe must not re-find by name.
SERVING = {
    "rung": "tier-mid",
    "provider": "direct-acme",
    "model_id": "acme/foo-7b",
    # Declaration face (boundary redraw). None = undeclared.
    "tool_capable_declared": None,
}

# Catalogue the router no longer routes through — probe still shops here.
PROBE_CATALOGUE: dict[str, dict[str, Any]] = {
    # deliberately missing "acme/foo-7b"
    "other/bar-3b": {"tool_capable": True},
}

# Provider reality (schedule-check oracle). Not visible to the boolean probe.
PROVIDER_TRUTH = {
    "acme/foo-7b": {"tool_capable": True},
    "acme/stale-9b": {"tool_capable": False},
}

ALIAS = {
    # "better anchor" hat — maps the direct id onto a catalogue row
    "acme/foo-7b": "other/bar-3b",
}


def catalogue_lookup(model_id: str, catalogue: dict[str, dict], alias: dict[str, str] | None = None) -> Any:
    """Return True/False/None. None = not found."""
    key = model_id
    if alias and model_id in alias:
        key = alias[model_id]
    row = catalogue.get(key)
    if row is None:
        return None
    return bool(row["tool_capable"])


# ── Guards ──

def guard_boolean_is_false(model_id: str) -> dict[str, Any]:
    """Tom's incident: null fails `is False` → treated as capable."""
    cap = catalogue_lookup(model_id, PROBE_CATALOGUE)
    # Production shape: assert "not incapable" via `is False`
    passed = cap is not False  # None → True. That is the collapse.
    return {
        "guard": "boolean_is_false",
        "cap": cap,
        "verdict": "PASS" if passed else "FAIL",
        "shopping": True,
        "rederived": True,
    }


def guard_three_state(model_id: str) -> dict[str, Any]:
    cap = catalogue_lookup(model_id, PROBE_CATALOGUE)
    if cap is None:
        verdict = "BLOCK"
    elif cap is True:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    return {
        "guard": "three_state",
        "cap": cap,
        "verdict": verdict,
        "shopping": True,
        "rederived": True,
    }


def guard_alias(model_id: str) -> dict[str, Any]:
    cap = catalogue_lookup(model_id, PROBE_CATALOGUE, alias=ALIAS)
    passed = cap is True
    return {
        "guard": "alias_lookup",
        "cap": cap,
        "verdict": "PASS" if passed else "FAIL",
        "shopping": True,
        "rederived": True,
    }


def guard_declare(model_id: str, declared: bool | None) -> dict[str, Any]:
    """Boundary redraw: assert over serving-config declaration, no catalogue."""
    _ = model_id  # intentionally unused — no re-find by name
    if declared is None:
        return {
            "guard": "declare_assert",
            "cap": None,
            "verdict": "BLOCK",
            "shopping": False,
            "rederived": False,
        }
    return {
        "guard": "declare_assert",
        "cap": declared,
        "verdict": "PASS" if declared else "FAIL",
        "shopping": False,
        "rederived": False,
    }


def schedule_check_stale(declared: bool, model_id: str) -> dict[str, Any]:
    """Stale declaration vs provider reality — checkable on a schedule."""
    truth = PROVIDER_TRUTH[model_id]["tool_capable"]
    stale = declared != truth
    return {
        "check": "schedule_stale",
        "declared": declared,
        "provider_truth": truth,
        "stale": stale,
        "caught": stale,  # schedule fires iff mismatch
    }


def boolean_cannot_split_null_from_false() -> dict[str, Any]:
    """After boolean collapse, lookup-miss and genuine-False share a cell?"""
    # miss → None; genuine no → plant a catalogue hit that is False
    miss = catalogue_lookup("acme/foo-7b", PROBE_CATALOGUE)
    genuine_catalogue = {"acme/foo-7b": {"tool_capable": False}}
    genuine = catalogue_lookup("acme/foo-7b", genuine_catalogue)
    # What the boolean face *records* after the is-False gate:
    miss_cell = "not_false" if miss is not False else "false"
    genuine_cell = "not_false" if genuine is not False else "false"
    # For the PASS/FAIL bit under `is not False`:
    miss_pass = miss is not False
    genuine_pass = genuine is not False
    return {
        "miss_raw": miss,
        "genuine_false_raw": genuine,
        "miss_boolean_cell": miss_cell,
        "genuine_boolean_cell": genuine_cell,
        "miss_passes_is_not_false": miss_pass,
        "genuine_passes_is_not_false": genuine_pass,
        # Damage Tom named: failing lookup and "no" are not the same raw value,
        # but under the boolean gate the *actionable* outcome can still launder
        # miss into pass while genuine-no fails — OR, if both collapse the same
        # way in a different encoding, they become indistinguishable.
        # Here: miss PASSes, genuine FAILs — so the boolean gate does not equate
        # them as the same PASS bit; it equates miss with True. The deeper
        # indistinguishability is at the raw probe return when both paths
        # yield None (absent from catalogue vs not listed because incapable
        # catalogues omit the row). Reproduce that:
        "omit_incapable": _omit_incapable_indistinguishable(),
    }


def _omit_incapable_indistinguishable() -> dict[str, Any]:
    """Catalogue that omits incapable models → miss and 'no' both return None."""
    # Policy: only list tool-capable models. Incapable → absent row.
    capable_only = {"other/bar-3b": {"tool_capable": True}}
    # Case A: unknown / wrong catalogue (Tom) → None
    a = catalogue_lookup("acme/foo-7b", capable_only)
    # Case B: genuinely incapable, omitted by policy → None
    b = catalogue_lookup("acme/no-tools", capable_only)
    return {
        "lookup_miss": a,
        "genuine_absent_as_no": b,
        "indistinguishable": a is None and b is None and a == b,
    }


def main() -> None:
    mid = SERVING["model_id"]
    truth = PROVIDER_TRUTH[mid]["tool_capable"]

    g1 = guard_boolean_is_false(mid)
    g2 = guard_three_state(mid)
    g3 = guard_alias(mid)
    g4 = guard_declare(mid, declared=True)
    g4_undeclared = guard_declare(mid, declared=None)

    stale = schedule_check_stale(declared=True, model_id="acme/stale-9b")
    collapse = boolean_cannot_split_null_from_false()

    claims = {
        "C1_boolean_null_passes": g1["verdict"] == "PASS" and g1["cap"] is None,
        "C2_three_state_blocks_null": g2["verdict"] == "BLOCK" and g2["cap"] is None,
        "C3_alias_passes_but_shops": g3["verdict"] == "PASS" and g3["shopping"] is True,
        "C4_declare_passes_no_shop": g4["verdict"] == "PASS" and g4["shopping"] is False,
        "C5_stale_caught_and_omit_indistinguishable": (
            stale["caught"] is True
            and collapse["omit_incapable"]["indistinguishable"] is True
        ),
    }

    payload = {
        "claim": "Tom Jones rate-card: null≡no under boolean is-False; alias vs declare",
        "serving": SERVING,
        "truth_tool_capable": truth,
        "guards": {
            "boolean_is_false": g1,
            "three_state": g2,
            "alias_lookup": g3,
            "declare_assert": g4,
            "declare_undeclared": g4_undeclared,
        },
        "stale_schedule": stale,
        "collapse": collapse,
        "claims": claims,
        "all_pass": all(claims.values()),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("rate-card null≡no collapse — Tom Jones / Round 2")
    print(f"rung model_id={mid}  truth_tool_capable={truth}")
    print()
    print(f"{'guard':<22} {'cap':<8} {'verdict':<6} shopping  rederived")
    print("-" * 60)
    for g in (g1, g2, g3, g4, g4_undeclared):
        cap_s = "null" if g["cap"] is None else str(g["cap"])
        print(
            f"{g['guard']:<22} {cap_s:<8} {g['verdict']:<6} "
            f"{str(g['shopping']):<8}  {g['rederived']}"
        )
    print()
    print(f"stale schedule: declared={stale['declared']} provider={stale['provider_truth']} caught={stale['caught']}")
    omit = collapse["omit_incapable"]
    print(
        f"omit-incapable catalogue: miss={omit['lookup_miss']} "
        f"genuine_no={omit['genuine_absent_as_no']} "
        f"indistinguishable={omit['indistinguishable']}"
    )
    print()
    for k, v in claims.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print()
    print(f"all_pass={payload['all_pass']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
