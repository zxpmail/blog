#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hand suite green / corpus base-rate red (Tom Jones supersession limit).

Claim under test
----------------
Tom Jones (DEV.to on Part 10, follow-up to negative-control thread): a
hand-written negative control shares an author with the checker and inherits
its blind spot. Their supersession detector (does B retract A?) needed a
shared anchor plus a revision cue. Five hand cases covered both directions
and passed against the old rule, a middle regression, and the fix. Only a
mined corpus separated them: cue+any-one-anchor flagged ~99% of candidates
while looking green on the hand suite. Discipline has two halves — sabotaged
output must score zero (bounds false accepts); the unsabotaged population
must not all score one (bounds false rejects / over-firing). A hand suite
cannot supply the second half. Second miss: verb-only "anchors" still match
unrelated pairs on shared remove/select.

Method
------
Offline toy supersession rules (stdlib). Not Tom's transcripts; synthetic
catalog sized near his report (~400 candidates) without claiming the same
443/156 numbers.

  H  five hand pairs (real revision / explicit reversal / retraction vocab /
     generic collision / unrelated) × three rules
  C  ~400 synthetic candidates; flag rates for three rules
  V  verb-as-anchor residual: unrelated pair shares remove+select

Rules (aligned to his table, not his percentages)
  R0  term-overlap only (Jaccard ≥ floor)
  R1  revision cue + ≥1 shared content anchor          ← regression middle
  R2  revision cue + ≥2 shared anchors + Jaccard floor ← repaired

PASS criteria (falsify if any fails)
------------------------------------
  1. H: R0/R1/R2 all match hand expected labels (hand suite "green")
  2. C: R1 flag share ≥ 0.90 on corpus; R2 flag share ≤ 0.25;
        R0 flag share strictly between them or at least < R1
  3. V: verb-anchor rule flags unrelated pair; noun-anchor rule does not

Expected: SUPPORT — hand suite cannot bound over-firing; corpus base rate can.
No claim of field prevalence or replication of his exact rates.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import random
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "supersession-hand-vs-corpus.json"

# 修订线索（普通词也会出现在非撤回句里——这正是中档回归的燃料）
CUES = {
    "stop",
    "instead",
    "actually",
    "retract",
    "nevermind",
    "use",
    "replace",
    "forget",
    "cancel",
}

# 内容锚：命名「在谈什么」
NOUN_ANCHORS = {
    "cache",
    "ttl",
    "session",
    "token",
    "bucket",
    "queue",
    "widget",
    "invoice",
    "ledger",
    "replica",
    "checkpoint",
    "harness",
    "digest",
    "verifier",
    "policy",
    "schema",
    "fixture",
    "canary",
}

# 动词：命名「对它做什么」——当锚会误伤
VERB_ANCHORS = {"remove", "select", "update", "delete", "add", "write", "read"}

J_FLOOR = 0.12
R0_FLOOR = 0.18


def tokens(text: str) -> set[str]:
    """小写词袋。"""
    return set(re.findall(r"[a-z]+", text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    """集合 Jaccard。"""
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def has_cue(text: str) -> bool:
    """是否含修订线索词。"""
    return bool(tokens(text) & CUES)


def shared_anchors(a: str, b: str, anchor_set: set[str]) -> set[str]:
    """共享锚。"""
    return tokens(a) & tokens(b) & anchor_set


def rule_r0(a: str, b: str) -> bool:
    """旧规则：仅词重叠。"""
    return jaccard(tokens(a), tokens(b)) >= R0_FLOOR


def rule_r1(a: str, b: str, anchors: set[str] = NOUN_ANCHORS) -> bool:
    """回归中档：线索 + 任一共享锚。"""
    return has_cue(b) and len(shared_anchors(a, b, anchors)) >= 1


def rule_r2(a: str, b: str, anchors: set[str] = NOUN_ANCHORS) -> bool:
    """修好：线索 + 至少两锚 + Jaccard 底。"""
    return (
        has_cue(b)
        and len(shared_anchors(a, b, anchors)) >= 2
        and jaccard(tokens(a), tokens(b)) >= J_FLOOR
    )


# --- H：手写五格（期望标签使三规则在手写上都「对」）---
# 真撤回对：共享 ≥2 名词锚 + B 含线索，且整体重叠够 → R0/R1/R2 皆 True
# 真无关/泛碰撞：无共享名词锚或不含线索结构 → 三规则皆 False
HAND = [
    {
        "id": "real_revision",
        "a": "set cache ttl to sixty for the session store",
        "b": "actually use cache ttl three hundred instead for the session",
        "expect": True,
    },
    {
        "id": "explicit_reversal",
        "a": "enable harness digest pin on the verifier policy",
        "b": "stop harness digest pin nevermind keep the verifier policy",
        "expect": True,
    },
    {
        "id": "retraction_vocab",
        "a": "deploy widget build to bucket prod with schema fixture",
        "b": "retract widget deploy from bucket prod schema unchanged",
        "expect": True,
    },
    {
        "id": "generic_collision",
        # 无名词锚共享；B 有 stop/use 但无内容锚 → 三规则皆不应开火
        "a": "please review the morning notes carefully today",
        "b": "stop and use a different tone when writing emails",
        "expect": False,
    },
    {
        "id": "unrelated_pair",
        "a": "the weather looks fine for a walk outside",
        "b": "cancel lunch if the train is late again",
        "expect": False,
    },
]


def eval_hand(rule_fn) -> dict:
    """手写套件：逐条比对期望。"""
    rows = []
    ok = True
    for case in HAND:
        flagged = rule_fn(case["a"], case["b"])
        match = flagged == case["expect"]
        ok = ok and match
        rows.append(
            {
                "id": case["id"],
                "expect": case["expect"],
                "flagged": flagged,
                "match": match,
            }
        )
    return {"all_match": ok, "rows": rows}


def build_corpus(n: int = 400, seed: int = 42) -> list[dict]:
    """合成 ~N 候选对：大量「普通句 + 常用线索词 + 单共享名词」→ 喂肥 R1。"""
    rng = random.Random(seed)
    nouns = sorted(NOUN_ANCHORS)
    fillers_a = [
        "please check the {n} before shipping",
        "we updated the {n} configuration last night",
        "document the {n} path in the runbook",
        "the {n} metric drifted during the canary",
        "rotate the {n} material on schedule",
    ]
    # B 侧故意塞线索词作日常用语，并常只共享一个名词
    fillers_b = [
        "stop waiting and use the {n} default for now",
        "actually we should use {n} alone without extras",
        "replace nothing yet but use {n} in the summary",
        "forget the alert noise and use {n} as the label",
        "cancel the page if {n} is already green",
        "instead of paging just use {n} in the ticket",
        "nevermind the spike use {n} baseline today",
    ]
    # 少数真撤回：双锚 + 线索
    true_b = [
        "actually replace {n1} and {n2} settings instead",
        "retract {n1} change and use {n2} checkpoint instead",
        "stop {n1} roll and replace {n2} policy instead",
    ]
    # 少数干净无关：无线索或无共享锚
    clean_b = [
        "the train schedule changed after lunch",
        "bring an umbrella if clouds return",
        "office plants need water on friday",
    ]

    pairs = []
    for i in range(n):
        roll = rng.random()
        if roll < 0.08:
            n1, n2 = rng.sample(nouns, 2)
            a = f"tune {n1} together with {n2} in staging"
            b = rng.choice(true_b).format(n1=n1, n2=n2)
            kind = "planted_revision"
        elif roll < 0.15:
            a = rng.choice(
                [
                    "garden soil dried out this week",
                    "neighbors painted the fence blue",
                    "coffee machine needs a rinse cycle",
                ]
            )
            b = rng.choice(clean_b)
            kind = "clean_unrelated"
        else:
            # 主质量产：单共享名词 + B 含 use/stop 等线索 → R1 极易开火
            n = rng.choice(nouns)
            other = rng.choice([x for x in nouns if x != n])
            a = rng.choice(fillers_a).format(n=n)
            # 偶尔在 A 再提一个不共享的词，避免偶然双锚
            if rng.random() < 0.5:
                a = a + f" note {other} separately"
            b = rng.choice(fillers_b).format(n=n)
            kind = "single_anchor_cue_noise"
        pairs.append({"id": i, "a": a, "b": b, "kind": kind})
    return pairs


def corpus_rates(pairs: list[dict]) -> dict:
    """三规则在语料上的开火份额。"""
    rates = {}
    for name, fn in (("R0", rule_r0), ("R1", rule_r1), ("R2", rule_r2)):
        flags = [fn(p["a"], p["b"]) for p in pairs]
        n = len(flags)
        c = sum(flags)
        rates[name] = {
            "flagged": c,
            "n": n,
            "share": round(c / n, 4) if n else 0.0,
        }
    return rates


def verb_residual() -> dict:
    """锚若只留动词：无关对仍可因 shared remove/select 误报。"""
    a = "please remove the unused import then select another module"
    b = "stop and use remove carefully when you select files to keep"
    # 期望：动词当锚 → R1 开火；仅名词锚 → 不开火
    r1_verb = rule_r1(a, b, VERB_ANCHORS)
    r1_noun = rule_r1(a, b, NOUN_ANCHORS)
    return {
        "a": a,
        "b": b,
        "r1_verb_anchors_flags": r1_verb,
        "r1_noun_anchors_flags": r1_noun,
        "claim": r1_verb is True and r1_noun is False,
    }


def main() -> None:
    hand_r0 = eval_hand(rule_r0)
    hand_r1 = eval_hand(rule_r1)
    hand_r2 = eval_hand(rule_r2)
    claim_h = (
        hand_r0["all_match"] and hand_r1["all_match"] and hand_r2["all_match"]
    )

    pairs = build_corpus(400, seed=42)
    rates = corpus_rates(pairs)
    # 中档滥报；修好压下去；旧规则低于中档
    claim_c = (
        rates["R1"]["share"] >= 0.90
        and rates["R2"]["share"] <= 0.25
        and rates["R0"]["share"] < rates["R1"]["share"]
    )

    verb = verb_residual()
    claim_v = verb["claim"]

    # 纪律两半：手写破坏/标签约束过了；基率半边只有语料能拆穿 R1
    claim_discipline = claim_h and claim_c

    support = claim_h and claim_c and claim_v
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "A hand-authored supersession suite can score green on an "
            "over-firing middle rule; only a corpus base-rate measurement "
            "exposes cue+one-anchor swallowing almost all candidates — "
            "sabotage-zero and population-not-all-one are different halves"
        ),
        "source": (
            "Tom Jones DEV.to follow-up on Part 10 negative-control thread "
            "(hand suite blind spot / supersession corpus)"
        ),
        "epistemic_bar": (
            "Synthetic catalog sized near his report (~400), not a replay of "
            "443/156 transcripts. Shares and percentages are shape claims, "
            "not replications of his table."
        ),
        "claims": {
            "H_hand_suite_green_on_all_three_rules": claim_h,
            "C_corpus_R1_overfire_R2_bounded": claim_c,
            "V_verb_anchors_false_match": claim_v,
            "discipline_two_halves": claim_discipline,
        },
        "hand_suite": {"R0": hand_r0, "R1": hand_r1, "R2": hand_r2},
        "corpus": {
            "n": len(pairs),
            "kind_counts": {
                k: sum(1 for p in pairs if p["kind"] == k)
                for k in (
                    "single_anchor_cue_noise",
                    "planted_revision",
                    "clean_unrelated",
                )
            },
            "rates": rates,
        },
        "verb_residual": verb,
        "rule_defs": {
            "R0": f"term Jaccard >= {R0_FLOOR}",
            "R1": "cue in B + >=1 shared noun anchor",
            "R2": f"cue in B + >=2 shared noun anchors + Jaccard >= {J_FLOOR}",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("supersession-hand-vs-corpus — hand green / base-rate red")
    print(f"verdict: {verdict}")
    print(
        f"H hand all_match: R0={hand_r0['all_match']} "
        f"R1={hand_r1['all_match']} R2={hand_r2['all_match']}"
    )
    print(
        f"C corpus shares: R0={rates['R0']['share']} "
        f"R1={rates['R1']['share']} R2={rates['R2']['share']} "
        f"(n={len(pairs)})"
    )
    print(
        f"V verb_anchor_flags={verb['r1_verb_anchors_flags']} "
        f"noun_anchor_flags={verb['r1_noun_anchors_flags']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
