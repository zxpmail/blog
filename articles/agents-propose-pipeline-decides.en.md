---
title: "Before You Let AI Build Enterprise Systems, Build the Approval Pipeline First"
published: false
description: "DAF (Domain Application Foundation) is an enterprise 'business-system factory': systems as versioned declarative blueprints, agents that propose assemblies, and a guard pipeline that decides. Design assumptions plus one end-to-end drill — not production validation. Every mechanism's evidence status and every step's cost is laid out."
tags: ai, architecture, agents, lowcode
---

# Before You Let AI Build Enterprise Systems, Build the Approval Pipeline First

— for organizations committed to continuously producing many kinds of business systems

We are building DAF (Domain Application Foundation) — an enterprise "business-system factory". This article lays out its core judgment: a business system should not be an application that gets developed; it should be a declarative blueprint — versionable, approvable, rollback-able. An agent may assemble blueprints, but only through a pipeline with a human at the gate.

The article does not stop at design. It also lays out the cost of every step.

What this piece is: design assumptions + a retrospective of one end-to-end drill, not production-validated conclusions. What has tests and what is still only a direction is marked section by section, with an evidence-status table at the end of section three.

## 1. An old problem

Anyone who has done enterprise IT has seen this loop:

A business team wants a new system (ticketing, inventory, project management…). The tech team builds one from scratch: login, permissions, org chart, menus, CRUD, reports, a workflow engine… Three months later it ships; the second request arrives; another build. Five years on, the company runs 30 systems, 30 user tables, 30 permission models, and nobody dares touch any of them.

Commercial low-code platforms try to solve this, but most build "fast" on a "black box": the model doesn't migrate, permissions aren't customizable, you're welded to the platform. Meanwhile, the rise of agents/LLMs makes "AI builds your system" plausible — but picture an agent executing what it "assembled" directly against the production database, and you can see what an enterprise actually needs: a foundation that an AI can assemble and a human can govern.

DAF's answer: abstract the generic capability needed to build a class of business systems into a component-based, composable foundation; business system = foundation + one declarative blueprint.

Here is what such a blueprint looks like. This is a real, existing sample ticketing blueprint (written against the daf.blueprint.v1 schema, used for pipeline-validation tests):

```json
{
  "apiVersion": "daf.blueprint.v1",
  "name": "ticket-intake",
  "version": "1.0.0",
  "entry": "/tickets/new",
  "entities": [{
    "apiVersion": "daf.entity.v1",
    "type": "ticket",
    "tenantIsolation": "row",
    "auditFields": true,
    "fields": [
      { "name": "title", "type": "string", "len": 200, "required": true },
      { "name": "status", "type": "enum", "enumValues": ["open", "done"], "required": true }
    ]
  }],
  "pages": [{
    "apiVersion": "daf.page.v1",
    "route": "/tickets/new",
    "layout": "form",
    "blocks": [{ "block": "form", "data": { "kind": "entity", "ref": "ticket" } }]
  }],
  "flows": [{ "key": "intake", "definitionRef": "sha256:demo" }]
}
```

Data model, pages, and flows in one file — signable, versionable, rollback-able. The complete definition of a minimal ticketing system, in under 40 lines.

**How far those 40 lines go — the blunt truth first**: they cover the routine cases that look alike — forms, lists, approval flows. By our internal review of historical demand, such cases are the majority; but that is an estimate, not a statistic. The rest — the ones that look different: billing rules, cross-system reconciliation, odd approval special cases — eventually fall back into controlled code slots.

**The slot is the most likely place this whole approach dies, so it gets its own paragraph**: what historically decides whether platforms like this live or die is rarely the elegance of the blueprint declarations; it is the debug, test, and versioning experience after a user hits the slot wall. Today the mechanism is one line: slot versioning rides with the blueprint; supply-chain verification (source signatures, dependency audits) is still a direction, not a mechanism. Our hedge is honest too: we mark it the top risk item and hand it to the first real project to hammer out. Whether the slot experience works is decided by that project, not by this document.

## 2. The architecture: one kernel + three planes

```text
Assembly plane: assembly workbench (manual) + semantic registry (agent-facing) + assembly pipeline
    ↓ publish/rollback (immutable artifacts)
Artifact plane: blueprints · semantic cards · templates · entity schemas — everything is an artifact, everything versioned
    ↓ instantiate/load
Runtime plane: gateway + core services + data services + frontend shell, self-contained infrastructure
```

(One term pinned down: a **semantic card** is a versioned artifact that captures a business concept — a field's precise definition, a metric's definition, a term — in a form an agent can retrieve by semantics; pages and flows use it by reference instead of each carrying a copy of the definition.)

The assembly plane is the soul. A blueprint moves from draft to production through a controlled pipeline:

```text
draft → static-validate → guard (policy/security railings)
      → preview (sandbox) → approve → publish → rollback-able
```

An agent may propose an assembly plan; whether it passes is decided by the guard. Take a real rule as the example: when a blueprint diff deletes an entity, deletes a field, or changes a type or width (the criterion is stock-data compatibility: string→int, shortening a length, or removing an enum value can invalidate existing data, so they count as tightening; int→string cannot, so it counts as loosening), the guard walks the reference graph and produces an impact report — which page binds this field, which flow, which semantic card — and then vetoes: the pipeline halts, HTTP 403, findings returned in full. Guard policies are configurable per tenant, but only toward stricter, never looser; if the rule engine itself throws, that counts as block too — fail closed. Rollback re-runs the same destructive checks; in-flight process instances stay pinned to the version they started on.

One sentence for this section: **agents propose; the pipeline holds the line.** "AI builds systems" without this pipeline, in enterprise environments that need audit and accountability, most likely stops at the demo stage.

Known boundaries of these mechanisms, stated up front:

- **The guard's policy expressiveness is limited** (five rule groups); complex business red lines still bottom out at L3 human review.
- **Appeals and overrides for false kills**: findings are retained in full, and the same rule's verdicts across runs can be compared; changes to destructive-class policies themselves require dual confirmation. There is a granularity gap — today's override mechanism is "change the policy", which operates at policy granularity, not per change; an exception-approval channel that registers an exception for a single change (time-boxed, on the record) does not exist yet.
- **Approval SLA is undefined** (an honest blank); tenant-side process discipline covers it for now. The pipeline guarantees sign-off semantics and the audit trail only; SLA is a runtime metric still to be added.
- **One unsolved problem we don't intend to pretend to solve — the rollback × forward-data interlock**: suppose v2 adds an enum value to an entity, existing data uses it, and then v2 turns out to have a fatal flaw and must roll back — from v1's blueprint, "remove this enum value" is exactly the tightening change the guard exists to block. That is, the moment you most need to roll back is the moment the guard is most likely to stop you. A rollback-able blueprint is not rollback-able data; the industry pattern here is expand-contract (expand first, never contract in the same step; data cleanup front-loaded). In what form it enters the guard's release path — there is no settled design yet.
- **Blueprint reuse** is template instantiation + upgrade-diff replay; there is no full blueprint inheritance hierarchy — this is deliberate (inheritance hierarchies are one of the main paths by which low-code platforms turn into black boxes). The cost: extracting cross-blueprint commonality is manual work.

Blunt words before anything else — who this fits and who it doesn't:

| Fits | Does not fit |
|------|--------|
| Organizations committed to continuously producing many kinds of business systems | Teams building only one or two systems (use a scaffold) |
| Has platform-ops capability (can run a mid-sized microservice cluster) | No platform team, wants to outsource all operations |
| Strong governance needs: audit, compliance, MLPS, multi-party approval | Demos, PoCs, fastest-possible-output scenarios |

Two execution-layer designs worth naming:

**Permissions are compiled into the execution plan**: row-level permissions are injected at query-compile time (the Hasura pattern) + PostgreSQL RLS as a second lock — no post-hoc filtering of result sets. This serves one plain goal: an agent querying through MCP tools and a human querying through pages are constrained by the same permission rules; there is no bypass.

**Protocol anti-corruption**: every external protocol stops at an adapter/bridge layer; the core meta-model is protocol-agnostic.

## 3. The closest thing to a case study: one end-to-end drill

Confession first: DAF has no production tenant, so there are no numbers like "draft to publish took three days, false-kill rate 5%". And let me ask the inevitable question myself: **do your own internal systems run on DAF? No — "no production tenant" includes us.** The first real tenant should be our own ticketing and project management; until then, the evidence-status table at the end of section three has an obvious hole — the entire production column reads unverified — and we own it.

The closest thing to a case study today is an automated end-to-end drill that runs the full chain (AssemblyStudioS1E2ETest, the DS4-phase exit evidence), worth recounting as-is because it exercised the pipeline's main promises:

- Path: from template → customization → L0 validation → L1 guard → L2 sandbox preview → L3 approval → L4 publish → upgrade → rollback, the whole chain walked end to end;
- The guard really blocked things: a field deletion was vetoed with a full impact receipt; type changes, page deletions, and data-binding changes were likewise verified to be blocked — broader than the design promised;
- Approval really had a gate: high-risk changes required at least two approvers stating their positions separately; one person's word is not enough;
- Rollback really happened: a semantic card failed during publish, and compensation logic actually invoked rollback — the application returned to the previous version instead of stopping half-done. One more iron rule was verified in the same batch: an admin trying to bypass the pipeline and install an artifact directly got a 403 — the pipeline has no bypass.

What the cycle looks like: the machine side (L0 validation, L1 guard) is deterministic checking — milliseconds to seconds, fixed cost, recomputable; the true wall-clock time of draft→publish is dominated by L2 preview startup and L3 human review — the bottleneck is people and preview environments, not the pipeline itself, which is exactly why the SLA blank must be filled. To be clear: this paragraph is a design judgment, not a measured number; with no citable per-stage timings, we report no numbers — that is the standing rule of this whole piece.

Equally honest boundaries: L2 preview data is currently synthetic, not production entity rows; approval implements only the high-risk countersign semantics, not full approval flows; the template catalog is still a code seed. This was a drill, not a track record — but "every main promise has a corresponding test" is itself the reason this article dares to describe this much mechanism detail.

Evidence status at a glance (✅ = implemented; ◐ = partial; ○ = unverified):

| Mechanism | Design | Implementation | Test | Production |
|------|------|------|------|----------|
| Guard veto / impact receipt | ✅ | ✅ | drill passed* | unverified (no production tenant) |
| Rollback compensation / version pinning for in-flight instances | ✅ | ✅ | triggered in drill* | unverified |
| High-risk countersign (≥2 approvers) | ✅ | ✅ | drill passed* | unverified |
| No pipeline bypass (403) | ✅ | ✅ | drill passed* | unverified |
| Compile-time permission injection + RLS | ✅ | ◐ | ◐ | unverified |
| Second-level policy-cache invalidation | ✅ | ◐ | ○ | unverified |
| Audit hash chain | ✅ | ◐ | ○ | unverified |
| Agent OS interop | ✅ | ◐ mock | ◐ mock | unverified |

\* "Test" means our self-written end-to-end drill passed — not third-party verification, and not production verification.

## 4. Relation to Agent OSes: whole-system cooperation, not module-level entanglement

DAF can plug into an external Agent OS to gain "intelligent assembly", but only four system-level open-protocol channels exist between them:

| Channel | Direction | Protocol |
|------|------|------|
| Task channel | DAF → Agent | A2A / REST |
| Tool channel | Agent → DAF | MCP (DAF as MCP Server) |
| Event channel | bidirectional | CloudEvents over HTTPS webhook |
| Identity channel | bidirectional | OIDC + Token Exchange (RFC 8693) |

All are open protocols, with contracts versioned and frozen. The design goal for swapping integrations is "write one new adapter, zero changes to the DAF core" — interop testing is still being filled in (no real-peer integration run yet; current verification is mock-based; the falsification test "a second implementation replays the suite" is on the exit-criteria list but has not been executed). Pull the bridge module and DAF runs in no-Agent mode: business functions degrade losslessly to manual assembly — intelligence is a gain, not a dependency.

The key point: "decoupling" here does not stay a slogan. CI hard gates scan specs and source with a closed set of regexes; the hit count must be 0. In the module dependency graph, every edge pointing outward must converge on the single bridge node, enforced at build time with ArchUnit. Decoupling is machine-verified, not document-promised.

But this section also has a bill to lay out: to keep a "self-contained runtime that shares no middleware instance", DAF must carry its own PG, Redis, RocketMQ, Keycloak, and observability stack. The minimal deployment profile is down to roughly 13 instances / 14 vCPU / 42 GB of memory — which still means operating a small platform of your own. Enterprise-grade fastidiousness has a price; this red line gets challenged again and again in customer environments, and we have left a path for plugging in externally managed cloud services.

## 5. Forty-two modules — what that means in plain words

The module catalog says 42 modules in three bundle tiers. That number needs translating: it means the foundation itself is roughly a mid-sized microservice cluster; what you buy with it is blueprint reuse.

We hedge this complexity two ways. First, 45 requirements are decomposed into 42 modules and 84 service keys and events, with the three catalogs cross-checked by script — if the documents lie, CI goes red. Second, every module has a structured spec, granular enough to hand to a developer to code directly. On design discipline we believe we have done the work — but consistency on paper is not consistency at runtime. Query-compile-time permission injection, second-level policy-cache invalidation, audit hash chains: only code and runtime data can prove those. The project is now in the phase of hammering design into running evidence, block by block; until that is done, please read this design as "a hypothesis that has been through several rounds of internal review", not "a validated conclusion".

This account pushes one step further into decision-making: **break-even ≈ the foundation's annual holding cost ÷ the repeated-development cost saved per system**. By our experience, that point sits above 3–5 systems — if the foundation ends up hosting only three to five business systems, its maintenance cost most likely outweighs what it saves. That is why the fit box in section one is drawn so narrow.

## 6. Why not just use what already exists?

This question will show up in the comments, so answer it first. A table:

| Option | Fits | Where it misses the DAF scenario |
|------|------|------------------------|
| Low-code platforms (Mingdao / Jiandaoyun / OutSystems) | fast business forms and flows | model doesn't migrate, platform black box, limited permission customization; agent assembly mostly has no governance channel |
| Salesforce / ServiceNow (metadata platforms) | mature metadata model + enterprise deployment governance + full ecosystem of reports and flows | closed source, vendor lock-in, per-seat pricing, model can't move out; deep customization goes back to the platform's closed stack (Apex etc.) |
| Frappe / Odoo (open-source metadata platforms) | open model, self-hostable, battle-tested in ERP | schema changes go through migration scripts — no guard-style impact veto or countersigned publish pipeline; agent access is RPC APIs, with no semantic-registry layer as a controlled assembly entrance; multi-tenancy is per-site, not row-level |
| Backstage / Port | developer portals, software-template catalogs | manages the catalog, not the runtime: no data layer / permission layer / assembly pipeline; from "template" to "system" you still write it yourself |
| GitOps + OPA (scaffold repo + CI + policy engine) | strong engineering culture, heterogeneous system shapes | governs infrastructure, not business semantics; the artifact layers — blueprints, entity models, semantic cards — you build entirely yourself |
| Traditional scaffolds | one or two systems, small teams | from the 2nd system on you re-build users/permissions/audit — exactly section one's death loop |
| Pure agent generation | prototypes, demos, one-off scripts | no approval pipeline, no artifact versioning, agent touches production directly — unacceptable for enterprises |
| DAF | continuously producing many kinds of business systems + strong governance + agent participation | for every row's scenario above, DAF skews heavy; the cost of running the foundation itself — see section five |

A few more words on the two closest rows: DAF's increment over Frappe/Odoo is not the declarative model — mechanisms like DocType have existed for years — but three things: governance of the release pipeline (guard impact veto and countersigned publish), a controlled assembly entrance for agents (the semantic registry), and no-bypass pipeline enforcement. Those three are exactly what the open-source metadata platforms did not build for you. Against Salesforce/ServiceNow, DAF bets on an open, self-hostable model; the price is giving up their ecosystem and years of production polish.

One sentence: DAF does not compete with these options on "better"; it competes on "narrower" — it bets on exactly one organizational shape: continuously producing many kinds of business systems. If your scenario matches any row above (other than DAF), honestly pick that row.

## 7. Closing

At least in the scenario we bet on — continuously producing many kinds of business systems — the future of enterprise software is most likely not "a bigger monolith" but "a factory that keeps producing business systems + a governed intelligent-assembly pipeline". DAF is our complete answer to that judgment — plus the cold water every section above kept pouring.

If you are also doing platform engineering or low-code, or thinking about what enterprise software looks like in the agent era, let's talk.
