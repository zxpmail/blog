#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Witness threshold + freshness (Peter: gossip admission / freeze case).

Claim under test
----------------
Peter (DEV.to follow-up after equivocation SUPPORT): consistency against one
honest prior detects a fork only after *that* client has seen a conflicting
view. Two isolated first-time jobs can still accept different, individually
valid heads.

Next fixture: checkpoint gossip as admission — each job submits the signed
tree head it observed to independent witnesses and requires a threshold of
witness receipts for that exact ``(root, size)`` before accepting the policy
version; persist receipts with build evidence so later jobs detect
equivocation rather than merely local rollback.

Freeze case: authority keeps returning an old but internally consistent head.
Consistency still passes, so admission also needs freshness / monotonic
progress with fail-closed offline behavior.

Three properties separated
--------------------------
  inclusion         — selected version is in one presented view
  consistency       — one observed view extends another (prior script)
  witness agreement — conflicting views become externally detectable

Method
------
Toy authority HMAC-STH + three independent witness keys. Threshold = 2/3.
Synthetic catalog; not a real quorum / social-consensus proof.

Cells
-----
  W0  two first-time jobs, no shared prior, no witness gate
      honest head vs shrink fork → both admit (gap consistency cannot see)
  W1  witness threshold on exact (root, size) before admit
      divergent submissions cannot both gather 2/3 on their own root;
      persisted receipt log lets a later job see two roots → equivocation
  F0  freeze: old head internally consistent with itself → consistency PASS
  F1  monotonic progress (size >= watermark) + offline fail-closed
      frozen head REJECT; offline without freshness evidence REJECT

PASS criteria (falsify if any fails)
------------------------------------
  1. W0: both first-time jobs admit without witnesses
  2. W1: neither divergent job reaches threshold alone; receipt log shows
     two roots; a later job reading the log flags equivocation
  3. F0: frozen head passes consistency-only admission
  4. F1: same frozen head fails monotonic rule; offline fails closed

Expected: SUPPORT — signature trusts one view; witness threshold makes
conflict externally detectable; monotonic progress blocks freeze. Upgrade
from trusting the authority key alone toward trusting a witness-set
threshold — necessary governance step, not a full-system security proof.

Dependencies: stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-pin-witness-freshness.json"

AUTHORITY_KEY = b"synthetic-authority-key-not-for-prod"
WITNESS_KEYS = {
    "w1": b"witness-key-1",
    "w2": b"witness-key-2",
    "w3": b"witness-key-3",
}
THRESHOLD = 2  # 2 of 3


def sha256(data: bytes) -> bytes:
    """SHA-256。"""
    return hashlib.sha256(data).digest()


def digest_of(text: str) -> str:
    """内容摘要 hex。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class STH:
    """签过名的树头。"""

    tree_size: int
    root: bytes
    minimum: int
    signature: bytes

    def to_public(self) -> dict:
        """可序列化。"""
        return {
            "tree_size": self.tree_size,
            "root": self.root.hex(),
            "minimum": self.minimum,
            "signature": self.signature.hex(),
        }

    def root_size_key(self) -> str:
        """见证钉住的 exact (root, size)。"""
        return f"{self.root.hex()}|{self.tree_size}"


def root_from_entries(entries: list[tuple[int, str]]) -> bytes:
    """玩具根：叶子规范编码的有序哈希链（本脚本不复用完整 Merkle）。"""
    h = sha256(b"")
    for version, dig in entries:
        leaf = f"version={version}|digest={dig}".encode("utf-8")
        h = sha256(h + leaf)
    return h


def sign_sth(entries: list[tuple[int, str]], minimum: int) -> STH:
    """权威签发。"""
    root = root_from_entries(entries)
    size = len(entries)
    msg = f"{size}|{root.hex()}|{minimum}".encode("utf-8")
    sig = hmac.new(AUTHORITY_KEY, msg, hashlib.sha256).digest()
    return STH(size, root, minimum, sig)


def verify_sth(sth: STH) -> bool:
    """验权威签。"""
    msg = f"{sth.tree_size}|{sth.root.hex()}|{sth.minimum}".encode("utf-8")
    expected = hmac.new(AUTHORITY_KEY, msg, hashlib.sha256).digest()
    return hmac.compare_digest(expected, sth.signature)


def inclusion_ok(sth: STH, entries: list[tuple[int, str]], version: int, dig: str) -> bool:
    """inclusion：选中条目在本视图叶子集，且根匹配。"""
    if not verify_sth(sth):
        return False
    if root_from_entries(entries) != sth.root or len(entries) != sth.tree_size:
        return False
    return (version, dig) in entries


def consistency_self(sth: STH) -> bool:
    """仅自洽：签名合法（冻结头对自身永远「一致」）。"""
    return verify_sth(sth)


def consistency_extends(old: STH, new: STH, new_entries: list[tuple[int, str]]) -> bool:
    """新视图前缀根等于旧根（缩树/换根失败）。"""
    if not verify_sth(old) or not verify_sth(new):
        return False
    if new.tree_size < old.tree_size:
        return False
    if len(new_entries) != new.tree_size:
        return False
    if root_from_entries(new_entries) != new.root:
        return False
    prefix = new_entries[: old.tree_size]
    return root_from_entries(prefix) == old.root


@dataclass
class Receipt:
    """见证收据：钉住 exact (root, size)。"""

    witness_id: str
    root_hex: str
    tree_size: int
    signature: bytes

    def to_public(self) -> dict:
        """可序列化。"""
        return {
            "witness_id": self.witness_id,
            "root": self.root_hex,
            "tree_size": self.tree_size,
            "signature": self.signature.hex(),
        }


def witness_sign(witness_id: str, sth: STH) -> Receipt:
    """见证签发收据。"""
    key = WITNESS_KEYS[witness_id]
    msg = f"{sth.root.hex()}|{sth.tree_size}".encode("utf-8")
    sig = hmac.new(key, msg, hashlib.sha256).digest()
    return Receipt(witness_id, sth.root.hex(), sth.tree_size, sig)


def verify_receipt(receipt: Receipt) -> bool:
    """验见证签。"""
    key = WITNESS_KEYS.get(receipt.witness_id)
    if key is None:
        return False
    msg = f"{receipt.root_hex}|{receipt.tree_size}".encode("utf-8")
    expected = hmac.new(key, msg, hashlib.sha256).digest()
    return hmac.compare_digest(expected, receipt.signature)


def gather_receipts(sth: STH, willing: list[str]) -> list[Receipt]:
    """愿意背书该头的见证集合。"""
    return [witness_sign(w, sth) for w in willing]


def threshold_met(sth: STH, receipts: list[Receipt], threshold: int = THRESHOLD) -> bool:
    """同一 (root, size) 上有效收据数 ≥ 阈值。"""
    key = sth.root_size_key()
    ok = 0
    for r in receipts:
        if not verify_receipt(r):
            continue
        if f"{r.root_hex}|{r.tree_size}" != key:
            continue
        ok += 1
    return ok >= threshold


def admit_local(sth: STH, entries: list[tuple[int, str]], version: int, dig: str) -> dict:
    """仅 inclusion + 密封底（首次 job、无旧头、无见证）。"""
    if not inclusion_ok(sth, entries, version, dig):
        return {"admit": "REJECT", "reason": "inclusion_fail"}
    if version < sth.minimum:
        return {"admit": "REJECT", "reason": "below_minimum"}
    return {"admit": "PASS", "reason": "local_inclusion_and_floor"}


def admit_with_witnesses(
    sth: STH,
    entries: list[tuple[int, str]],
    version: int,
    dig: str,
    receipts: list[Receipt],
) -> dict:
    """本地 inclusion/floor + 见证阈值。"""
    local = admit_local(sth, entries, version, dig)
    if local["admit"] != "PASS":
        return {**local, "witness_ok": False}
    w_ok = threshold_met(sth, receipts)
    if not w_ok:
        return {
            "admit": "REJECT",
            "reason": "witness_threshold_unmet",
            "witness_ok": False,
            "receipts_n": sum(
                1
                for r in receipts
                if verify_receipt(r)
                and f"{r.root_hex}|{r.tree_size}" == sth.root_size_key()
            ),
        }
    return {
        "admit": "PASS",
        "reason": "local_plus_witness_threshold",
        "witness_ok": True,
        "receipts_n": THRESHOLD,
    }


def detect_equivocation(receipt_log: list[Receipt]) -> dict:
    """后到者读持久化收据：同一审计窗出现多个 root → 分叉。"""
    roots = set()
    for r in receipt_log:
        if verify_receipt(r):
            roots.add(r.root_hex)
    return {
        "equivocation": len(roots) > 1,
        "distinct_roots": sorted(roots),
    }


def admit_consistency_only(old: STH, new: STH, new_entries: list[tuple[int, str]]) -> dict:
    """仅 consistency（冻结场景：old==new 时自洽即过）。"""
    if old.root == new.root and old.tree_size == new.tree_size:
        ok = consistency_self(new)
        return {
            "admit": "PASS" if ok else "REJECT",
            "reason": "self_consistent_freeze" if ok else "bad_sth",
        }
    ok = consistency_extends(old, new, new_entries)
    return {
        "admit": "PASS" if ok else "REJECT",
        "reason": "extends_prior" if ok else "consistency_fail",
    }


def admit_strict_progress(
    new: STH,
    watermark_size: int,
    *,
    offline: bool,
    freshness_evidence: bool,
) -> dict:
    """严格单调：tree_size 必须 > 水位；离线且无新鲜度证据 → fail-closed。"""
    if offline and not freshness_evidence:
        return {"admit": "REJECT", "reason": "offline_fail_closed"}
    if new.tree_size <= watermark_size:
        return {
            "admit": "REJECT",
            "reason": "no_monotonic_progress",
            "watermark": watermark_size,
            "got": new.tree_size,
        }
    if not verify_sth(new):
        return {"admit": "REJECT", "reason": "bad_sth"}
    return {
        "admit": "PASS",
        "reason": "strict_progress",
        "watermark": watermark_size,
        "got": new.tree_size,
    }


def main() -> None:
    d1 = digest_of("v1-false-green")
    d2 = digest_of("v2-honest")
    honest_entries = [(1, d1), (2, d2)]
    fork_entries = [(1, d1)]
    honest = sign_sth(honest_entries, minimum=2)
    fork = sign_sth(fork_entries, minimum=1)

    # --- W0：两个首次 job，无旧头无见证 ---
    w0_a = admit_local(honest, honest_entries, 2, d2)
    w0_b = admit_local(fork, fork_entries, 1, d1)
    claim_w0 = w0_a["admit"] == "PASS" and w0_b["admit"] == "PASS"

    # --- W1：见证阈值；见证集合不愿同时背书两个根 ---
    # 诚实头：w1,w2 背书；分叉头：只有 w3 愿意（凑不齐 2）
    receipts_a = gather_receipts(honest, ["w1", "w2"])
    receipts_b = gather_receipts(fork, ["w3"])
    w1_a = admit_with_witnesses(honest, honest_entries, 2, d2, receipts_a)
    w1_b = admit_with_witnesses(fork, fork_entries, 1, d1, receipts_b)
    # 持久化两边提交过的收据（即便 B 未准入，提交痕迹仍在 gossip 日志）
    # 为检出分叉：假设 B 仍向见证请求、w3 签发了收据并写入共享日志
    receipt_log = receipts_a + receipts_b
    # 若攻击者试图让两边都过：需要同一根上的 2/3——给 fork 硬塞 w1,w2 会与 honest 根冲突
    # 后到 job 读日志
    later = detect_equivocation(receipt_log)
    claim_w1 = (
        w1_a["admit"] == "PASS"
        and w1_b["admit"] == "REJECT"
        and w1_b["reason"] == "witness_threshold_unmet"
        and later["equivocation"] is True
        and len(later["distinct_roots"]) == 2
    )

    # --- F0：冻结旧头，仅 consistency（权威反复给同一合法头）---
    f0_repeat = admit_consistency_only(honest, honest, honest_entries)
    claim_f0 = f0_repeat["admit"] == "PASS"

    # --- F1：严格单调进度（size 必须 > 水位）+ 离线 fail-closed ---
    older = sign_sth([(1, d1)], minimum=1)
    f1_frozen_at_watermark = admit_strict_progress(
        older, watermark_size=1, offline=False, freshness_evidence=True
    )
    f1_advanced = admit_strict_progress(
        honest, watermark_size=1, offline=False, freshness_evidence=True
    )
    f1_offline = admit_strict_progress(
        honest, watermark_size=1, offline=True, freshness_evidence=False
    )
    f1_repeat_blocked = admit_strict_progress(
        honest, watermark_size=2, offline=False, freshness_evidence=True
    )
    claim_f1 = (
        f1_frozen_at_watermark["admit"] == "REJECT"
        and f1_frozen_at_watermark["reason"] == "no_monotonic_progress"
        and f1_advanced["admit"] == "PASS"
        and f1_offline["admit"] == "REJECT"
        and f1_offline["reason"] == "offline_fail_closed"
        and f1_repeat_blocked["admit"] == "REJECT"
    )

    support = claim_w0 and claim_w1 and claim_f0 and claim_f1
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Signature trusts one view; two first-time jobs can dual-admit "
            "without witnesses. A witness threshold on exact (root, size) "
            "makes conflicting views externally detectable; monotonic "
            "progress blocks an old but self-consistent freeze. Upgrade from "
            "trusting the authority key alone toward a witness-set threshold "
            "— necessary governance step, not full-system safety proof"
        ),
        "source": (
            "Peter DEV.to follow-up on equivocation thread "
            "(checkpoint gossip / freeze / three properties)"
        ),
        "epistemic_bar": (
            "Toy HMAC witnesses ≠ deployed quorum. Threshold independence / "
            "non-collusion assumed, not proven. Offline fail-closed is a "
            "policy choice. Synthetic catalog only."
        ),
        "three_properties": {
            "inclusion": "selected version in one presented view",
            "consistency": "one observed view extends another (see equivocation script)",
            "witness_agreement": "conflicting views externally detectable via receipts",
        },
        "claims": {
            "W0_first_time_dual_admit_without_witnesses": claim_w0,
            "W1_threshold_blocks_fork_and_log_detects": claim_w1,
            "F0_freeze_passes_consistency_only": claim_f0,
            "F1_monotonic_and_offline_fail_closed": claim_f1,
        },
        "cell_W0": {"job_A": w0_a, "job_B": w0_b},
        "cell_W1": {
            "job_A": w1_a,
            "job_B": w1_b,
            "receipt_log_roots": later,
            "threshold": THRESHOLD,
            "witnesses": list(WITNESS_KEYS),
        },
        "cell_F0": {"repeat_honest_consistency_only": f0_repeat},
        "cell_F1": {
            "frozen_at_watermark": f1_frozen_at_watermark,
            "advanced": f1_advanced,
            "offline_fail_closed": f1_offline,
            "repeat_at_watermark_2": f1_repeat_blocked,
        },
        "heads": {"honest": honest.to_public(), "fork": fork.to_public()},
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("parent-pin-witness-freshness — gossip threshold + freeze")
    print(f"verdict: {verdict}")
    print(f"W0 first-time: A={w0_a['admit']} B={w0_b['admit']}")
    print(
        f"W1 witness: A={w1_a['admit']} B={w1_b['admit']} "
        f"later_equivocation={later['equivocation']}"
    )
    print(f"F0 freeze consistency-only: {f0_repeat['admit']}")
    print(
        f"F1 monotonic: freeze={f1_frozen_at_watermark['admit']} "
        f"advance={f1_advanced['admit']} offline={f1_offline['admit']} "
        f"repeat={f1_repeat_blocked['admit']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
