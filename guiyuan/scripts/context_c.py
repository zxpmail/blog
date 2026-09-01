# -*- coding: utf-8 -*-
"""C 情境实验（3.0 目标）：条文自洽 + 账本。默认不调模型。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEME_PATH = os.path.join(HERE, "context.md")
EXTRACT_DIR = os.path.join(HERE, "C")
EXTRACT_FILES = (
    "C-user.md",
    "C-default.md",
    "C-orchestration.md",
    "C-worker.md",
    "C-group.md",
    "C-projection.md",
)
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "没写的轴就是空",
    "这次对话",
    "关于他",
    "进 system",
    "first-match",
    "真源",
    "userId",
    "卸用户段",
    "对人默认",
    "写了也不算",
    "禁止写成「我是」「我必须」",
    "必须卸用户段",
    "必须有说明书",
    "说明书必须灌",
    "不得挂在 Agent",
    "被委派必须灌说明书",
    "跨用户房不搬 1:1",
    "也不搬个人召回",
    "仍搬召回，也算搬",
    "由装载器按入口表执行",
    "任务单走子 user",
    "写法见 D",
    "目标提示词",
    "C-user.md",
    "C-default.md",
    "C-orchestration.md",
    "C-worker.md",
    "C-group.md",
    "C-projection.md",
    "LOADER-DRAFT",
)
BANNED = (
    "默认脸",
    "这一窗",
    "稳 C",
)


def load_scheme(path: str = SCHEME_PATH) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    face = ledger.get("face")
    if ledger.get("user_in_history"):
        v.append("C-USER-HISTORY")
    if ledger.get("user_as_i_must"):
        v.append("C-USER-AS-MUST")
    if ledger.get("spec_in_system"):
        v.append("C-SPEC-SYSTEM")
    if face == "default" and ledger.get("has_yellow"):
        v.append("C-YELLOW-DEFAULT")
    if face == "default" and ledger.get("has_ext"):
        v.append("C-EXT-DEFAULT")
    if face == "orchestration" and ledger.get("has_ext"):
        v.append("C-EXT-ORCH")
    if face == "orchestration" and ledger.get("has_user"):
        v.append("C-ORCH-USER")
    if face == "orchestration" and ledger.get("has_spec") is False:
        v.append("C-ORCH-NO-SPEC")
    if face == "worker" and ledger.get("has_spec") is False:
        v.append("C-WORKER-NO-SPEC")
    if face == "worker" and ledger.get("has_yellow"):
        v.append("C-WORKER-YELLOW")
    if face == "worker" and ledger.get("has_user"):
        v.append("C-WORKER-USER")
    if face == "worker" and ledger.get("has_parent_dialog"):
        v.append("C-WORKER-PARENT")
    if face == "group" and ledger.get("brought_1to1"):
        v.append("C-GROUP-1TO1")
    if ledger.get("user_crossed"):
        v.append("C-USER-CROSS")
    if ledger.get("project_stale"):
        v.append("C-PROJECT-STALE")
    if ledger.get("key_on_agent"):
        v.append("C-KEY-AGENT")
    if ledger.get("user_key_is_replica"):
        v.append("C-USER-KEY-REPLICA")
    if ledger.get("verbal_auth"):
        v.append("C-VERBAL-AUTH")
    if ledger.get("coord_hands"):
        v.append("C-REWRITE-COORD")
    if ledger.get("recall_in_system"):
        v.append("C-RECALL-SYSTEM")
    if ledger.get("recall_on_child"):
        v.append("C-RECALL-CHILD")
    if ledger.get("model_in_soul"):
        v.append("C-MODEL-SOUL")
    if ledger.get("model_off_list"):
        v.append("C-MODEL-OFFLIST")
    return v


FIXTURES = [
    {
        "id": "C-OK-1",
        "note": "对人默认：用户段进 system，无黄页无 Ext",
        "ledger": {
            "face": "default", "user_in_system": True,
            "has_yellow": False, "has_ext": False,
        },
        "expect": [],
    },
    {
        "id": "C-OK-2",
        "note": "编排：说明书 + 手写黄页，已卸用户段",
        "ledger": {
            "face": "orchestration", "has_spec": True, "has_yellow": True,
            "has_user": False, "has_ext": False,
        },
        "expect": [],
    },
    {
        "id": "C-OK-3",
        "note": "执行体：有说明书，无黄页无用户段无父对话",
        "ledger": {
            "face": "worker", "has_spec": True, "has_yellow": False,
            "has_user": False, "has_parent_dialog": False,
        },
        "expect": [],
    },
    {
        "id": "C-OK-4",
        "note": "跨用户房不沿用 1:1",
        "ledger": {"face": "group", "brought_1to1": False},
        "expect": [],
    },
    {
        "id": "C-OK-5",
        "note": "用户段键 userId，副本只拼这次对话",
        "ledger": {"user_key_is_replica": False, "key_on_agent": False},
        "expect": [],
    },
    {
        "id": "C-OK-6",
        "note": "换项目卸项目侧",
        "ledger": {"project_stale": False},
        "expect": [],
    },
    {
        "id": "C-OK-7",
        "note": "授权只陈述；编排仍禁动手",
        "ledger": {"verbal_auth": False, "coord_hands": False},
        "expect": [],
    },
    {
        "id": "C-OK-8",
        "note": "召回不进 system、不进子会话",
        "ledger": {"recall_in_system": False, "recall_on_child": False},
        "expect": [],
    },
    {
        "id": "C-OK-9",
        "note": "模型不进灵魂、须在名单内",
        "ledger": {"model_in_soul": False, "model_off_list": False},
        "expect": [],
    },
    {
        "id": "C-X1",
        "note": "用户段放历史",
        "ledger": {"user_in_history": True},
        "expect": ["C-USER-HISTORY"],
    },
    {
        "id": "C-X2",
        "note": "用户段写成我必须",
        "ledger": {"user_as_i_must": True},
        "expect": ["C-USER-AS-MUST"],
    },
    {
        "id": "C-X3",
        "note": "说明书抬进 system",
        "ledger": {"spec_in_system": True},
        "expect": ["C-SPEC-SYSTEM"],
    },
    {
        "id": "C-X4",
        "note": "对人默认灌黄页",
        "ledger": {"face": "default", "has_yellow": True},
        "expect": ["C-YELLOW-DEFAULT"],
    },
    {
        "id": "C-X5",
        "note": "编排仍带着 1:1 用户段",
        "ledger": {"face": "orchestration", "has_spec": True, "has_user": True},
        "expect": ["C-ORCH-USER"],
    },
    {
        "id": "C-X6",
        "note": "编排只有黄页没有说明书",
        "ledger": {"face": "orchestration", "has_spec": False, "has_yellow": True},
        "expect": ["C-ORCH-NO-SPEC"],
    },
    {
        "id": "C-X7",
        "note": "执行体不灌说明书、灌父对话",
        "ledger": {
            "face": "worker", "has_spec": False, "has_parent_dialog": True,
        },
        "expect": ["C-WORKER-NO-SPEC", "C-WORKER-PARENT"],
    },
    {
        "id": "C-X8",
        "note": "跨用户房搬进 1:1",
        "ledger": {"face": "group", "brought_1to1": True},
        "expect": ["C-GROUP-1TO1"],
    },
    {
        "id": "C-X9",
        "note": "甲的用户段进乙的对话",
        "ledger": {"user_crossed": True},
        "expect": ["C-USER-CROSS"],
    },
    {
        "id": "C-X10",
        "note": "用户段按副本当真源；挂在 Agent 上",
        "ledger": {"user_key_is_replica": True, "key_on_agent": True},
        "expect": ["C-USER-KEY-REPLICA", "C-KEY-AGENT"],
    },
    {
        "id": "C-X11",
        "note": "口头放开；因此改编排器动手",
        "ledger": {"verbal_auth": True, "coord_hands": True},
        "expect": ["C-VERBAL-AUTH", "C-REWRITE-COORD"],
    },
    {
        "id": "C-X12",
        "note": "召回整桶进 system；子会话仍灌 1:1",
        "ledger": {"recall_in_system": True, "recall_on_child": True},
        "expect": ["C-RECALL-SYSTEM", "C-RECALL-CHILD"],
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
    for name in EXTRACT_FILES:
        path = os.path.join(EXTRACT_DIR, name)
        if not os.path.isfile(path):
            fails.append(f"缺目标提示词：{name}")
            continue
        body = load_scheme(path)
        if "<c_" not in body:
            fails.append(f"{name} 无 <c_ 块")
        for ban in BANNED:
            if ban in body:
                fails.append(f"{name} 仍含：{ban}")
        if "G1" in body or "G12" in body:
            fails.append(f"{name} 含缺口编号")
        if "<playbook" in body:
            fails.append(f"{name} 写成了操作手册")
    return fails


def main() -> int:
    failed = []
    rows = []
    print("== C 方案静态（实验）==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== C 账本（实验）==")
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
    out = os.path.join(RESULTS, "context_c.jsonl")
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
