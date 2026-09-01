# -*- coding: utf-8 -*-
"""A–G 整体：先各层账本（不调模型），再模型实验（无 key 自 SKIP）。G 不进 system。

仓内真源版：模型面直接调 charter_model.py（读环境变量 / ~/.gnex/gnex.local.yml），
不走 _cc_switch_run_model.py（那是实验场私设，读本机 cc-switch.db，不进仓）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent

LEDGERS = (
    "charter_constitution.py",
    "role_charter.py",
    "behavior_prime.py",
    "agent_ext.py",
    "context_c.py",
    "playbook_d.py",
    "gate_g.py",
    "loader.py",
)


def main() -> int:
    print("== A–G 整体：账本（不调模型）==")
    for name in LEDGERS:
        print(f"-- {name}")
        code = subprocess.call([sys.executable, "-u", str(HERE / name)])
        if code != 0:
            print(f"FAIL ledger {name} exit={code}")
            return code
    print("== A–G 整体：模型（按入口满栈；G 不进 system）==")
    os.environ["CHARTER_SUITE"] = "ag"
    return subprocess.call(
        [sys.executable, "-u", str(HERE / "charter_model.py")],
    )


if __name__ == "__main__":
    raise SystemExit(main())
