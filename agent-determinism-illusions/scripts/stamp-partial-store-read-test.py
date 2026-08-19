#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Partial store read: honest stamp over incomplete join (Tom Jones, stamp thread).

Claim under test
----------------
Tom Jones (DEV.to on harness-ladder stamp / threshold follow-up): agrees START
flip and that healthy-run spread cannot bound tomorrow. Adds a third failure
beside too-old (bound) / too-new (hope): both stay silent when the document
is treated as the whole state and only its age is questioned.

He read a store with BASE snapshot + append-only oplog, but read the base
alone. Fourteen items rendered with original text, internally consistent, no
gaps, zero answers shown — ten of fourteen had answers in the oplog (thirty
update batches the base never absorbs). Every stamp on that read was honest:
the base was current *as a base*. START and END would both be right; no age
threshold would fire. Fresh and partial at once, partial in the way that
prints as complete.

So beside temporal error direction: a document assembled from part of its
store carries an accurate timestamp for the reads that happened. The error
lives in the **join**. Check is structural: assert the read touched every
store the state lives in, and print which ones it touched. A base-only read
that names itself leaves the consumer somewhere to stand.

Method
------
Offline synthetic catalog (stdlib). Board = base items + oplog answer patches.

  P  base-only read: publishes 0 answers, stamp honest, looks complete
  F  base+oplog join: publishes true answered count
  T  temporal controls silent: START/END ages do not distinguish P from healthy
  S  structural gate: require stores_touched == required; base-only fails gate
     unless it labels itself partial
  U  blind step inside gate: same partial doc, reader declares required=["base"]
     → gate PASS as complete (caller-supplied required)
  W  store-derived required: enumerate stores at connection, not from reader
     → gate REJECT even when reader would declare base-only

PASS criteria (falsify if any fails)
------------------------------------
  1. P: answered_shown == 0 while true_answered >= 10; stamp fresh; item_count
     matches base size (looks complete)
  2. F: answered_shown == true_answered
  3. T: age thresholds do not flag P as stale relative to base mtime
  4. S: unlabeled base-only fails structural gate; labeled base-only passes
     as partial; full join passes as complete
  5. U: reader-supplied required=["base"] admits unlabeled partial as complete
  6. W: store-enumerated required=["base","oplog"] rejects same partial doc

Expected: SUPPORT — timestamp speaks only for reads that happened; join
coverage is a separate predicate; caller-supplied required is a blind step
inside the gate unless required is derived from the store.

Dependencies: stdlib only.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "stamp-partial-store-read.json"

# 十四项 base；十项答案只在 oplog
BASE_ITEMS = [
    {"id": i, "text": f"question-{i}", "answer": None} for i in range(1, 15)
]
OPLOG = [
    {"batch": b, "id": i, "answer": f"answer-{i}"}
    for b, i in enumerate(range(1, 11), start=1)
]  # 10 answered; batches 1..10 (Tom: ~30 batches — we keep 10 patches, shape OK)


def read_base_only(base: list, base_mtime: float, now: float) -> dict:
    """只读 base：章对 base 诚实；答案全空；表面完整。"""
    doc = {
        "items": [dict(x) for x in base],
        "stores_touched": ["base"],
        "generated": base_mtime,  # START=END 对「这次读到的 store」都诚实
        "write_time": now,
    }
    answered = sum(1 for x in doc["items"] if x.get("answer"))
    return {
        **doc,
        "answered_shown": answered,
        "item_count": len(doc["items"]),
        "published_age": now - doc["generated"],
        "looks_complete": answered == 0
        and len(doc["items"]) == len(base)
        and all(x.get("text") for x in doc["items"]),
    }


def read_base_plus_oplog(
    base: list, oplog: list, base_mtime: float, oplog_mtime: float, now: float
) -> dict:
    """联结 base+oplog。"""
    items = {x["id"]: dict(x) for x in base}
    for patch in oplog:
        if patch["id"] in items:
            items[patch["id"]]["answer"] = patch["answer"]
    # 章取所触及 store 的最旧读时刻（保守）或最晚——此处用 min 表 START 形
    generated = min(base_mtime, oplog_mtime)
    doc_items = [items[i] for i in sorted(items)]
    answered = sum(1 for x in doc_items if x.get("answer"))
    return {
        "items": doc_items,
        "stores_touched": ["base", "oplog"],
        "generated": generated,
        "write_time": now,
        "answered_shown": answered,
        "item_count": len(doc_items),
        "published_age": now - generated,
        "looks_complete": True,
    }


def true_answered(base: list, oplog: list) -> int:
    """真值：oplog 覆盖后的已答数。"""
    ids = {p["id"] for p in oplog}
    return sum(1 for x in base if x["id"] in ids)


def age_threshold_fires(published_age: float, threshold: float) -> bool:
    """时间阈值是否开火。"""
    return published_age + 1e-9 >= threshold


def enumerate_stores_at_connection() -> list[str]:
    """连接上实际存在的 store——不来自 reader 声明。"""
    return ["base", "oplog"]


def structural_gate(
    stores_touched: list[str],
    required: list[str],
    *,
    label_partial: bool,
) -> dict:
    """结构门：必须触及全部 store，或显式自报 partial。"""
    touched = set(stores_touched)
    need = set(required)
    complete = touched >= need
    if complete:
        return {"admit": "PASS", "as": "complete", "stores_touched": stores_touched}
    if label_partial and touched == {"base"}:
        return {
            "admit": "PASS",
            "as": "partial_base_only",
            "stores_touched": stores_touched,
        }
    return {
        "admit": "REJECT",
        "as": "unlabeled_partial",
        "stores_touched": stores_touched,
        "missing": sorted(need - touched),
    }


def main() -> None:
    base_mtime = 1000.0
    oplog_mtime = 1000.0  # oplog 也「新鲜」——时间轴帮不上忙
    now = 1005.0  # 读发生后 5s；章很新
    threshold_hours = 3600.0

    truth = true_answered(BASE_ITEMS, OPLOG)
    partial = read_base_only(BASE_ITEMS, base_mtime, now)
    full = read_base_plus_oplog(
        BASE_ITEMS, OPLOG, base_mtime, oplog_mtime, now
    )

    claim_p = (
        partial["answered_shown"] == 0
        and truth >= 10
        and partial["item_count"] == 14
        and partial["looks_complete"] is True
        and partial["published_age"] < 60
    )
    claim_f = full["answered_shown"] == truth and set(full["stores_touched"]) == {
        "base",
        "oplog",
    }
    claim_t = (
        not age_threshold_fires(partial["published_age"], threshold_hours)
        and not age_threshold_fires(full["published_age"], threshold_hours)
        # START/END 对 base-only 都「对」：generated == base_mtime
        and partial["generated"] == base_mtime
    )

    gate_unlabeled = structural_gate(
        partial["stores_touched"], ["base", "oplog"], label_partial=False
    )
    gate_labeled = structural_gate(
        partial["stores_touched"], ["base", "oplog"], label_partial=True
    )
    gate_full = structural_gate(
        full["stores_touched"], ["base", "oplog"], label_partial=False
    )
    claim_s = (
        gate_unlabeled["admit"] == "REJECT"
        and gate_labeled["admit"] == "PASS"
        and gate_labeled["as"] == "partial_base_only"
        and gate_full["admit"] == "PASS"
        and gate_full["as"] == "complete"
    )

    # Tom round-2: required 来自 reader 时，同一文档可过门
    gate_reader_base_only = structural_gate(
        partial["stores_touched"], ["base"], label_partial=False
    )
    stores_at_conn = enumerate_stores_at_connection()
    gate_store_derived = structural_gate(
        partial["stores_touched"], stores_at_conn, label_partial=False
    )
    claim_u = (
        gate_reader_base_only["admit"] == "PASS"
        and gate_reader_base_only["as"] == "complete"
    )
    claim_w = (
        gate_store_derived["admit"] == "REJECT"
        and gate_store_derived["as"] == "unlabeled_partial"
        and set(stores_at_conn) == {"base", "oplog"}
    )

    support = claim_p and claim_f and claim_t and claim_s and claim_u and claim_w
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "A timestamp only speaks for the reads that happened; a base-only "
            "read of a base+oplog store can be temporally honest yet publish "
            "a complete-looking board with zero answers while answers live in "
            "the oplog — START/END/age thresholds stay silent; structural "
            "coverage of stores_touched is the missing predicate; "
            "caller-supplied required is a blind step unless derived "
            "from store enumeration"
        ),
        "source": (
            "Tom Jones DEV.to follow-up on harness-ladder stamp/threshold "
            "thread (base+oplog partial join)"
        ),
        "epistemic_bar": (
            "Synthetic 14-item board / 10 oplog answers (shape of his "
            "fourteen / ten / thirty-batches story, not a field replay). "
            "Structural gate is a fixture, not his production reader."
        ),
        "claims": {
            "P_base_only_zero_answers_looks_complete": claim_p,
            "F_join_recovers_answers": claim_f,
            "T_temporal_controls_silent": claim_t,
            "S_structural_store_coverage_gate": claim_s,
            "U_reader_supplied_required_blind_step": claim_u,
            "W_store_derived_required_catches": claim_w,
        },
        "truth": {"answered_in_oplog": truth, "base_items": 14},
        "cell_P_base_only": {
            "answered_shown": partial["answered_shown"],
            "item_count": partial["item_count"],
            "published_age": partial["published_age"],
            "stores_touched": partial["stores_touched"],
            "looks_complete": partial["looks_complete"],
        },
        "cell_F_join": {
            "answered_shown": full["answered_shown"],
            "stores_touched": full["stores_touched"],
            "published_age": full["published_age"],
        },
        "cell_T_temporal": {
            "threshold_s": threshold_hours,
            "partial_age_fires": age_threshold_fires(
                partial["published_age"], threshold_hours
            ),
            "full_age_fires": age_threshold_fires(
                full["published_age"], threshold_hours
            ),
        },
        "cell_S_structural": {
            "unlabeled_partial": gate_unlabeled,
            "labeled_partial": gate_labeled,
            "full_join": gate_full,
        },
        "cell_U_reader_required": {
            "required": ["base"],
            "same_doc_as_P": True,
            "gate": gate_reader_base_only,
        },
        "cell_W_store_derived": {
            "enumerated_at_connection": stores_at_conn,
            "gate": gate_store_derived,
        },
        "third_beside_old_new": (
            "too old = bound; too new = hope; partial join with honest stamp "
            "= silent completeness lie"
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("stamp-partial-store-read — honest stamp / incomplete join")
    print(f"verdict: {verdict}")
    print(
        f"P answered_shown={partial['answered_shown']} "
        f"truth={truth} age={partial['published_age']}"
    )
    print(f"F answered_shown={full['answered_shown']} stores={full['stores_touched']}")
    print(
        f"S unlabeled={gate_unlabeled['admit']} "
        f"labeled={gate_labeled['as']} full={gate_full['as']}"
    )
    print(
        f"U reader_required=base -> {gate_reader_base_only['admit']} "
        f"as={gate_reader_base_only['as']}"
    )
    print(f"W store_derived -> {gate_store_derived['admit']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
