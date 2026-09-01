# -*- coding: utf-8 -*-
"""装卸方案实验：静态 + 判例账本。不调模型。不问模型改没改栈。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEME_PATH = os.path.join(HERE, "loader.md")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "程序硬闸",
    "不进模型",
    "不写进",
    "模型不能改栈",
    "口头套岗不算",
    "G 不装进",
    "对人默认",
    "用户段",
    "假 user",
    "变了才追加",
    "换人",
    "换项目",
    "任务单走子 user",
    "脏单",
    "机器挡住",
)
BANNED = (
    "默认脸",
    "这一窗",
    "稳 C",
    "facing",
)


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    entry = ledger.get("entry")
    full = bool(ledger.get("full_entry"))

    if ledger.get("g_in_system"):
        v.append("L-G-IN-SYSTEM")
    if ledger.get("model_changed_stack"):
        v.append("L-VERBAL-STACK")
    if ledger.get("reloaded_unchanged"):
        v.append("L-RELOAD-UNCHANGED")

    if entry == "default":
        if ledger.get("wore_coord") or ledger.get("wore_worker"):
            v.append("L-DEFAULT-ROLE")
        if ledger.get("loaded_d1"):
            v.append("L-DEFAULT-D1")
        if ledger.get("loaded_ext"):
            v.append("L-DEFAULT-EXT")
        if ledger.get("loaded_yellow"):
            v.append("L-DEFAULT-YELLOW")
        if full:
            if not ledger.get("loaded_face"):
                v.append("L-DEFAULT-NO-FACE")
            if not ledger.get("loaded_bprime"):
                v.append("L-DEFAULT-NO-BPRIME")
            if not ledger.get("loaded_cuser"):
                v.append("L-DEFAULT-NO-CUSER")

    elif entry == "orchestration":
        if ledger.get("loaded_face") or ledger.get("loaded_bprime"):
            v.append("L-ORCH-FACE")
        if ledger.get("loaded_ext"):
            v.append("L-ORCH-EXT")
        if ledger.get("loaded_cuser"):
            v.append("L-ORCH-CUSER")
        if ledger.get("wore_worker"):
            v.append("L-ORCH-WORKER")
        if full:
            if not ledger.get("d1o_loaded"):
                v.append("L-ORCH-NO-D1")
            if not ledger.get("d2_loaded"):
                v.append("L-ORCH-NO-D2")
            if not ledger.get("loaded_yellow"):
                v.append("L-ORCH-NO-YELLOW")

    elif entry == "worker":
        if ledger.get("loaded_face") or ledger.get("loaded_bprime"):
            v.append("L-WORKER-FACE")
        if ledger.get("wore_coord"):
            v.append("L-WORKER-COORD")
        if ledger.get("loaded_cuser"):
            v.append("L-WORKER-CUSER")
        if ledger.get("loaded_parent_dialog"):
            v.append("L-WORKER-PARENT-DIALOG")
        if ledger.get("loaded_parent_d1"):
            v.append("L-WORKER-PARENT-D1")
        if ledger.get("loaded_yellow"):
            v.append("L-WORKER-YELLOW")
        if ledger.get("loaded_recall"):
            v.append("L-WORKER-RECALL")
        if ledger.get("unpinned_ext_loaded"):
            v.append("L-WORKER-UNPINNED-EXT")
        if full and not ledger.get("d1w_loaded"):
            v.append("L-WORKER-NO-D1")

    elif entry == "btw":
        if ledger.get("queued_in_main"):
            v.append("L-BTW-QUEUE")
        if ledger.get("wore_coord") or ledger.get("wore_worker"):
            v.append("L-BTW-ROLE")
        if ledger.get("loaded_d1") or ledger.get("loaded_d"):
            v.append("L-BTW-D")
        if ledger.get("loaded_cuser") or ledger.get("loaded_c"):
            v.append("L-BTW-C")

    elif entry == "group":
        if ledger.get("cuser_1to1"):
            v.append("L-GROUP-1TO1-CUSER")
        if ledger.get("soul_1to1"):
            v.append("L-GROUP-1TO1-SOUL")
        if ledger.get("loaded_yellow"):
            v.append("L-GROUP-YELLOW")
        if ledger.get("loaded_recall"):
            v.append("L-GROUP-RECALL")
        if ledger.get("loaded_d1"):
            v.append("L-GROUP-1TO1-D1")

    if ledger.get("kept_prev_user_segment"):
        v.append("L-SWITCH-USER-LEAK")
    if ledger.get("dropped_user_on_project_switch"):
        v.append("L-SWITCH-PROJ-DROPS-USER")
    if ledger.get("dropped_manual_same_project"):
        v.append("L-SAME-PROJ-DROPS-MANUAL")
    if ledger.get("kept_role_after_return"):
        v.append("L-RETURN-KEPT-ROLE")
    if ledger.get("dirty_task_in_child"):
        v.append("L-DIRTY-IN-CHILD")
    return v


FIXTURES = [
    {
        "id": "L-OK-1",
        "note": "对人默认：face+B′+用户段，卸岗卸黄页卸 D1",
        "ledger": {
            "entry": "default", "full_entry": True,
            "loaded_face": True, "loaded_bprime": True, "loaded_cuser": True,
        },
        "expect": [],
    },
    {
        "id": "L-OK-2",
        "note": "编排：A+Coord+说明书黄页（假 user）+D1 编排+D2；卸 face/B′/Ext/用户段",
        "ledger": {
            "entry": "orchestration", "full_entry": True,
            "wore_coord": True, "d1o_loaded": True, "d2_loaded": True,
            "loaded_yellow": True, "loaded_manual": True,
        },
        "expect": [],
    },
    {
        "id": "L-OK-3",
        "note": "被委派：A+Worker+被点到 Ext+D1 执行体+D2；不灌父对话/黄页/召回/父 D1",
        "ledger": {
            "entry": "worker", "full_entry": True,
            "wore_worker": True, "d1w_loaded": True, "d2_loaded": True,
            "loaded_ext": True,
        },
        "expect": [],
    },
    {
        "id": "L-OK-4",
        "note": "btw：只读快照，不进主队列，不灌岗/D/C",
        "ledger": {
            "entry": "btw",
            "queued_in_main": False, "wore_coord": False, "loaded_d1": False,
        },
        "expect": [],
    },
    {
        "id": "L-OK-5",
        "note": "跨用户房：本场皮+本场事实；不搬 1:1 用户段/灵魂/黄页/召回/委派百科",
        "ledger": {
            "entry": "group", "full_entry": True,
            "loaded_skin_local": True, "loaded_c_local": True,
        },
        "expect": [],
    },
    {
        "id": "L-OK-6",
        "note": "换人：卸甲的用户段与召回，灌乙的；甲的不进乙",
        "ledger": {"entry": "default", "kept_prev_user_segment": False},
        "expect": [],
    },
    {
        "id": "L-OK-7",
        "note": "换项目：重灌说明书黄页；用户段不卸",
        "ledger": {
            "entry": "orchestration",
            "dropped_user_on_project_switch": False,
            "reloaded_manual": True,
        },
        "expect": [],
    },
    {
        "id": "L-OK-8",
        "note": "回对人默认：卸 Coord/Worker；再灌 face/B′/用户段",
        "ledger": {"entry": "default", "kept_role_after_return": False},
        "expect": [],
    },
    {
        "id": "L-OK-9",
        "note": "脏单进子 user 前被机器挡住，不开跑",
        "ledger": {"entry": "worker", "dirty_task_in_child": False},
        "expect": [],
    },
    {
        "id": "L-X1",
        "note": "对人默认误套 Coord",
        "ledger": {"entry": "default", "wore_coord": True},
        "expect": ["L-DEFAULT-ROLE"],
    },
    {
        "id": "L-X2",
        "note": "对人默认灌 D1 委派百科",
        "ledger": {"entry": "default", "loaded_d1": True},
        "expect": ["L-DEFAULT-D1"],
    },
    {
        "id": "L-X3",
        "note": "编排灌 face",
        "ledger": {"entry": "orchestration", "loaded_face": True},
        "expect": ["L-ORCH-FACE"],
    },
    {
        "id": "L-X4",
        "note": "编排缺 D1+D2（用户说别灌也卸不掉，缺了就是缺）",
        "ledger": {
            "entry": "orchestration", "full_entry": True,
            "wore_coord": True, "loaded_yellow": True,
        },
        "expect": ["L-ORCH-NO-D1", "L-ORCH-NO-D2"],
    },
    {
        "id": "L-X5",
        "note": "被委派灌父对话当手册",
        "ledger": {"entry": "worker", "loaded_parent_dialog": True},
        "expect": ["L-WORKER-PARENT-DIALOG"],
    },
    {
        "id": "L-X6",
        "note": "被委派灌父的 D1 百科",
        "ledger": {"entry": "worker", "loaded_parent_d1": True},
        "expect": ["L-WORKER-PARENT-D1"],
    },
    {
        "id": "L-X7",
        "note": "被委派卸 A（不可卸）且误套编排岗",
        "ledger": {"entry": "worker", "wore_coord": True},
        "expect": ["L-WORKER-COORD"],
    },
    {
        "id": "L-X8",
        "note": "btw 进主队列还灌岗",
        "ledger": {
            "entry": "btw", "queued_in_main": True, "wore_worker": True,
        },
        "expect": ["L-BTW-QUEUE", "L-BTW-ROLE"],
    },
    {
        "id": "L-X9",
        "note": "跨用户房搬 1:1 用户段+黄页",
        "ledger": {
            "entry": "group", "cuser_1to1": True, "loaded_yellow": True,
        },
        "expect": ["L-GROUP-1TO1-CUSER", "L-GROUP-YELLOW"],
    },
    {
        "id": "L-X10",
        "note": "G 被装进这次对话的 system",
        "ledger": {"entry": "orchestration", "g_in_system": True},
        "expect": ["L-G-IN-SYSTEM"],
    },
    {
        "id": "L-X11",
        "note": "用户口头套岗，装卸照办改栈",
        "ledger": {"entry": "default", "model_changed_stack": True},
        "expect": ["L-VERBAL-STACK"],
    },
    {
        "id": "L-X12",
        "note": "时间没变又灌第二份",
        "ledger": {"entry": "default", "reloaded_unchanged": True},
        "expect": ["L-RELOAD-UNCHANGED"],
    },
    {
        "id": "L-X13",
        "note": "换人后甲的用户段泄漏给乙",
        "ledger": {"entry": "default", "kept_prev_user_segment": True},
        "expect": ["L-SWITCH-USER-LEAK"],
    },
    {
        "id": "L-X14",
        "note": "脏单进了子 user 开跑",
        "ledger": {"entry": "worker", "dirty_task_in_child": True},
        "expect": ["L-DIRTY-IN-CHILD"],
    },
    {
        "id": "L-X15",
        "note": "同项目换房把说明书卸了",
        "ledger": {"entry": "orchestration", "dropped_manual_same_project": True},
        "expect": ["L-SAME-PROJ-DROPS-MANUAL"],
    },
    {
        "id": "L-X16",
        "note": "回对人默认还穿着 Coord",
        "ledger": {
            "entry": "default", "kept_role_after_return": True, "wore_coord": True,
        },
        "expect": ["L-RETURN-KEPT-ROLE", "L-DEFAULT-ROLE"],
    },
]


def test_scheme() -> list[str]:
    with open(SCHEME_PATH, encoding="utf-8") as f:
        text = f.read()
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
    print("== 装卸方案静态 ==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== 装卸账本（判例）==")
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
    out = os.path.join(RESULTS, "loader.jsonl")
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
