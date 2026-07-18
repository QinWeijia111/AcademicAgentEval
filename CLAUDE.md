# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This is a Python 3.10+ package managed by `uv`.

```bash
# Install/sync the project environment
uv sync

# Run the complete test suite
uv run python -m unittest discover -s tests -v

# Run one test file
uv run python -m unittest discover -s tests -p 'test_evaluator.py' -v

# Compile and lint
uv run python -m compileall -q src tests examples
uv run ruff check src tests
uv run ruff format --check src tests

# Exercise the deterministic core demo
uv run python examples/run_demo.py

# Harness CLI (does not invoke an external baseline)
uv run python -m academic_agent_eval --help
academic-agent-eval validate-config --config <config.json>
academic-agent-eval validate-dataset --config <config.json>
academic-agent-eval doctor --config <config.json>

# Final whitespace check
git diff --check
```

## Architecture

AcademicAgentEval evaluates end-to-end academic paper-search agents. The stable execution path is:

```text
Dataset adapter → BenchmarkCase → AgentQuery → BaseAgent / worker
  → OutputParser → AgentResult → F1Evaluator / scoring helpers → Runner artifacts
```

- **Canonical data boundary** — `schemas.py` defines `Query`, `Paper`, `GroundTruth`, `BenchmarkCase`, `Prediction`, and `AgentResult`. Dataset adapters normalize external rows before they reach the evaluator.
- **Label isolation** — `BenchmarkCase` retains ground truth for evaluation; `ExperimentRunner` projects `Query` into `AgentQuery` before calling `BaseAgent.search()`. `AgentQuery` recursively drops evaluation-label fields. Do not bypass this projection or pass raw benchmark rows to an agent/worker.
- **Agent boundary** — `agents.py` provides `BaseAgent.setup/search/teardown`; `AgentContext` owns the per-query tracker and artifact directory. Only `AgentResult.papers` are final predictions. Search trees, candidate pools, query-rewrite traces, and citation graphs belong in artifacts.
- **Evaluation boundary** — `evaluator.py` owns deterministic `canonical-v1`: normalized stable-ID matching, then normalized exact-title fallback, with one-to-one deduplication. Preserve this protocol; baseline-specific compatibility metrics must use another protocol name.
- **Metrics and reporting** — `tracking.py` records usage and runner-owned wall latency. `scoring.py` adds ranking and structured-schema helpers. `local-proxy-v1` is a research proxy, not an official contest score, because the contest has not published all scoring details. `runner.py` writes JSON/JSONL/CSV/HTML artifacts.
- **External systems** — `integrations/` currently contains dependency-free parsers for recorded PaSa, SPAR, and Asta output. It is not proof that any live baseline has run. Upstream projects, heavyweight libraries, models, and data belong in external isolated environments; the core package must remain dependency-light.
- **Config and datasets** — `config.py` loads strict JSON `eval-config-v1` configs. `dataset_adapters.py` converts supported public benchmark-shaped rows. Smoke templates are in `configs/smoke/`; copy them into a local config and replace placeholders before use.

## Project-specific constraints

- `AGENTS.md` is the detailed project contract. It defines the current research scope, artifact layout, canonical matcher, efficiency accounting, and PaSa-specific deployment findings.
- The competition weights are F1 70%, efficiency 20%, and structured output 10%, but aggregation, Top-K, efficiency normalization, and structure rubric are not official. Report raw metrics and mark any composite score as non-official.
- Keep evaluator inputs and agent-visible inputs separate. In particular, do not allow `answer`, `ground_truth`, `gold`, `label`, or related nested fields into `AgentQuery`, worker payloads, prediction metadata, or saved baseline artifacts.
- Live PaSa, SPAR, and Asta smoke runs are environment-dependent and currently unverified. Use the baseline guides in `docs/baselines/` and describe blockers precisely rather than treating parser fixtures as a reproduction.

## Documentation and commit sequence

For a code change, use this order:

1. Implement and run the relevant validation successfully.
2. Update `CHANGE_LOG.md` under **Unreleased** and update `CLAUDE.md`, `README.md`, and `AGENTS.md` when the change materially affects their guidance, public workflow, or architecture contract.
3. Inspect the resulting diff. Run `git commit` only when the user explicitly asks to commit; documentation maintenance does not authorize an automatic commit.

## Reference docs

- `README.md` — setup, status matrix, CLI, data boundary, and user-facing workflow.
- `docs/evaluation-protocol.md` — matching, proxy-score, efficiency, and comparability rules.
- `docs/new-system-guide.md` — checklist for adding a new agent or worker.
- `docs/baselines/` — PaSa GPU gate and the SPAR/Asta integration plans.
