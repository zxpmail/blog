# -*- coding: utf-8 -*-
"""Ext 任务扩展实验（3.0 目标）：条文自洽 + 账本。默认不调模型。"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEME_PATH = os.path.join(HERE, "ext.md")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

MUST = (
    "可以没有",
    "没写就是空",
    "黄页",
    "手写",
    "禁止从 Ext 自动摘",
    "不灌 Ext",
    "被点到",
    "任务单走子的 user",
    "不授予",
    "写了也不算",
    "由装载器按入口表执行",
)
BANNED = ("夹克",)


def load_scheme(path: str = SCHEME_PATH) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def judge(ledger: dict) -> list[str]:
    v: list[str] = []
    face = ledger.get("face")
    if face == "orchestration" and ledger.get("wore_ext"):
        v.append("EXT-COORD")
    if face == "default" and ledger.get("wore_ext"):
        v.append("EXT-DEFAULT")
    if ledger.get("yellow_from_ext"):
        v.append("EXT-YELLOW-EXCERPT")
    if ledger.get("loaded_unpicked"):
        v.append("EXT-UNPICKED")
    if ledger.get("wore_soul"):
        v.append("EXT-SOUL")
    if ledger.get("ext_grants_tools"):
        v.append("EXT-GRANT")
    if ledger.get("agents_md_as_ext"):
        v.append("EXT-AGENTS-MD")
    if ledger.get("third_role"):
        v.append("EXT-THIRD-ROLE")
    if ledger.get("rewrote_done"):
        v.append("EXT-VS-A")
    if ledger.get("rewrote_job"):
        v.append("EXT-REWRITE-JOB")
    return v


FIXTURES = [
    {
        "id": "EXT-OK-1",
        "note": "兜底没写 Ext，空着仍套 Worker",
        "ledger": {"face": "worker", "ext": None, "wore_ext": False},
        "expect": [],
    },
    {
        "id": "EXT-OK-2",
        "note": "编排窗只有手写黄页",
        "ledger": {
            "face": "orchestration", "wore_ext": False,
            "yellow": "fpga-sim：跑仿真", "yellow_from_ext": False,
        },
        "expect": [],
    },
    {
        "id": "EXT-OK-3",
        "note": "被点到才灌那一篇",
        "ledger": {
            "face": "worker", "picked": "fpga-sim",
            "loaded": ["fpga-sim"], "loaded_unpicked": False,
        },
        "expect": [],
    },
    {
        "id": "EXT-OK-4",
        "note": "仓库 AGENTS.md 当 C，不当 Ext",
        "ledger": {"agents_md_as_ext": False},
        "expect": [],
    },
    {
        "id": "EXT-OK-5",
        "note": "默认脸不灌 Ext",
        "ledger": {"face": "default", "wore_ext": False},
        "expect": [],
    },
    {
        "id": "EXT-OK-6",
        "note": "工具以本轮授权为准",
        "ledger": {"ext_grants_tools": False, "tools_from": "grant"},
        "expect": [],
    },
    {
        "id": "EXT-OK-7",
        "note": "卸的是窗，注册表还在",
        "ledger": {"window_dropped_ext": True, "registry_cleared": False},
        "expect": [],
    },
    {
        "id": "EXT-OK-8",
        "note": "同名只灌被派的那一篇",
        "ledger": {
            "same_name": True, "picked": "fpga-sim",
            "loaded": ["fpga-sim"], "loaded_unpicked": False,
        },
        "expect": [],
    },
    {
        "id": "EXT-X1",
        "note": "编排窗灌了 Ext",
        "ledger": {"face": "orchestration", "wore_ext": True},
        "expect": ["EXT-COORD"],
    },
    {
        "id": "EXT-X2",
        "note": "从 Ext 摘长文当黄页",
        "ledger": {"yellow_from_ext": True},
        "expect": ["EXT-YELLOW-EXCERPT"],
    },
    {
        "id": "EXT-X3",
        "note": "灌了没点到的专家正文",
        "ledger": {"loaded_unpicked": True},
        "expect": ["EXT-UNPICKED"],
    },
    {
        "id": "EXT-X4",
        "note": "干活还灌灵魂",
        "ledger": {"wore_soul": True},
        "expect": ["EXT-SOUL"],
    },
    {
        "id": "EXT-X5",
        "note": "Ext 写你有 Write 就算授予",
        "ledger": {"ext_grants_tools": True},
        "expect": ["EXT-GRANT"],
    },
    {
        "id": "EXT-X6",
        "note": "对人默认灌 Ext",
        "ledger": {"face": "default", "wore_ext": True},
        "expect": ["EXT-DEFAULT"],
    },
    {
        "id": "EXT-X7",
        "note": "AGENTS.md 当成 Ext",
        "ledger": {"agents_md_as_ext": True},
        "expect": ["EXT-AGENTS-MD"],
    },
    {
        "id": "EXT-X8",
        "note": "Ext 升成第三岗",
        "ledger": {"third_role": True},
        "expect": ["EXT-THIRD-ROLE"],
    },
    {
        "id": "EXT-X9",
        "note": "Ext 改什么叫做完",
        "ledger": {"rewrote_done": True},
        "expect": ["EXT-VS-A"],
    },
    {
        "id": "EXT-X10",
        "note": "Ext 改成编排器",
        "ledger": {"rewrote_job": True},
        "expect": ["EXT-REWRITE-JOB"],
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
    print("== Ext 方案静态（实验）==")
    doc_fails = test_scheme()
    if doc_fails:
        for x in doc_fails:
            print("  FAIL", x)
            failed.append("DOC " + x)
    else:
        print("  PASS")
    print("== Ext 账本（实验）==")
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
    out = os.path.join(RESULTS, "agent_ext.jsonl")
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
