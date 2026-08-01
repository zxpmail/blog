# -*- coding: utf-8 -*-
"""
Position-adjacency obedience test — Tom Jones's Part 15 follow-up (2026-07-29).

Question (Tom's finding on his own fixture, different model):
  Last slot (position 100%, adjacent to question) obeyed 60/60 across 3 runs;
  every other position sat at 80-85%. Edge padding (12 notes of separation)
  erased the ends advantage entirely.

  "The privileged position is not lateness in the budget, it is adjacency to
  the question, and twelve notes of separation is enough to remove it."

Method:
  - Inner block of K=12 notes; one is the "governing directive."
  - Other 11 are trivia distractors (content-neutral).
  - Sweep directive position across 5 quintiles of the inner block.
  - Two conditions:
      no_padding:   K=12 inner block alone. Directive at pos_100 is the LAST
                    note, immediately followed by Question (adjacency=0).
      with_padding: 12 leading trivia + K=12 inner + 12 trailing trivia = 36.
                    Directive at inner pos_100 has 12 trailing notes between
                    it and the Question (adjacency=12). Tests whether the
                    no_padding pos_100 advantage is boundary or adjacency.
  - Directive: "Begin your response with the word BANANA."
  - Question (varied, unrelated to directive): trivia like "What is the capital of France?"
  - Obedience check: case-insensitive regex ^\\s*BANANA\\b on first token.
  - N=20 trials per cell × 5 positions × 2 conditions = 200 LLM calls.

Expected / falsification:
  - Replication: no_padding pos_100 obedience > no_padding pos_0/50 obedience.
  - Edge-padding erasure: with_padding pos_100 ≈ with_padding pos_0/50.
  - If no position effect at all on this model+fixture, that itself is informative.

Output: results-v2/position-adjacency-obedience.json
"""

import json, os, sys, io, time, argparse, re, urllib.request, random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)

TRIVIA = [
    "The Eiffel Tower was completed in 1889 for the World's Fair.",
    "Honey has a typical pH of approximately 3.9.",
    "Octopuses have three hearts and blue blood.",
    "A group of flamingos is called a flamboyance.",
    "The Great Wall of China is over 13,000 miles long.",
    "Venus is the hottest planet in the solar system.",
    "A jiffy is an actual unit of time equal to 1/100th of a second.",
    "Wombat excrement is shaped like a cube.",
    "The Amazon River is approximately 4,000 miles long.",
    "A single cloud can weigh more than a million pounds.",
    "The shortest war in history lasted 38 minutes in 1896.",
    "Bananas are botanically classified as berries.",
    "The human nose can distinguish over 1 trillion scents.",
    "A blue whale's heart can weigh as much as a small car.",
    "The filing cabinet was invented in the United States in 1858.",
    "There are more possible chess games than atoms in the universe.",
    "A day on Venus is longer than its year.",
    "The national animal of Scotland is the unicorn.",
    "The first computer programmer was Ada Lovelace in the 1840s.",
    "Cows have four stomachs to digest their food.",
    "A bolt of lightning is five times hotter than the sun's surface.",
    "The Pacific Ocean is the largest ocean on Earth.",
    "An adult human body has 206 bones.",
    "The longest English word without a vowel is 'rhythm'.",
    "A tablespoon of honey is the lifetime work of 12 bees.",
    "The Mariana Trench reaches a depth of about 36,000 feet.",
    "Polar bears have black skin beneath their fur.",
    "The average cloud droplet falls at 0.3 mph.",
    "Sharks existed before trees did.",
    "The average human blinks about 15,000 times per day.",
    "The world's oldest known living tree is over 5,000 years old.",
    "A teaspoon of a neutron star would weigh 6 billion tons.",
    "The Egyptian pyramids were built over 4,500 years ago.",
    "Some species of bamboo can grow 35 inches in a single day.",
    "The average raindrop falls at 7 to 18 mph.",
    "Hawaii is moving toward Japan at about 4 inches per year.",
    "A single bolt of lightning contains up to 1 billion volts.",
    "There are roughly 3 trillion trees on Earth.",
    "Armadillo shells are bulletproof in some cases.",
    "The Atlantic Ocean covers about 20% of the Earth's surface.",
]

DIRECTIVE = "Begin your response with the word BANANA."

QUESTIONS = [
    "What is the capital of France?",
    "What is the largest planet in our solar system?",
    "Who wrote the play Hamlet?",
    "What is the chemical symbol for water?",
    "In what year did World War II end?",
    "What is the longest river in the world?",
    "Who painted the Mona Lisa?",
    "What is the boiling point of water in Celsius?",
    "What is the tallest mountain in the world?",
    "What language has the most native speakers worldwide?",
    "What is the smallest country in the world?",
    "Who developed the theory of relativity?",
    "What is the largest mammal on Earth?",
    "What gas do plants absorb during photosynthesis?",
    "Who was the first emperor of Rome?",
    "What is the currency of Japan?",
    "What is the largest desert in the world?",
    "Who invented the telephone?",
    "What is the speed of light in vacuum (approx km/s)?",
    "What is the population of the Earth (approx billions)?",
]

POSITIONS_PCT = [0, 25, 50, 75, 100]
K_INNER = 12
K_PAD = 12
POSITION_INNER_IDX = {0: 1, 25: 3, 50: 6, 75: 9, 100: 12}


# Windows 系统代理（如 127.0.0.1:7890）挂掉时会拖死直连可用的 API；此处强制直连
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call_model(prompt, model, base_url, api_key, backend, temp=0.0, timeout=60):
    headers = {"Content-Type": "application/json"}
    msgs = [{"role": "user", "content": prompt}]
    try:
        if backend == "ollama":
            body = {"model": model, "messages": msgs, "temperature": temp,
                    "max_tokens": 80, "stream": False}
            url = f"{base_url}/api/chat"
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            resp = json.loads(_OPENER.open(req, timeout=timeout).read())
            return resp["message"]["content"].strip()
        if backend == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            # deepseek 可能先吐 thinking；留足 token 再取 text 块
            body = {"model": model, "max_tokens": 256, "messages": msgs, "temperature": temp}
            url = f"{base_url}/v1/messages"
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            resp = json.loads(_OPENER.open(req, timeout=timeout).read())
            for block in resp.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
            return resp["content"][0].get("text", str(resp)).strip()
        headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": model, "messages": msgs, "temperature": temp, "max_tokens": 80}
        url = f"{base_url}/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        resp = json.loads(_OPENER.open(req, timeout=timeout).read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"__API_ERROR__: {e}"


def is_obeyed(text):
    if not text or text.startswith("__API_ERROR__"):
        return None
    return bool(re.match(r'^\s*BANANA\b', text, re.IGNORECASE))


def build_block(position_pct, with_padding, seed):
    rng = random.Random(seed)
    n_needed = (K_INNER - 1) + (2 * K_PAD if with_padding else 0)
    pool = list(TRIVIA)
    rng.shuffle(pool)
    picked = pool[:n_needed]

    pos_idx = POSITION_INNER_IDX[position_pct]
    inner_contents = []
    trivia_iter = iter(picked[:K_INNER - 1])
    for i in range(1, K_INNER + 1):
        if i == pos_idx:
            inner_contents.append(("directive", DIRECTIVE))
        else:
            inner_contents.append(("trivia", next(trivia_iter)))

    lines = []
    note_num = 0
    directive_abs_pos = None

    if with_padding:
        for t in picked[K_INNER - 1:K_INNER - 1 + K_PAD]:
            note_num += 1
            lines.append(f"Note {note_num}: {t}")
        for kind, content in inner_contents:
            note_num += 1
            if kind == "directive":
                directive_abs_pos = note_num
            lines.append(f"Note {note_num}: {content}")
        for t in picked[K_INNER - 1 + K_PAD:]:
            note_num += 1
            lines.append(f"Note {note_num}: {t}")
    else:
        for kind, content in inner_contents:
            note_num += 1
            if kind == "directive":
                directive_abs_pos = note_num
            lines.append(f"Note {note_num}: {content}")

    return "\n".join(lines), pos_idx, directive_abs_pos, note_num


def main():
    parser = argparse.ArgumentParser(description="Position-adjacency obedience test")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "glm-5.2"))
    parser.add_argument("--backend", default="anthropic", choices=["ollama", "openai", "anthropic"])
    parser.add_argument("--base-url", default=os.environ.get("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"))
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", ""))
    parser.add_argument("--temp", type=float, default=0.0)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument(
        "--out",
        default="",
        help="Output JSON path (default: results-v2/position-adjacency-obedience.json)",
    )
    args = parser.parse_args()

    if not args.api_key and args.backend != "ollama":
        print("[ABORT] API key required")
        sys.exit(1)

    cells = [(c, p) for c in ["no_padding", "with_padding"] for p in POSITIONS_PCT]
    total_calls = len(cells) * args.n_trials

    print("=" * 78)
    print(f"  Position-adjacency obedience test (Tom Jones Part 15 follow-up)")
    print(f"  Model: {args.model}  |  Backend: {args.backend}")
    print(f"  Cells: {len(cells)} (5 positions x 2 conditions)")
    print(f"  Trials/cell: {args.n_trials}  |  Total LLM calls: {total_calls}")
    print(f"  Directive: {DIRECTIVE}")
    print(f"  Inner K={K_INNER}, Padding K={K_PAD}")
    print("=" * 78)
    print()

    trials = []
    t0 = time.time()
    call_count = 0

    for cond, pos in cells:
        cell_obeyed = 0
        cell_parsed = 0
        for trial in range(args.n_trials):
            seed = args.seed + trial + (pos * 100) + (10000 if cond == "with_padding" else 0)
            block, inner_pos, abs_pos, total_notes = build_block(pos, cond == "with_padding", seed)
            question = QUESTIONS[trial % len(QUESTIONS)]
            prompt = f"{block}\n\nQuestion: {question}"

            response = call_model(prompt, args.model, args.base_url, args.api_key, args.backend, args.temp)
            call_count += 1
            obeyed = is_obeyed(response)

            trials.append({
                "condition": cond,
                "position_pct": pos,
                "inner_position": inner_pos,
                "absolute_position": abs_pos,
                "total_notes": total_notes,
                "trial": trial + 1,
                "question": question,
                "response_preview": response[:120] if response else "",
                "obeyed": obeyed,
            })
            if obeyed is True:
                cell_obeyed += 1
            if obeyed is not None:
                cell_parsed += 1
            time.sleep(0.05)

        rate = cell_obeyed / cell_parsed if cell_parsed else 0
        print(f"  {cond:>12} | pos={pos:>3}% (inner note {inner_pos}, abs note {abs_pos}/{total_notes}) | obeyed {cell_obeyed}/{cell_parsed} ({rate*100:.0f}%)")
        sys.stdout.flush()

    elapsed = time.time() - t0
    print(f"\n  Done. {call_count} calls in {elapsed:.1f}s.")

    # Aggregate by cell
    by_cell = {}
    for cond in ["no_padding", "with_padding"]:
        for pos in POSITIONS_PCT:
            cell_trials = [t for t in trials if t["condition"] == cond and t["position_pct"] == pos]
            obeyed = sum(1 for t in cell_trials if t["obeyed"] is True)
            parsed = sum(1 for t in cell_trials if t["obeyed"] is not None)
            by_cell[f"{cond}|pos_{pos}"] = {
                "condition": cond,
                "position_pct": pos,
                "n_trials": len(cell_trials),
                "n_obeyed": obeyed,
                "n_parsed": parsed,
                "obedience_rate": obeyed / parsed if parsed else None,
                "inner_position": cell_trials[0]["inner_position"] if cell_trials else None,
                "absolute_position": cell_trials[0]["absolute_position"] if cell_trials else None,
                "total_notes": cell_trials[0]["total_notes"] if cell_trials else None,
            }

    position_effect = {}
    for cond in ["no_padding", "with_padding"]:
        pos0 = by_cell[f"{cond}|pos_0"]["obedience_rate"]
        pos50 = by_cell[f"{cond}|pos_50"]["obedience_rate"]
        pos100 = by_cell[f"{cond}|pos_100"]["obedience_rate"]
        position_effect[cond] = {
            "rate_pos_0": pos0,
            "rate_pos_25": by_cell[f"{cond}|pos_25"]["obedience_rate"],
            "rate_pos_50": pos50,
            "rate_pos_75": by_cell[f"{cond}|pos_75"]["obedience_rate"],
            "rate_pos_100": pos100,
            "ends_advantage_100_vs_0": (pos100 - pos0) if (pos100 is not None and pos0 is not None) else None,
        }

    padding_effect = {
        "pos_100_no_padding": by_cell["no_padding|pos_100"]["obedience_rate"],
        "pos_100_with_padding": by_cell["with_padding|pos_100"]["obedience_rate"],
        "all_positions_no_padding_avg": sum(by_cell[f"no_padding|pos_{p}"]["obedience_rate"] or 0 for p in POSITIONS_PCT) / 5,
        "all_positions_with_padding_avg": sum(by_cell[f"with_padding|pos_{p}"]["obedience_rate"] or 0 for p in POSITIONS_PCT) / 5,
    }
    np100 = padding_effect["pos_100_no_padding"]
    wp100 = padding_effect["pos_100_with_padding"]
    padding_effect["padding_erases_ends_advantage"] = (
        np100 is not None and wp100 is not None and np100 > wp100
    )

    result = {
        "experiment": "position-adjacency-obedience",
        "claim": "Replicate Tom Jones's finding: note adjacent to Question (position 100%) obeyed more than other positions; edge padding erases the advantage.",
        "method": {
            "model": args.model,
            "backend": args.backend,
            "temp": args.temp,
            "n_trials_per_cell": args.n_trials,
            "total_calls": call_count,
            "directive": DIRECTIVE,
            "obedience_check": "^\\s*BANANA\\b (case-insensitive)",
            "inner_block_size": K_INNER,
            "padding_size": K_PAD,
            "positions_pct": POSITIONS_PCT,
            "conditions": ["no_padding", "with_padding"],
            "design_note": "no_padding: directive at pos_100 is the LAST note, immediately followed by Question (adjacency=0). with_padding: directive at inner pos_100 has K_PAD=12 trailing notes between it and Question (adjacency=12). Tests boundary-vs-adjacency.",
        },
        "by_cell": by_cell,
        "position_effect": position_effect,
        "padding_effect": padding_effect,
        "interpretation_hints": [
            "Replication of Tom's shape: no_padding ends_advantage_100_vs_0 > 0 (last slot > first slot).",
            "Edge-padding erasure: with_padding pos_100 obedience < no_padding pos_100 obedience.",
            "If both hold: advantage is adjacency-to-question, not boundary.",
            "If neither holds: effect does not survive on this model+fixture (informative negative).",
        ],
        "tom_jones_reference": {
            "no_padding_pos_100_obedience": 60/60,
            "no_padding_other_positions_range": [0.80, 0.85],
            "edge_padding_erased_advantage": True,
        },
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "trials": trials,
    }

    out_path = Path(args.out) if args.out else OUT_DIR / "position-adjacency-obedience.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  → {out_path}")

    print("\n" + "=" * 78)
    print("  OBEDIENCE RATE BY CELL")
    print("=" * 78)
    print(f"  {'Condition':<15} {'pos=0':<10} {'pos=25':<10} {'pos=50':<10} {'pos=75':<10} {'pos=100':<10}")
    for cond in ["no_padding", "with_padding"]:
        row = f"  {cond:<15} "
        for pos in POSITIONS_PCT:
            rate = by_cell[f"{cond}|pos_{pos}"]["obedience_rate"]
            row += f"{rate*100:>5.0f}%   " if rate is not None else "  N/A   "
        print(row)
    print()
    print(f"  Ends advantage (pos_100 - pos_0):")
    for cond in ["no_padding", "with_padding"]:
        e = position_effect[cond]["ends_advantage_100_vs_0"]
        if e is None:
            print(f"    {cond:<15} N/A")
        elif e > 0.10:
            print(f"    {cond:<15} {e*100:+.0f}%  (Tom shape replicates)")
        elif abs(e) < 0.05:
            print(f"    {cond:<15} {e*100:+.0f}%  (no effect)")
        else:
            print(f"    {cond:<15} {e*100:+.0f}%  (weak)")
    print()
    print(f"  Padding effect at pos_100:")
    if np100 is not None: print(f"    no_padding    {np100*100:.0f}%")
    if wp100 is not None: print(f"    with_padding  {wp100*100:.0f}%")
    if np100 is not None and wp100 is not None:
        erased = "ERASED" if wp100 < np100 else "preserved"
        print(f"    → advantage {erased} by padding")
    print()
    print("=" * 78)


if __name__ == "__main__":
    main()
