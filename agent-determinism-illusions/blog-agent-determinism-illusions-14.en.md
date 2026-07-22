<!--
  Title options:
  Harness Is a Gate, Not an Orchestrator — an engineering memo
  I welded an agent kernel into gates — then beat only a strawman baseline
  ─────────────────────────────────────────────────────────────────
-->

# Harness Is a Gate, Not an Orchestrator — an engineering memo

**Agent Determinism Illusions (Part 14)**

> **Where this sits:** An earlier piece tore apart “drawing the architecture = solving the problem.” This one flips the move: instead of a thicker orchestration shell, weld the harness into **gates** (stop, refuse, destroy), and measure false accepts / false rejects under a controlled contrast. Genre: **engineering memo**, not a paper claim.

The trend wants long memory, stronger autonomy, finish-at-all-costs, and harness-as-capability-orchestrator. Those product wants can stay. What’s wrong is **defining** the harness as the orchestrator — interrupts, forgetting, and shredding get optimized away because they “block completion.”

One engineering proposition:

> **Capabilities may be thick; the harness must be a gate first.**  
> Embed lifetime and shreddability into memory; hang timeout / deposit / startle on autonomy; define “done” by contracts and deterministic layers — not by vibes.

---

## 1. What got welded (deployable process, not a product shell)

`scripts/harness-kernel.py`: a long-lived process over NDJSON / multi-session HTTP.

| Gate | Behavior |
|------|----------|
| `PHYSICAL_TIMEOUT_MS` | Wall-clock overrun → refuse the turn, **drop the late answer**, process stays up |
| Token% deposit | Exhausted → `BUDGET_EXIT`, clear `plan`, exit=1 (single-session) |
| Startle | Latency spike → refuse this turn, don’t kill the process |
| Session lifetime | Expiry refuses LLM |
| `verify` / turn→verify | forge L0→L1→(optional) L2 |
| wind_down | Clear plan, session dies |

Docker probes (chaos / adversarial / reset / compose / harness-kernel) and path acceptance A/B/C/D (`prod-gate-acceptance.py`) are green.  
**Honest label:** lab acceptance — not customer production validation.

---

## 2. Contrast: ORCH vs GATE

Script: `scripts/gate-vs-orch-controlled.py`.

| Condition | Meaning |
|-----------|---------|
| **ORCH** | Strawman orchestrator: non-empty output ⇒ ACCEPT |
| **GATE** | forge layered verify + (slow arm) wall-clock hard cap |
| Ablations | no verify / no timeout |

Task set: P1+P4+write-test, plus hand-labeled code/test (**business-proxy**). **Not private production traffic.**

### 2.1 SKIP_LLM (L0/L1 only)

False accept (should-reject): ORCH **15/15 = 100%**, GATE **0/13 = 0%** (Wilson 95% in the result JSON).  
Late accept on slow-harmful (N=20): ORCH **20/20**, GATE **0/20**.  
Ablation: drop verify → FA back to 100%; drop timeout → late back to 100%.

Should-pass cases mostly `UNCLEAR` under SKIP → **false-reject denominator was 0**; semantic over-refusal wasn’t measurable yet.

### 2.2 L2 on (real API, glm-5.2) + suite=both

| Metric | ORCH | GATE |
|--------|------|------|
| False accept (should-reject, n=20) | 20/20 = 100% | **0/20 = 0%** |
| False reject (should-pass) | 0/20 | **4/19 = 21.1%** (Wilson ≈ [8.5%, 43.3%]) |

False reject is finally measurable. Gates have a cost: ~one-fifth of should-pass cases refused in this run (single model, wide CI).

Artifact: `scripts/results-v2/gate-vs-orch-controlled_both_l2_result.json`.

---

## 3. What this supports — and what it doesn’t

**Supports:**

- Against “accept if non-empty,” gates crush false accepts on this proxy; timeout blocks late-as-success.  
- Ablations track the mechanism — not mysticism.  
- With L2 on, over-refusal is quantifiable (~21% here).

**Does not support:**

- Validated on *your* production.  
- Beat a real orchestrator (Cursor / LangGraph / a real runtime) — ORCH is a strawman.  
- That 21% FR is acceptable or optimal — no business cost function.  
- A peer-reviewable theorem — small N, one model, no multiplicity correction.

One line:  
**We showed our gates beat a fool orchestrator on our own script. We have not shown they hold against real systems, real adversaries, or real cost.**

---

## 4. How this hooks the series

The series keeps tearing down the same shape: temperature 0, Phase Gate, LLM-as-Judge, architecture diagrams — **treating “looks like a constraint” as “already converged.”**

The orchestration shell is the next isomorphic stop: more tools, longer memory, fewer interrupts — hallucinations get orchestrated longer. Gates don’t ban capability; they require a **hard stop on the completion path.**

Parts on L0→L1→L2 / argument-space are gates on the *verify* side. This part is gates on the *runtime* side. Same preference: **cowardly, ephemeral, willing to discard.**

---

## Close

Trends can keep long memory and strong autonomy.  
If harness means orchestrator, gates get optimized away.

**Capabilities may be thick. The harness must be a gate first.**

This is an engineering memo: numbers are reproducible, claims are narrow, not sold as a paper result. If we get serious next — non-strawman baselines, external task sets, a cost function — that deserves another part.

---

**Series:** Agent Determinism Illusions · scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)  
**Scripts:** `harness-kernel.py` · `prod-gate-acceptance.py` · `gate-vs-orch-controlled.py`  
**Notes:** `working-notes/agent-harness-kernel-design.md` · `working-notes/gate-vs-orch-controlled.md`
