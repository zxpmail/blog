---
title: "What Agent Memory Should Keep, What It Should Drop — and Why That Is Harder Than It Sounds"
published: false
description: "A bounded design note for agent-memory builders: trust decays, not capacity. Criteria order, promotion/demotion rules, how to set frequencies without fake constants, and a soft toy that only shows stale reuse under stated prompts."
tags: ai, agents, memory, engineering
---

# What Agent Memory Should Keep, What It Should Drop — and Why That Is Harder Than It Sounds

This piece turns an earlier set of principles into an operable mechanism draft, with evidence bounds marked. (Hard flaws in the old draft are listed at the end.)

**Audience:** people building agent memory systems. Basic concepts are not taught here; conclusions carry premises and scope. Non-engineering readers can stop after “It was right when stored, wrong when reused” and “The three layers move.”

Two sentences at the core: the main tension in agent memory is **trust**, not capacity. Garbage is not “useless information”; it is information that gets treated as knowledge on reuse while it is false or stale. The hard part is not taxonomy; it is that memory **rots**.

This is a **design note**, not a benchmark paper. The toy run later only illustrates inertia under stated prompts.

## Nail the words

**Metadata** here is not DB column comments. It is the long-lived rule layer the system trusts by default (system prompt, global handbook, equivalents). Promoting to metadata means entering that layer.

At least four kinds: safety constraints, experience rules, environment defaults, representation structure. The first two are expanded below; the last two are hung on the same pipes in one short block, not spun into separate subsystems.

## It was right when stored, wrong when reused

A Mt. Moon–style failure is enough to show the mechanism: in-session the agent notes “the center is at A”; the map fragment supports it; the entry is promoted to experience and maybe into the handbook; the map changes; the agent still follows the handbook and fails. If “correction” only re-summarizes the old note, the error gets compressed into something that looks like an axiom. Real correction goes back to the raw execution record — what was seen, which observation justified A — then demote, rewrite conditions, or mark “overturned.”

That is the whole spine: session → (with evidence) experience → (with approval) metadata; when the environment moves, you need demotion, expiry, and a path back to raw logs. Classification tables do not stop rot; a state machine might — and only under stated sensors.

## Unconditional rules: constraint vs experience first

“No applicability conditions = half-finished” was overstated. Safety constraints (confirm before irreversible acts; never leak secrets) may be unconditional; their stability comes from design. Experience rules (retry on error; read the file before editing) need conditions, or they over-generalize.

Maintenance splits the same way: constraints are reviewed against whether the design still holds; experience against whether the conditions still cover the field.

## Four criteria: order + exception

When they conflict, a rough order: verifiability → clear conditions → reusability → retrievability.

No evidence: you may store it, only as “unverified,” never as a rule. Cannot write conditions: case library, no auto-apply. Useful only for the current task: session layer. Retrieval cost decides cleanup cadence, not whether storage is allowed.

Exception: high-risk safety constraints should bind before a full experience-verification chain — design admission, not experience admission. The order governs experience promotion; it does not license laundering an emergent habit into a constraint.

## Derived facts: compare derivation cost, no blanket ban

“If it is derivable, do not store” was too absolute. Cheap and stable derivation → compute each time. Expensive or external-state-dependent → may store, must expire. Costly to recompute and easy to get wrong → store as cache, validate on read. Rules are generators; caches are snapshots. A snapshot with no invalidation path is future garbage.

## The three layers move

Session still holds with evidence → experience; current-task only → stay in session and clean. Unverified entries that hold repeatedly with clear conditions → experience rules; falsified → keep as counterexamples. Experience rules into metadata → candidates only, approval required; conditions fail → demote or expire. Safety-constraint metadata moves only with design change, human review, no auto-promotion.

Demotion and expiry are routine, not incident response. Re-summarizing old notes is not correction.

## Frequencies and periods: no universal numbers, a way to set them

“Multiple times,” “periodically,” and “environment changed” leave teams stuck if you only add fields. There is no industry constant here — only a method. You fill the numbers by risk.

**Multiple verifications:** write minimum count `n` and a window into the review condition; ban oral “multiple.” A scaffold default can be “`n ≥ 3` independent tasks and no counterexample” — **3 is a placeholder, not a recommendation**. Raise `n` for high-risk work, or require a human nod.

**Holds across tasks:** tasks need distinct task IDs or scene tags; three clicks in one session do not count as three. Cover at least two scene tags before promotion candidacy.

**Periodic review:** choose period by failure cost. Low-cost experience can sweep by week/sprint; once an experience rule sits in metadata, the period should be shorter than the longest time you will tolerate running with a wrong rule. Review output is only keep / demote / mark expired — never “looked at it.”

**Detecting environment change:** do not fantasize that the model “feels” it. Wire at least one external signal — config version, tool schema hash, permission set, data snapshot id, or a human-declared domain switch. When the signal moves, re-review related entries. No signal source means you cannot auto-demote; you can only shorten periodic review.

Expiry is the same idea: caches follow the refresh rhythm of external state; for experience rules, expiry means “latest time a re-review is mandatory,” not “becomes truth on a timer.”

## Metadata: shape, who approves; hanging the other two types

Entries in the metadata layer need at least: content, type, basis, review conditions (including expiry/signals).

Who approves: safety constraints — design changes only, human review. Experience rules — the agent may propose with an evidence chain; human or independent review approves; no auto-promotion.

Environment defaults (default timezone, default cluster): same conditions, evidence, and approval as experience rules; they drift with deploys more easily than safety constraints, so review conditions must attach config/environment signals. Representation structure (directory conventions, ID formats, note templates): treat as design artifacts by default, change via design review; if they emerge from use and then harden, treat them first as experience-rule candidates and only write them into metadata after approval. Both types share the experience-rule approval pipe; they differ mainly in which review signals they bind.

Say the degradation path up front: if you cannot detect environment change, “failure cost” is often unestimable too, and the demotion branch collapses to “a human looks periodically.” That is not a failed design; it is a missing premise. In that case the state machine does not give automatic trust — only a record shape and an entry point for manual checks. Do not mistake “we have a state machine” for “we are automatically trustworthy.”

## Intake screen

Walk the criteria order above; do not invent a second logic:

Still useful next session? No → do not promote. Evidence? No → unverified. Constraint or experience? Constraint → human review. Conditions written? Cannot → case library. Derivable? Yes → compare cost before caching. How many tasks? Once → not into the rule layer; at your written `n` → evidence chain into approval. The agent reports counts; it need not self-label “emergent pattern.”

## Close

Long-lived memory needs at least three things: structured entries; promotion with approval and demotion/expiry as routine; a correction path back to raw records.

Worth keeping: safely reusable generative rules, conditioned verified experience, caches with invalidation. Worth dropping: one-shot context, unverified guesses, unbounded experience, derived snapshots with no expiry.

The engineering problem is not growing the store. It is keeping memory trustworthy through promotion, demotion, expiry, and correction.

**Discount (read with the body):** This is a bounded mechanism draft, not a production evaluation. The toy only shows that old memory can be reused sluggishly; it does **not** show that a state machine prevents the failure. N=5, one model, no statistical transfer. Frequencies have a method, not universal constants; `n=3` in the text is scaffold filler. If signal sources are missing, automatic demotion is unavailable — confirm that before you trust the scheme. A real “right when stored, wrong when reused” incident report is worth more than another architecture diagram.

---

Old-draft hard flaws (memo): criteria in parallel fought each other; three layers looked like static rooms; “if derivable, do not store” was absolute; one intake step was not executable.

Footnote — toy: [`stale-memory-reuse-test.py`](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/stale-memory-reuse-test.py) ([results JSON](https://github.com/zxpmail/blog/blob/main/agent-determinism-illusions/scripts/results-v2/stale-memory-reuse_glm-5.3-flash.json)). Center A→B, observation visible; handbook pinned to A with no expiry. Control arm post-jump accuracy 1.0. `glm-5.3-flash`, N=5, “prefer memory” prompt: never_adapted_rate=0.4, median lag 3 rounds among adapters, mean post-jump accuracy 0.125. Strength stops at “illustratively measurable.”
