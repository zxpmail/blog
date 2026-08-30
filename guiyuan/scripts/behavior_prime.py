# -*- coding: utf-8 -*-
"""B′ 性格方案实验（3.0 目标）：条文自洽 + 账本。默认不调模型。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_PATH = os.path.join(HERE, "behavior.md")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "用户面前那张助手",
    "可以没有",
    "没写就是空",
    "都不算",
    "同名也脱",
    "自己动手",
    "也不脱",
    "开编排",
    "不灌灵魂",
    "由装载器按入口表执行",
)
BANNED = ("夹克",)


def load_scheme(path: str = SCHEME_PATH) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    if ledger.get("wore_tenant_default"):
        v.append("BP-TENANT-DEFAULT")
    if ledger.get("login_mutates_same_agent"):
        v.append("BP-LOGIN-MUTATE")
    if ledger.get("model_in_soul"):
        v.append("BP-MODEL-IN-SOUL")
    if ledger.get("project_swap_drops_soul"):
        v.append("BP-PROJECT-DROPS")
    if ledger.get("stamp_mutates_soul_store"):
        v.append("BP-STAMP-STORE")
    if ledger.get("obeyed_unverified_soul"):
        v.append("BP-VS-A")
    if ledger.get("rewrote_job"):
        v.append("BP-REWRITE-JOB")
    if ledger.get("inherited_face_soul"):
        v.append("BP-INHERIT-FACE")
    if ledger.get("self_work") and ledger.get("stripped_on_self_work"):
        v.append("BP-SELF-STRIP")
    if ledger.get("utility") and ledger.get("utility_wore_soul"):
        v.append("BP-UTILITY")
    if ledger.get("wore_worker_own_skin"):
        v.append("BP-WORKER-OWN")
    if ledger.get("wore_soul_on_coord"):
        v.append("BP-COORD-SOUL")
    return v


FIXTURES = [
    {
        "id": "BP-OK-1",
        "note": "没写人设，空着",
        "ledger": {"soul": None, "wore_tenant_default": False},
        "expect": [],
    },
    {
        "id": "BP-OK-2",
        "note": "甲乙同种助手，各副本",
        "ledger": {"copies": ["alice", "bob"], "login_mutates_same_agent": False},
        "expect": [],
    },
    {
        "id": "BP-OK-3",
        "note": "换项目，脾气还在",
        "ledger": {"project_swap_drops_soul": False},
        "expect": [],
    },
    {
        "id": "BP-OK-4",
        "note": "本轮印章，不改灵魂库",
        "ledger": {"stamp": "CONCIERGE", "stamp_mutates_soul_store": False},
        "expect": [],
    },
    {
        "id": "BP-OK-5",
        "note": "这张脸自己动手，皮不脱",
        "ledger": {"self_work": True, "stripped_on_self_work": False, "inherited_face_soul": False},
        "expect": [],
    },
    {
        "id": "BP-OK-6",
        "note": "派给同名，脱面前灵魂；干活也不灌",
        "ledger": {
            "same_name": True, "inherited_face_soul": False,
            "wore_worker_own_skin": False,
        },
        "expect": [],
    },
    {
        "id": "BP-OK-7",
        "note": "开编排，不灌灵魂",
        "ledger": {
            "face": "orchestration", "wore_soul_on_coord": False,
            "inherited_face_soul": False,
        },
        "expect": [],
    },
    {
        "id": "BP-OK-8",
        "note": "起标题不套性格",
        "ledger": {"utility": "title", "utility_wore_soul": False},
        "expect": [],
    },
    {
        "id": "BP-X1",
        "note": "没写却填公司默认人格",
        "ledger": {"soul": None, "wore_tenant_default": True},
        "expect": ["BP-TENANT-DEFAULT"],
    },
    {
        "id": "BP-X2",
        "note": "按登录改同一对象",
        "ledger": {"login_mutates_same_agent": True},
        "expect": ["BP-LOGIN-MUTATE"],
    },
    {
        "id": "BP-X3",
        "note": "模型写进灵魂",
        "ledger": {"model_in_soul": True},
        "expect": ["BP-MODEL-IN-SOUL"],
    },
    {
        "id": "BP-X4",
        "note": "换项目卸掉脾气",
        "ledger": {"project_swap_drops_soul": True},
        "expect": ["BP-PROJECT-DROPS"],
    },
    {
        "id": "BP-X5",
        "note": "印章改了灵魂库",
        "ledger": {"stamp_mutates_soul_store": True},
        "expect": ["BP-STAMP-STORE"],
    },
    {
        "id": "BP-X6",
        "note": "人设要求无依据声称完成",
        "ledger": {"obeyed_unverified_soul": True},
        "expect": ["BP-VS-A"],
    },
    {
        "id": "BP-X7",
        "note": "人设改成自己去跑命令",
        "ledger": {"rewrote_job": True},
        "expect": ["BP-REWRITE-JOB"],
    },
    {
        "id": "BP-X8",
        "note": "同名派出去仍穿面前灵魂",
        "ledger": {"same_name": True, "inherited_face_soul": True},
        "expect": ["BP-INHERIT-FACE"],
    },
    {
        "id": "BP-X9",
        "note": "自己动手却脱掉人设",
        "ledger": {"self_work": True, "stripped_on_self_work": True},
        "expect": ["BP-SELF-STRIP"],
    },
    {
        "id": "BP-X10",
        "note": "起标题套陪伴灵魂",
        "ledger": {"utility": "title", "utility_wore_soul": True},
        "expect": ["BP-UTILITY"],
    },
    {
        "id": "BP-X11",
        "note": "干活灌自己的几句",
        "ledger": {"inherited_face_soul": False, "wore_worker_own_skin": True},
        "expect": ["BP-WORKER-OWN"],
    },
    {
        "id": "BP-X12",
        "note": "开编排还穿灵魂",
        "ledger": {"face": "orchestration", "wore_soul_on_coord": True},
        "expect": ["BP-COORD-SOUL"],
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
    print("== B′ 方案静态（实验）==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== B′ 账本（实验）==")
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
    out = os.path.join(RESULTS, "behavior_prime.jsonl")
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
