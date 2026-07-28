# -*- coding: utf-8 -*-
"""Load DeepSeek env from ~/.cc-switch/cc-switch.db into a local JSON (not for commit)."""
import json
import sqlite3
from pathlib import Path

db = Path.home() / ".cc-switch" / "cc-switch.db"
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, name, settings_config, is_current FROM providers "
    "WHERE lower(name) LIKE '%deepseek%' ORDER BY is_current DESC, created_at DESC"
).fetchall()
conn.close()
if not rows:
    raise SystemExit("no deepseek provider")
cfg = json.loads(rows[0]["settings_config"] or "{}")
env = cfg.get("env") or {}
key = (
    env.get("ANTHROPIC_AUTH_TOKEN")
    or env.get("ANTHROPIC_API_KEY")
    or env.get("DEEPSEEK_API_KEY")
    or ""
).strip()
model = (
    env.get("ANTHROPIC_MODEL")
    or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
    or "deepseek-v4-flash"
).strip()
out = {
    "DEEPSEEK_API_KEY": key,
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "DEEPSEEK_MODEL": model,
}
dest = Path(__file__).parent / "data" / ".deepseek_env.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("provider:", rows[0]["name"])
print("model:", model)
print("key_prefix:", (key[:6] + "***") if key else "MISSING")
print("wrote:", dest)
