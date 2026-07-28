# -*- coding: utf-8 -*-
"""Agree-set HaluEval probe — Tom Jones Part 15 mirror (DeepSeek × gemma3).

Question / claims from Tom Jones (2026-07-28):
  1) On the agree-set: P(wrong | they agree) can be large on real traffic;
     the auto-pass lane may already hold the mass.
  2) Same-model pairs agree more than cross-model pairs (provider-collapse
     mirror under controlled backends).
  3) P(both wrong | disagree) = 0 is construction under binary verdicts —
     do not report as evidence.

This script:
  - Downloads HaluEval qa + summarization JSON if missing
  - Stratified sample (default n=70 matching Tom) or --full for all rows
  - Two judges: DeepSeek (OpenAI-compat API) + Ollama gemma3:latest
  - Faithfulness binary: is the candidate answer/summary faithful to evidence?
  - Gold: right_* = faithful (label OK); hallucinated_* = not faithful (label BAD)

Metrics:
  agreement_rate, P(wrong|agree) + Wilson 95% CI, by family
  same_model_agreement (gemma×gemma second draw) vs cross (deepseek×gemma)

Env:
  DEEPSEEK_API_KEY or OPENAI_API_KEY or ANTHROPIC_AUTH_TOKEN
  DEEPSEEK_BASE_URL (default https://api.deepseek.com)
  DEEPSEEK_MODEL (default deepseek-chat)
  OLLAMA_HOST (default http://127.0.0.1:11434)
  OLLAMA_MODEL (default gemma3:latest)

Run:
  python agree-set-halueval-probe.py --n 70 --seed 7
  python agree-set-halueval-probe.py --full --seed 7
  python agree-set-halueval-probe.py --n 70 --skip-deepseek   # ollama-only dry path
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).parent
RESULTS = ROOT / "results-v2"
DATA_DIR = ROOT / "data" / "halueval"
OUT = RESULTS / "agree-set-halueval.json"
CHECKPOINT = RESULTS / "agree-set-halueval.checkpoint.jsonl"

QA_URLS = [
    "https://cdn.jsdelivr.net/gh/RUCAIBox/HaluEval@main/data/qa_data.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/data/qa_data.json",
    "https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/data/qa_data.json",
]
SUM_URLS = [
    "https://ghproxy.net/https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/data/summarization_data.json",
    "https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/data/summarization_data.json",
]


def download_first(urls: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return
    last_err: Exception | None = None
    for url in urls:
        print(f"Downloading {url} → {dest}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
            if dest.stat().st_size > 1000:
                return
        except Exception as e:
            last_err = e
            print(f"  fail: {e}")
    raise RuntimeError(f"could not download {dest.name}: {last_err}")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - margin) / den), min(1.0, (centre + margin) / den))


def load_json_array(path: Path) -> list[dict]:
    print(f"Loading {path.name}…", flush=True)
    text = path.read_text(encoding="utf-8")
    text = text.strip()
    if text.startswith("["):
        rows = json.loads(text)
    else:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"  {path.name}: {len(rows)} rows", flush=True)
    return rows


def row_to_items(family: str, i: int, r: dict) -> list[dict]:
    if family == "qa":
        return [
            {
                "family": "qa",
                "src_idx": i,
                "gold_ok": True,
                "evidence": r.get("knowledge", ""),
                "prompt_user": r.get("question", ""),
                "candidate": r.get("right_answer", ""),
                "kind": "right_answer",
            },
            {
                "family": "qa",
                "src_idx": i,
                "gold_ok": False,
                "evidence": r.get("knowledge", ""),
                "prompt_user": r.get("question", ""),
                "candidate": r.get("hallucinated_answer", ""),
                "kind": "hallucinated_answer",
            },
        ]
    return [
        {
            "family": "summarization",
            "src_idx": i,
            "gold_ok": True,
            "evidence": r.get("document", ""),
            "prompt_user": "Summarize the document faithfully.",
            "candidate": r.get("right_summary", ""),
            "kind": "right_summary",
        },
        {
            "family": "summarization",
            "src_idx": i,
            "gold_ok": False,
            "evidence": r.get("document", ""),
            "prompt_user": "Summarize the document faithfully.",
            "candidate": r.get("hallucinated_summary", ""),
            "kind": "hallucinated_summary",
        },
    ]


def build_items(qa_rows: list[dict], sum_rows: list[dict], n: int | None, seed: int) -> list[dict]:
    """Stratified sample without materializing the full 40k pool when n is set."""
    rng = random.Random(seed)
    if n is None:
        out: list[dict] = []
        for i, r in enumerate(qa_rows):
            out.extend(row_to_items("qa", i, r))
        for i, r in enumerate(sum_rows):
            out.extend(row_to_items("summarization", i, r))
        return out

    half = n // 2
    out = []
    for family, rows in (("qa", qa_rows), ("summarization", sum_rows)):
        idxs = list(range(len(rows)))
        rng.shuffle(idxs)
        take_ok = half // 2
        take_bad = half - take_ok
        # pick distinct source rows for ok/bad
        for j in range(take_ok):
            i = idxs[j]
            pair = row_to_items(family, i, rows[i])
            out.append(pair[0])  # gold_ok True
        for j in range(take_ok, take_ok + take_bad):
            i = idxs[j]
            pair = row_to_items(family, i, rows[i])
            out.append(pair[1])  # gold_ok False
    rng.shuffle(out)
    return out


def judge_prompt(item: dict) -> str:
    ev = item["evidence"]
    if len(ev) > 2500:
        ev = ev[:2500] + "\n…[truncated]"
    if item["family"] == "qa":
        return (
            "You are a faithfulness judge. Given Wikipedia knowledge and a question, "
            "decide if the candidate answer is faithful (supported) or hallucinated.\n"
            "Reply with exactly one JSON object: {\"faithful\": true|false, \"confidence\": 0..1}\n\n"
            f"Knowledge:\n{ev}\n\nQuestion:\n{item['prompt_user']}\n\n"
            f"Candidate answer:\n{item['candidate']}\n"
        )
    return (
        "You are a faithfulness judge. Given a document and a candidate summary, "
        "decide if the summary is faithful (supported) or hallucinated.\n"
        "Reply with exactly one JSON object: {\"faithful\": true|false, \"confidence\": 0..1}\n\n"
        f"Document:\n{ev}\n\nCandidate summary:\n{item['candidate']}\n"
    )


def parse_judge(text: str) -> tuple[bool | None, float]:
    if not text or text.startswith("API_ERROR"):
        return None, 0.0
    m = re.search(r"\{[^{}]*\}", text, flags=re.S)
    if not m:
        # fallback keywords
        low = text.lower()
        if "faithful\": false" in low or "faithful\":false" in low or "hallucinat" in low:
            return False, 0.5
        if "faithful\": true" in low or "faithful\":true" in low:
            return True, 0.5
        return None, 0.0
    try:
        obj = json.loads(m.group(0))
        faith = obj.get("faithful")
        conf = float(obj.get("confidence", 0.5))
        if isinstance(faith, bool):
            return faith, conf
    except Exception:
        pass
    return None, 0.0


def http_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_ollama(model: str, prompt: str, host: str, temp: float = 0.0) -> str:
    url = host.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": temp},
        "messages": [{"role": "user", "content": prompt}],
    }
    for attempt in range(3):
        try:
            body = http_json(url, payload, {"Content-Type": "application/json"})
            return body.get("message", {}).get("content") or ""
        except Exception as e:
            if attempt == 2:
                return f"API_ERROR: {e}"
            time.sleep(2**attempt)
    return "API_ERROR"


def call_deepseek(model: str, prompt: str, base: str, key: str, temp: float = 0.0) -> str:
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": temp,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    for attempt in range(3):
        try:
            body = http_json(url, payload, headers)
            return body["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 2:
                return f"API_ERROR: {e}"
            time.sleep(2**attempt)
    return "API_ERROR"


def judge(backend: str, prompt: str, cfg: dict, temp: float = 0.0) -> tuple[bool | None, float, str]:
    if backend == "ollama":
        text = call_ollama(cfg["ollama_model"], prompt, cfg["ollama_host"], temp=temp)
    elif backend == "deepseek":
        text = call_deepseek(cfg["deepseek_model"], prompt, cfg["deepseek_base"], cfg["deepseek_key"], temp=temp)
    else:
        raise ValueError(backend)
    faith, conf = parse_judge(text)
    return faith, conf, text[:500]


def load_checkpoint() -> dict[str, dict]:
    if not CHECKPOINT.exists():
        return {}
    done = {}
    with CHECKPOINT.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            done[row["key"]] = row
    return done


def append_checkpoint(row: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict]) -> dict:
    """rows have gold_ok, a_ok (judge says faithful), b_ok, family."""
    usable = [r for r in rows if r.get("a_ok") is not None and r.get("b_ok") is not None]
    agree = [r for r in usable if r["a_ok"] == r["b_ok"]]
    disagree = [r for r in usable if r["a_ok"] != r["b_ok"]]

    def wrong_agree(r: dict) -> bool:
        # agreed verdict is wrong vs gold: gold_ok means candidate IS faithful
        agreed_faithful = r["a_ok"]
        return agreed_faithful != r["gold_ok"]

    wa = [r for r in agree if wrong_agree(r)]
    both_wrong_disagree = 0  # by construction under binary + single gold: exactly one right when disagree if we defined wrong vs gold per side
    # Tom's caveat: P(both wrong|disagree)=0 by construction for binary complementary — we count sides wrong vs gold
    both_wrong = [
        r
        for r in disagree
        if (r["a_ok"] != r["gold_ok"]) and (r["b_ok"] != r["gold_ok"])
    ]

    def pack(subset: list[dict], label: str) -> dict:
        u = [r for r in subset if r.get("a_ok") is not None and r.get("b_ok") is not None]
        ag = [r for r in u if r["a_ok"] == r["b_ok"]]
        wa_s = [r for r in ag if wrong_agree(r)]
        lo, hi = wilson(len(wa_s), len(ag)) if ag else (0.0, 0.0)
        return {
            "label": label,
            "n": len(u),
            "n_agree": len(ag),
            "agreement_rate": len(ag) / len(u) if u else None,
            "n_wrong_agree": len(wa_s),
            "p_wrong_given_agree": len(wa_s) / len(ag) if ag else None,
            "wilson95": [round(lo, 4), round(hi, 4)] if ag else None,
        }

    overall = pack(usable, "overall")
    by_fam = {
        "qa": pack([r for r in usable if r["family"] == "qa"], "qa"),
        "summarization": pack([r for r in usable if r["family"] == "summarization"], "summarization"),
    }
    return {
        "n_usable": len(usable),
        "n_agree": len(agree),
        "n_disagree": len(disagree),
        "n_both_wrong_on_disagree": len(both_wrong),
        "note_both_wrong": (
            "Under binary faithfulness vs a single gold, disagree usually means "
            "exactly one side matches gold; both-wrong-on-disagree is rare and "
            "must not be read as independence evidence (Tom's caveat)."
        ),
        "overall": overall,
        "by_family": by_fam,
    }


def load_optional_env_file() -> None:
    """Load scripts/data/.deepseek_env.json into os.environ if present (cc-switch export)."""
    path = ROOT / "data" / ".deepseek_env.json"
    if not path.exists():
        return
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for k, v in cfg.items():
        if v and not os.environ.get(k):
            os.environ[k] = str(v)


def main() -> int:
    load_optional_env_file()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=70, help="stratified sample size (ignored if --full)")
    ap.add_argument("--full", action="store_true", help="use full HaluEval qa+sum expanded pool")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skip-deepseek", action="store_true", help="use ollama qwen3:0.5b instead of DeepSeek")
    ap.add_argument("--reset-checkpoint", action="store_true")
    args = ap.parse_args()

    download_first(QA_URLS, DATA_DIR / "qa_data.json")
    download_first(SUM_URLS, DATA_DIR / "summarization_data.json")
    qa_rows = load_json_array(DATA_DIR / "qa_data.json")
    sum_rows = load_json_array(DATA_DIR / "summarization_data.json")
    items = build_items(qa_rows, sum_rows, None if args.full else args.n, args.seed)
    print(f"Items: {len(items)} (full={args.full})", flush=True)
    # free large row arrays
    qa_n, sum_n = len(qa_rows), len(sum_rows)
    del qa_rows, sum_rows

    cfg = {
        "ollama_host": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "gemma3:latest"),
        "deepseek_base": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "deepseek_model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "deepseek_key": (
            os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or ""
        ),
    }
    print(
        f"models: deepseek={cfg['deepseek_model']!r} ollama={cfg['ollama_model']!r} "
        f"key={'yes' if cfg['deepseek_key'] else 'no'}",
        flush=True,
    )

    use_deepseek = not args.skip_deepseek
    if use_deepseek and not cfg["deepseek_key"]:
        print("ERROR: set DEEPSEEK_API_KEY (or OPENAI_API_KEY / ANTHROPIC_AUTH_TOKEN), or pass --skip-deepseek")
        return 2

    model_a = "deepseek" if use_deepseek else "ollama_qwen"
    model_b = "ollama_gemma"
    if args.reset_checkpoint and CHECKPOINT.exists():
        CHECKPOINT.unlink()

    done = load_checkpoint()
    rows_cross: list[dict] = []
    rows_same: list[dict] = []

    for idx, item in enumerate(items):
        key = f"{item['family']}:{item['src_idx']}:{item['kind']}:{args.seed}"
        prompt = judge_prompt(item)

        if key in done and done[key].get("phase") == "complete":
            row = done[key]
        else:
            print(f"  [{idx+1}/{len(items)}] {item['family']}/{item['kind']} deepseek…", flush=True)
            if use_deepseek:
                a_ok, a_conf, a_raw = judge("deepseek", prompt, cfg, temp=0.0)
            else:
                text = call_ollama("qwen3:0.5b", prompt, cfg["ollama_host"], temp=0.0)
                a_ok, a_conf = parse_judge(text)
                a_raw = text[:500]
            print(f"    deepseek done faithful={a_ok}; gemma…", flush=True)
            b_ok, b_conf, b_raw = judge("ollama", prompt, cfg, temp=0.0)
            print(f"    gemma done faithful={b_ok}; gemma2…", flush=True)
            b2_ok, b2_conf, b2_raw = judge("ollama", prompt, cfg, temp=0.0)
            print(f"    gemma2 done faithful={b2_ok}", flush=True)

            row = {
                "key": key,
                "phase": "complete",
                "family": item["family"],
                "kind": item["kind"],
                "gold_ok": item["gold_ok"],
                "a_backend": model_a,
                "b_backend": model_b,
                "a_ok": a_ok,
                "b_ok": b_ok,
                "b2_ok": b2_ok,
                "a_conf": a_conf,
                "b_conf": b_conf,
                "b2_conf": b2_conf,
                "a_raw": a_raw,
                "b_raw": b_raw,
                "b2_raw": b2_raw,
            }
            append_checkpoint(row)
            if (idx + 1) % 5 == 0:
                print(f"  judged {idx+1}/{len(items)}")

        rows_cross.append(
            {
                "family": row["family"],
                "gold_ok": row["gold_ok"],
                "a_ok": row["a_ok"],
                "b_ok": row["b_ok"],
            }
        )
        rows_same.append(
            {
                "family": row["family"],
                "gold_ok": row["gold_ok"],
                "a_ok": row["b_ok"],
                "b_ok": row["b2_ok"],
            }
        )

    cross_sum = summarize(rows_cross)
    same_sum = summarize(rows_same)

    out = {
        "source": "Tom Jones Part 15 agree-set / same-vs-cross mirror",
        "n_requested": None if args.full else args.n,
        "full": args.full,
        "seed": args.seed,
        "models": {"a": model_a, "b": model_b, "same_second_draw": model_b},
        "halueval": {"qa_rows": qa_n, "sum_rows": sum_n, "items": len(items)},
        "cross_model": cross_sum,
        "same_model_gemma": same_sum,
        "agreement_gap_same_minus_cross": (
            (same_sum["overall"]["agreement_rate"] or 0)
            - (cross_sum["overall"]["agreement_rate"] or 0)
        ),
        "answer_for_tom": (
            f"Cross-model agree-set: agreement={cross_sum['overall']['agreement_rate']}, "
            f"P(wrong|agree)={cross_sum['overall']['p_wrong_given_agree']} "
            f"Wilson95={cross_sum['overall']['wilson95']}; "
            f"qa={cross_sum['by_family']['qa']['p_wrong_given_agree']}, "
            f"sum={cross_sum['by_family']['summarization']['p_wrong_given_agree']}. "
            f"Same-model (gemma×gemma) agreement={same_sum['overall']['agreement_rate']} "
            f"vs cross={cross_sum['overall']['agreement_rate']}. "
            "Model tier is DeepSeek-chat × gemma3, not Tom's 70B pair — numbers are "
            "same-question replications, not copies of 27.5%/88%."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
