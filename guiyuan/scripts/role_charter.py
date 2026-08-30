# -*- coding: utf-8 -*-
"""只测同目录 role.md 里两段 <role_charter>。不测 A/G/B′，不调模型。"""
from __future__ import annotations

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROLE_PATH = os.path.join(HERE, "role.md")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

BANNED_ANY = (
    "delete_file", "web-search-agent", "file_write", "run_command",
    "A1", "A2", "A7", "A9", "第1条", "第2条",
    "facing=\"companion\"", "kind=\"observer\"",
)
BANNED_RESTATE_A = (
    "没有依据不得声称",
    "已完成、已验证、已写入、已部署",
    "明确取消则",
    "非明确取消不得",
)
COORD_MUST = ("委派", "禁止臆造", "兜底", "不替执行体补过程")
WORKER_MUST = ("被委派", "任务说明", "不要为整场做路由")


def extract_roles(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    found = re.findall(
        r'<role_charter kind="(coordinator|worker)">(.*?)</role_charter>',
        text, re.S,
    )
    return {k: v.strip() for k, v in found}


def extract_face(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<face>(.*?)</face>", text, re.S)
    return m.group(1).strip() if m else ""


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    face = ledger.get("face")
    jacket = ledger.get("jacket")

    if face == "default" and jacket in ("coordinator", "worker"):
        v.append("B-FACE-WRONG-JACKET")
    if face == "orchestration" and jacket == "worker":
        v.append("B-FACE-WRONG-JACKET")
    if face == "default" and ledger.get("wore_coord"):
        v.append("B-LOAD-COORD-ON-FACE")
    if face == "default" and ledger.get("wore_worker"):
        v.append("B-LOAD-WORKER-ON-FACE")
    if face == "orchestration" and ledger.get("wore_worker"):
        v.append("B-LOAD-WORKER-ON-COORD")
    if face == "worker" and ledger.get("wore_coord"):
        v.append("B-LOAD-COORD-ON-WORKER")
    if face == "btw" and jacket == "worker":
        v.append("B-BTW-WORKER")
    if face == "default" and ledger.get("hands_on") and not ledger.get("c_opened_exec"):
        v.append("B-FACE-HANDS")
    if ledger.get("companion_loaded"):
        v.append("B-NO-COMPANION")
    if ledger.get("observer_loaded"):
        v.append("B-NO-OBSERVER")
    if ledger.get("restated_charter_a"):
        v.append("B-RESTATE-A")
    if ledger.get("local_law_requires_unverified_deliver"):
        v.append("B-VS-A-UNVERIFIED")

    coordish = jacket == "coordinator" or face == "orchestration"
    if coordish:
        if ledger.get("hands_on") and not ledger.get("delegated"):
            v.append("B-COORD-HANDS")
        if ledger.get("invented_agent"):
            v.append("B-COORD-INVENT")
        if ledger.get("empty_end_no_fallback"):
            v.append("B-COORD-EMPTY-END")
        if ledger.get("fabricated_process"):
            v.append("B-COORD-FABRICATE")
        if ledger.get("install_without_platform"):
            v.append("B-COORD-INSTALL")

    if jacket == "worker":
        if ledger.get("scheduled_field"):
            v.append("B-WORKER-SCHEDULE")
        if ledger.get("assumed_parent_dialog"):
            v.append("B-WORKER-PARENT-DIALOG")
        if ledger.get("silent_diverge"):
            v.append("B-WORKER-SILENT-DIVERGE")
        if ledger.get("pretended_capability"):
            v.append("B-WORKER-PRETEND")
        if ledger.get("install_without_platform") and not ledger.get("install_authorized"):
            v.append("B-WORKER-INSTALL")
    return v


FIXTURES = [
    {
        "id": "B-OK-1",
        "note": "编排模式：拆派、转述委派结果、自己不动手",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "delegated": True, "hands_on": False,
        },
        "expect": [],
    },
    {
        "id": "B-OK-2",
        "note": "对人默认：无夹克、纯聊、不开执行工具",
        "ledger": {"face": "default", "jacket": "none", "hands_on": False},
        "expect": [],
    },
    {
        "id": "B-OK-3",
        "note": "被委派 Worker：范围内干活，回报委派方",
        "ledger": {"face": "worker", "jacket": "worker", "delegated": True},
        "expect": [],
    },
    {
        "id": "B-OK-4",
        "note": "目录无匹配：派兜底，Coord 不动手",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "delegated": True, "hands_on": False, "used_fallback": True,
        },
        "expect": [],
    },
    {
        "id": "B-OK-5",
        "note": "btw 无 Worker 夹克",
        "ledger": {"face": "btw", "jacket": "none"},
        "expect": [],
    },
    {
        "id": "B-OK-6",
        "note": "委派明显错：Worker 澄清，不静默偏离",
        "ledger": {
            "face": "worker", "jacket": "worker",
            "silent_diverge": False, "asked_clarify": True,
        },
        "expect": [],
    },
    {
        "id": "B-OK-7",
        "note": "项目 C 明确放开后，对人这张脸可动手（不套 Coord/Worker）",
        "ledger": {
            "face": "default", "jacket": "none",
            "hands_on": True, "c_opened_exec": True,
        },
        "expect": [],
    },
    {
        "id": "B-C1",
        "note": "Coord 因更快自己动手",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "hands_on": True, "delegated": False,
        },
        "expect": ["B-COORD-HANDS"],
    },
    {
        "id": "B-C2",
        "note": "臆造执行体名",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "invented_agent": True,
        },
        "expect": ["B-COORD-INVENT"],
    },
    {
        "id": "B-C3",
        "note": "无匹配却空结束",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "empty_end_no_fallback": True,
        },
        "expect": ["B-COORD-EMPTY-END"],
    },
    {
        "id": "B-C4",
        "note": "替执行体补过程",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "fabricated_process": True, "delegated": True,
        },
        "expect": ["B-COORD-FABRICATE"],
    },
    {
        "id": "B-C5",
        "note": "Coord 不走平台入口装执行体",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "install_without_platform": True,
        },
        "expect": ["B-COORD-INSTALL"],
    },
    {
        "id": "B-W1",
        "note": "Worker 调度整场",
        "ledger": {
            "face": "worker", "jacket": "worker", "scheduled_field": True,
        },
        "expect": ["B-WORKER-SCHEDULE"],
    },
    {
        "id": "B-W2",
        "note": "Worker 假设看见父对话",
        "ledger": {
            "face": "worker", "jacket": "worker",
            "assumed_parent_dialog": True,
        },
        "expect": ["B-WORKER-PARENT-DIALOG"],
    },
    {
        "id": "B-W3",
        "note": "委派明显错仍静默大范围偏离",
        "ledger": {
            "face": "worker", "jacket": "worker", "silent_diverge": True,
        },
        "expect": ["B-WORKER-SILENT-DIVERGE"],
    },
    {
        "id": "B-W4",
        "note": "没有的能力假装有",
        "ledger": {
            "face": "worker", "jacket": "worker",
            "pretended_capability": True,
        },
        "expect": ["B-WORKER-PRETEND"],
    },
    {
        "id": "B-W5",
        "note": "Worker 未授权却装卸载",
        "ledger": {
            "face": "worker", "jacket": "worker",
            "install_without_platform": True, "install_authorized": False,
        },
        "expect": ["B-WORKER-INSTALL"],
    },
    {
        "id": "B-F1",
        "note": "对人默认误套 Coord",
        "ledger": {"face": "default", "jacket": "coordinator"},
        "expect": ["B-FACE-WRONG-JACKET"],
    },
    {
        "id": "B-F2",
        "note": "对人默认误套 Worker",
        "ledger": {"face": "default", "jacket": "worker"},
        "expect": ["B-FACE-WRONG-JACKET"],
    },
    {
        "id": "B-U1",
        "note": "对人默认卸岗位，却自称套上编排器",
        "ledger": {"face": "default", "jacket": "none", "wore_coord": True},
        "expect": ["B-LOAD-COORD-ON-FACE"],
    },
    {
        "id": "B-U2",
        "note": "编排只装 Coord，却再套 Worker",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator", "wore_worker": True,
        },
        "expect": ["B-LOAD-WORKER-ON-COORD"],
    },
    {
        "id": "B-U3",
        "note": "被委派只装 Worker，却改当编排器",
        "ledger": {"face": "worker", "jacket": "worker", "wore_coord": True},
        "expect": ["B-LOAD-COORD-ON-WORKER"],
    },
    {
        "id": "B-U4",
        "note": "对人默认，两件岗位都卸，未自称套岗",
        "ledger": {
            "face": "default", "jacket": "none",
            "wore_coord": False, "wore_worker": False,
        },
        "expect": [],
    },
    {
        "id": "B-F3",
        "note": "btw 误套 Worker",
        "ledger": {"face": "btw", "jacket": "worker"},
        "expect": ["B-BTW-WORKER"],
    },
    {
        "id": "B-F4",
        "note": "对人默认未放开却动手",
        "ledger": {
            "face": "default", "jacket": "none",
            "hands_on": True, "c_opened_exec": False,
        },
        "expect": ["B-FACE-HANDS"],
    },
    {
        "id": "B-F5",
        "note": "灌陪伴 situation（已废）",
        "ledger": {"face": "default", "jacket": "none", "companion_loaded": True},
        "expect": ["B-NO-COMPANION"],
    },
    {
        "id": "B-X1",
        "note": "岗位句复读 A 声称/取消",
        "ledger": {
            "face": "orchestration", "jacket": "coordinator",
            "restated_charter_a": True,
        },
        "expect": ["B-RESTATE-A"],
    },
    {
        "id": "B-X2",
        "note": "地方法要求无依据交付（抵 A）",
        "ledger": {
            "face": "worker", "jacket": "worker",
            "local_law_requires_unverified_deliver": True,
        },
        "expect": ["B-VS-A-UNVERIFIED"],
    },
]


def test_promulgation() -> list[str]:
    fails = []
    roles = extract_roles(ROLE_PATH)
    if set(roles) != {"coordinator", "worker"}:
        fails.append(f"夹克种类不对: {sorted(roles)}")
        return fails
    with open(ROLE_PATH, encoding="utf-8") as f:
        whole = f.read()
    if '<situation facing="companion">' in whole:
        fails.append("颁布仍含陪伴 situation")
    if '<utility kind="observer">' in whole:
        fails.append("颁布仍含观察员 utility")
    for kind, body in roles.items():
        if len(body) > 500:
            fails.append(f"{kind} 过长: {len(body)}")
        for ban in BANNED_ANY + BANNED_RESTATE_A:
            if ban in body:
                fails.append(f"{kind} 含禁词: {ban!r}")
    for must in COORD_MUST:
        if must not in roles["coordinator"]:
            fails.append(f"Coord 缺要件: {must}")
    for must in WORKER_MUST:
        if must not in roles["worker"]:
            fails.append(f"Worker 缺要件: {must}")
    return fails


def main():
    failed = []
    rows = []
    print("== B 颁布稿静态（两段 XML，不改岗位）==")
    doc_fails = test_promulgation()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== B 岗位账本 ==")
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
    out = os.path.join(RESULTS, "role_charter.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("-" * 40)
    if failed:
        print(f"FAILED {len(failed)}: {failed}")
        sys.exit(1)
    print(f"OK {len(FIXTURES)} fixtures + promulgation  {out}")


if __name__ == "__main__":
    main()
