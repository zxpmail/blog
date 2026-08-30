# -*- coding: utf-8 -*-
"""D 操作手册实验（3.0 目标）：条文自洽 + 账本。默认不调模型。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_PATH = os.path.join(HERE, "operations.md")
EXTRACT_DIR = os.path.join(HERE, "D")
EXTRACT_FILES = (
    "D1-orchestration.md",
    "D1-worker.md",
    "D2.md",
    "D3.md",
    "D4.md",
    "D7.md",
)
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "没写的主题就是空",
    "这次对话",
    "禁止整本灌进这次对话",
    "由装载器按主题路由",
    "不灌 D1 委派百科",
    "D1 + D2",
    "编排必须灌 D1 + D2",
    "用户说别灌也不卸",
    "搜写拆分属 D",
    "必须自洽",
    "按上面说的做」也不算",
    "任务单走子 user 属 C",
    "触顶是部分结果",
    "只回 `done` 不算",
    "盖不住 A",
    "不进 B 颁布稿",
    "写了也不算",
    "对人默认",
    "拒绝三分",
    "分标记在 G",
    "点名哪个工具是实现",
    "目标提示词",
    "D1-orchestration",
    "D1-worker",
    "手册随工具",
    "不要缩范围",
    "旧进度不当令",
    "D3.md",
    "短追问粘当前话题",
    "指代先消解",
)
BANNED = (
    "默认脸",
    "这一窗",
    "稳 D",
    "facing",
)


def load_scheme(path: str = SCHEME_PATH) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    face = ledger.get("face")
    if ledger.get("dump_all_themes"):
        v.append("D-DUMP-ALL")
    if face == "default" and ledger.get("has_d1"):
        v.append("D-D1-DEFAULT")
    if face == "orchestration" and ledger.get("has_d1") is False:
        v.append("D-ORCH-NO-D1")
    if face == "orchestration" and ledger.get("has_d2") is False:
        v.append("D-ORCH-NO-D2")
    if face == "orchestration" and ledger.get("has_domain_long"):
        v.append("D-ORCH-DOMAIN")
    if ledger.get("search_write_in_role"):
        v.append("D-SEARCH-WRITE-IN-B")
    if ledger.get("lead_self_as_coord_law"):
        v.append("D-LEAD-SELF")
    if face == "worker" and ledger.get("task_self_contained") is False:
        v.append("D-TASK-INCOHERENT")
    if face == "worker" and ledger.get("report_done_only"):
        v.append("D-DONE-ONLY")
    if face == "worker" and ledger.get("has_parent_d1"):
        v.append("D-PARENT-D1")
    if face == "btw" and ledger.get("has_d"):
        v.append("D-BTW")
    if face == "group" and ledger.get("has_d1"):
        v.append("D-GROUP-D1")
    if ledger.get("cap_as_new_delivery"):
        v.append("D-CAP-AS-NEW")
    if ledger.get("promise_without_handle"):
        v.append("D-PROMISE-EMPTY")
    if ledger.get("claimed_complete_without_artifact"):
        v.append("D-OVERRIDE-A")
    if ledger.get("steps_rewrite_job"):
        v.append("D-REWRITE-JOB")
    if ledger.get("mix_reject_kinds"):
        v.append("D-REJECT-MIX")
    if ledger.get("reject_prompt_replaces_gate"):
        v.append("D-REJECT-AS-G")
    if face == "worker" and ledger.get("retry_deny_self"):
        v.append("D-WORKER-DENY-RETRY")
    if ledger.get("shrink_scope"):
        v.append("D-SHRINK-SCOPE")
    if ledger.get("d3_as_plan_gate"):
        v.append("D-D3-AS-GATE")
    return v


FIXTURES = [
    {
        "id": "D-OK-1",
        "note": "对人默认：可空，无 D1 委派百科",
        "ledger": {"face": "default", "has_d1": False, "dump_all_themes": False},
        "expect": [],
    },
    {
        "id": "D-OK-2",
        "note": "编排：D1+D2，搜写在 D，无领域长步骤",
        "ledger": {
            "face": "orchestration", "has_d1": True, "has_d2": True,
            "has_domain_long": False, "search_write_in_role": False,
            "lead_self_as_coord_law": False,
        },
        "expect": [],
    },
    {
        "id": "D-OK-3",
        "note": "被委派：任务单自洽，有回报，无父 D1",
        "ledger": {
            "face": "worker", "task_self_contained": True,
            "report_done_only": False, "has_parent_d1": False,
            "retry_deny_self": False,
        },
        "expect": [],
    },
    {
        "id": "D-OK-4",
        "note": "同活同写集 continue；触顶不装新交付",
        "ledger": {"cap_as_new_delivery": False},
        "expect": [],
    },
    {
        "id": "D-OK-5",
        "note": "许诺后续有句柄",
        "ledger": {"promise_without_handle": False},
        "expect": [],
    },
    {
        "id": "D-OK-6",
        "note": "细则盖不住 A；步骤不改岗",
        "ledger": {
            "claimed_complete_without_artifact": False,
            "steps_rewrite_job": False,
        },
        "expect": [],
    },
    {
        "id": "D-OK-7",
        "note": "旁问不灌 D；跨用户房无 1:1 委派百科",
        "ledger": {"face": "btw", "has_d": False},
        "expect": [],
    },
    {
        "id": "D-OK-8",
        "note": "跨用户房不灌 D1",
        "ledger": {"face": "group", "has_d1": False},
        "expect": [],
    },
    {
        "id": "D-OK-9",
        "note": "三种拒分开说；分标记在 G",
        "ledger": {"mix_reject_kinds": False, "reject_prompt_replaces_gate": False},
        "expect": [],
    },
    {
        "id": "D-OK-10",
        "note": "不缩范围；薄 D3 不假装计划闸",
        "ledger": {"shrink_scope": False, "d3_as_plan_gate": False},
        "expect": [],
    },
    {
        "id": "D-X1",
        "note": "整本灌进这次对话",
        "ledger": {"dump_all_themes": True},
        "expect": ["D-DUMP-ALL"],
    },
    {
        "id": "D-X2",
        "note": "对人默认灌 D1 委派百科",
        "ledger": {"face": "default", "has_d1": True},
        "expect": ["D-D1-DEFAULT"],
    },
    {
        "id": "D-X3",
        "note": "编排缺 D1+D2，还灌领域长步骤",
        "ledger": {
            "face": "orchestration", "has_d1": False, "has_d2": False,
            "has_domain_long": True,
        },
        "expect": ["D-ORCH-NO-D1", "D-ORCH-NO-D2", "D-ORCH-DOMAIN"],
    },
    {
        "id": "D-X4",
        "note": "搜写写进岗；Lead 默认自己干当编排法",
        "ledger": {"search_write_in_role": True, "lead_self_as_coord_law": True},
        "expect": ["D-SEARCH-WRITE-IN-B", "D-LEAD-SELF"],
    },
    {
        "id": "D-X5",
        "note": "任务单不自洽；只回 done；灌父 D1",
        "ledger": {
            "face": "worker", "task_self_contained": False,
            "report_done_only": True, "has_parent_d1": True,
        },
        "expect": ["D-TASK-INCOHERENT", "D-DONE-ONLY", "D-PARENT-D1"],
    },
    {
        "id": "D-X6",
        "note": "触顶假装新交付",
        "ledger": {"cap_as_new_delivery": True},
        "expect": ["D-CAP-AS-NEW"],
    },
    {
        "id": "D-X7",
        "note": "空口稍后处理",
        "ledger": {"promise_without_handle": True},
        "expect": ["D-PROMISE-EMPTY"],
    },
    {
        "id": "D-X8",
        "note": "无物为完成；步骤改成自己上手",
        "ledger": {
            "claimed_complete_without_artifact": True,
            "steps_rewrite_job": True,
        },
        "expect": ["D-OVERRIDE-A", "D-REWRITE-JOB"],
    },
    {
        "id": "D-X9",
        "note": "旁问灌 D",
        "ledger": {"face": "btw", "has_d": True},
        "expect": ["D-BTW"],
    },
    {
        "id": "D-X10",
        "note": "跨用户房灌 1:1 委派百科",
        "ledger": {"face": "group", "has_d1": True},
        "expect": ["D-GROUP-D1"],
    },
    {
        "id": "D-X11",
        "note": "三种拒混成一种；用长文代替分标记",
        "ledger": {"mix_reject_kinds": True, "reject_prompt_replaces_gate": True},
        "expect": ["D-REJECT-MIX", "D-REJECT-AS-G"],
    },
    {
        "id": "D-X12",
        "note": "自己重试升权；缩范围当交付；D3 当计划闸",
        "ledger": {
            "face": "worker", "retry_deny_self": True,
            "shrink_scope": True, "d3_as_plan_gate": True,
        },
        "expect": ["D-WORKER-DENY-RETRY", "D-SHRINK-SCOPE", "D-D3-AS-GATE"],
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
        if "<playbook" not in body:
            fails.append(f"{name} 无 <playbook>")
        for ban in BANNED:
            if ban in body:
                fails.append(f"{name} 仍含：{ban}")
        if "G1" in body or "G12" in body:
            fails.append(f"{name} 含缺口编号")
    return fails


def main() -> int:
    failed = []
    rows = []
    print("== D 方案静态（实验）==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== D 账本（实验）==")
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
    out = os.path.join(RESULTS, "playbook_d.jsonl")
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
