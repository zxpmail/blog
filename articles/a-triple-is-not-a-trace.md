---
title: A Triple Is Not a Trace
published: false
tags: architecture, ontology, software
---

# A Triple Is Not a Trace

Two camps keep missing each other. One treats an event as a real modeling object: you do not rewrite it, a process still in progress is not the finished event, and a status field is only a projection. The other looks at the stack those words usually drag in. OWL is expensive to run, SPARQL is a poor daily tool, and a triple store is a narrow piece of infrastructure. What a team can actually keep is the model in the code.

Both are pointing at the same gap. A triple is the smallest thing you can store. It is not yet something you can trace.

`(AS-12, overheated, 2026-10-20)` is an assertion. You can store a hundred more in the same shape and still have a pile. Three questions turn the pile into a trace.

1. **Is this edge legal?** What may connect to what, and which way does the arrow point?
2. **When does a legal edge count?** The moment the event happened and the moment the edge was written are different clocks. "What was in the set at time T" uses the write. The system stamps that write. The caller does not.
3. **Which list is in force?** A new kind of part, or a second work order, is a version choice. It is not a quiet extra edge.

Skip any one of these and you can still store triples. What you lose is the ability to run the same trace twice and get the same answer.

## One work order, three cuts

Device AS-12 overheats. Someone files a repair, a job is dispatched, a technician does the work, the order is closed. The bare triple becomes an event, OV-1, not a word painted on the device. OV-1 brings a situation, "awaiting a report." The rest of the chain follows: report, dispatch, repair, close. The work order and the technician are objects that stay. The overheating and the repair are things that happen.

**A device is not a part of the repair.** That edge is illegal. If you allow `AS-12 part-of FIX-9`, the question "what is this repair made of?" returns a machine. The legal parts, if you care about them, are the steps: diagnose, replace, retest. They hang on the repair event. They are not parts of each other, and the device enters the story by taking part in the event, not by being a piece of it. This check belongs in the first tier. It is a rule in the write path.

**A wrong record does not rewrite the repair.** Suppose the original record left out the retest. You do not open FIX-9 and edit it. You append a correction that argues with that one fact. The repair event stays the same individual. Later corrections argue with the same fact; the later one, when neither record is the parent of the other, wins. Before you compare them, drop every correction that had not been written yet. If you compare first and drop second, a correction from the future changes the winner, and deleting it afterward does not put the old winner back. This is the second tier. You do not need it until a stored fact can be wrong.

**A mistaken close is a new event, not a deleted one.** CL-1 happened. Leaving it in place is the point. Undo it with another event, `UNCL-1 → CL-1`, and a new situation node whose type is "awaiting acceptance" again. Do not reuse the old node. If a further event `UNCL-2 → UNCL-1` brings a new node of type "closed," the close is in effect again, and both compensation links are still there. CL-1's direct compensation is still UNCL-1, not UNCL-2. The current stage is whatever that latest node says. This is the full tier. Build it when undoing a business effect matters. Do not build it so you can reject `AS-12 part-of FIX-9`.

A second work order can share the dispatch and still have its own stage. The small tier does not answer that. The second tier does, by keeping each order's situation chain separate. The status column on the work order may still say "in progress" after the chain says "closed." The column is a projection. When they disagree, the chain is the answer.

## Three tiers, because the full stack is how you reinvent OWL

The engineering objection is fair. If every team has to keep kind catalogs, correction locks, two clocks, and a closed query language, the maintenance bill can exceed the stack this was supposed to replace. One ordering rule — drop late records, then compare — is already easy to write backwards. So the full procedure is not the entry price.

| Tier | What you maintain | What you can answer | What you do not claim |
|---|---|---|---|
| Small | Endpoint checks. Nothing is a part of itself. Events are appended, not edited. One work order. Count events of a type directly. | What happened on this order. How many times it overheated. | A corrected parts list. A second order's stage. |
| Second | Corrections that name the fact they dispute. Drop records that were not written yet, then pick the winner. A second order gets its own chain. | Whether the retest is part of the repair after the correction. Each order's current stage. | Compensation. Counts that include subtypes. A catalog of part kinds. |
| Full | Part kinds, with a default rule instead of a handwritten pair list. Compensation as its own link. A closed set of query shapes, so the next question cannot invent a new query language. | A close that was undone, without deleting the close. | That you needed this tier for the rows above. |

Path existence stays proportional to the number of edges at every tier. Listing every path is the expensive query. The table above is the cost of keeping the rules, which is the cost that matters.

The small tier fits in one module two people can read. There is no reasoner. The second tier adds one piece of code and a test that the order of operations is the right one. The full tier costs review, whenever a new part kind or a new query shape is allowed in. It does not cost a reasoner on every read.

Stop at the tier that answers the question you have. A standards body can adopt the second tier and leave the rest. That is a smaller decision than swallowing a whole ontology.

## Where this sits

OCEL already gives you objects, events, and participation. PROV already points a record at the record it came from. EPCIS dispositions are close to the type of a situation, and they are not the node on the chain. Event sourcing already refuses to rewrite what was stored. It usually still uses one kind of appended message for both "the record was wrong" and "the business effect must be undone." Those are different messages. The split is the whole integration.

SNOMED CT, FHIR, FIBO, OPC UA, EPCIS: each one grew up to carry a slice, under real pressure to interoperate. None of them is a single picture of objects, events, situations, and participation. This is the same shape. The three questions are a check an implementation can adopt beside those interfaces. They do not replace the interfaces.

A trace is not a denser pile of triples. It is the same pile after the three questions have answers, at a tier the team will still be maintaining next year. The checklist, the lock, and the test that fails if you compare corrections before you drop late records stay next to the code. They do not belong in this post.
