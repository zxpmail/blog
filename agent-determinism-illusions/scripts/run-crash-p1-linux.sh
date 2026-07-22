#!/usr/bin/env bash
# P1：在 Linux（或本 Dockerfile）上跑齐环境感知超时 + tmpfs + selfdestruct
set -euo pipefail
cd "$(dirname "$0")"

echo "=== host: $(uname -a) ==="
echo "=== /dev/shm fstype ==="
df -T /dev/shm || true
export CRASH_TEST_EPHEMERAL_ROOT="${CRASH_TEST_EPHEMERAL_ROOT:-/dev/shm}"
# 可选：墙钟 60s 死亡收尾（默认开，可用 CRASH_TEST_FULL_WIND_DOWN=0 关掉）
export CRASH_TEST_FULL_WIND_DOWN="${CRASH_TEST_FULL_WIND_DOWN:-1}"

python3 crash-test-chaos.py
python3 crash-test-adversarial.py
python3 crash-test-reset.py
python3 crash-test-kernel-compose.py
python3 crash-test-harness-kernel.py
python3 prod-gate-acceptance.py

echo ""
echo "=== P1 summary (jq optional) ==="
python3 - <<'PY'
import json
from pathlib import Path
for name in ("chaos", "adversarial", "reset", "kernel-compose", "harness-kernel"):
    p = Path(f"results-v2/crash-test-{name}_result.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    em = d.get("evidence_map", {})
    print(f"--- {name} ---")
    if name == "chaos":
        print("  PHYSICAL_TIMEOUT_MS", d.get("arch_constants", {}).get("PHYSICAL_TIMEOUT_MS"))
        print("  BASELINE_RTT_MS", d.get("arch_constants", {}).get("BASELINE_RTT_MS"))
        print("  net_delay_mode", d.get("net_delay_mode"))
        print("  degraded", (d.get("env_health") or {}).get("degraded"))
        print("  os_signal_kill_probe.pass", (d.get("os_signal_kill_probe") or {}).get("pass"))
    if name == "adversarial":
        print("  selfdestruct_verified", d.get("selfdestruct_verified"))
        print("  process_probe.pass", (d.get("selfdestruct_process_probe") or {}).get("pass"))
        print("  token_budget_probe.pass", (d.get("token_budget_probe") or {}).get("pass"))
        print("  startle_reflex_probe.pass", (d.get("startle_reflex_probe") or {}).get("pass"))
    if name == "reset":
        print("  is_truly_ephemeral", d.get("is_truly_ephemeral"))
        print("  storage_compliant", d.get("storage_compliant"))
        print("  session_lifetime_probe.pass", (d.get("session_lifetime_probe") or {}).get("pass"))
        print("  death_wind_down_probe.pass", (d.get("death_wind_down_probe") or {}).get("pass"))
        print("  wallclock_probe.pass", (d.get("death_wind_down_wallclock_probe") or {}).get("pass"))
        print("  git_shred_probe.pass", (d.get("git_objects_shred_probe") or {}).get("pass"))
        print("  shred_scan_scope", (d.get("git_objects_shred_probe") or {}).get("scan_scope"))
    if name == "kernel-compose":
        print("  overall_pass", d.get("overall_pass"))
        arms = d.get("arms") or {}
        for k, v in arms.items():
            print(f"  arm.{k}.pass", v.get("pass"))
    if name == "harness-kernel":
        print("  overall_pass", d.get("overall_pass"))
        arms = d.get("arms") or {}
        for k, v in arms.items():
            print(f"  arm.{k}.pass", v.get("pass"))
    print("  supports:", em.get("supports"))
    print("  does_not_support:", em.get("does_not_support"))

p = Path("results-v2/prod-gate-acceptance_result.json")
if p.is_file():
    d = json.loads(p.read_text(encoding="utf-8"))
    em = d.get("evidence_map", {})
    print("--- prod-gate-acceptance ---")
    print("  overall_pass", d.get("overall_pass"))
    for k, v in (d.get("arms") or {}).items():
        print(f"  arm.{k}.pass", v.get("pass"))
    print("  stance:", em.get("stance"))
    print("  supports:", em.get("supports"))
    print("  does_not_support:", em.get("does_not_support"))
PY
