#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pin equivocation: sealed floor ≠ global history (Peter, transparency-log half).

Claim under test
----------------
A sealed local minimum proves this job did not roll the floor backwards on the
view it was shown. It does not prove the approval history itself is a single
global append-only log. A compromised authority can show job A a signed
checkpoint whose minimum is 2 and job B a fork whose minimum is still 1; each
job may see a locally valid signed tree head + inclusion proof while no single
history exists.

Peter's prescription under test (witness/quorum out of scope): persist the
previously accepted signed tree head somewhere the job cannot rewrite; require
an inclusion proof for the selected verifier *and* a consistency proof from
the old head to the new one.

Attack-family addendum (still not a security proof): under that prescription,
a same-size root-swap fork is caught when the prior is honest and unwritable;
rewriting the prior slot, or giving each job only a private prior with no
cross-view compare, re-opens dual-green equivocation.

Method
------
Toy Certificate Transparency (RFC 6962–style) Merkle tree over approval
leaves. Authority HMAC-signs tree heads (STH). Ground harness story matches
parent-pin-rollback: v1 always PASS on failing obs (false-green); v2 REJECT.
Same-size fork uses an alternate false-green leaf at version 2.

Cells
-----
  A local sealed floor + inclusion only (no consistency to persisted head)
    job A sees honest history min=2, selects v2 → locally green
    job B sees shrink fork min=1, selects v1 → locally green
  B + consistency against job-unwritable persisted STH (honest size=2, min=2)
    job A: consistency PASS; job B shrink fork: consistency FAIL
  C negative control — honest append on one history
    old size=1/min=1 → new size=2/min=2; inclusion + consistency PASS
  D same-size root-swap fork vs unwritable honest prior
    consistency REJECT (prescription holds under that assumption)
  E attacker rewrites persisted-prior slot to fork-compatible STH
    consistency PASS + false green (unwritable-prior assumption broken)
  F per-job private priors, no cross-view compare
    each job consistency-green on its own history; global fork invisible

PASS criteria (falsify if any fails)
------------------------------------
  1–3. A/B/C as above
  4. D: same-size fork rejected against honest persisted prior
  5. E: rewritten prior lets fork consistency-pass and false-green
  6. F: private priors → both jobs pipeline-green despite global fork

Expected: SUPPORT — two predicates + assumption boundary of the
prescription; not a field security proof.

Dependencies: stdlib only.
How to falsify: any of the six cells misses its expected catch/break.
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

OUT = Path(__file__).parent / "results-v2" / "parent-pin-equivocation.json"

# 玩具权威密钥（仅合成目录；不宣称密码学安全）
AUTHORITY_KEY = b"synthetic-authority-key-not-for-prod"

OBS_FAILING = {"invalidated": False}

V1_VERSION = 1
V2_VERSION = 2

V1_SOURCE = (
    "def adjudicate(obs):\n"
    "    return 'PASS'  # BACKDOOR: ignore observation\n"
)
V2_SOURCE = (
    "def adjudicate(obs):\n"
    "    return 'PASS' if obs.get('invalidated') else 'REJECT'\n"
)
# 同尺寸换根：另一份假绿 artifact（version 同为 2，字节不同 → 根不同）
V2_ALT_SOURCE = (
    "def adjudicate(obs):\n"
    "    return 'PASS'  # ALT BACKDOOR: ignore observation\n"
)


def sha256(data: bytes) -> bytes:
    """SHA-256 摘要。"""
    return hashlib.sha256(data).digest()


def leaf_hash(data: bytes) -> bytes:
    """RFC6962 叶子哈希：H(0x00 || data)。"""
    return sha256(b"\x00" + data)


def node_hash(left: bytes, right: bytes) -> bytes:
    """RFC6962 节点哈希：H(0x01 || left || right)。"""
    return sha256(b"\x01" + left + right)


def largest_power_of_two_less_than(n: int) -> int:
    """小于 n 的最大 2 的幂（n ≥ 2）。"""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def digest_of_source(source: str) -> str:
    """artifact 内容摘要（hex）。"""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def encode_leaf(version: int, artifact_digest: str) -> bytes:
    """批准叶子的规范编码。"""
    return f"version={version}|digest={artifact_digest}".encode("utf-8")


def mth(leaves: list[bytes]) -> bytes:
    """Merkle Tree Hash（RFC6962 §2.1）。"""
    n = len(leaves)
    if n == 0:
        return sha256(b"")
    if n == 1:
        return leaf_hash(leaves[0])
    k = largest_power_of_two_less_than(n)
    return node_hash(mth(leaves[:k]), mth(leaves[k:]))


def path_to_root(leaves: list[bytes], index: int) -> list[bytes]:
    """inclusion 路径：从叶子到根所需的兄弟哈希（自底向上）。"""
    n = len(leaves)
    if not (0 <= index < n):
        raise IndexError("leaf index out of range")
    if n == 1:
        return []

    k = largest_power_of_two_less_than(n)
    if index < k:
        proof = path_to_root(leaves[:k], index)
        proof.append(mth(leaves[k:]))
        return proof
    proof = path_to_root(leaves[k:], index - k)
    proof.append(mth(leaves[:k]))
    return proof


def verify_inclusion(
    leaf: bytes,
    index: int,
    tree_size: int,
    root: bytes,
    proof: list[bytes],
) -> bool:
    """用 inclusion proof 复算根。"""
    if tree_size == 0 or index >= tree_size:
        return False
    node = leaf_hash(leaf)
    fn = index
    sn = tree_size - 1
    for sibling in proof:
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            node = node_hash(sibling, node)
            while fn % 2 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
            fn >>= 1
            sn >>= 1
        else:
            node = node_hash(node, sibling)
            fn >>= 1
            sn >>= 1
    return sn == 0 and node == root


def prove_consistency(leaves: list[bytes], m: int, n: int) -> list[bytes]:
    """生成 size m → size n 的 consistency proof（m ≤ n，同前缀叶子）。"""
    if not (0 <= m <= n <= len(leaves)):
        raise ValueError("bad consistency range")
    if m == n or m == 0:
        return []

    def subproof(lo: int, hi: int, target: int, include_root: bool) -> list[bytes]:
        """对 leaves[lo:hi] 证明到 target 尺寸子树的路径分量。"""
        size = hi - lo
        if size == target:
            return [mth(leaves[lo:hi])] if include_root else []
        k = largest_power_of_two_less_than(size)
        if target <= k:
            proof = subproof(lo, lo + k, target, True)
            proof.append(mth(leaves[lo + k : hi]))
            return proof
        proof = subproof(lo + k, hi, target - k, False)
        proof.append(mth(leaves[lo : lo + k]))
        return proof

    return subproof(0, n, m, m < n)


def verify_consistency(
    old_size: int,
    new_size: int,
    old_root: bytes,
    new_root: bytes,
    proof: list[bytes],
) -> bool:
    """验证 old tree 是 new tree 的前缀（RFC6962 §2.1.2 验证逻辑）。"""
    if old_size > new_size:
        return False
    if old_size == new_size:
        return old_root == new_root and proof == []
    if old_size == 0:
        return new_size > 0 and len(new_root) == 32

    fn, sn = old_size - 1, new_size - 1
    while fn % 2 == 1:
        fn >>= 1
        sn >>= 1

    if len(proof) == 0:
        return False

    node = proof[0]
    old_hash = node
    new_hash = node
    pi = 1
    while pi < len(proof):
        p = proof[pi]
        pi += 1
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            old_hash = node_hash(p, old_hash)
            new_hash = node_hash(p, new_hash)
            while fn % 2 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
            fn >>= 1
            sn >>= 1
        else:
            new_hash = node_hash(new_hash, p)
            fn >>= 1
            sn >>= 1

    return sn == 0 and old_hash == old_root and new_hash == new_root


def harness_v1_adjudicate(obs: dict) -> str:
    """已知假绿通道。"""
    _ = obs
    return "PASS"


def harness_v2_adjudicate(obs: dict) -> str:
    """诚实 harness：失败观测 → REJECT。"""
    return "PASS" if obs.get("invalidated") else "REJECT"


def harness_v2_alt_adjudicate(obs: dict) -> str:
    """同尺寸换根用的另一假绿通道。"""
    _ = obs
    return "PASS"


HARNESS_RUN = {
    digest_of_source(V1_SOURCE): harness_v1_adjudicate,
    digest_of_source(V2_SOURCE): harness_v2_adjudicate,
    digest_of_source(V2_ALT_SOURCE): harness_v2_alt_adjudicate,
}


@dataclass(frozen=True)
class STH:
    """签过名的树头：尺寸、根、策略最低版本。"""

    tree_size: int
    root: bytes
    minimum: int
    signature: bytes

    def to_public(self) -> dict:
        """可序列化视图。"""
        return {
            "tree_size": self.tree_size,
            "root": self.root.hex(),
            "minimum": self.minimum,
            "signature": self.signature.hex(),
        }


def sign_sth(tree_size: int, root: bytes, minimum: int) -> STH:
    """权威签发 STH（HMAC 玩具签名）。"""
    msg = f"{tree_size}|{root.hex()}|{minimum}".encode("utf-8")
    sig = hmac.new(AUTHORITY_KEY, msg, hashlib.sha256).digest()
    return STH(tree_size, root, minimum, sig)


def verify_sth_signature(sth: STH) -> bool:
    """验签。"""
    msg = f"{sth.tree_size}|{sth.root.hex()}|{sth.minimum}".encode("utf-8")
    expected = hmac.new(AUTHORITY_KEY, msg, hashlib.sha256).digest()
    return hmac.compare_digest(expected, sth.signature)


def build_log(entries: list[tuple[int, str]]) -> list[bytes]:
    """(version, artifact_digest) → 叶子字节。"""
    return [encode_leaf(v, d) for v, d in entries]


def make_sth_for(
    entries: list[tuple[int, str]], minimum: int
) -> tuple[STH, list[bytes]]:
    """从批准条目建树并签发。"""
    leaves = build_log(entries)
    root = mth(leaves)
    return sign_sth(len(leaves), root, minimum), leaves


def local_admit(
    selected_version: int,
    selected_leaf: bytes,
    leaf_index: int,
    sth: STH,
    leaves: list[bytes],
) -> dict:
    """本视图：验签 + 密封底 + inclusion；不查跨检查点一致性。"""
    if not verify_sth_signature(sth):
        return {"admit": "REJECT", "reason": "bad_sth_signature"}
    if selected_version < sth.minimum:
        return {"admit": "REJECT", "reason": "below_sealed_minimum"}
    proof = path_to_root(leaves, leaf_index)
    ok = verify_inclusion(
        selected_leaf, leaf_index, sth.tree_size, sth.root, proof
    )
    if not ok:
        return {"admit": "REJECT", "reason": "inclusion_fail"}
    return {
        "admit": "PASS",
        "reason": "local_sealed_floor_and_inclusion",
        "inclusion_ok": True,
    }


def run_adjudicate(artifact_digest: str, obs: dict) -> str:
    """准入后裁决。"""
    return HARNESS_RUN[artifact_digest](obs)


def pipeline_local(
    selected_version: int,
    artifact_digest: str,
    leaf_index: int,
    sth: STH,
    leaves: list[bytes],
    obs: dict,
) -> dict:
    """本地谓词管道。"""
    leaf = encode_leaf(selected_version, artifact_digest)
    admit = local_admit(selected_version, leaf, leaf_index, sth, leaves)
    if admit["admit"] != "PASS":
        return {
            "admit": "REJECT",
            "adjudicate": None,
            "ci_green": False,
            "detail": admit,
        }
    verdict = run_adjudicate(artifact_digest, obs)
    return {
        "admit": "PASS",
        "adjudicate": verdict,
        "ci_green": verdict == "PASS",
        "detail": admit,
    }


def consistency_admit(old: STH, new: STH, new_leaves: list[bytes]) -> dict:
    """跨检查点：旧 head → 新 head 的 consistency。"""
    if not verify_sth_signature(old) or not verify_sth_signature(new):
        return {"consistency": "REJECT", "reason": "bad_signature"}
    if new.tree_size < old.tree_size:
        return {"consistency": "REJECT", "reason": "tree_shrank"}
    if len(new_leaves) != new.tree_size:
        return {"consistency": "REJECT", "reason": "leaf_count_mismatch"}
    if mth(new_leaves) != new.root:
        return {"consistency": "REJECT", "reason": "new_root_mismatch"}
    if old.tree_size > len(new_leaves):
        return {"consistency": "REJECT", "reason": "old_not_prefix_of_presented"}

    prefix_root = mth(new_leaves[: old.tree_size])
    if prefix_root != old.root:
        return {"consistency": "REJECT", "reason": "equivocating_fork"}

    proof = prove_consistency(new_leaves, old.tree_size, new.tree_size)
    ok = verify_consistency(
        old.tree_size, new.tree_size, old.root, new.root, proof
    )
    if not ok:
        return {"consistency": "REJECT", "reason": "consistency_proof_fail"}
    return {"consistency": "PASS", "reason": "consistent_append"}


def pipeline_with_consistency(
    local: dict,
    cons: dict,
) -> dict:
    """本地准入 ∧ consistency；两者都过才算管道绿（再看裁决）。"""
    admitted = local["admit"] == "PASS" and cons["consistency"] == "PASS"
    return {
        **local,
        "consistency": cons,
        "pipeline_admit": admitted,
        "pipeline_green": admitted and local.get("ci_green") is True,
    }


def main() -> None:
    d1 = digest_of_source(V1_SOURCE)
    d2 = digest_of_source(V2_SOURCE)
    d2_alt = digest_of_source(V2_ALT_SOURCE)

    honest_entries = [(V1_VERSION, d1), (V2_VERSION, d2)]
    shrink_fork_entries = [(V1_VERSION, d1)]
    # 同尺寸换根：仍是两条叶、min=2，但第二叶是另一假绿
    same_size_fork_entries = [(V1_VERSION, d1), (V2_VERSION, d2_alt)]

    honest_sth, honest_leaves = make_sth_for(honest_entries, minimum=2)
    shrink_sth, shrink_leaves = make_sth_for(shrink_fork_entries, minimum=1)
    same_sth, same_leaves = make_sth_for(same_size_fork_entries, minimum=2)

    # 共享、假定不可写的持久化槽：此前已接受诚实头
    persisted_sth = honest_sth

    # --- A：仅本地密封底 + inclusion ---
    a_job_a = pipeline_local(
        V2_VERSION, d2, 1, honest_sth, honest_leaves, OBS_FAILING
    )
    a_job_b = pipeline_local(
        V1_VERSION, d1, 0, shrink_sth, shrink_leaves, OBS_FAILING
    )

    # --- B：本地 + 对持久化旧头的 consistency（缩树分叉）---
    b_cons_a = consistency_admit(persisted_sth, honest_sth, honest_leaves)
    b_cons_b = consistency_admit(persisted_sth, shrink_sth, shrink_leaves)
    b_job_a = pipeline_with_consistency(a_job_a, b_cons_a)
    b_job_b = pipeline_with_consistency(a_job_b, b_cons_b)
    b_a_ok = (
        a_job_a["admit"] == "PASS"
        and b_cons_a["consistency"] == "PASS"
        and a_job_a["adjudicate"] == "REJECT"
    )
    b_b_ok = b_cons_b["consistency"] == "REJECT"

    # --- C：诚实 append 负对照 ---
    old_entries = [(V1_VERSION, d1)]
    old_sth, _old_leaves = make_sth_for(old_entries, minimum=1)
    new_sth, new_leaves = make_sth_for(honest_entries, minimum=2)
    c_cons = consistency_admit(old_sth, new_sth, new_leaves)
    c_local = pipeline_local(
        V2_VERSION, d2, 1, new_sth, new_leaves, OBS_FAILING
    )
    c_ok = (
        c_cons["consistency"] == "PASS"
        and c_local["admit"] == "PASS"
        and c_local["adjudicate"] == "REJECT"
    )

    # --- D：同尺寸换根；旧头仍为诚实且不可写 ---
    d_local = pipeline_local(
        V2_VERSION, d2_alt, 1, same_sth, same_leaves, OBS_FAILING
    )
    d_cons = consistency_admit(persisted_sth, same_sth, same_leaves)
    d_pipe = pipeline_with_consistency(d_local, d_cons)
    claim_d = (
        d_local["admit"] == "PASS"  # 单视图仍可本地过
        and d_cons["consistency"] == "REJECT"
        and d_cons["reason"] == "equivocating_fork"
        and same_sth.tree_size == honest_sth.tree_size
        and same_sth.root != honest_sth.root
    )

    # --- E：改写持久化槽 → 与缩树分叉兼容 ---
    rewritten_prior = shrink_sth  # 攻击者写入 fork 兼容旧头
    e_local = pipeline_local(
        V1_VERSION, d1, 0, shrink_sth, shrink_leaves, OBS_FAILING
    )
    e_cons = consistency_admit(rewritten_prior, shrink_sth, shrink_leaves)
    e_pipe = pipeline_with_consistency(e_local, e_cons)
    claim_e = (
        e_cons["consistency"] == "PASS"
        and e_pipe["pipeline_green"] is True
        and e_local["adjudicate"] == "PASS"
    )

    # --- F：每 job 私有旧头、从不跨视图对照 ---
    f_prior_a = honest_sth
    f_prior_b = shrink_sth  # B 从未见过诚实史
    f_local_a = pipeline_local(
        V2_VERSION, d2, 1, honest_sth, honest_leaves, OBS_FAILING
    )
    f_local_b = pipeline_local(
        V1_VERSION, d1, 0, shrink_sth, shrink_leaves, OBS_FAILING
    )
    f_cons_a = consistency_admit(f_prior_a, honest_sth, honest_leaves)
    f_cons_b = consistency_admit(f_prior_b, shrink_sth, shrink_leaves)
    f_pipe_a = pipeline_with_consistency(f_local_a, f_cons_a)
    f_pipe_b = pipeline_with_consistency(f_local_b, f_cons_b)
    # 各自管道准入都过；B 假绿；全局两根不一致且无对照
    claim_f = (
        f_cons_a["consistency"] == "PASS"
        and f_cons_b["consistency"] == "PASS"
        and f_pipe_a["pipeline_admit"] is True
        and f_pipe_b["pipeline_green"] is True
        and f_prior_a.root != f_prior_b.root
    )

    claim_a = (
        a_job_a["admit"] == "PASS"
        and a_job_b["admit"] == "PASS"
        and a_job_b["ci_green"] is True
        and a_job_a["adjudicate"] == "REJECT"
    )
    claim_b = b_a_ok and b_b_ok
    claim_c = c_ok
    support = claim_a and claim_b and claim_c and claim_d and claim_e and claim_f
    verdict = "SUPPORT" if support else "FALSIFY"

    result = {
        "verdict": verdict,
        "thesis": (
            "Local sealed-minimum + inclusion and persisted-prior + consistency "
            "are different predicates; consistency catches shrink and same-size "
            "forks when the prior is honest and unwritable; rewriting that prior "
            "or using only per-job private priors without cross-view compare "
            "re-opens dual-green equivocation — assumption boundary, not a "
            "field security proof"
        ),
        "source": (
            "Peter DEV.to follow-up on Part 10 pin-rollback thread "
            "(equivocation / transparency-log consistency + attack family)"
        ),
        "epistemic_bar": (
            "Synthetic catalog only. Toy HMAC ≠ deployed CT. No prevalence. "
            "Witness/quorum residual untested. Cells D–F map assumptions, "
            "not an exhaustive adversary proof."
        ),
        "observation": OBS_FAILING,
        "persisted_sth": persisted_sth.to_public(),
        "views": {
            "honest": honest_sth.to_public(),
            "shrink_fork": shrink_sth.to_public(),
            "same_size_fork": same_sth.to_public(),
        },
        "claims": {
            "A_local_only_both_jobs_green_on_fork": claim_a,
            "B_consistency_catches_shrink_fork": claim_b,
            "C_honest_append_passes": claim_c,
            "D_same_size_fork_caught_with_honest_prior": claim_d,
            "E_rewritten_prior_reopens_false_green": claim_e,
            "F_private_priors_no_cross_check_dual_green": claim_f,
        },
        "cell_A_local_sealed_and_inclusion": {
            "job_A": a_job_a,
            "job_B": a_job_b,
        },
        "cell_B_plus_consistency_to_persisted": {
            "job_A": b_job_a,
            "job_B": b_job_b,
            "claim_parts": {
                "A_consistent_honest": b_a_ok,
                "B_fork_rejected": b_b_ok,
            },
        },
        "cell_C_honest_append": {
            "old_sth": old_sth.to_public(),
            "new_sth": new_sth.to_public(),
            "consistency": c_cons,
            "select_v2": c_local,
        },
        "cell_D_same_size_root_swap": {
            "local": d_local,
            "consistency": d_cons,
            "pipeline": d_pipe,
        },
        "cell_E_rewritten_persisted_prior": {
            "rewritten_prior": rewritten_prior.to_public(),
            "local": e_local,
            "consistency": e_cons,
            "pipeline": e_pipe,
        },
        "cell_F_private_priors_no_cross_check": {
            "job_A": f_pipe_a,
            "job_B": f_pipe_b,
            "prior_A": f_prior_a.to_public(),
            "prior_B": f_prior_b.to_public(),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("parent-pin-equivocation — sealed floor vs global history + attack family")
    print(f"verdict: {verdict}")
    print(
        f"A local-only: jobA admit={a_job_a['admit']} adj={a_job_a['adjudicate']} "
        f"| jobB admit={a_job_b['admit']} ci_green={a_job_b['ci_green']}"
    )
    print(
        f"B consistency: A={b_cons_a['consistency']} ({b_cons_a['reason']}) "
        f"| B={b_cons_b['consistency']} ({b_cons_b['reason']})"
    )
    print(
        f"C honest append: cons={c_cons['consistency']} "
        f"admit={c_local['admit']} adj={c_local['adjudicate']}"
    )
    print(
        f"D same-size fork: local={d_local['admit']} "
        f"cons={d_cons['consistency']} ({d_cons['reason']})"
    )
    print(
        f"E rewritten prior: cons={e_cons['consistency']} "
        f"pipeline_green={e_pipe['pipeline_green']}"
    )
    print(
        f"F private priors: A_admit={f_pipe_a['pipeline_admit']} "
        f"B_green={f_pipe_b['pipeline_green']}"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
