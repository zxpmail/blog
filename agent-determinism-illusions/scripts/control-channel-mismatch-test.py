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

Tom's follow-up (top-level comment, same thread) extends the channel
invariant in two directions, with three field receipts:

  Q  false QUIET (M inverted). The instrument writes on stderr, the observer
     reads stdout, so a real error scores as silence. M locked the *loud*
     face (false BROKEN accuses a healthy instrument); Q locks the *quiet*
     face (a real error passes as no output). Cost: false BROKEN spends
     credibility; false QUIET spends the entire reason the instrument exists,
     and it is the only one of the three that grows more convincing the
     longer it runs.
  D  downstream observer / self-authored channel. A commit hook meant to
     refuse auto-derived identities read ``GIT_AUTHOR_EMAIL`` — a variable
     the tool under test itself wrote moments earlier (git always exports it,
     populated with its guess). "Caller supplied" and "git guessed" are
     byte-identical by the time the observer looks, so the guard can never
     fire. The fix is not to read the env; it is to ask the subject to
     resolve the identity *with guessing disabled*, which fails exactly when
     the identity would have been derived.

The check that generalizes both: before trusting a control, enumerate every
transformation between the thing under test and the assertion, and ask which
can (a) turn a signal into an absence, or (b) hand you the subject's own
output as if it were independent. For Tom's three cases the answers were a
redirect, a pipe, and an inherited environment.

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
  Q  false QUIET (M inverted): instrument writes stderr, observer reads
     stdout → real error scores as silence; stderr-reading observer catches
     it
  D  downstream observer: subject exports env it just wrote; observer reads
     it as if independent → guard cannot fire; resolve-with-guessing-disabled
     fails exactly when the identity would have been derived

PASS criteria (falsify if any fails)
------------------------------------
  1. M: hook works (decision=block on sabotage, exit=0); exit-only control
     reports BROKEN; JSON-channel control reports OK
  2. R: static registration PASS; effect fire FAIL on planted defect
  3. Q: on sabotage, stdout-only observer reads silence (false QUIET) while
     stderr-reading observer catches the error; the same observer on a clean
     run reads correctly
  4. D: env-reading guard on a subject-written env var never fires (false
     PASS on the exact address it exists to reject); resolve-without-guess
     fails exactly when identity would have been derived, passes when truly
     supplied
  5. Accusation cost shape: false_BROKEN spends credibility flag True while
     unproven_guard does not

Expected: SUPPORT — channel agreement is prior to the three legs; it extends
to which stream the instrument writes vs the observer reads, and to whether
the observer reads a channel the subject itself wrote.
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


# --- Q: false QUIET (M inverted) — instrument writes stderr, observer reads stdout ---

def stream_instrument(sabotage: bool) -> dict:
    """被测：真错误写 stderr，成功写 stdout（Tom 的 python3 script.py 形状）。"""
    if sabotage:
        return {
            "stdout": "",
            "stderr": "traceback: invalidate failed\n",
            "real_status": "FAIL",
        }
    return {
        "stdout": "done\n",
        "stderr": "",
        "real_status": "PASS",
    }


def observer_stdout_only(result: dict) -> dict:
    """只读 stdout：失败时读到空 → 报安静（false QUIET）。"""
    fired = bool(result["stdout"].strip())
    return {
        "channel": "stdout_only",
        "reads_signal": fired,
        "verdict": "OK" if fired else "QUIET",
    }


def observer_stderr_aware(result: dict) -> dict:
    """读 stdout + stderr：失败时抓到 traceback → 正确报失败。"""
    signal = bool(result["stdout"].strip()) or bool(result["stderr"].strip())
    failed = result.get("real_status") == "FAIL"
    return {
        "channel": "stdout_plus_stderr",
        "reads_signal": signal,
        "verdict": "OK" if (signal and not failed) else ("FAIL" if failed else "OK"),
        "caught_error": failed and bool(result["stderr"].strip()),
    }


# --- D: downstream observer / self-authored channel — subject writes the env the observer reads ---

def git_like_guard(auto_derive: bool) -> dict:
    """git 形状的守卫：git 永远导出 GIT_AUTHOR_EMAIL（填的是它的猜测）。"""
    # git 总是 export GIT_AUTHOR_EMAIL = 它刚猜的值
    env_author_email = "guessed@example.com" if auto_derive else None
    configured_email = None  # 该 job 没配 email
    # 守卫条件：没有配置 email 且 环境没有身份 → 才 block
    block = (configured_email is None) and (env_author_email is None)
    return {
        "auto_derive": auto_derive,
        "env_author_email": env_author_email,
        "configured_email": configured_email,
        "guard_fired": block,
        "verdict": "REJECT" if block else "PASS",
        "note": (
            "git always exports GIT_AUTHOR_EMAIL with its guess, so the "
            "'env supplies none' half is never true — the guard cannot fire"
            if auto_derive
            else "env truly absent (no guessed export) — guard fires"
        ),
    }


def resolve_with_guessing_disabled(would_derive: bool) -> dict:
    """修法：问被测解析身份、禁用猜测——恰在身份会被派生时失败。"""
    if would_derive:
        return {
            "resolved": False,
            "verdict": "REJECT",
            "reason": "identity_would_be_derived",
        }
    return {
        "resolved": True,
        "verdict": "PASS",
        "reason": "identity_truly_supplied",
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

    # --- Q ---
    q_sabotage = stream_instrument(sabotage=True)
    q_clean = stream_instrument(sabotage=False)
    q_stdout_on_sabotage = observer_stdout_only(q_sabotage)
    q_stderr_on_sabotage = observer_stderr_aware(q_sabotage)
    q_stdout_on_clean = observer_stdout_only(q_clean)

    claim_q = (
        q_sabotage["real_status"] == "FAIL"
        and q_sabotage["stdout"] == ""  # 真错误只写 stderr
        and q_sabotage["stderr"] != ""
        and q_stdout_on_sabotage["verdict"] == "QUIET"  # false QUIET
        and q_stderr_on_sabotage["caught_error"] is True
        and q_stdout_on_clean["verdict"] == "OK"  # 干净 run 不误报
    )

    # --- D ---
    d_derive = git_like_guard(auto_derive=True)
    d_supplied = git_like_guard(auto_derive=False)
    d_fix_derive = resolve_with_guessing_disabled(would_derive=True)
    d_fix_supplied = resolve_with_guessing_disabled(would_derive=False)

    claim_d = (
        d_derive["verdict"] == "PASS"  # 守卫永远开不了火 → 假绿
        and d_derive["note"].startswith("git always exports")
        and d_supplied["verdict"] == "REJECT"  # 身份真缺时守卫能 block
        and d_fix_derive["verdict"] == "REJECT"  # 禁用猜测→恰在会派生时失败
        and d_fix_supplied["verdict"] == "PASS"
    )

    support = claim_m and claim_r and claim_cost and claim_q and claim_d
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Control and instrument must share a signal channel before base "
            "rate, sabotage-zero, or version governance mean anything; a "
            "hook that blocks in JSON while the control reads exit/grep-zero "
            "yields false BROKEN on a healthy guard; registration validity "
            "is not firing — only effect separates them. The invariant "
            "extends to which stream the instrument writes vs the observer "
            "reads (false QUIET: real error scores as silence — the M cell "
            "inverted and the more expensive face), and to whether the "
            "observer reads a channel the subject itself wrote (self-authored "
            "env: guard cannot fire; resolve-with-guessing-disabled fails "
            "exactly when the identity would have been derived). The "
            "generalized check: enumerate every transformation between the "
            "thing under test and the assertion — which can turn a signal "
            "into an absence, or hand you the subject's own output as if it "
            "were independent"
        ),
        "source": (
            "Tom Jones DEV.to top-level comment on Part 10 thread (field "
            "receipts: DRILL marker, 2>/dev/null stderr-eaten, git identity "
            "guard) extending the control-channel invariant"
        ),
        "epistemic_bar": (
            "Synthetic hook/checker and rule-loader shapes. Not a replay of "
            "Tom's binaries. Fourth invariant is prior to the three legs, "
            "not a replacement for them; Q and D lock the quiet face and "
            "the downstream-observer face synthetically, no field prevalence."
        ),
        "fourth_invariant": (
            "control and instrument agree on signal channel "
            "(exit | stdout | stderr | JSON field | side effect) before "
            "statistics — and the observer must not read a channel the "
            "subject itself wrote"
        ),
        "claims": {
            "M_exit_control_false_BROKEN_on_working_hook": claim_m,
            "R_register_green_fire_red": claim_r,
            "Q_false_QUIET_stdout_reads_silence_on_stderr_error": claim_q,
            "D_downstream_guard_reads_subject_env_cannot_fire": claim_d,
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
        "cell_Q_false_quiet": {
            "sabotage_stream": {
                "stdout": q_sabotage["stdout"],
                "stderr": q_sabotage["stderr"],
                "real_status": q_sabotage["real_status"],
            },
            "stdout_only_observer": q_stdout_on_sabotage,
            "stderr_aware_observer": q_stderr_on_sabotage,
            "clean_run_stdout_observer": q_stdout_on_clean,
        },
        "cell_D_downstream_observer": {
            "guard_with_auto_derived_env": {
                "verdict": d_derive["verdict"],
                "note": d_derive["note"],
                "env_author_email": d_derive["env_author_email"],
            },
            "guard_when_identity_truly_missing": {
                "verdict": d_supplied["verdict"],
                "note": d_supplied["note"],
            },
            "fix_resolve_with_guessing_disabled_would_derive": d_fix_derive,
            "fix_resolve_when_truly_supplied": d_fix_supplied,
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
    print(
        f"Q stdout_on_sabotage={q_stdout_on_sabotage['verdict']} "
        f"stderr_aware_caught={q_stderr_on_sabotage['caught_error']} "
        f"clean_ok={q_stdout_on_clean['verdict']}"
    )
    print(
        f"D derive_guard={d_derive['verdict']} missing_guard={d_supplied['verdict']} "
        f"fix_derive={d_fix_derive['verdict']} fix_supplied={d_fix_supplied['verdict']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
