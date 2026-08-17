# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`agent-determinism-illusions/` is the **reproducible-experiment repository** for the Agent Determinism Illusions series (published on [dev.to/zxpmail](https://dev.to/zxpmail)). It is not an application. It contains:

- **Experiment scripts** (`scripts/*.py`) — standalone Python files that falsify or validate specific claims. Each script is self-documenting (docstring states the claim under test, sample size, dependencies, env vars, expected result).
- **Inputs and results** — `samples/*.json` (reference scenario copies for the reader — **not loaded by any script**, each script hardcodes its own `SCENARIOS`), `scripts/test_cases/*.py` (hand-written tests for the redline tasks), `scripts/results-v2/` (JSON/JSONL output from the Phase-2 experiments).

**Articles, reply drafts, and status memos are NOT in this repo** — they live in a private docs repository (`blog/` directory: `articles/`, `working-notes/`, `CONTEXT.md`). Published articles link into this repo's `scripts/` paths, which must stay stable. Experiment numbers cited in articles (`N=3`, `N=5`, …) are load-bearing — rerun the script before changing any result that prose depends on.

Read `agent-determinism-illusions/scripts/README.md` for the experiment index before editing that area.

## Running things

There is no build, no test runner, no linter. Each experiment script is a self-contained executable.

```bash
# Zero-dependency experiments (pure Python)
python agent-determinism-illusions/scripts/lexical-overlap-test.py
python agent-determinism-illusions/scripts/phasegate-formalism-test.py

# Experiments needing an LLM API — set env first
export ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
export ANTHROPIC_AUTH_TOKEN=...
export ANTHROPIC_MODEL=glm-5.2
python agent-determinism-illusions/scripts/temp0-determinism-test.py

# Experiments needing Ollama
ollama pull qwen3-embedding:0.6b
python agent-determinism-illusions/scripts/embedding-semantic-test.py
```

**Do not invent a runner or wrap scripts in a test harness.** The author's design is one script per claim, runnable in isolation. If you add an experiment, follow that pattern — a new standalone script with a docstring, not a framework.

## Environment variables (shared contract across scripts)

Scripts auto-detect their LLM backend from `*_BASE_URL`:

| URL pattern | Backend | Endpoint |
|-------------|---------|----------|
| contains `:11434` | Ollama | `/api/chat` |
| contains `anthropic` | Anthropic-compatible (e.g. GLM via open.bigmodel.cn) | `/v1/messages` |
| otherwise | OpenAI-compatible | `/chat/completions` |

Common env vars:
- `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` (or `ANTHROPIC_API_KEY`), `ANTHROPIC_MODEL` — used by `temp0-determinism-test.py`, `redline-v2-experiment.py`, the P1/P2/P3/P4 scripts, and `forge-verify-layered-prototype.py`.
- `VERIFY_MODEL`, `VERIFY_BASE_URL`, `VERIFY_API_KEY`, `VERIFY_N` — used only by `harness-verify-test.py` and `directional-failure-test.py` (v1). API-key fallback chain: `VERIFY_API_KEY → OPENAI_API_KEY → ANTHROPIC_AUTH_TOKEN → ZHIPU_API_KEY`.
- `SKIP_LLM=1` — runs only deterministic Layer 0/1 checks without API calls. Supported by `forge-verify-layered-prototype.py`, `channel-comparison-test.py` (`--skip-llm` flag), and `contract-comparison-test.py` (`--skip-llm` flag).

**Two newer scripts take CLI args instead of env vars** (useful for sweep runs):
- `directional-failure-v2.py --model X --backend ollama|openai --temp 0.0`
- `structured-vs-open-test.py --model X --backend ollama|openai`

## Conventions when writing or editing scripts

- **UTF-8 stdout on Windows** — every script that prints Chinese starts with `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`. Keep this when adding new scripts.
- **Docstring is the spec.** Each script's module docstring must state: the claim being tested, the method, the dependencies, the expected result, and how to falsify it. Future Claude instances should be able to read the docstring and reproduce the run without reading the rest of the file.
- **Newer experiments write to `scripts/results-v2/`.** Output filenames use model slugs (e.g. `qwen3-0-5b.jsonl`, `deepseek-v4-flash_summary.json`). The directory is created on demand via `Path(__file__).parent / "results-v2"`; no setup needed.
- **Scenarios are inline.** Every experiment script hardcodes its `SCENARIOS` list at the top. The JSON files in `samples/` are reference copies for the user — they are not loaded by any script. To change scenario inputs, edit the script.
- **`redline-v2-experiment.py` accepts `--task-file`** — see `scripts/test_cases/README.md` for the JSON format. This is the only script that loads external scenarios.
- **Generated agent-output directories are not tracked** (`.gitignore`: `scripts/fixtures-b*/`). Tracked fixtures are hand-written (e.g. `scripts/argument-space/fixtures/`, `fixtures-rewrite-attack/`); per-run agent outputs live in the results JSON, not the tree.

## The conceptual architecture (read before editing experiments)

The series builds a layered verification pipeline iteratively across parts. New experiments usually extend or refute one layer:

```
L0  evidence gate        — file exists & non-empty   (deterministic, ~0ms, no model)
L1  contract regex       — per-requirement pattern    (deterministic, ~0ms)
L2  per-requirement LLM  — LLM judges each REQ atom   (model, ~1s × N_REQ)
L3  human                — residual ambiguous cases
```

Without a contract, the pipeline degrades to L0 → Channel-A (free-text LLM judge). The Data Processing Inequality (DPI) is the recurring theoretical constraint: a text-channel evaluator cannot detect a compliance gap that is not present in the text. The skillgate design (file-system channel) is the proposed escape.

Two recurring experiment patterns:

1. **Channel comparison** — text-channel LLM (Channel A) vs. file-system gate (Channel B). See `channel-comparison-test.py`.
2. **Directional failure** — paraphrase vs. antonym vs. unrelated pairs, measured across model tiers. See `directional-failure-v2.py`, `embedding-semantic-test.py`.

A third pattern from the argument-space line: **oracle hardening under adversarial producers** — synonym attacks vs. rewrite attacks (special-case-key, stack-detect, cache-intercept, prototype poison, exit-override), split into data-channel (closed by randomized keys × multi-channel probes) and control-channel (needs capability isolation). See `argument-space/rewrite-attack-test.py`.

### The P-series progression (read before adding a new "P" script)

A sequence of build-on-each-other scripts (P1 → P2 → P3 → P3b → P4 → Experiment F) drives the multi-article arc on quality-inspection tradeoffs. Each script's docstring references its predecessor's findings:

| Script | Question it asks | What it inherits |
|--------|------------------|------------------|
| `adversarial-verify-p1.py` | Can a single Agent B drop Phase Gate's 50% FP to ≤25%? | Phase Gate 8-scenario set |
| `consistency-test-p2.py` | Is P1's 75% false-negative rate stable across N=10? | P1's chosen scenarios, repeated more |
| `multi-perspective-vote-p3.py` | Does 3-perspective voting (Strict/Balanced/Lenient) fix P1's misses? | P1's 8 scenarios, 3 prompts |
| `prompt-calibration-p3b.py` | Can a 5-level strictness sweep find a better operating point? | P1 prompt as v2 baseline |
| `p4-expanded-test.py` | Do P1/P3b findings hold on 30 samples with Wilson CIs? | P3b's v3 prompt + P1's v2 |
| `forge-verify-layered-prototype.py` | Can deterministic Layer 0/1 absorb the garbage so the LLM only sees semantic residual? | All of the above as motivation |

When asked to add another experiment in this line, extend the table rather than start a parallel naming scheme. P-series scripts inline their own copy of the 8 Phase Gate scenarios (L1-L4 legitimate, G1-G4 garbage) and share the `ANTHROPIC_*` env-var contract.
