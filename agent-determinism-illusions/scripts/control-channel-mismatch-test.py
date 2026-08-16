#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Control/instrument channel mismatch (Tom Jones, fourth failure under three legs).

Claim under test
----------------
Tom Jones (DEV.to on Part 10, after hand-suite/base-rate): agrees with the
three legs, then names a fourth failure that walked past all three. A meta
check runs every guard against the defect it exists to catch. It reported one
guard BROKEN while the guard was working — the **control was inverted**.

Most guards are checkers: non-zero exit on defect; negative control asserts
non-zero. One guard is a **hook**: always exits 0 and signals in JSON
``{"decision": "block"}``. Its control ended in a bare grep for that string;
successful grep exits 0, which the harness reads as "guard did not fire."
The control returned success exactly when the guard worked, so the meta check
accused a healthy instrument.

None of the three legs sees this: base rate fine, sabotage-zero "passes"
because the control cannot *read* the score, version governance fine. The
invariant sits under all three: control and instrument must agree on the
**signal channel** (exit code, stdout, JSON field, side effect) before any
statistic means anything. False BROKEN also costs more than an unproven
guard — it spends report credibility.

Same night, same family: a rule file registered cleanly, passed every static
validity check, and never fired. Schema key is ``on`` but they wrote ``act``;
match field is raw comma-separated text but they wrote a quoted JSON list, so
it matched the literal ``["`` as a term. Registration ≠ firing; only verify
by effect.

Method
------
Offline synthetic catalog (stdlib).

  M  meta-control channel mismatch
     hook always exit 0 + JSON block on sabotage
     control_A: assert exit != 0           → false BROKEN (cannot read JSON)
     control_B: assert decision == block   → correctly sees fire
  R  registration green / firing red
     rule file with act/JSON-list → static register PASS
     effect runner with on/csv semantics → never fires on real defect

PASS criteria (falsify if any fails)
------------------------------------
  1. M: hook works (decision=block on sabotage, exit=0); exit-only control
     reports BROKEN; JSON-channel control reports OK
  2. R: static registration PASS; effect fire FAIL on planted defect
  3. Accusation cost shape: false_BROKEN spends credibility flag True while
     unproven_guard does not

Expected: SUPPORT — channel agreement is prior to the three legs.
No field prevalence; not a claim about Tom's exact hook binary.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "control-channel-mismatch.json"


# --- M: hook vs checker control ---

def hook_guard(sabotage: bool) -> dict:
    """钩子：永远 exit 0；用 JSON decision 说话。"""
    decision = "block" if sabotage else "approve"
    return {
        "exit_code": 0,
        "payload": {"decision": decision},
        "stdout": json.dumps({"decision": decision}),
    }


def checker_guard(sabotage: bool) -> dict:
    """普通检查器：缺陷时非零退出。"""
    return {
        "exit_code": 1 if sabotage else 0,
        "payload": None,
        "stdout": "defect\n" if sabotage else "ok\n",
    }


def control_exit_nonzero(result: dict) -> dict:
    """负对照：断言 exit != 0 表示开火。钩子上会假 BROKEN。"""
    fired = result["exit_code"] != 0
    return {
        "channel": "exit_code",
        "reads_as_fired": fired,
        "verdict": "OK" if fired else "BROKEN",
    }


def control_json_decision(result: dict) -> dict:
    """负对照：读 JSON decision==block。"""
    decision = None
    if result.get("payload"):
        decision = result["payload"].get("decision")
    else:
        try:
            decision = json.loads(result.get("stdout") or "{}").get("decision")
        except json.JSONDecodeError:
            decision = None
    fired = decision == "block"
    return {
        "channel": "json.decision",
        "reads_as_fired": fired,
        "verdict": "OK" if fired else "BROKEN",
    }


def control_grep_block_string(result: dict) -> dict:
    """Tom 形：裸 grep 字符串；grep 成功 exit 0 → 被读成未开火。"""
    text = result.get("stdout") or ""
    grep_found = '"decision": "block"' in text or '"decision":"block"' in text
    # 成功 grep 的进程 exit 0；若 harness 把「对照进程 exit 0」当未开火：
    control_process_exit = 0 if grep_found else 1
    harness_reads_fired = control_process_exit != 0  # 倒置：0 = 没开火
    return {
        "channel": "grep_exit_inverted",
        "grep_found": grep_found,
        "control_process_exit": control_process_exit,
        "harness_reads_fired": harness_reads_fired,
        "verdict": "OK" if harness_reads_fired else "BROKEN",
    }


# --- R: register vs fire ---

def static_register(rule_file: dict, schema: dict) -> dict:
    """静态注册：文件可解析 + 有触发字段 + 非空匹配表 → PASS（不跑效果）。"""
    # 错误 schema：接受 "act" 当存在性检查（他们写了 act）
    has_trigger_key = "act" in rule_file or "on" in rule_file
    match = rule_file.get("match")
    has_match = match is not None and (
        (isinstance(match, list) and len(match) > 0)
        or (isinstance(match, str) and len(match) > 0)
    )
    ok = has_trigger_key and has_match and rule_file.get("name")
    return {
        "registered": bool(ok),
        "verdict": "PASS" if ok else "REJECT",
        "note": "validity of file shape only",
    }


def effect_fire(rule_file: dict, event: dict) -> dict:
    """真实加载语义：只认 on；match 为逗号分隔原文，按子串项匹配。"""
    on = rule_file.get("on")
    if on is None:
        return {"fired": False, "reason": "missing_on_key"}
    raw = rule_file.get("match", "")
    if isinstance(raw, list):
        # 误写成 JSON 列表时，加载器按「整段序列化文本」当一项——会匹配字面 ["
        terms = [json.dumps(raw)]
    else:
        terms = [t.strip() for t in str(raw).split(",") if t.strip()]
    hay = event.get("text", "")
    for t in terms:
        if t and t in hay:
            return {"fired": True, "matched_term": t, "reason": "term_hit"}
    return {"fired": False, "reason": "no_term_hit", "terms": terms}


def main() -> None:
    # --- M ---
    sabotage = True
    hook = hook_guard(sabotage)
    checker = checker_guard(sabotage)

    m_exit_on_hook = control_exit_nonzero(hook)
    m_json_on_hook = control_json_decision(hook)
    m_grep_on_hook = control_grep_block_string(hook)
    m_exit_on_checker = control_exit_nonzero(checker)

    claim_m = (
        hook["exit_code"] == 0
        and hook["payload"]["decision"] == "block"
        and m_exit_on_hook["verdict"] == "BROKEN"  # 假指控
        and m_json_on_hook["verdict"] == "OK"
        and m_grep_on_hook["verdict"] == "BROKEN"  # Tom 形倒置
        and m_exit_on_checker["verdict"] == "OK"  # 同对照在检查器上正确
        and m_grep_on_hook["grep_found"] is True  # 字符串在，但读成没开火
    )

    # 指控成本：假 BROKEN 花报告信用；未证明的卫士不花
    false_broken_costs_credibility = m_grep_on_hook["verdict"] == "BROKEN"
    unproven_guard_costs_credibility = False
    claim_cost = (
        false_broken_costs_credibility is True
        and unproven_guard_costs_credibility is False
    )

    # --- R ---
    # 他们写的坏配置（静态仍绿）
    bad_rule = {
        "name": "block-todo",
        "act": "PreToolUse",  # 应为 on
        "match": ["TODO", "FIXME"],  # 应为 raw CSV
    }
    schema = {"trigger_key": "on", "match": "csv"}
    reg = static_register(bad_rule, schema)
    # 真实缺陷事件
    event = {"text": "please fix the TODO in auth.ts"}
    fire = effect_fire(bad_rule, event)
    # 修好后应开火
    good_rule = {
        "name": "block-todo",
        "on": "PreToolUse",
        "match": "TODO, FIXME",
    }
    fire_good = effect_fire(good_rule, event)

    claim_r = (
        reg["verdict"] == "PASS"
        and fire["fired"] is False
        and fire_good["fired"] is True
    )

    support = claim_m and claim_r and claim_cost
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Control and instrument must share a signal channel before base "
            "rate, sabotage-zero, or version governance mean anything; a "
            "hook that blocks in JSON while the control reads exit/grep-zero "
            "yields false BROKEN on a healthy guard; registration validity "
            "is not firing — only effect separates them"
        ),
        "source": (
            "Tom Jones DEV.to follow-up on Part 10 three-legs / hand-suite "
            "thread (meta-check inverted control; register≠fire)"
        ),
        "epistemic_bar": (
            "Synthetic hook/checker and rule-loader shapes. Not a replay of "
            "Tom's binary. Fourth invariant is prior to the three legs, not "
            "a replacement for them."
        ),
        "fourth_invariant": (
            "control and instrument agree on signal channel "
            "(exit | stdout | JSON field | side effect) before statistics"
        ),
        "claims": {
            "M_exit_control_false_BROKEN_on_working_hook": claim_m,
            "R_register_green_fire_red": claim_r,
            "false_BROKEN_costs_credibility": claim_cost,
        },
        "cell_M_meta_control": {
            "hook_on_sabotage": hook,
            "control_exit_on_hook": m_exit_on_hook,
            "control_json_on_hook": m_json_on_hook,
            "control_grep_inverted_on_hook": m_grep_on_hook,
            "control_exit_on_checker": m_exit_on_checker,
        },
        "cell_R_register_vs_fire": {
            "bad_rule": bad_rule,
            "registration": reg,
            "effect_on_defect": fire,
            "good_rule_effect": fire_good,
        },
        "accusation_vs_unproven": {
            "false_BROKEN_spends_report_credibility": false_broken_costs_credibility,
            "unproven_guard_spends_report_credibility": unproven_guard_costs_credibility,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("control-channel-mismatch — fourth invariant under three legs")
    print(f"verdict: {verdict}")
    print(
        f"M hook exit={hook['exit_code']} decision={hook['payload']['decision']} "
        f"| exit_ctrl={m_exit_on_hook['verdict']} "
        f"json_ctrl={m_json_on_hook['verdict']} "
        f"grep_inv={m_grep_on_hook['verdict']}"
    )
    print(
        f"R register={reg['verdict']} fire_bad={fire['fired']} "
        f"fire_good={fire_good['fired']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
