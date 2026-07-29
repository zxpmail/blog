# -*- coding: utf-8 -*-
"""
Position-adjacency obedience test v2 — Tom Jones Part 15 follow-up (2026-07-29).

v2 change from v1: harder directive (uppercase override instead of BANANA
prefix) to escape ceiling. Tom's binary-verdict caveat predicted the v1
ceiling: "on a binary task the same-model arm saturates near 1.0, so the wedge
is close to a ceiling effect."

v2 directive: uppercase override (sustained constraint) — harder than prefix,
requires attention through entire generation, well-documented source of position
effects.

Method:
  - Same as v1: K=12 inner block, 5 positions × 2 conditions (no_padding /
    with_padding), N=20 trials/cell = 200 calls.
  - Directive: "Respond entirely in UPPERCASE letters. Do not use any lowercase
    letters in your response. This means every letter you write must be a
    capital letter, not lowercase."
  - Questions: require multi-sentence answers (e.g., "Explain in three sentences
    why the sky appears blue."), so uppercase must be sustained across more
    tokens — higher slip probability.
  - Obedience check: any lowercase [a-z] in response → not obeyed.

Expected (if Tom's position-adjacency finding generalizes):
  - no_padding: pos_100 > pos_0 (last note adjacent to question is more obeyed)
  - with_padding: pos_100 advantage reduced (12 notes of separation = less
    adjacency)

Output: results-v2/position-adjacency-obedience-v2.json
"""

import json, os, sys, io, time, argparse, re, urllib.request, random
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

DIRECTIVE = ("Respond entirely in UPPERCASE letters. Do not use any lowercase "
             "letters in your response. This means every letter you write must "
             "be a capital letter, not lowercase.")

# Questions requiring multi-sentence answers (more tokens → more slip chance)
QUESTIONS = [
    "Explain why the sky appears blue during the daytime in three sentences.",
    "Describe three differences between oceans and lakes in complete sentences.",
    "What causes the seasons on Earth? Explain in three sentences.",
    "Describe three benefits of regular exercise in complete sentences.",
    "Explain in three sentences how a refrigerator keeps food cold.",
    "What are three differences between plants and animals? Explain.",
    "Describe three uses of water in daily life in full sentences.",
    "Explain in three sentences why leaves change color in autumn.",
    "What are three properties of water that make it essential for life?",
    "Describe three ways that computers have changed communication.",
    "Explain in three sentences how the human heart pumps blood.",
    "What causes rainbows to form? Explain in three sentences.",
    "Describe three differences between renewable and non-renewable energy.",
    "Explain in three sentences why exercise strengthens the immune system.",
    "What are three functions of the human skeleton? Describe.",
    "Explain in three sentences how a seed grows into a plant.",
    "Describe three ways that birds are adapted for flight.",
    "What causes thunder? Explain in three sentences.",
    "Describe three benefits of reading books regularly.",
    "Explain in three sentences how the internet transfers data.",
]

POSITIONS_PCT = [0, 25, 50, 75, 100]
K_INNER = 12
K_PAD = 12
POSITION_INNER_IDX = {0: 1, 25: 3, 50: 6, 75: 9, 100: 12}


def call_model(prompt, model, base_url, api_key, backend, temp=0.0, timeout=60):
    headers = {"Content-Type": "application/json"}
    msgs = [{"role": "user", "content": prompt}]
    try:
        if backend == "ollama":
            body = {"model": model, "messages": msgs, "temperature": temp,
                    "max_tokens": 200, "stream": False}
            url = f"{base_url}/api/chat"
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return resp["message"]["content"].strip()
        if backend == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            body = {"model": model, "max_tokens": 300, "messages": msgs, "temperature": temp}
            url = f"{base_url}/v1/messages"
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            # Some providers (deepseek-v4-flash) return thinking blocks first;
            # find the first text content block
            for block in resp.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
            return resp["content"][0].get("text", str(resp)).strip()
        headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": model, "messages": msgs, "temperature": temp, "max_tokens": 200}
        url = f"{base_url}/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"__API_ERROR__: {e}"


def is_obeyed(text):
    """Check: response must be entirely in uppercase (no lowercase letters)."""
    if not text or text.startswith("__API_ERROR__"):
        return None
    # Contains no lowercase letters → obeyed
    # Contains any lowercase letter → not obeyed
    # Ignore punctuation, digits, whitespace — only check [a-z]
    return not bool(re.search(r'[a-z]', text))


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
    parser = argparse.ArgumentParser(description="Position-adjacency obedience test v2 (uppercase)")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "glm-5.2"))
    parser.add_argument("--backend", default="anthropic", choices=["ollama", "openai", "anthropic"])
    parser.add_argument("--base-url", default=os.environ.get("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"))
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", ""))
    parser.add_argument("--temp", type=float, default=0.0)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()

    if not args.api_key and args.backend != "ollama":
        print("[ABORT] API key required")
        sys.exit(1)

    cells = [(c, p) for c in ["no_padding", "with_padding"] for p in POSITIONS_PCT]
    total_calls = len(cells) * args.n_trials

    print("=" * 78)
    print(f"  Position-adjacency obedience test v2 — UPPERCASE override")
    print(f"  Model: {args.model}  |  Backend: {args.backend}")
    print(f"  Cells: {len(cells)} (5 positions x 2 conditions)")
    print(f"  Trials/cell: {args.n_trials}  |  Total LLM calls: {total_calls}")
    print(f"  Directive: UPPERCASE override (sustained constraint)")
    print(f"  Obedience check: no lowercase [a-z] in response")
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

            # Sample lowercase letters in response for diagnostic
            lower_chars = re.findall(r'[a-z]', response) if response else []

            trials.append({
                "condition": cond,
                "position_pct": pos,
                "inner_position": inner_pos,
                "absolute_position": abs_pos,
                "total_notes": total_notes,
                "trial": trial + 1,
                "question": question,
                "response_preview": response[:150] if response else "",
                "lowercase_count": len(lower_chars),
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

    by_cell = {}
    for cond in ["no_padding", "with_padding"]:
        for pos in POSITIONS_PCT:
            ct = [t for t in trials if t["condition"] == cond and t["position_pct"] == pos]
            obeyed = sum(1 for t in ct if t["obeyed"] is True)
            parsed = sum(1 for t in ct if t["obeyed"] is not None)
            avg_lower = sum(t["lowercase_count"] for t in ct if t["lowercase_count"] is not None) / len(ct) if ct else 0
            by_cell[f"{cond}|pos_{pos}"] = {
                "condition": cond, "position_pct": pos,
                "n_trials": len(ct), "n_obeyed": obeyed, "n_parsed": parsed,
                "obedience_rate": obeyed / parsed if parsed else None,
                "avg_lowercase_count": avg_lower,
                "inner_position": ct[0]["inner_position"] if ct else None,
                "absolute_position": ct[0]["absolute_position"] if ct else None,
                "total_notes": ct[0]["total_notes"] if ct else None,
            }

    position_effect = {}
    for cond in ["no_padding", "with_padding"]:
        rates = {p: by_cell[f"{cond}|pos_{p}"]["obedience_rate"] for p in POSITIONS_PCT}
        position_effect[cond] = {
            **{f"rate_pos_{p}": rates[p] for p in POSITIONS_PCT},
            "ends_advantage_100_vs_0": r_sub(rates[100], rates[0]),
            "ends_advantage_100_vs_75": r_sub(rates[100], rates[75]),
            "position_100_is_max": rates[100] >= max(rates[p] for p in POSITIONS_PCT if rates[p] is not None) if rates[100] is not None else None,
        }

    np100 = by_cell["no_padding|pos_100"]["obedience_rate"]
    wp100 = by_cell["with_padding|pos_100"]["obedience_rate"]
    padding_effect = {
        "pos_100_no_padding": np100,
        "pos_100_with_padding": wp100,
        "padding_erases_ends_advantage": (
            np100 is not None and wp100 is not None and np100 > wp100
        ),
    }

    # Tom's reference: 60/60 at pos_100 vs 80-85% elsewhere
    # On this model+fixture: if pos_100 > 80% and others lower → replicates
    # If all ≈ ceiling → cardinality-bound (like v1)
    # If all uniform < 100% → no position effect, not ceiling

    result = {
        "experiment": "position-adjacency-obedience-v2",
        "claim": "Replicate Tom Jones's position-adjacency finding using a harder directive (uppercase override) to escape the binary-verdict ceiling effect seen in v1.",
        "tom_jones_reference": {
            "no_padding_pos_100_obedience_overall": 60/60,
            "no_padding_other_positions_range": [0.80, 0.85],
            "edge_padding_erased_advantage": True,
        },
        "v1_caveat": "v1 (BANANA prefix) hit ceiling on both glm-5.2 and qwen3:0.6b — no variance to measure position effect. Consistent with Tom's binary-verdict cardinality bound.",
        "method": {
            "model": args.model,
            "backend": args.backend,
            "temp": args.temp,
            "n_trials_per_cell": args.n_trials,
            "total_calls": call_count,
            "directive": DIRECTIVE,
            "obedience_check": "No lowercase [a-z] in response",
            "inner_block_size": K_INNER,
            "padding_size": K_PAD,
            "positions_pct": POSITIONS_PCT,
            "conditions": ["no_padding", "with_padding"],
        },
        "by_cell": by_cell,
        "position_effect": position_effect,
        "padding_effect": padding_effect,
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "trials": trials,
    }

    out_path = OUT_DIR / "position-adjacency-obedience-v2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  → {out_path}")

    # Console
    print("\n" + "=" * 78)
    print("  OBEDIENCE RATE BY CELL")
    print("=" * 78)
    header = f"  {'Condition':<15} "
    for p in POSITIONS_PCT:
        header += f"{'pos='+str(p):<12}"
    print(header)
    print(f"  {'-'*15} {'-'*12*5}")
    for cond in ["no_padding", "with_padding"]:
        row = f"  {cond:<15} "
        for p in POSITIONS_PCT:
            rate = by_cell[f"{cond}|pos_{p}"]["obedience_rate"]
            lc = by_cell[f"{cond}|pos_{p}"]["avg_lowercase_count"]
            row += f"{rate*100:>5.0f}%({lc:.0f}lc) " if rate is not None else "   N/A  "
        print(row)
    print()
    for cond in ["no_padding", "with_padding"]:
        e = position_effect[cond]["ends_advantage_100_vs_0"]
        if e is None:
            print(f"  {cond:<15} ends advantage: N/A")
        elif e > 0.10:
            print(f"  {cond:<15} ends advantage: {e*100:+.0f}%  → replicates Tom")
        elif abs(e) <= 0.05:
            print(f"  {cond:<15} ends advantage: {e*100:+.0f}%  → no effect")
        else:
            print(f"  {cond:<15} ends advantage: {e*100:+.0f}%  → weak")
    print()
    pe_erased = padding_effect["padding_erases_ends_advantage"]
    print(f"  Padding erases ends advantage (pos_100): {'YES' if pe_erased else 'NO'}")
    print("=" * 78)


def r_sub(a, b):
    if a is None or b is None:
        return None
    return a - b


if __name__ == "__main__":
    main()
