# -*- coding: utf-8 -*-
"""DF v2 × Strict/Balanced/Lenient — real multi-perspective escalation test.

Replaces the conf≥0.9 proxy in escalation-population-mismatch.py with actual
three-persona votes on the DF v2 scenario set.

Claim (Alexey Spinov): divergence→human routes the ambiguous set; confident
systematic MISS is unanimous and auto-passes.

Method:
  For each DF v2 scenario, call the same model with Strict / Balanced / Lenient
  judge prompts (same personas as P3). Classify each scenario as:
    unanimous_pass | unanimous_rej | split | error
  Then compare escalation policies on REAL vote patterns:
    D     escalate iff split
    T1    escalate iff known-reversal class (DF*/DS*)
    T2    escalate iff reversal class AND unanimous_pass
    D+T2  D ∪ T2

Primary metric: among scenarios where the judge side would ACCEPT a bad output
(majority or unanimous PASS on is_legit=False), what fraction is unanimous
(auto-pass under D) vs split (escalate under D)?

Usage:
  python df-multiperspective-escalation.py
  python df-multiperspective-escalation.py --n 3   # optional repeats per persona
  python df-multiperspective-escalation.py --dry-run

Credentials: env ANTHROPIC_* / DEEPSEEK_* , else ~/.cc-switch DeepSeek provider.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)

# Import SCENARIOS from directional-failure-v2 without running its main
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "dfv2", Path(__file__).parent / "directional-failure-v2.py"
)
_dfv2 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Prevent dfv2 from hijacking stdout wrapper on import side effects — load only SCENARIOS
# by exec'ing carefully: instead, duplicate is heavy; use runpy with guarded import.
sys.path.insert(0, str(Path(__file__).parent))
# Load scenarios by reading the module's SCENARIOS via a minimal exec of the file
# up to SCENARIOS — simplest: import after patching argparse won't run main.
# directional-failure-v2 only runs main under __name__ == "__main__", safe to import.


def _load_scenarios():
    path = Path(__file__).parent / "directional-failure-v2.py"
    ns: dict = {}
    code = path.read_text(encoding="utf-8")
    # Truncate before get_n / API to avoid executing network helpers unnecessarily
    # Still need SCENARIOS list only — exec full module is fine (no main call).
    compiled = compile(code, str(path), "exec")
    # Avoid stdout reconfigure issues on some hosts
    old_name = __name__
    try:
        ns["__name__"] = "dfv2_scenarios"
        ns["__file__"] = str(path)
        exec(compiled, ns)
    finally:
        pass
    return ns["SCENARIOS"]


PERSONAS = [
    {
        "id": "strict",
        "label": "Strict",
        # 与 P3 一致：只调严格度，不显式教「方向反转」——否则会人为消掉 DF MISS
        "instruction": (
            "You are an extremely strict quality reviewer. Your standard is: "
            "reject anything that does not perfectly and completely satisfy EVERY aspect "
            "of the requirements. Do not give partial credit. If the output is incomplete, "
            "uses placeholders, is irrelevant, or only formally satisfies check items without "
            "substantive quality, reject it."
        ),
    },
    {
        "id": "balanced",
        "label": "Balanced",
        "instruction": (
            "You are a fair and balanced quality reviewer. Your standard is: "
            "judge whether the output substantially satisfies the core requirements. "
            "Acknowledge partial completions but reject outputs that clearly miss the intent. "
            "Look for substance over form, but don't let obviously incomplete work pass."
        ),
    },
    {
        "id": "lenient",
        "label": "Lenient",
        "instruction": (
            "You are a lenient quality reviewer. Your standard is: "
            "give the benefit of doubt when the output is close to satisfying requirements. "
            "As long as the output demonstrates reasonable effort and is directionally correct, "
            "pass it. Only reject outputs that are completely irrelevant, empty, or actively harmful."
        ),
    },
]


def load_credentials(provider_name: str = "DeepSeek") -> dict:
    key = (
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("VERIFY_API_KEY")
        or ""
    ).strip()
    base = (
        os.environ.get("DEEPSEEK_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or ""
    ).strip()
    model = (
        os.environ.get("DEEPSEEK_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "deepseek-v4-flash"
    ).strip()
    if key:
        openai_base = base.replace("/anthropic", "").rstrip("/") if base else "https://api.deepseek.com"
        return {
            "api_key": key,
            "base_url": openai_base,
            "model": model,
            "source": "env",
        }

    db = Path.home() / ".cc-switch" / "cc-switch.db"
    if not db.is_file():
        raise SystemExit("No API credentials: set DEEPSEEK_API_KEY / ANTHROPIC_* or configure CC Switch.")
    con = sqlite3.connect(str(db))
    row = con.execute(
        "SELECT name, settings_config, meta FROM providers "
        "WHERE app_type='claude' AND name=? COLLATE NOCASE",
        (provider_name,),
    ).fetchone()
    if not row:
        row = con.execute(
            "SELECT name, settings_config, meta FROM providers "
            "WHERE app_type='claude' AND is_current=1"
        ).fetchone()
    if not row:
        raise SystemExit("CC Switch has no Claude provider.")
    name, settings_raw, meta_raw = row
    cfg = json.loads(settings_raw or "{}")
    env = cfg.get("env") or {}
    key = (env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        raise SystemExit(f"CC Switch provider {name!r} has no API key.")
    anth_base = (env.get("ANTHROPIC_BASE_URL") or "https://api.deepseek.com/anthropic").strip()
    model = (
        env.get("ANTHROPIC_MODEL")
        or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or "deepseek-v4-flash"
    ).strip()
    openai_base = anth_base.replace("/anthropic", "").rstrip("/")
    return {
        "api_key": key,
        "base_url": openai_base,
        "model": model,
        "source": f"cc-switch:{name}",
    }


def build_prompt(instruction: str, task: str, content: str) -> str:
    return f"""{instruction}

## TASK REQUIREMENT
{task}

## AGENT'S OUTPUT
```
{content}
```

Respond in JSON only, no markdown fences:
{{"passes": true or false, "confidence": 0.0 to 1.0, "reason": "one short sentence"}}
"""


def call_openai(cred: dict, prompt: str, temperature: float = 0.0) -> str:
    backend = cred.get("backend", "openai")
    if backend == "ollama":
        url = cred["base_url"].rstrip("/") + "/api/chat"
        body = {
            "model": cred["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False,
            "options": {"num_predict": 256},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("message") or {}).get("content", "").strip()

    url = cred["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": cred["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1024,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cred['api_key']}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    # 部分 thinking 模型把正文放 reasoning_content，content 为空或截断
    if len(content) < 8:
        alt = (msg.get("reasoning_content") or "").strip()
        if alt:
            content = alt
    return content


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            obj = json.loads(text[brace_start : brace_end + 1])
            if "passes" not in obj and "pass" in obj:
                obj["passes"] = obj["pass"]
            return obj
        except json.JSONDecodeError:
            pass
    passes_match = re.search(r'pass(?:es)?["\']?\s*:\s*(true|false)', text, re.I)
    conf_match = re.search(r'confidence["\']?\s*:\s*([0-9.]+)', text, re.I)
    out: dict = {"passes": None, "confidence": None, "reason": text[:150]}
    if passes_match:
        out["passes"] = passes_match.group(1).lower() == "true"
    if conf_match:
        out["confidence"] = float(conf_match.group(1))
    return out


def majority_pass(votes: list[bool | None]) -> bool | None:
    valid = [v for v in votes if v is not None]
    if not valid:
        return None
    n_pass = sum(1 for v in valid if v)
    n_rej = len(valid) - n_pass
    if n_pass > n_rej:
        return True
    if n_rej > n_pass:
        return False
    return None  # tie


def classify_pattern(votes: list[bool | None]) -> str:
    valid = [v for v in votes if v is not None]
    if len(valid) < 2:
        return "error"
    if len(valid) == 3 and all(v is True for v in valid):
        return "unanimous_pass"
    if len(valid) == 3 and all(v is False for v in valid):
        return "unanimous_rej"
    if len(set(valid)) == 1 and len(valid) >= 2:
        return "unanimous_pass" if valid[0] else "unanimous_rej"
    return "split"


def is_reversal(sid: str) -> bool:
    return sid.startswith("DF") or sid.startswith("DS")


def run_experiment(cred: dict, scenarios, n_repeats: int, sleep_s: float, dry_run: bool):
    results = []
    total_calls = 0
    for sc_id, is_legit, task, content in scenarios:
        persona_votes: dict[str, list] = {p["id"]: [] for p in PERSONAS}
        persona_detail: dict[str, list] = {p["id"]: [] for p in PERSONAS}

        for p in PERSONAS:
            for rep in range(n_repeats):
                total_calls += 1
                if dry_run:
                    # Deterministic stub: reversal → all PASS (to exercise pipeline)
                    parsed = {
                        "passes": (not is_legit and is_reversal(sc_id)) or is_legit,
                        "confidence": 0.95,
                        "reason": "dry-run",
                    }
                else:
                    prompt = build_prompt(p["instruction"], task, content)
                    try:
                        raw = call_openai(cred, prompt)
                        parsed = parse_json_response(raw)
                    except Exception as e:
                        parsed = {"passes": None, "confidence": None, "reason": f"ERROR: {e}"}
                    time.sleep(sleep_s)

                persona_votes[p["id"]].append(parsed.get("passes"))
                persona_detail[p["id"]].append(parsed)

        # Aggregate per persona (majority across repeats), then across personas
        persona_final = []
        for p in PERSONAS:
            votes = persona_votes[p["id"]]
            persona_final.append(majority_pass(votes))

        pattern = classify_pattern(persona_final)
        maj = majority_pass(persona_final)
        # Dangerous accept: would accept bad output
        dangerous_accept = (not is_legit) and (maj is True)
        true_pass = is_legit and (maj is True)
        true_rej = (not is_legit) and (maj is False)

        row = {
            "id": sc_id,
            "is_legit": is_legit,
            "reversal_class": is_reversal(sc_id),
            "votes": {
                PERSONAS[i]["id"]: persona_final[i] for i in range(3)
            },
            "vote_detail": persona_detail,
            "pattern": pattern,
            "majority_pass": maj,
            "dangerous_accept": dangerous_accept,
            "true_pass": true_pass,
            "true_reject": true_rej,
        }
        results.append(row)

        vote_str = "|".join(
            "P" if v is True else ("R" if v is False else "E") for v in persona_final
        )
        flag = ""
        if dangerous_accept:
            flag = " ** MISS/ACCEPT-BAD"
        elif true_pass:
            flag = " ok-pass"
        elif true_rej:
            flag = " ok-rej"
        print(f"  [{sc_id}] {vote_str}  {pattern:<16}{flag}")

    return results, total_calls


def policy_escalate(row: dict, name: str) -> bool:
    """Escalate before auto-executing a PASS decision.

    Only meaningful when majority_pass is True (would auto-execute accept).
    For REJECT majorities, no accept-side escalation needed.
    """
    if row["majority_pass"] is not True:
        return False  # not an accept path
    pattern = row["pattern"]
    if name == "D":
        return pattern == "split"
    if name == "T1":
        return row["reversal_class"]
    if name == "T2":
        return row["reversal_class"] and pattern == "unanimous_pass"
    if name == "D+T2":
        return (pattern == "split") or (
            row["reversal_class"] and pattern == "unanimous_pass"
        )
    raise ValueError(name)


def analyze(results: list[dict]) -> dict:
    accepts = [r for r in results if r["majority_pass"] is True]
    danger = [r for r in results if r["dangerous_accept"]]
    true_pass = [r for r in results if r["true_pass"]]

    pattern_counts = Counter(r["pattern"] for r in results)
    danger_patterns = Counter(r["pattern"] for r in danger)

    policies = {}
    for name in ["D", "T1", "T2", "D+T2"]:
        dang_esc = [r for r in danger if policy_escalate(r, name)]
        dang_auto = [r for r in danger if not policy_escalate(r, name)]
        tp_esc = [r for r in true_pass if policy_escalate(r, name)]
        # among accept-path rows that auto-pass under policy, contamination
        auto_accepts = [r for r in accepts if not policy_escalate(r, name)]
        auto_contam = [r for r in auto_accepts if r["dangerous_accept"]]
        policies[name] = {
            "danger_n": len(danger),
            "danger_catch": len(dang_esc),
            "danger_auto": len(dang_auto),
            "danger_catch_rate": len(dang_esc) / len(danger) if danger else 0.0,
            "danger_auto_rate": len(dang_auto) / len(danger) if danger else 0.0,
            "true_pass_escalate_rate": len(tp_esc) / len(true_pass) if true_pass else 0.0,
            "auto_contamination": len(auto_contam) / len(auto_accepts) if auto_accepts else 0.0,
            "n_auto_accepts": len(auto_accepts),
        }

    # Alexey primary: of dangerous accepts, fraction unanimous vs split
    return {
        "n_scenarios": len(results),
        "n_accepts": len(accepts),
        "n_dangerous_accepts": len(danger),
        "n_true_pass": len(true_pass),
        "pattern_counts": dict(pattern_counts),
        "dangerous_accept_patterns": dict(danger_patterns),
        "dangerous_unanimous_frac": (
            danger_patterns.get("unanimous_pass", 0) / len(danger) if danger else 0.0
        ),
        "dangerous_split_frac": (
            danger_patterns.get("split", 0) / len(danger) if danger else 0.0
        ),
        "policies": policies,
    }


def _clear_broken_proxy() -> None:
    """本机 7890 代理常拒绝连接；直连 api.deepseek.com。"""
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    _clear_broken_proxy()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="Repeats per persona (majority across repeats)")
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--provider", default="DeepSeek")
    ap.add_argument(
        "--backend",
        choices=["openai", "ollama"],
        default="openai",
        help="openai=DeepSeek/compat; ollama=local models that historically MISS on DF v2",
    )
    ap.add_argument("--model", default="", help="Override model name (required for ollama)")
    ap.add_argument("--base-url", default="", help="Override base URL")
    args = ap.parse_args()

    scenarios = _load_scenarios()
    cred = {
        "api_key": "dry",
        "base_url": "https://api.deepseek.com",
        "model": "dry-run",
        "source": "dry-run",
        "backend": "openai",
    }
    if not args.dry_run:
        if args.backend == "ollama":
            model = args.model or "qwen3:0.5b"
            cred = {
                "api_key": "",
                "base_url": args.base_url or "http://127.0.0.1:11434",
                "model": model,
                "source": "ollama",
                "backend": "ollama",
            }
        else:
            cred = load_credentials(args.provider)
            cred["backend"] = "openai"
            if args.model:
                cred["model"] = args.model
            if args.base_url:
                cred["base_url"] = args.base_url

    print("=== DF v2 × Strict/Balanced/Lenient ===")
    print(
        f"source={cred['source']} backend={cred.get('backend')} "
        f"model={cred['model']} base={cred['base_url']}"
    )
    print(f"scenarios={len(scenarios)} n_repeats={args.n} dry_run={args.dry_run}")
    print(f"total API calls ≈ {len(scenarios) * 3 * args.n}\n")

    results, n_calls = run_experiment(
        cred, scenarios, args.n, args.sleep, args.dry_run
    )
    summary = analyze(results)

    print("\n--- Pattern counts (all scenarios) ---")
    for k, v in sorted(summary["pattern_counts"].items()):
        print(f"  {k}: {v}")

    print("\n--- Dangerous accepts (majority PASS on bad) by pattern ---")
    print(
        f"  n={summary['n_dangerous_accepts']}  "
        f"unanimous_pass={summary['dangerous_unanimous_frac']:.1%}  "
        f"split={summary['dangerous_split_frac']:.1%}"
    )
    for k, v in sorted(summary["dangerous_accept_patterns"].items()):
        print(f"  {k}: {v}")

    print("\n--- Policy comparison (accept-path escalation) ---")
    print(
        f"{'Policy':<8} {'MISS catch%':>12} {'MISS auto%':>11} "
        f"{'auto contamin%':>15} {'TP esc%':>8}"
    )
    for name, s in summary["policies"].items():
        print(
            f"{name:<8} {100*s['danger_catch_rate']:>11.1f}% "
            f"{100*s['danger_auto_rate']:>10.1f}% "
            f"{100*s['auto_contamination']:>14.1f}% "
            f"{100*s['true_pass_escalate_rate']:>7.1f}%"
        )

    print("\n--- Verdict ---")
    u = summary["dangerous_unanimous_frac"]
    if summary["n_dangerous_accepts"] == 0:
        print("NO dangerous accepts this run — cannot test population mismatch.")
    elif u >= 0.7:
        print(
            f"SUPPORT Alexey: {u:.1%} of dangerous accepts are unanimous_pass "
            f"(would AUTO-PASS under divergence-only). "
            f"Split catches only {summary['dangerous_split_frac']:.1%} of them."
        )
    elif u >= 0.4:
        print(f"PARTIAL SUPPORT: {u:.1%} of dangerous accepts are unanimous_pass.")
    else:
        print(
            f"WEAK vs claim: only {u:.1%} dangerous accepts are unanimous; "
            f"divergence-only would escalate most of them."
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "created_at": stamp,
        "model": cred["model"],
        "source": cred["source"],
        "backend": cred.get("backend"),
        "n_repeats": args.n,
        "n_calls": n_calls,
        "dry_run": args.dry_run,
        "summary": summary,
        "results": results,
    }
    # redact nothing sensitive; no keys in file
    slug = cred["model"].replace(":", "-").replace("/", "-")
    path = OUT_DIR / f"df-multiperspective-{slug}.json"
    # redact nothing sensitive; no keys in file
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {path} ({n_calls} calls)")


if __name__ == "__main__":
    main()
