# -*- coding: utf-8 -*-
"""G 闸门实验（3.0 目标）：条文自洽 + 账本。不调模型。不灌进 system。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_PATH = os.path.join(HERE, "gate.md")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "不装进这次对话的 system",
    "这次对话",
    "不要叫 L6",
    "不写第二套宪章",
    "盖不住 A",
    "催办不得违反",
    "纯聊不套",
    "完成证据门",
    "触顶立即终态",
    "分标记",
    "超时不得写成",
    "禁止静默",
    "写了也不算",
    "注入槽",
    "轨迹纠偏",
    "D7",
    "LOADER-DRAFT",
    "由代码在事件上执行",
    "三种拒",
    "四种分标记",
    "假死立即停",
    "无句柄则催办或改写",
    "开局钉死",
    "只信平台打在 tool_result",
    "会响的硬停",
    "改不了门",
    "必须丢",
    "不当证物",
    "不得放行",
    "认错靶",
    "fail-open",
    "验收侧",
    "取消认定",
    "脏单开跑",
    "机器位",
    "模型自报不当认定",
)
BANNED = (
    "默认脸",
    "这一窗",
    "稳 G",
    "facing",
)


def load_scheme(path: str = SCHEME_PATH) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    if ledger.get("g_in_system"):
        v.append("G-IN-SYSTEM")
    if ledger.get("second_charter_in_gate"):
        v.append("G-REWRITE-A")
    if ledger.get("prompt_as_gate"):
        v.append("G-PROMPT-AS-GATE")
    if ledger.get("inject_slot_as_g"):
        v.append("G-D7-AS-G")
    if ledger.get("claimed_complete_without_artifact") and ledger.get("gate_let_through"):
        v.append("G-NO-EVIDENCE")
    if ledger.get("chat_only") and ledger.get("deliverable_gate_fired"):
        v.append("G-CHAT-AS-DELIVER")
    if ledger.get("user_cancelled") and ledger.get("executed_after_cancel"):
        v.append("G-CANCEL-RUN")
    if ledger.get("capped") and ledger.get("marked_completed"):
        v.append("G-CAP-AS-DONE")
    if ledger.get("deny_as_user_reject"):
        v.append("G-DENY-AS-USER")
    if ledger.get("timeout_as_user_deny"):
        v.append("G-TIMEOUT-AS-USER")
    if ledger.get("retry_after_user_deny"):
        v.append("G-RETRY-DENY")
    if ledger.get("promise_empty_as_success"):
        v.append("G-PROMISE-OK")
    if ledger.get("child_self_escalate"):
        v.append("G-CHILD-ESCALATE")
    if ledger.get("silent_fail"):
        v.append("G-SILENT")
    if ledger.get("degrade_after_cap"):
        v.append("G-DEGRADE-AFTER-CAP")
    if ledger.get("verify_as_complete"):
        v.append("G-VERIFY-AS-DONE")
    if ledger.get("late_answer_as_success"):
        v.append("G-LATE-AS-DONE")
    if ledger.get("agent_rewrote_gate"):
        v.append("G-AGENT-REWRITE-GATE")
    if ledger.get("self_report_as_evidence"):
        v.append("G-SELF-REPORT")
    if ledger.get("no_referent_passed"):
        v.append("G-NO-REFERENT-PASS")
    if ledger.get("wrong_target_passed"):
        v.append("G-WRONG-TARGET")
    if ledger.get("fail_open_as_pass"):
        v.append("G-FAIL-OPEN")
    if ledger.get("stalled") and ledger.get("degrade_after_stall"):
        v.append("G-STALL-AS-GRADUAL")
    if ledger.get("machine_gate_as_user"):
        v.append("G-MACHINE-AS-USER")
    if ledger.get("web_as_token"):
        v.append("G-WEB-AS-TOKEN")
    if ledger.get("task_channel_as_permission"):
        v.append("G-TASK-AS-PERM")
    if ledger.get("cancel_by_model"):
        v.append("G-CANCEL-BY-MODEL")
    if ledger.get("dirty_task_ran"):
        v.append("G-DIRTY-TASK-RUN")
    return v


FIXTURES = [
    {
        "id": "G-OK-1",
        "note": "G 不进 system；不是人格层",
        "ledger": {"g_in_system": False, "second_charter_in_gate": False},
        "expect": [],
    },
    {
        "id": "G-OK-2",
        "note": "无证物不放行；纯聊不套交付门",
        "ledger": {
            "claimed_complete_without_artifact": True,
            "gate_let_through": False,
            "chat_only": True,
            "deliverable_gate_fired": False,
        },
        "expect": [],
    },
    {
        "id": "G-OK-3",
        "note": "取消停；触顶不标 completed；假死停",
        "ledger": {
            "user_cancelled": True, "executed_after_cancel": False,
            "capped": True, "marked_completed": False,
            "stalled": True, "degrade_after_stall": False,
        },
        "expect": [],
    },
    {
        "id": "G-OK-4",
        "note": "无句柄不当时成功；四种拒分开",
        "ledger": {
            "promise_empty_as_success": False,
            "deny_as_user_reject": False,
            "timeout_as_user_deny": False,
            "machine_gate_as_user": False,
        },
        "expect": [],
    },
    {
        "id": "G-OK-5",
        "note": "子钉死；禁止静默；触顶不空转",
        "ledger": {
            "child_self_escalate": False,
            "silent_fail": False,
            "degrade_after_cap": False,
        },
        "expect": [],
    },
    {
        "id": "G-OK-6",
        "note": "注入槽不是 G；Verify 不代替完成门",
        "ledger": {"inject_slot_as_g": False, "verify_as_complete": False, "prompt_as_gate": False},
        "expect": [],
    },
    {
        "id": "G-OK-7",
        "note": "用户拒不原样重试",
        "ledger": {"retry_after_user_deny": False},
        "expect": [],
    },
    {
        "id": "G-OK-8",
        "note": "迟到丢；自报不当证物；无指称不放行；认错靶不放；门不可改",
        "ledger": {
            "late_answer_as_success": False,
            "self_report_as_evidence": False,
            "no_referent_passed": False,
            "wrong_target_passed": False,
            "fail_open_as_pass": False,
            "agent_rewrote_gate": False,
        },
        "expect": [],
    },
    {
        "id": "G-X1",
        "note": "G 灌进 system",
        "ledger": {"g_in_system": True},
        "expect": ["G-IN-SYSTEM"],
    },
    {
        "id": "G-X2",
        "note": "门里另造完成标准",
        "ledger": {"second_charter_in_gate": True},
        "expect": ["G-REWRITE-A"],
    },
    {
        "id": "G-X3",
        "note": "无证物放行",
        "ledger": {"claimed_complete_without_artifact": True, "gate_let_through": True},
        "expect": ["G-NO-EVIDENCE"],
    },
    {
        "id": "G-X4",
        "note": "陪聊套交付门",
        "ledger": {"chat_only": True, "deliverable_gate_fired": True},
        "expect": ["G-CHAT-AS-DELIVER"],
    },
    {
        "id": "G-X5",
        "note": "取消后续跑；触顶标完成",
        "ledger": {
            "user_cancelled": True, "executed_after_cancel": True,
            "capped": True, "marked_completed": True,
        },
        "expect": ["G-CANCEL-RUN", "G-CAP-AS-DONE"],
    },
    {
        "id": "G-X6",
        "note": "DENY 当用户拒；超时当用户拒；原样重试",
        "ledger": {
            "deny_as_user_reject": True,
            "timeout_as_user_deny": True,
            "retry_after_user_deny": True,
        },
        "expect": ["G-DENY-AS-USER", "G-TIMEOUT-AS-USER", "G-RETRY-DENY"],
    },
    {
        "id": "G-X7",
        "note": "空口稍后当成功",
        "ledger": {"promise_empty_as_success": True},
        "expect": ["G-PROMISE-OK"],
    },
    {
        "id": "G-X8",
        "note": "子自己升权；静默；触顶后逐渐",
        "ledger": {
            "child_self_escalate": True,
            "silent_fail": True,
            "degrade_after_cap": True,
        },
        "expect": ["G-CHILD-ESCALATE", "G-SILENT", "G-DEGRADE-AFTER-CAP"],
    },
    {
        "id": "G-X9",
        "note": "prompt 代替门；注入槽当 G；Verify 当完成",
        "ledger": {
            "prompt_as_gate": True,
            "inject_slot_as_g": True,
            "verify_as_complete": True,
        },
        "expect": ["G-PROMPT-AS-GATE", "G-D7-AS-G", "G-VERIFY-AS-DONE"],
    },
    {
        "id": "G-X10",
        "note": "迟到当成功；自报当证物；无指称放行；认错靶；fail-open；卸闸",
        "ledger": {
            "late_answer_as_success": True,
            "self_report_as_evidence": True,
            "no_referent_passed": True,
            "wrong_target_passed": True,
            "fail_open_as_pass": True,
            "agent_rewrote_gate": True,
        },
        "expect": [
            "G-LATE-AS-DONE",
            "G-SELF-REPORT",
            "G-NO-REFERENT-PASS",
            "G-WRONG-TARGET",
            "G-FAIL-OPEN",
            "G-AGENT-REWRITE-GATE",
        ],
    },
    {
        "id": "G-OK-9",
        "note": "假死不逐渐；机器闸≠用户拒；网页不当令；任务通道不是权限",
        "ledger": {
            "stalled": True, "degrade_after_stall": False,
            "machine_gate_as_user": False,
            "web_as_token": False,
            "task_channel_as_permission": False,
        },
        "expect": [],
    },
    {
        "id": "G-X11",
        "note": "假死当逐渐；机器闸当用户拒；网页当令；任务通道当权限",
        "ledger": {
            "stalled": True, "degrade_after_stall": True,
            "machine_gate_as_user": True,
            "web_as_token": True,
            "task_channel_as_permission": True,
        },
        "expect": [
            "G-STALL-AS-GRADUAL",
            "G-MACHINE-AS-USER",
            "G-WEB-AS-TOKEN",
            "G-TASK-AS-PERM",
        ],
    },
    {
        "id": "G-OK-10",
        "note": "取消认定在平台；脏单开跑被拦",
        "ledger": {
            "cancel_by_model": False,
            "dirty_task_ran": False,
        },
        "expect": [],
    },
    {
        "id": "G-X12",
        "note": "模型认定取消；脏单开跑",
        "ledger": {
            "cancel_by_model": True,
            "dirty_task_ran": True,
        },
        "expect": ["G-CANCEL-BY-MODEL", "G-DIRTY-TASK-RUN"],
    },
]


def test_scheme() -> list[str]:
    text = load_scheme()
    fails = []
    for must in MUST:
        if must not in text:
            fails.append(f"方案缺：{must}")
    for ban in BANNED:
        if ban in text:
            fails.append(f"方案仍含：{ban}")
    return fails


def main() -> int:
    failed = []
    rows = []
    print("== G 方案静态（实验）==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== G 账本（实验）==")
    for fx in FIXTURES:
        got = judge(fx["ledger"])
        exp = list(fx["expect"])
        ok = sorted(got) == sorted(exp)
        print(f"  {'PASS' if ok else 'FAIL'} {fx['id']}  {fx['note']}")
        if not ok:
            print(f"       expect {exp} got {got}")
            failed.append(fx["id"])
        rows.append({
            "id": fx["id"], "pass": ok,
            "expect": exp, "got": got, "note": fx["note"],
        })
    out = os.path.join(RESULTS, "gate_g.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("-" * 40)
    if failed:
        print(f"FAILED {len(failed)}: {failed}")
        return 1
    print(f"OK {len(FIXTURES)} fixtures + scheme  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
