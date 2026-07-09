# The Channel Gap: Why Your LLM Judge is Blind in One Eye

**Agent Determinism Illusions (Part 11)**

*2026-07-09*

Part 10 ended with a functioning layered pipeline built from community corrections. L0/L1 filter deterministically, L2 handles semantic residual, L3 detects divergence. It's better than what came before. But it still has a fundamental design flaw that I only recognized after reading the tool that implements the *opposite* design choice.

This article compares two competing designs for the verification layer — one reading text through an LLM, one reading the filesystem through deterministic checks — and shows why neither works alone, but why a combined approach closes all but one theoretically uncloseable gap.

---

## 1. The Comment That Changed the Frame

After the series went live, René Zander ([@reneza on dev.to](https://dev.to/reneza/comment/3akon)) left this:

> *"Lexical overlap, a temperature-0 judge, and a phase gate are all trying to make a probabilistic judgment call ('is this done', 'is this a new task') return a binary fact, and dressing it in code does not change what it is."*

They were saying that every "deterministic fix" in the series was a **deterministic wrapper on a semantic decision**. Vocabulary overlap thresholds, temperature-0 evaluation, Phase Gate formalism — all of them put a probabilistic judgment inside a code structure that looked deterministic, but the underlying decision was still a model output. The code didn't make the judgment more reliable; it made the unreliability harder to see.

The commenter identified the root cause as the **Data Processing Inequality**: when the evaluator shares the same communication channel as the producer (both read/write text), information available to the evaluator is a *subset* of what the producer output. If the deviation doesn't appear in the text, the evaluator — human or LLM — cannot detect it.

They had created a tool to implement the alternative: skillgate.

### 1.1 The alternative: skillgate

Skillgate (`@reneza/skillgate` on npm) is a deterministic, model-independent gate that checks the **filesystem** instead of reading the model's output. Its thesis:

> *Don't ask whether the task was done. Ask whether the evidence exists.*

The implementation is minimal — a compact TypeScript package with two external dependencies (a YAML parser and a glob matcher). Its gate types:

- `file-exists` — path exists
- `evidence` — file exists AND non-empty
- `not-empty` — directory at `path` contains at least `min` entries
- `absent` — regex pattern does NOT appear in matched files
- `file-contains` — file matches regex
- `command` — shell command exits 0
- `instruction-sync` — instruction files haven't drifted (LCS similarity ≥ 0.95)

Note what's missing: **no LLM judge**. Every gate is a pure function over the filesystem. Same disk state, same verdict. Always.

The enforcement mechanism is a `PreToolUse` hook in Claude Code that intercepts `git commit`, `git push`, `npm publish`, runs the gates, and exits with code 2 (blocking the tool call) if any gate fails. The agent sees the failure messages and can attempt fixes, but it cannot override the gate — the gate lives outside the model's control flow.

Three deployment tiers, each enforcing the same `.skillgate/done.yaml`:

| Layer | Where | Who controls it | Bypassable? |
|-------|-------|----------------|-------------|
| Soft | Claude Code PreToolUse hook | Project config | Model can modify the hook |
| Soft | pre-commit git hook | Local repo | `git commit --no-verify` |
| Hard | pre-receive hook on self-hosted VPS | Server admin | Agent cannot log into the box |

The hard layer is the architectural innovation: a pre-receive hook that materializes the pushed tree, runs `skillgate check` against the authoritative `.skillgate/done.yaml` (which lives on the server, not in the repo), and **rejects the push** if any gate fails. The agent cannot git-push its way past the gate because the gate runs after `git push` completes on the server.

This is not a theoretical design. It shipped as v0.5.0 and the source is readable on GitHub.

### 1.2 What skillgate does differently

ReqForge's `forge-verify` and skillgate solve the same problem — "is the work actually done?" — through completely different channels:

| Dimension | forge-verify (L0-L3) | skillgate |
|-----------|---------------------|-----------|
| Channel | **Text** — reads model output | **Filesystem** — checks artifacts |
| Evaluator | Code + LLM | Code only |
| DPI bound | Yes — evaluates text through text | No — evaluates actions through artifacts |
| Judge variance | LLM temperature, model version, prompt | Zero — pure function |
| Scope | **What** was produced | **That** it was produced |
| Enforcement | Stop-time hook (soft) | Pre-receive hook (hard) |

The contrast exposes the question I should have asked in Part 10 but didn't:

> **If we have two completely different channels for evaluating compliance, what does each one catch that the other misses — and what does both together still miss?**

That question drove two rounds of experiments.

---

## 2. Phase 1: Channel Comparison

### 2.1 Design

12 scenarios where an agent claims to have completed a task. Each scenario has:
1. **Agent output text** — what the agent says it did
2. **Evidence files** — what artifact files exist (or don't)
3. **Ground truth** — whether the agent actually complied

Two evaluators, each limited to its own channel:

- **Channel A (in-channel):** LLM (deepseek-v4-flash, temperature 0) reads the agent's output text + any evidence file content. Decides: "is the work done?" N=3 votes per scenario, majority decides.
- **Channel B (out-of-band):** File system check — for each required evidence file, does it exist and is it non-empty? No LLM involved. Pure function.

The 12 scenarios cover: full compliance, missing evidence, empty evidence, fabricated evidence, partial evidence, stale evidence, semantic compliance gaps, and agent rationalization.

### 2.2 Results

| Metric | Channel A (LLM text) | Channel B (filesystem) |
|--------|:--------------------:|:----------------------:|
| **Overall accuracy** | **83.3%** | **75.0%** |
| **Detection rate** | **77.8%** | **66.7%** |
| False acceptance (FA) | 2 | 3 |
| False rejection (FR) | 0 | 0 |

Each channel has **zero false rejections** — when they flag something, it's real. The difference is in what they miss.

**Channel A caught that Channel B missed:**
- **Fabricated evidence (SC04):** Evidence files exist with content like "All tests passed!" but no real test output. Channel A read the content and rejected it as too vague. Channel B said "file exists and non-empty → PASS."
- **Stale evidence (SC07):** Evidence files from yesterday claiming "cleaned 3 files" while the agent's log claims "cleaned 5 files today." Channel A noticed the date mismatch. Channel B said "file exists → PASS."

**Channel B caught that Channel A missed:**
- **Review-only (SC11):** Agent wrote a code review but didn't run tests. Its self-review justified: "No test run needed — change is minimal." Channel A found this reasoning persuasive (2/3 votes PASS). Channel B checked: test-output.txt absent → REJECT.

**The most revealing scenario — semantic gap (SC10):**
- Agent's task: "Implement rate limiting middleware with key write-invalidation."
- Agent produced: A RateLimiter class with IP/User level limiting, Redis storage, 24 passing tests, 92% coverage. Everything looked complete.
- Not present: Write-invalidation. The diff review noted: "Keys expire via TTL, not write-invalidation — TTL is simpler and sufficient."
- Channel A: 3/3 PASS — confident the work was done.
- Channel B: PASS — all evidence files present and non-empty.

**Both channels missed the same one: a structurally perfect output that doesn't meet the requirement.**

### 2.3 The blind spot map

| Failure mode | Channel A (text) | Channel B (filesystem) |
|-------------|:----------------:|:----------------------:|
| Evidence missing | ✅ |
| Empty evidence | ✅ |
| Fabricated content | ✅ | ❌ |
| Stale content | ✅ | ❌ |
| Partial evidence | ✅ |
| Agent rationalization ("no test needed") | ❌ | ✅ |
| **Semantic gap (DPI bound)** | **❌** | **❌** |

Combined (A or B rejects), the detection rate is 11/12 = 91.7%. The only shared blind spot is the semantic gap — and that's provably undetectable from text or filesystem evidence alone.

---

## 3. Phase 2: Contract Verification

The Phase 1 blind spot map says: to close the remaining gap, we need to check *what* the evidence says, not just *that* it exists. But how? Channel A (LLM reading text) already failed on that exact scenario.

The answer: **don't ask the LLM to judge the whole picture. Decompose "done" into individual requirements and check each one separately.**

### 3.1 Design

7 scenarios sharing a common 5-requirement contract for a rate-limiting middleware task:

```
REQ-1: IP-level rate limiting       → evidence: test-output.txt
REQ-2: User-level rate limiting     → evidence: test-output.txt  
REQ-3: Write-invalidation on write  → evidence: diff-review.md (review text)
REQ-4: Coverage ≥ 85%               → evidence: coverage-summary.txt
REQ-5: Lint 0 errors                → evidence: lint-report.txt
```

Three evaluators:

- **C0 (free-text LLM):** Same as Phase 1 Channel A — LLM reads everything and judges holistically.
- **C1 (contract regex):** For each requirement, read the evidence file and regex match a pattern. No model. Zero cost.
- **C2 (per-requirement LLM):** For each requirement, ask the LLM: "Does this evidence prove requirement N?" Then check whether ALL pass. Cost: ~1s per requirement instead of ~1s for one holistic call.

### 3.2 Results

| Metric | C0 (free-text) | C1 (contract regex) | C2 (per-req LLM) |
|--------|:--------------:|:-------------------:|:----------------:|
| **Overall accuracy** | **42.9%** | **85.7%** | **85.7%** |
| **Detection rate** | **20.0%** | **80.0%** | **100%** |
| False acceptance | 4 | 1 | 0 |
| False rejection | 0 | 0 | 1 |
| Per-item accuracy | — | 88.6% | 82.9% |

The numbers tell a clear story.

**C0 (free-text LLM) collapses on the hardest set.** 4 of 5 non-compliant scenarios were missed. The LLM read the agent's output, saw "tests pass, lint clean, coverage 92%," and declared it done — even when the core requirement (write-invalidation) was missing. Same mechanism as Phase 1's SC10: the LLM is doing an impression judgment, not a line-by-line audit.

**C1 (contract regex) is surprisingly effective for a zero-cost solution.** 85.7% overall, 80% detection. The one failure is instructive: SC10a (the write-invalidation gap again). The diff-review.md says "keys expire via TTL, not write-invalidation" — and the regex `write.?invalidat` matched the word "write-invalidation" in the negation. **C1 has a "negation blind spot": it matches the mention of a requirement, not its satisfaction.**

But C1 is **excellent on numerical and format constraints:**

| Pattern type | Reliability | Example |
|-------------|:-----------:|---------|
| Numerical comparison | ✅ | `(8[5-9]\|90+)\%` for coverage ≥ 85% |
| Fixed-format text | ✅ | `0\s+errors` for lint |
| Functional keywords | ⚠️ | Naming-sensitive (purgeCacheOnWrite vs write-invalidation) |
| **Negated mentions** | **❌** | `"not write-invalidation"` matches `write.?invalidat` |

**C2 (per-requirement LLM) achieves 100% detection rate — the only mechanism in either experiment to catch every non-compliant scenario.** It works because forcing the LLM to judge one requirement at a time prevents the "everything looks fine" gestalt from overriding the missing-item signal.

On SC10a (the semantic gap), the per-requirement LLM correctly rejected REQ-3:

> "Evidence clearly states TTL expiration is used instead of write-invalidation. The requirement is not satisfied."

While the same LLM in C0 mode on the same scenario:

> "Agent completed rate limiter implementation, tests all pass, lint clean, coverage 92% — all requirements met."

The difference isn't model capability. It's **the same model, same temperature, different framing.** The holistic frame asks "is this good?" The per-item frame asks "is this specific thing proven?"

C2's one false rejection (SC10c — which was genuinely compliant) was on REQ-3: the per-req LLM rejected write-invalidation because the diff-review.md "only mentions it, doesn't prove it with code." This is arguably correct behavior — a review file *shouldn't* be sufficient evidence for code-level requirements. The false rejection exposed a contract design issue, not an evaluator issue.

### 3.3 Contract regex failure pattern

The C1 negation blind spot deserves deeper analysis because it mirrors the Data Processing Inequality at the regex level:

| Input | Regex | Match? | Correct? |
|-------|-------|:-------:|:--------:|
| "Keys expire via TTL, not **write-invalidation**" | `write.?invalidat` | **YES** | ❌ False pass |
| "Coverage: **72.3%**" | `(8[5-9]\|90+)\%` | NO | ✅ Correct reject |
| "Implemented **purgeCacheOnWrite**" | `purgeOnWrite` | **YES** | ✅ Correct pass |

The numerical constraint (`85%+`) is immune to the negation problem because a number below threshold is factually wrong regardless of context. The keyword constraint (`write.?invalidat`) is vulnerable because the regex can't tell the difference between "I implemented X" and "I didn't implement X."

A regex constraint can be strengthened with negative lookahead — `(?!not.*)write.?invalidat` — but this quickly becomes fragile and regex-specific. The practical fix is to route semantic requirements (where negation matters) to C2 (per-req LLM) and reserve C1 for numerical and format constraints.

---

## 4. Synthesis: The Evidence Gate Pipeline

Putting Phase 1 and Phase 2 together produces a three-layer post-L1 pipeline that replaces the single L2 free-text LLM from Part 10:

```
                   output file
                        │
                    L0 → L0e → L1
                        │ pass
              ┌─────────▼──────────┐
              │  Evidence Gate     │  file exists + non-empty
              │  (deterministic)   │  ~0ms
              └─────────┬──────────┘
                        │ pass
              ┌─────────▼──────────┐
              │  C1 Contract Regex │  per-requirement regex
              │  (deterministic)   │  best for: numerical, format
              └─────────┬──────────┘
                   │          │
                UNCLEAR     ALL PASS
                   │          │
              ┌────▼───┐      │
              │ C2 Per- │      │
              │ Req LLM │      │
              │ ~1s/REQ │      │
              └────┬───┘      │
                   │          │
              ┌────▼────┐     │
              │   L3    ◄─────┘
              │ (shared)│
              └─────────┘
```

### 4.1 When to use each path

**No contract defined (no `evidence_gates` config):**
- Traditional L0 → L0e → L1 → L2 (free-text LLM) → L3
- Same as Part 10 architecture. Works when there's no predefined set of verifiable requirements.

**Contract defined (with `evidence_gates`):**
- L0 → L0e → L1 → Evidence Gate → C1 → (C2 if needed) → L3
- C1 handles numerical and format constraints deterministically (zero cost)
- C2 handles semantic constraints per-requirement (higher cost, but higher detection rate)
- The contract defines requirements with a `type` field: `"regex"` for C1, `"llm"` for C2

**The combined channel performance:**

| Mechanism | Detection rate | Cost per scenario |
|-----------|:--------------:|:-----------------:|
| C0 free-text LLM (old L2) | 20% | ~1s |
| Evidence Gate only | 66.7% | ~0ms |
| + C1 contract regex | 80.0% | ~0ms |
| + C2 per-req LLM | **100%** | ~1s × N_req |
| Combined C0+C1 (any reject) | 91.7% | ~1s |

### 4.2 The remaining gap

One scenario still evades every mechanism we tested: **SC10, the semantic compliance gap.** The agent produces a structurally complete output with correct evidence files, all tests pass, coverage is adequate, the self-review is coherent — but the output doesn't satisfy the actual requirement. The requirement missing from the evidence is also missing from every signal the evaluator can observe.

This is not an implementation bug. It's a **theoretically provable** blind spot. If the evaluator only has access to the same data the producer had (the output text and evidence files), the Data Processing Inequality guarantees that the evaluator cannot detect a deviation that the producer's output doesn't surface.

The fixes for this gap are all outside the evaluation channel:
- **Human review on material calls** — a person reads the requirement vs the implementation
- **Hard step budgets** — the agent runs out of steps before it can simulate compliance
- **Server-side enforcement** — the VPS pre-receive hook cannot be fooled by plausible output

Skillgate's self-hosted gate implements the last two. The first requires human attention.

### 4.3 Implementation

The pipeline described here has been integrated into `forge-verify`'s `content-verify.mjs` as an optional evidence gate mode. Configured via `.forge/content-verify.json`:

```json
{
  "task": "Implement rate limiting middleware",
  "files": ["src/rate-limit.ts"],
  "evidence_gates": {
    "evidence_dir": ".skillgate/evidence",
    "requirements": [
      {
        "id": "REQ-1",
        "desc": "IP level rate limiting",
        "evidence_file": "test-output.txt",
        "pattern": "(?i)(RateLimiter.*IP|isRateLimited.*IP)",
        "type": "regex"
      },
      {
        "id": "REQ-2",
        "desc": "Write-invalidation on cache writes",
        "evidence_file": "diff-review.md",
        "type": "llm"
      },
      {
        "id": "REQ-3",
        "desc": "Coverage >= 85%",
        "evidence_file": "coverage-summary.txt",
        "pattern": "(8[5-9]|90+)%",
        "type": "regex"
      }
    ]
  }
}
```

When `evidence_gates` is configured, the pipeline runs the evidence gate → C1 (regex requirements) → C2 (LLM requirements) → L3 path. When absent, it falls back to the traditional L0 → L2 → L3 path. Backward compatible — existing configurations don't need changes.

---

## 5. What the Two Experiments Established

**First, the channel you evaluate through determines what you can detect.** An LLM reading text catches semantic patterns that a filesystem check cannot — fabricated content, stale dates, implausible narratives. A filesystem check catches mechanical gaps that an LLM cannot — missing artifacts, empty evidence, incomplete coverage. Neither channel alone is sufficient, and the shared blind spot is provably uncloseable from either channel alone.

**Second, per-requirement evaluation outperforms holistic evaluation by a wide margin.** The same LLM, same temperature, same evidence — but asking "does this evidence prove requirement N?" instead of "is the work done?" raised detection rate from 20% to 100%. The frame matters more than the model.

**Third, contract regex is a practical zero-cost filter for a surprisingly wide set of constraints.** Numerical thresholds, format validity, and fixed-pattern detection all work reliably. The exception — negation patterns — can be handled by routing them to the per-requirement LLM.

**Fourth, the negation blind spot in regex evaluation is the same problem as the DPI blind spot, one level down.** A regex that matches "write-invalidation" in "not write-invalidation" is making the same error as an LLM that reads "all tests pass" and misses that the wrong test suite was run. Both are pattern-matchers that can't distinguish "mentioned" from "satisfied."

---

## 6. Summary

| Experiment | Question | Answer |
|-----------|----------|--------|
| Phase 1 (12 scenarios) | Text channel vs filesystem channel | Complementary blind spots; combined = 91.7% |
| Phase 2 (7 scenarios) | Free-text vs contract regex vs per-req LLM | Per-req = 100% detection; contract regex = 85.7% at zero cost |
| Combined (19 scenarios) | What mechanism closes the DPI gap? | Per-requirement LLM (C2), but only when the requirement is in the contract |

The architectural conclusion: replace the single free-text LLM evaluation (old L2) with a three-stage pipeline — evidence gate (file system) → contract regex (text patterns) → per-requirement LLM (semantic checks). Each stage catches what the previous one misses, and the combination covers all scenarios we could construct except the theoretically uncloseable semantic compliance gap.

---

*All experiment scripts: [GitHub](https://github.com/zxpmail/blog/tree/main/agent-determinism-illusions/scripts)*
- Phase 1: `channel-comparison-test.py` — 12 scenarios, deepseek-v4-flash
- Phase 2: `contract-comparison-test.py` — 7 scenarios, 3 mechanisms
- skillgate source: v0.5.0 on [npm](https://www.npmjs.com/package/@reneza/skillgate) and [GitHub](https://github.com/renezander030/skillgate)
- Pipeline implementation: `ReqForge/scripts/forge-verify/content-verify.mjs`
- *Series start:* [I tested the 'deterministic agent loop' claims with four experiments. They all failed — including my own fix.](blog-agent-determinism-illusions.en.md)
