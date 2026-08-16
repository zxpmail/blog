#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Absence of signal ≠ presence of health (Xiao Man, Part 10 §9 follow-up).

Claim under test
----------------
Xiao Man (DEV.to on Part 10): three independent systems share one failure
grammar — a replay gate whose catches are its heartbeat (never-fires ≡
healthy); a reconciler where ``zero downgrades`` means both ``checked, clean``
and ``never ran``; Tom's accept-only verifier whose aggregate improves as
reliability drops. Absence of a signal is not presence of health. The shared
operational patch is a negative control: sabotage must score zero before any
real (green) number prints. §9 abstain / ESCALATE makes ``no referent``
routable instead of a silent hole.

Method
------
Offline synthetic catalog (stdlib). Three isomorphic cells; each prints a
``quiet-looking`` aggregate that collides healthy with dead/silent, then a
negative-control (or explicit ran/alive bit) that forbids printing health
from silence.

  R  replay gate: catches==0 looks healthy; planted sabotage still 0 → dead
  Q  reconciler: downgrades==0 collides ran=true/clean vs ran=false
  A  accept-only verifier: pass_rate rises as reliability falls; sabotage
     must score 0 before pass_rate may print

Also: ternary outcome PASS/REJECT/ESCALATE on a no-referent claim — ESCALATE
is routing success, not checker failure.

PASS criteria (falsify if any fails)
------------------------------------
  1. R: quiet gate and live-clean gate both show catches=0; only sabotage
     NC fails the quiet/dead gate and passes the live gate
  2. Q: same downgrades=0 for ran=false and ran=true/clean; health print
     allowed only when ran=true
  3. A: broken accept-only has higher pass_rate and lower reliability than
     honest; NC blocks printing pass_rate on broken, allows on honest
  4. E: no-referent claim → ESCALATE (not PASS/REJECT guess)

Expected: SUPPORT — shared failure grammar + NC as necessary liveness probe
for printing green-from-quiet; not the only fix across all legs; not a
field security proof.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "absence-not-health.json"


# --- R: 重放门 ---

def replay_gate_run(alive: bool, events: list[str]) -> dict:
    """重放门：alive=False 时永不开火；返回 catches 计数。"""
    catches = 0
    if alive:
        for e in events:
            if e == "SABOTAGE":
                catches += 1
    return {"alive": alive, "catches": catches, "events_n": len(events)}


def replay_may_print_healthy(report: dict, require_nc: bool, nc_events: list[str]) -> dict:
    """仅当 catches==0 且（若要求 NC）破坏样必被抓住时，才准印健康。"""
    quiet = report["catches"] == 0
    if not require_nc:
        return {
            "print_healthy": quiet,
            "reason": "catches_eq_zero_only",
            "nc_ok": None,
        }
    nc = replay_gate_run(report["alive"], nc_events)
    nc_ok = nc["catches"] >= 1
    return {
        "print_healthy": quiet and nc_ok,
        "reason": "zero_catches_and_nc_fired" if (quiet and nc_ok) else "blocked",
        "nc_ok": nc_ok,
        "nc_catches": nc["catches"],
    }


# --- Q: 对账 ---

def reconcile(ran: bool, downgrades: int) -> dict:
    """对账报告：downgrades 与 ran 正交。"""
    return {"ran": ran, "downgrades": downgrades}


def reconcile_may_print_healthy(report: dict) -> dict:
    """downgrades==0 不够；必须 ran=true 才准印『查过且干净』。"""
    zero = report["downgrades"] == 0
    return {
        "raw_zero": zero,
        "print_healthy": zero and report["ran"] is True,
        "ambiguous_if_zero_only": zero,  # 零本身双读
    }


# --- A: accept-only 验证器 ---

def accept_only_score(cases: list[dict], mode: str) -> dict:
    """mode=broken: 凡非显式 REJECT 标签都接受；honest: 按 label。"""
    accepts = 0
    for c in cases:
        if mode == "broken":
            # 只朝 accept 偏：除非标成 must_reject 且我们「碰巧」拒——broken 从不拒
            accepts += 1
        else:
            if c["label"] == "PASS":
                accepts += 1
    n = len(cases)
    pass_rate = accepts / n if n else 0.0
    # 可靠度：与真值一致的比例
    correct = 0
    for c in cases:
        pred_pass = True if mode == "broken" else (c["label"] == "PASS")
        truth_pass = c["label"] == "PASS"
        if pred_pass == truth_pass:
            correct += 1
    reliability = correct / n if n else 0.0
    return {
        "mode": mode,
        "pass_rate": round(pass_rate, 4),
        "reliability": round(reliability, 4),
        "n": n,
    }


def sabotage_score(mode: str, sabotage: list[dict]) -> int:
    """破坏样被接受的个数；NC 要求 == 0。"""
    accepted = 0
    for c in sabotage:
        if mode == "broken":
            accepted += 1
        else:
            # honest 对 sabotage 应 REJECT → 接受数 0
            if c["label"] != "REJECT":
                accepted += 1
    return accepted


def accept_may_print_pass_rate(score: dict, sab_accepted: int) -> dict:
    """破坏样接受数必须为 0 才准打印通过率。"""
    nc_ok = sab_accepted == 0
    return {
        "print_pass_rate": nc_ok,
        "sabotage_accepted": sab_accepted,
        "nc_ok": nc_ok,
        "pass_rate_if_allowed": score["pass_rate"] if nc_ok else None,
    }


# --- E: §9 三值 ---

def adjudicate_claim(claim: dict) -> str:
    """有指称则跑观测；无指称 → ESCALATE（不上 PASS/REJECT 猜）。"""
    if not claim.get("referent"):
        return "ESCALATE"
    obs = claim.get("obs")
    if obs is None:
        return "ESCALATE"
    return "PASS" if obs.get("ok") else "REJECT"


def main() -> None:
    nc_events = ["SABOTAGE"]

    # R：安静死门 vs 活着且本轮无坏样 → 同为 catches=0
    dead = replay_gate_run(alive=False, events=["ok", "ok"])
    live_clean = replay_gate_run(alive=True, events=["ok", "ok"])
    r_no_nc_dead = replay_may_print_healthy(dead, require_nc=False, nc_events=nc_events)
    r_no_nc_live = replay_may_print_healthy(
        live_clean, require_nc=False, nc_events=nc_events
    )
    r_nc_dead = replay_may_print_healthy(dead, require_nc=True, nc_events=nc_events)
    r_nc_live = replay_may_print_healthy(
        live_clean, require_nc=True, nc_events=nc_events
    )
    claim_r = (
        dead["catches"] == 0
        and live_clean["catches"] == 0
        and r_no_nc_dead["print_healthy"] is True
        and r_no_nc_live["print_healthy"] is True  # 无 NC 时两者都「绿」
        and r_nc_dead["print_healthy"] is False
        and r_nc_live["print_healthy"] is True
    )

    # Q：同一 downgrades=0 双读
    never_ran = reconcile(ran=False, downgrades=0)
    checked_clean = reconcile(ran=True, downgrades=0)
    checked_dirty = reconcile(ran=True, downgrades=2)
    q_never = reconcile_may_print_healthy(never_ran)
    q_clean = reconcile_may_print_healthy(checked_clean)
    q_dirty = reconcile_may_print_healthy(checked_dirty)
    claim_q = (
        never_ran["downgrades"] == checked_clean["downgrades"] == 0
        and q_never["ambiguous_if_zero_only"] is True
        and q_never["print_healthy"] is False
        and q_clean["print_healthy"] is True
        and q_dirty["print_healthy"] is False
    )

    # A：broken 通过率高、可靠度低；NC 挡住打印
    suite = [
        {"id": "t1", "label": "PASS"},
        {"id": "t2", "label": "PASS"},
        {"id": "t3", "label": "REJECT"},
        {"id": "t4", "label": "REJECT"},
        {"id": "t5", "label": "PASS"},
        {"id": "t6", "label": "REJECT"},
        {"id": "t7", "label": "PASS"},
        {"id": "t8", "label": "REJECT"},
    ]
    sab = [
        {"id": "s1", "label": "REJECT"},
        {"id": "s2", "label": "REJECT"},
        {"id": "s3", "label": "REJECT"},
    ]
    broken = accept_only_score(suite, "broken")
    honest = accept_only_score(suite, "honest")
    sab_b = sabotage_score("broken", sab)
    sab_h = sabotage_score("honest", sab)
    print_b = accept_may_print_pass_rate(broken, sab_b)
    print_h = accept_may_print_pass_rate(honest, sab_h)
    claim_a = (
        broken["pass_rate"] > honest["pass_rate"]
        and broken["reliability"] < honest["reliability"]
        and print_b["print_pass_rate"] is False
        and print_h["print_pass_rate"] is True
        and sab_b > 0
        and sab_h == 0
    )

    # E：无指称 → ESCALATE
    e_no = adjudicate_claim({"referent": None, "text": "architecture is extensible"})
    e_ok = adjudicate_claim(
        {"referent": "cache[k]", "obs": {"ok": True}, "text": "invalidates key"}
    )
    e_bad = adjudicate_claim(
        {"referent": "cache[k]", "obs": {"ok": False}, "text": "invalidates key"}
    )
    claim_e = e_no == "ESCALATE" and e_ok == "PASS" and e_bad == "REJECT"

    support = claim_r and claim_q and claim_a and claim_e
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Quiet-looking aggregates (zero catches, zero downgrades, high "
            "pass rate) collide healthy with silent/dead; sabotage-must-score-"
            "zero (or an explicit ran/alive bit) is a necessary probe before "
            "printing health-from-quiet — shared failure grammar across three "
            "cells, not the only fix across all evaluation legs"
        ),
        "source": (
            "Xiao Man DEV.to on Part 10 §9 abstain / failure grammar "
            "(replay gate, reconciler, accept-only verifier)"
        ),
        "epistemic_bar": (
            "Synthetic isomorphic catalog. NC is necessary for printing "
            "green-from-quiet, not sufficient for system safety, and not the "
            "only operational fix (explicit ran/alive, base-rate half, "
            "version governance remain other legs). No field prevalence."
        ),
        "colloquial_internal": (
            "安静≠安全；通过率≠可信度。已知破坏打非零，是否定『传感器还活着』"
            "的证据——活性探针，不是安全证明。"
        ),
        "claims": {
            "R_replay_quiet_collides_until_nc": claim_r,
            "Q_zero_downgrades_ambiguous_until_ran": claim_q,
            "A_accept_only_pass_rate_vs_nc": claim_a,
            "E_no_referent_escalates": claim_e,
        },
        "cell_R_replay_gate": {
            "dead_quiet": dead,
            "live_clean": live_clean,
            "without_nc": {"dead": r_no_nc_dead, "live": r_no_nc_live},
            "with_nc": {"dead": r_nc_dead, "live": r_nc_live},
        },
        "cell_Q_reconciler": {
            "never_ran": {"report": never_ran, "gate": q_never},
            "checked_clean": {"report": checked_clean, "gate": q_clean},
            "checked_dirty": {"report": checked_dirty, "gate": q_dirty},
        },
        "cell_A_accept_only": {
            "broken": broken,
            "honest": honest,
            "print_broken": print_b,
            "print_honest": print_h,
        },
        "cell_E_ternary": {
            "no_referent": e_no,
            "referent_ok": e_ok,
            "referent_bad": e_bad,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("absence-not-health — quiet ≠ healthy (three isomorphic cells)")
    print(f"verdict: {verdict}")
    print(
        f"R catches=0 collide; NC print dead={r_nc_dead['print_healthy']} "
        f"live={r_nc_live['print_healthy']}"
    )
    print(
        f"Q zero ambiguous; print never_ran={q_never['print_healthy']} "
        f"clean={q_clean['print_healthy']}"
    )
    print(
        f"A broken pass_rate={broken['pass_rate']} rel={broken['reliability']} "
        f"| honest pass_rate={honest['pass_rate']} rel={honest['reliability']} "
        f"| print b/h={print_b['print_pass_rate']}/{print_h['print_pass_rate']}"
    )
    print(f"E no_referent={e_no} ok={e_ok} bad={e_bad}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
