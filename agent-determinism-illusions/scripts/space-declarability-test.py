#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Space Declarability Experiment — the honest boundary of key-space C3.

QUESTION:
  Key-space C3 requires the key space to be declarable. When it's not,
  C3 falls back to single-key verification — and the gap from Part 14
  reopens. How large is that "undeclarable" class in real requirements?

EXPERIMENT:
  A corpus of requirements from cache invalidation, authorization, and
  write-path domains. Each requirement is classified along two axes:

  Axis 1 — Human ground truth:
    Can a human read this requirement and declare a concrete key space?
    Classes: declarable, partial, undeclarable, out-of-scope

  Axis 2 — Automated classifier:
    Can a set of deterministic rules (pattern matching, keyword heuristics)
    produce the same classification without human judgment?

MEASUREMENTS:
  - Undeclarable rate: what % of requirements resist key-space declaration?
  - False undeclarable rate: automated classifier says undeclarable/partial
    but human says declarable
  - False declarable rate: automated classifier says declarable but human
    says undeclarable/partial
  - Cohen's kappa (or simple agreement) between human and automated
  - Breakdown by domain: cache vs auth vs write-path

  Also measures: for "partial" cases, what additional information would
  be needed to make the space declarable?

USAGE:
  python space-declarability-test.py            # run classification
  python space-declarability-test.py --save     # + save JSON

PURE DETERMINISTIC — zero API cost.
"""

import sys, io, json, argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results-v2"


# ============================================================
# Classification labels
# ============================================================

# Human ground truth
DECLARABLE = "declarable"          # key space can be unambiguously declared
PARTIAL = "partial"                # partially declarable, needs human judgment
UNDECLARABLE = "undeclarable"      # cannot declare a key space
OUT_OF_SCOPE = "out-of-scope"      # not in C3's domain (UX, ops, etc.)


# ============================================================
# Requirement corpus
# ============================================================

@dataclass
class Requirement:
    id: str
    text: str
    domain: str                         # cache / auth / write-path / mixed
    human_class: str                    # ground truth
    reason: str                         # why this classification
    possible_space: Optional[str] = None  # if declarable, what space?
    needed_for_resolution: Optional[str] = None  # if partial, what's missing?


CORPUS = [
    # ── Cache invalidation ──
    Requirement("C1", "invalidate cache entry when its key is written",
                "cache", DECLARABLE, "explicit key reference",
                possible_space="{written_key}"),
    Requirement("C2", "invalidate all cache entries with prefix user:*",
                "cache", DECLARABLE, "explicit prefix pattern",
                possible_space="user:*"),
    Requirement("C3", "invalidate the relevant cache entry when user data changes",
                "cache", PARTIAL, "'relevant' is ambiguous — known prefix, unknown scope",
                possible_space="user:*", needed_for_resolution="does 'relevant' mean all user:* or just the written key?"),
    Requirement("C4", "clear stale cache entries before writing new data",
                "cache", PARTIAL, "'stale' is ambiguous — could mean all, could mean specific",
                possible_space="{written_key}", needed_for_resolution="does 'stale' refer to the written key only, or all expired entries?"),
    Requirement("C5", "on password change, invalidate the user's security token",
                "cache", DECLARABLE, "explicit entity (token) with user reference",
                possible_space="token:*"),
    Requirement("C6", "when permissions change, invalidate all active sessions",
                "cache", DECLARABLE, "explicit entity (sessions) with 'all' quantifier",
                possible_space="session:*"),
    Requirement("C7", "invalidate cache if write affects the user's active session",
                "cache", DECLARABLE, "explicit entity (session) with user reference",
                possible_space="session:*"),
    Requirement("C8", "when updating user profile, invalidate all related entries",
                "cache", PARTIAL, "'related' is open-ended — could mean profile, user, or both",
                possible_space="user:*,profile:*", needed_for_resolution="does 'related' include profile:* in addition to user:*?"),
    Requirement("C9", "ensure cached data is eventually consistent with the source of truth",
                "cache", UNDECLARABLE, "'eventually consistent' is a timing property, not a key space"),
    Requirement("C10", "TTL-based expiry: keys auto-expire after 5 minutes",
                "cache", UNDECLARABLE, "TTL is time-based invalidation, not write-path — no key to invalidate on write"),
    Requirement("C11", "invalidate all entries in the cache",
                "cache", DECLARABLE, "explicit 'all' quantifier",
                possible_space="*"),
    Requirement("C12", "invalidate entries modified by a transaction",
                "cache", PARTIAL, "'modified by a transaction' is traceable if tx writes are logged",
                possible_space="tx_writes:{tx_id}", needed_for_resolution="are transaction write-sets tracked and queryable?"),
    Requirement("C13", "purgeCacheOnWrite: purge entire cache partition on any write",
                "cache", DECLARABLE, "explicit operation name with known scope",
                possible_space="partition:*"),
    Requirement("C14", "invalidate keys matching a glob pattern",
                "cache", DECLARABLE, "explicit glob pattern (pattern can be declared at runtime)",
                possible_space="{declared_pattern}"),

    # ── Authorization ──
    Requirement("A1", "invalidate role-based permissions when a user's role changes",
                "auth", DECLARABLE, "explicit entity (role) with user reference",
                possible_space="roles:{user_id}"),
    Requirement("A2", "invalidate all tokens issued before a password change",
                "auth", DECLARABLE, "explicit entity (tokens) with temporal condition",
                possible_space="tokens:{user_id}"),
    Requirement("A3", "invalidate cached decisions derived from user role assignment",
                "auth", PARTIAL, "'decisions derived from role' is traceable if dependency graph exists",
                possible_space="decision:*", needed_for_resolution="are role-dependency traces maintained?"),
    Requirement("A4", "clear authorization cache when a permission is revoked",
                "auth", DECLARABLE, "explicit entity (permission) with clear scope",
                possible_space="perm:{permission_id}"),
    Requirement("A5", "invalidate cached policies when the policy document changes",
                "auth", DECLARABLE, "explicit entity (policy) with version reference",
                possible_space="policy:{policy_id}"),
    Requirement("A6", "ensure access decisions reflect the latest organizational hierarchy",
                "auth", UNDECLARABLE, "'latest hierarchy' is a freshness property, not a key space"),
    Requirement("A7", "invalidate all sessions for a user on logout",
                "auth", DECLARABLE, "explicit entity (sessions) with user reference",
                possible_space="session:{user_id}"),

    # ── Write-path ──
    Requirement("W1", "update the materialized view when the underlying table changes",
                "write-path", DECLARABLE, "explicit entity (materialized view) with table reference",
                possible_space="mv:{table_name}"),
    Requirement("W2", "recompute derived fields when source data is updated",
                "write-path", DECLARABLE, "explicit entity (derived fields) with source reference",
                possible_space="derived:{source_id}"),
    Requirement("W3", "propagate cache invalidation to downstream consumers",
                "write-path", PARTIAL, "'downstream consumers' is traceable if subscription graph exists",
                possible_space="downstream:{source_id}", needed_for_resolution="are consumer subscriptions tracked as a dependency graph?"),
    Requirement("W4", "reindex search when documents are added or modified",
                "write-path", DECLARABLE, "explicit entity (search index) with document reference",
                possible_space="index:{doc_type}"),
    Requirement("W5", "synchronize cache state across all nodes in the cluster",
                "write-path", UNDECLARABLE, "'synchronize across all nodes' is a distribution property, not a local key space"),
    Requirement("W6", "on cascade delete, invalidate all dependent records",
                "write-path", DECLARABLE, "'cascade delete' has known referents via foreign key graph",
                possible_space="dependent:{record_id}"),
    Requirement("W7", "archive completed orders and remove from active cache",
                "write-path", DECLARABLE, "explicit entity (orders) with state filter",
                possible_space="order:completed:*"),

    # ── Edge / mixed ──
    Requirement("E1", "invalidate the relevant cache entry",
                "mixed", PARTIAL, "pure qualification, no named referent",
                possible_space="N/A — requires intent inference",
                needed_for_resolution="what is 'relevant' defined by? (user? session? transaction?)"),
    Requirement("E2", "ensure data integrity across cache and database",
                "mixed", OUT_OF_SCOPE, "data integrity is a consistency property, not invalidation"),
    Requirement("E3", "system should gracefully handle cache misses",
                "mixed", OUT_OF_SCOPE, "UX/robustness property, not a C3-detectable claim"),
    Requirement("E4", "UI should feel responsive to user interactions",
                "mixed", OUT_OF_SCOPE, "UX property — outside C3's domain entirely"),
    Requirement("E5", "ensure cached queries reflect the latest database state",
                "mixed", UNDECLARABLE, "'latest database state' is a freshness property, not a key space"),
    Requirement("E6", "on configuration change, invalidate all cached values that depend on that config",
                "mixed", DECLARABLE, "config dependency is traceable if dependency graph exists",
                possible_space="config_dep:{config_key}"),
    Requirement("E7", "invalidate all entries belonging to a tenant on tenant deactivation",
                "mixed", DECLARABLE, "explicit entity (tenant) with clear scope",
                possible_space="tenant:{tenant_id}"),
]


# ============================================================
# Automated classifier (deterministic rules)
# ============================================================

def auto_classify(text: str, domain: str) -> dict:
    """Classify a requirement using deterministic rules.
    Returns {class, possible_space, needed_for_resolution, confidence}."""

    text_lower = text.lower()

    # Rule 1: explicit key/pattern reference
    if any(p in text_lower for p in [":*", "key:", "key ", "prefix ", "pattern "]):
        return {"class": DECLARABLE, "confidence": "high",
                "note": "explicit key/pattern reference"}

    # Rule 2: explicit quantifier "all" + named entity
    if "all " in text_lower and any(e in text_lower for e in
            ["entries", "tokens", "sessions", "keys", "records", "cached", "index", "policies"]):
        return {"class": DECLARABLE, "confidence": "high",
                "note": "explicit 'all' + named entity"}

    # Rule 3: single key reference (cache[k], specific id)
    if any(p in text_lower for p in ["its key", "specific key", "written key", "that key"]):
        return {"class": DECLARABLE, "confidence": "high",
                "note": "self-referential key reference"}

    # Rule 4: named entity with owner reference
    if any(p in text_lower for p in ["user's", "for a user", "for this user", "by user",
                                       "belonging to", "for all"]):
        if any(e in text_lower for e in ["session", "token", "role", "permission", "record",
                                           "decision", "entry"]):
            return {"class": DECLARABLE, "confidence": "medium",
                    "note": "named entity with owner reference"}
        return {"class": PARTIAL, "confidence": "low",
                "note": "owner reference but entity type is ambiguous"}

    # Rule 5: dependency-traceable
    if any(p in text_lower for p in ["derived from", "depends on", "underlying",
                                       "dependent", "cascade", "downstream", "source of"]):
        return {"class": PARTIAL, "confidence": "medium",
                "note": "traceable if dependency graph exists"}

    # Rule 6: UX/ops/quality properties
    if any(p in text_lower for p in ["should feel", "gracefully", "responsiveness",
                                       "user experience", "feel responsive"]):
        return {"class": OUT_OF_SCOPE, "confidence": "high",
                "note": "UX/quality property — outside C3 domain"}

    # Rule 7: temporal/freshness properties
    if any(p in text_lower for p in ["eventually", "latest", "consistent",
                                       "after 5", "ttl", "expire"]):
        return {"class": UNDECLARABLE, "confidence": "medium",
                "note": "temporal/freshness property — not a write-path key space"}

    # Rule 8: ambiguous qualifiers
    if any(p in text_lower for p in ["relevant", "related", "associated",
                                       "stale", "appropriate"]):
        return {"class": PARTIAL, "confidence": "low",
                "note": "ambiguous qualifier — needs human resolution"}

    # Rule 9: unclassified — default to partial
    return {"class": PARTIAL, "confidence": "low",
            "note": "no rule matched — requires human judgment"}


# ============================================================
# Agreement calculation
# ============================================================

def agreement(human: str, auto: str) -> str:
    """Classify agreement between human and automated classification."""
    if human == auto:
        return "agree"
    if auto == PARTIAL and human == DECLARABLE:
        return "false_partial"  # auto said partial, human says declarable
    if auto == DECLARABLE and human == PARTIAL:
        return "false_declarable"
    if auto in (UNDECLARABLE, OUT_OF_SCOPE) and human == DECLARABLE:
        return "false_undeclarable"  # auto said can't, human says can — the critical miss
    if auto == DECLARABLE and human in (UNDECLARABLE, OUT_OF_SCOPE):
        return "false_declarable_overreach"
    if auto == PARTIAL and human == UNDECLARABLE:
        return "partial_too_optimistic"
    if auto == UNDECLARABLE and human == OUT_OF_SCOPE:
        return "scope_mismatch"
    return f"{auto}_vs_{human}"


# ============================================================
# Main
# ============================================================

def run():
    parser = argparse.ArgumentParser(description="Space declarability experiment")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("Space Declarability Experiment")
    print("Measuring how much of the 'undeclarable' class is real vs. resolvable")
    print("=" * 72)
    print()
    print(f"Corpus: {len(CORPUS)} requirements")
    print(f"Domains: cache ({sum(1 for r in CORPUS if r.domain=='cache')}), "
          f"auth ({sum(1 for r in CORPUS if r.domain=='auth')}), "
          f"write-path ({sum(1 for r in CORPUS if r.domain=='write-path')}), "
          f"mixed/edge ({sum(1 for r in CORPUS if r.domain=='mixed')})")
    print()

    # Classification
    results = []
    agreement_counts = {}
    class_counts_human = {}
    class_counts_auto = {}

    for req in CORPUS:
        auto = auto_classify(req.text, req.domain)
        agree = agreement(req.human_class, auto["class"])

        results.append({
            "id": req.id,
            "domain": req.domain,
            "text": req.text,
            "human_class": req.human_class,
            "auto_class": auto["class"],
            "auto_confidence": auto["confidence"],
            "auto_note": auto["note"],
            "agreement": agree,
            "possible_space": req.possible_space,
            "needed_for_resolution": req.needed_for_resolution,
        })

        agreement_counts[agree] = agreement_counts.get(agree, 0) + 1
        class_counts_human[req.human_class] = class_counts_human.get(req.human_class, 0) + 1
        class_counts_auto[auto["class"]] = class_counts_auto.get(auto["class"], 0) + 1

    # ── Print results ──
    print("── Per-requirement classification ──")
    print(f"{'ID':<6} {'Domain':<12} {'Human':<16} {'Auto':<16} {'Agreement':<22} Text")
    print("-" * 100)
    for r in results:
        # Truncate text to 50 chars
        text_short = r["text"][:50] + ("..." if len(r["text"]) > 50 else "")
        print(f"{r['id']:<6} {r['domain']:<12} {r['human_class']:<16} "
              f"{r['auto_class']:<16} {r['agreement']:<22} {text_short}")

    # ── Summary ──
    print()
    print("── Human classification distribution ──")
    for cls in [DECLARABLE, PARTIAL, UNDECLARABLE, OUT_OF_SCOPE]:
        count = class_counts_human.get(cls, 0)
        pct = count / len(CORPUS) * 100
        print(f"  {cls:<16}: {count:>2}/{len(CORPUS)} ({pct:.0f}%)")

    print()
    print("── Automated classifier distribution ──")
    for cls in [DECLARABLE, PARTIAL, UNDECLARABLE, OUT_OF_SCOPE]:
        count = class_counts_auto.get(cls, 0)
        pct = count / len(CORPUS) * 100
        print(f"  {cls:<16}: {count:>2}/{len(CORPUS)} ({pct:.0f}%)")

    print()
    print("── Agreement matrix ──")
    total_agree = sum(v for k, v in agreement_counts.items() if k == "agree")
    print(f"  Exact agreement: {total_agree}/{len(CORPUS)} ({total_agree/len(CORPUS)*100:.0f}%)")
    print()

    # Key metrics
    false_undeclarable = agreement_counts.get("false_undeclarable", 0)
    false_declarable = agreement_counts.get("false_declarable", 0)
    false_partial = agreement_counts.get("false_partial", 0)
    false_overreach = agreement_counts.get("false_declarable_overreach", 0)

    print("── Critical metrics ──")
    print(f"  False undeclarable (auto says can't, human says can): {false_undeclarable}")
    print(f"  False declarable (auto says can, human says partial): {false_declarable}")
    print(f"  False partial (auto says partial, human says declarable): {false_partial}")
    print(f"  False declarable overreach (auto says can, human says can't/OOS): {false_overreach}")
    print()

    # Domain breakdown
    print("── Domain breakdown ──")
    for domain in ["cache", "auth", "write-path", "mixed"]:
        domain_reqs = [r for r in results if r["domain"] == domain]
        declarable_count = sum(1 for r in domain_reqs if r["human_class"] == DECLARABLE)
        partial_count = sum(1 for r in domain_reqs if r["human_class"] == PARTIAL)
        undeclarable_count = sum(1 for r in domain_reqs if r["human_class"] in (UNDECLARABLE, OUT_OF_SCOPE))
        print(f"  {domain}: {len(domain_reqs)} reqs — "
              f"declarable={declarable_count} partial={partial_count} undeclarable/out={undeclarable_count}")

    # Honest boundary
    print()
    print("=" * 72)
    print("HONEST BOUNDARY")
    print("=" * 72)
    print()
    human_undeclarable = class_counts_human.get(UNDECLARABLE, 0) + class_counts_human.get(OUT_OF_SCOPE, 0)
    human_declarable = class_counts_human.get(DECLARABLE, 0)
    human_partial = class_counts_human.get(PARTIAL, 0)
    print(f"  By human ground truth:")
    print(f"    Declarable: {human_declarable}/{len(CORPUS)} "
          f"({human_declarable/len(CORPUS)*100:.0f}%)")
    print(f"    Partial (needs human resolution): {human_partial}/{len(CORPUS)} "
          f"({human_partial/len(CORPUS)*100:.0f}%)")
    print(f"    Undeclarable + out-of-scope: {human_undeclarable}/{len(CORPUS)} "
          f"({human_undeclarable/len(CORPUS)*100:.0f}%)")
    print()
    print(f"  The undeclarable class ({human_undeclarable} cases) breaks down into:")
    for r in results:
        if r["human_class"] in (UNDECLARABLE, OUT_OF_SCOPE):
            print(f"    - [{r['id']}] {r['text'][:60]} → {r['reason'] if 'reason' in r else ''}")
            print(f"      {getattr([x for x in CORPUS if x.id==r['id']][0], 'reason', '')}")
    print()
    print("  Partial cases ({human_partial}) break down into:")
    partials_needing_trace = 0
    partials_needing_intent = 0
    for r in results:
        if r["human_class"] == PARTIAL:
            needed = r.get("needed_for_resolution", "")
            if "trace" in needed.lower() or "graph" in needed.lower() or "track" in needed.lower():
                partials_needing_trace += 1
            else:
                partials_needing_intent += 1
            print(f"    - [{r['id']}] {r['text'][:60]}")
            print(f"      needs: {needed}")
    print()
    print(f"  Of the {human_partial} partial cases:")
    print(f"    - {partials_needing_trace} need a dependency trace (potentially resolvable)")
    print(f"    - {partials_needing_intent} need intent inference (human judgment)")

    # ── Save ──
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / "space-declarability.json"

        # Build machine-readable summary
        human_undeclarable_list = [r for r in results if r["human_class"] in (UNDECLARABLE, OUT_OF_SCOPE)]
        partial_list = [r for r in results if r["human_class"] == PARTIAL]
        partial_resolvable = sum(1 for r in partial_list
                                 if any(w in (r.get("needed_for_resolution") or "").lower()
                                        for w in ["trace", "graph", "track"]))

        summary = {
            "experiment": "space-declarability-test",
            "design": {
                "claim": "The undeclarable class of key-space C3 is small and mostly resolvable via dependency tracing",
                "method": f"{len(CORPUS)} requirements × human ground truth × automated classifier",
                "domains": ["cache", "auth", "write-path", "mixed"],
            },
            "corpus_size": len(CORPUS),
            "human_distribution": class_counts_human,
            "auto_distribution": class_counts_auto,
            "agreement": agreement_counts,
            "exact_agreement_rate": total_agree / len(CORPUS),
            "critical_metrics": {
                "false_undeclarable": false_undeclarable,
                "false_declarable": false_declarable,
                "false_partial": false_partial,
                "false_overreach": false_overreach,
            },
            "declarable_rate": human_declarable / len(CORPUS),
            "undeclarable_rate": human_undeclarable / len(CORPUS),
            "partial_rate": human_partial / len(CORPUS),
            "partial_resolvable_via_trace": partial_resolvable,
            "partial_needing_judgment": human_partial - partial_resolvable,
            "human_undeclarable_cases": [
                {"id": r["id"], "text": r["text"], "class": r["human_class"]}
                for r in human_undeclarable_list
            ],
            "all_results": results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Saved: {path}")


if __name__ == "__main__":
    run()
