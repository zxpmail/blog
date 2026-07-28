# -*- coding: utf-8 -*-
import json
import urllib.request
from pathlib import Path

cfg = json.loads(Path(__file__).parent.joinpath("data/.deepseek_env.json").read_text(encoding="utf-8"))
payload = {
    "model": cfg["DEEPSEEK_MODEL"],
    "temperature": 0,
    "max_tokens": 64,
    "messages": [
        {
            "role": "user",
            "content": 'Reply with JSON only: {"faithful": true, "confidence": 0.9}',
        }
    ],
}
req = urllib.request.Request(
    cfg["DEEPSEEK_BASE_URL"].rstrip("/") + "/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + cfg["DEEPSEEK_API_KEY"],
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as r:
    body = json.loads(r.read().decode("utf-8"))
print("deepseek_ok:", body["choices"][0]["message"]["content"][:200])
