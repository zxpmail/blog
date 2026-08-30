# -*- coding: utf-8 -*-
"""装卸方案静态检查。不调模型。"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_PATH = os.path.join(HERE, "loader.md")

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
)
BANNED = (
    "默认脸",
    "这一窗",
    "稳 C",
    "facing",
)


def main() -> int:
    with open(SCHEME_PATH, encoding="utf-8") as f:
        text = f.read()
    fails = []
    for must in MUST:
        if must not in text:
            fails.append(f"方案缺：{must}")
    for ban in BANNED:
        if ban in text:
            fails.append(f"方案仍含：{ban}")
    print("== 装卸方案静态 ==")
    if fails:
        for x in fails:
            print("  FAIL", x)
        return 1
    print("  PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
