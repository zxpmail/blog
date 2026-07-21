#!/usr/bin/env bash
# P1：在 Linux（或本 Dockerfile）上跑齐环境感知超时 + tmpfs + selfdestruct
set -euo pipefail
cd "$(dirname "$0")"

echo "=== host: $(uname -a) ==="
echo "=== /dev/shm fstype ==="
df -T /dev/shm || true
export CRASH_TEST_EPHEMERAL_ROOT="${CRASH_TEST_EPHEMERAL_ROOT:-/dev/shm}"

python3 crash-test-chaos.py
python3 crash-test-adversarial.py
python3 crash-test-reset.py

echo ""
echo "=== P1 summary (jq optional) ==="
python3 - <<'PY'
import json
from pathlib import Path
for name in ("chaos", "adversarial", "reset"):
    p = Path(f"results-v2/crash-test-{name}_result.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    em = d.get("evidence_map", {})
    print(f"--- {name} ---")
    if name == "chaos":
        print("  PHYSICAL_TIMEOUT_MS", d.get("arch_constants", {}).get("PHYSICAL_TIMEOUT_MS"))
        print("  BASELINE_RTT_MS", d.get("arch_constants", {}).get("BASELINE_RTT_MS"))
    if name == "adversarial":
        print("  selfdestruct_verified", d.get("selfdestruct_verified"))
        print("  process_probe.pass", (d.get("selfdestruct_process_probe") or {}).get("pass"))
    if name == "reset":
        print("  is_truly_ephemeral", d.get("is_truly_ephemeral"))
        print("  storage_compliant", d.get("storage_compliant"))
    print("  supports:", em.get("supports"))
    print("  does_not_support:", em.get("does_not_support"))
PY
