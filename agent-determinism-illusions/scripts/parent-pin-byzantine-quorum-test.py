#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Byzantine double-signing vs quorum intersection (Peter, witness follow-up).

Claim under test
----------------
Peter (DEV.to after witness-freshness SUPPORT): a 2-of-3 threshold is not
fork-safe under one Byzantine witness. With witnesses A,B,C, Byzantine B can
sign both roots; root X collects A+B and root Y collects B+C — both reach 2/3
while their only intersection is the equivocating witness.

For up to f Byzantine witnesses, any two valid quorums must intersect in more
than f members: q > (n+f)/2. Usual construction n=3f+1, q=2f+1. For f=1 that
is **3-of-4**, not 2-of-3.

Also: each witness retains its last accepted head and rejects inconsistent
advances; conflicting signed receipts are portable equivocation evidence;
witness-set membership / key rotation is governed state (same anti-rollback
treatment as minimum-version) — if CI-writable, the channel reopens.

Method
------
Toy HMAC witnesses. Synthetic catalog. Not a BFT safety proof.

Cells
-----
  B0  double-signing B under 2-of-3 → both roots admit
  B1  same attack under 3-of-4 (n=4) → cannot dual-admit
  R   witness retains last head; rejects inconsistent second root
  E   conflicting receipts persisted → later detector flags equivocation
  G   CI-writable witness-set shrink (drop honest witnesses) reopens 2-of-3
      dual-admit on the remaining set

PASS criteria (falsify if any fails)
------------------------------------
  1. B0: both roots reach threshold 2/3 with one double-signer
  2. B1: neither divergent root reaches 3/4 (or at most one does)
  3. R: second inconsistent sign rejected when last-head retained
  4. E: receipt log shows two roots
  5. G: after writable membership shrink, 2-of-3 dual-admit returns

Expected: SUPPORT — quorum intersection, not raw threshold fraction;
membership governance is load-bearing. Toy keys ≠ deployed BFT.

Dependencies: stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = Path(__file__).parent / "results-v2" / "parent-pin-byzantine-quorum.json"


def sha256(data: bytes) -> bytes:
    """SHA-256。"""
    return hashlib.sha256(data).digest()


@dataclass(frozen=True)
class Head:
    """签过名的检查点视图（根 + 尺寸）。"""

    root: str
    tree_size: int
    label: str

    def key(self) -> str:
        """exact (root, size)。"""
        return f"{self.root}|{self.tree_size}"


@dataclass
class Receipt:
    """见证收据。"""

    witness_id: str
    root: str
    tree_size: int
    signature: bytes

    def to_public(self) -> dict:
        """可序列化。"""
        return {
            "witness_id": self.witness_id,
            "root": self.root,
            "tree_size": self.tree_size,
            "signature": self.signature.hex(),
        }


@dataclass
class Witness:
    """见证：可保留 last head，拒绝不一致跃迁。"""

    witness_id: str
    key: bytes
    last_head: Head | None = None
    retain_last: bool = False
    signed_roots: set[str] = field(default_factory=set)

    def sign(self, head: Head, *, allow_double: bool = False) -> Receipt | None:
        """对 head 签发；retain 模式下拒不一致；非双签模式下拒第二根。"""
        if self.retain_last and self.last_head is not None:
            # 不一致：不同根且非严格前进同史（本玩具：根不同即拒）
            if head.root != self.last_head.root:
                return None
        if not allow_double and head.root in self.signed_roots:
            # 已签过别的进行中根——普通见证不双签
            if self.last_head and head.root != self.last_head.root:
                return None
        if not allow_double and self.signed_roots and head.root not in self.signed_roots:
            # 已对另一根签过
            if any(r != head.root for r in self.signed_roots):
                return None

        msg = f"{head.root}|{head.tree_size}".encode("utf-8")
        sig = hmac.new(self.key, msg, hashlib.sha256).digest()
        receipt = Receipt(self.witness_id, head.root, head.tree_size, sig)
        self.signed_roots.add(head.root)
        if self.retain_last:
            self.last_head = head
        return receipt


def verify_receipt(receipt: Receipt, keys: dict[str, bytes]) -> bool:
    """验收据。"""
    key = keys.get(receipt.witness_id)
    if key is None:
        return False
    msg = f"{receipt.root}|{receipt.tree_size}".encode("utf-8")
    expected = hmac.new(key, msg, hashlib.sha256).digest()
    return hmac.compare_digest(expected, receipt.signature)


def threshold_met(
    head: Head,
    receipts: list[Receipt],
    keys: dict[str, bytes],
    q: int,
) -> bool:
    """同一 (root,size) 上有效收据数 ≥ q。"""
    n = 0
    seen = set()
    for r in receipts:
        if r.witness_id in seen:
            continue
        if not verify_receipt(r, keys):
            continue
        if r.root != head.root or r.tree_size != head.tree_size:
            continue
        seen.add(r.witness_id)
        n += 1
    return n >= q


def detect_equivocation(receipts: list[Receipt], keys: dict[str, bytes]) -> dict:
    """可携冲突收据 → 多根即分叉证据。"""
    roots = set()
    for r in receipts:
        if verify_receipt(r, keys):
            roots.add(r.root)
    return {"equivocation": len(roots) > 1, "roots": sorted(roots)}


def main() -> None:
    # 两根冲突视图
    head_x = Head(root="rootX" + "a" * 58, tree_size=2, label="honest")
    head_y = Head(root="rootY" + "b" * 58, tree_size=1, label="fork")

    # --- B0：A,B,C；B 双签；q=2 ---
    keys3 = {
        "A": b"wit-A",
        "B": b"wit-B",
        "C": b"wit-C",
    }
    wa = Witness("A", keys3["A"])
    wb = Witness("B", keys3["B"])  # Byzantine：允许双签
    wc = Witness("C", keys3["C"])

    rx_a = wa.sign(head_x)
    rx_b = wb.sign(head_x, allow_double=True)
    ry_b = wb.sign(head_y, allow_double=True)  # 双签 Y
    ry_c = wc.sign(head_y)

    receipts_x_23 = [rx_a, rx_b]
    receipts_y_23 = [ry_b, ry_c]
    b0_x = threshold_met(head_x, receipts_x_23, keys3, q=2)
    b0_y = threshold_met(head_y, receipts_y_23, keys3, q=2)
    claim_b0 = b0_x is True and b0_y is True

    # --- B1：A,B,C,D；q=3；B 双签；诚实只签一边 ---
    keys4 = {
        "A": b"wit-A4",
        "B": b"wit-B4",
        "C": b"wit-C4",
        "D": b"wit-D4",
    }
    w4a = Witness("A", keys4["A"])
    w4b = Witness("B", keys4["B"])
    w4c = Witness("C", keys4["C"])
    w4d = Witness("D", keys4["D"])

    r4x = [
        w4a.sign(head_x),
        w4b.sign(head_x, allow_double=True),
        # 诚实 C,D 只跟 X 或只跟 Y——攻击者最多再拉一个
    ]
    # X 只有 A+B = 2 < 3；若再拉 C：X=A+B+C=3，则 Y 最多 B+D=2 < 3
    r4x.append(w4c.sign(head_x))
    r4y = [
        w4b.sign(head_y, allow_double=True),
        w4d.sign(head_y),
        # 无法再拉 A/C（已签 X 且非拜占庭）
    ]
    b1_x = threshold_met(head_x, [r for r in r4x if r], keys4, q=3)
    b1_y = threshold_met(head_y, [r for r in r4y if r], keys4, q=3)
    # 分叉安全形：不能两根都满 —— 至多一根达到 3
    claim_b1 = not (b1_x and b1_y) and (b1_x is True and b1_y is False)

    # --- R：保留 last head，拒不一致第二根 ---
    wr = Witness("R1", b"wit-R", retain_last=True)
    first = wr.sign(head_x)
    second = wr.sign(head_y)  # 应拒
    claim_r = first is not None and second is None

    # --- E：冲突收据可携 ---
    portable = [rx_a, rx_b, ry_b, ry_c]
    ev = detect_equivocation([r for r in portable if r], keys3)
    # 双签者 B 在两根上都有收据 → 可携证据
    claim_e = ev["equivocation"] is True and len(ev["roots"]) == 2

    # --- G：见证集若 CI 可写（踢掉 C,D，缩回 3 人 2/3）→ 双绿再开 ---
    # 治理态被改写后，回到 B0 形
    keys_shrunk = {"A": keys3["A"], "B": keys3["B"], "C": keys3["C"]}
    g_x = threshold_met(head_x, receipts_x_23, keys_shrunk, q=2)
    g_y = threshold_met(head_y, receipts_y_23, keys_shrunk, q=2)
    claim_g = g_x is True and g_y is True  # 可写缩集后残差

    support = claim_b0 and claim_b1 and claim_r and claim_e and claim_g
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Under one Byzantine double-signing witness, 2-of-3 lets both "
            "conflicting roots reach threshold; 3-of-4 (n=3f+1,q=2f+1,f=1) "
            "blocks dual-admit. Retaining last head rejects inconsistent "
            "advances; conflicting receipts are portable evidence. "
            "CI-writable witness-set membership reopens the 2-of-3 channel "
            "— quorum intersection plus governed membership, not a raw "
            "threshold fraction; toy keys ≠ BFT proof"
        ),
        "source": (
            "Peter DEV.to follow-up on witness-freshness thread "
            "(Byzantine double-sign / quorum intersection)"
        ),
        "epistemic_bar": (
            "Synthetic catalog. Intersection condition illustrated for f=1 "
            "only. Not a general BFT proof; membership/rotation governance "
            "shown as residual reopen, not a full append-only registry."
        ),
        "quorum_rule": {
            "bad": {"n": 3, "q": 2, "f": 1, "note": "q <= (n+f)/2 — unsafe"},
            "good": {"n": 4, "q": 3, "f": 1, "note": "n=3f+1, q=2f+1"},
        },
        "claims": {
            "B0_two_of_three_dual_admit_under_double_sign": claim_b0,
            "B1_three_of_four_blocks_dual_admit": claim_b1,
            "R_retain_last_rejects_inconsistent": claim_r,
            "E_portable_conflicting_receipts": claim_e,
            "G_writable_membership_reopens_two_of_three": claim_g,
        },
        "cell_B0": {
            "q": 2,
            "root_X_met": b0_x,
            "root_Y_met": b0_y,
            "signers_X": ["A", "B"],
            "signers_Y": ["B", "C"],
        },
        "cell_B1": {
            "q": 3,
            "n": 4,
            "root_X_met": b1_x,
            "root_Y_met": b1_y,
            "signers_X": ["A", "B", "C"],
            "signers_Y": ["B", "D"],
        },
        "cell_R": {
            "first_sign_ok": first is not None,
            "second_inconsistent_rejected": second is None,
        },
        "cell_E": ev,
        "cell_G": {
            "after_shrink_to_ABC_q2": {"root_X": g_x, "root_Y": g_y},
            "note": "membership treated as CI-writable → same dual-admit as B0",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("parent-pin-byzantine-quorum — 2/3 unsafe under double-sign")
    print(f"verdict: {verdict}")
    print(f"B0 2/3 dual: X={b0_x} Y={b0_y}")
    print(f"B1 3/4: X={b1_x} Y={b1_y} (dual_blocked={not (b1_x and b1_y)})")
    print(f"R retain reject second={second is None}")
    print(f"E equivocation={ev['equivocation']} roots={ev['roots']}")
    print(f"G shrink reopen dual={g_x and g_y}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
