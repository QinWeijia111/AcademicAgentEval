# AGENTS.md

This file is the working contract for AI coding agents and human contributors in
`AcademicAgentEval`. Read it before changing the repository.

## Project context

AcademicAgentEval is an evaluation harness for end-to-end academic paper search agents.
It is being developed for a research-paper intelligent search Agent competition.

Given a complex natural-language research request, a complete search agent may perform:

```text
query understanding
  -> query decomposition / rewriting
  -> multi-strategy paper retrieval
  -> candidate filtering
  -> relevance ranking
  -> result synthesis
  -> structured output
```

The competition score emphasizes:

1. Retrieval quality, primarily Precision, Recall, and F1 (70%).
2. Efficiency, including LLM calls, token usage, cost, and latency (20%).
3. Structured output quality (10%).

The current research plan is:

1. Build a reliable, reproducible, agent-independent Evaluation Harness.
2. Reproduce and evaluate PaSa, SPAR, and Ai2 Paper Finder.
3. Compare their quality and efficiency.
4. Use the evidence to build a query-aware adaptive research agent.

The current owner focus is Evaluation Harness construction and PaSa reproduction. This is
not currently a model-training repository.

## Current repository status

Version `0.1` implements the Evaluation Core:

- Canonical schemas for queries, papers, ground truth, predictions, and usage.
- JSON and JSONL dataset loading.
- A stable `BaseAgent` interface.
- A default output parser.
- Deterministic paper matching and Precision/Recall/F1 evaluation.
- Macro and Micro aggregation.
- LLM/API/token/cost/latency tracking.
- An experiment runner with per-query failure isolation.
- JSON, JSONL, CSV, and self-contained HTML reports.
- Unit tests and a deterministic demo experiment.

PaSa, SPAR, and Ai2 adapters have **not** been implemented yet. Do not describe any of
them as working until an actual end-to-end run has been verified.

## Repository layout

```text
AcademicAgentEval/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── examples/
│   ├── demo_dataset.jsonl
│   └── run_demo.py
├── resources/                 # local-only models/data; ignored by Git
├── results/                   # generated runs; ignored except .gitkeep
├── src/academic_agent_eval/
│   ├── __init__.py
│   ├── schemas.py             # canonical cross-module data contracts
│   ├── datasets.py            # normalized JSON/JSONL datasets
│   ├── agents.py              # BaseAgent and AgentContext
│   ├── parsers.py             # heterogeneous output -> AgentResult
│   ├── evaluator.py           # matcher and F1 evaluation
│   ├── tracking.py            # efficiency accounting
│   ├── reporting.py           # self-contained HTML report
│   └── runner.py              # experiment orchestration and artifacts
└── tests/
```

## Environment and commands

Use `uv` for environment and dependency management.

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python examples/run_demo.py
```

The Evaluation Core intentionally has no runtime third-party dependencies. Keep core
dependencies minimal. Agent-specific heavyweight dependencies should be optional and must
not be imported when the core package is imported.

Before handing off any change, run at minimum:

```bash
uv run python -m compileall -q src tests examples
uv run python -m unittest discover -s tests -v
git diff --check
```

## Architectural boundaries

The framework has three primary plugin boundaries:

```text
Dataset Adapter -> BenchmarkCase
Agent Adapter   -> raw agent output
Output Parser   -> AgentResult

BenchmarkCase + AgentResult -> Evaluator -> Reports
```

Maintain these boundaries strictly.

### Dataset contract

`BaseDataset` must expose normalized `BenchmarkCase` objects. Benchmark-specific raw field
names must not leak into the evaluator.

A `BenchmarkCase` contains:

- `Query`: ID, natural-language text, optional constraints/metadata/raw record.
- `GroundTruth`: a list of normalized `Paper` objects.
- Benchmark metadata.

Ground truth must never be passed to an agent. `AgentContext` deliberately contains no
ground-truth field.

### Agent contract

Every search system must be wrapped behind `BaseAgent`:

```python
class SomeAgent(BaseAgent):
    name = "some-agent"
    version = "..."

    def setup(self) -> None:
        ...

    def search(self, query, context):
        ...

    def teardown(self) -> None:
        ...
```

Long-lived models and clients belong in `setup()`/`teardown()`, not per-query construction.
Use `context.tracker` for LLM and retrieval accounting and `context.artifacts_dir` for raw
agent traces.

An agent may return canonical objects or a system-specific raw result. A dedicated
`BaseOutputParser` must convert system-specific output to `AgentResult`.

### Prediction contract

Only `AgentResult.papers` participates in final F1 evaluation. Candidate pools and search
traces must not silently become final predictions. Preserve them as artifacts instead.

Each prediction should contain, when available:

- Rank and relevance score.
- Title.
- DOI, arXiv ID, Semantic Scholar ID, OpenAlex ID, or other stable identifier.
- Authors/year/abstract/venue.
- Retrieval provenance.

Do not fabricate missing metadata. Use `None` or an empty collection.

### Evaluator contract

The evaluator must never import a concrete agent implementation. Metric functions must be
deterministic and independently testable.

The current matching protocol is `canonical-v1`:

1. Exact normalized identifier match within the same namespace.
2. Exact normalized-title fallback.

Predictions and ground truth are deduplicated, then matched one-to-one. Changes to matching
semantics require a new protocol name/version and regression tests.

Report both Macro and Micro metrics. Never label one as plain “F1” without context in
research tables.

### Efficiency contract

The Runner-owned wall-clock latency is authoritative. Track these separately:

- LLM call count by provider.
- Prompt, completion, and cached tokens.
- Estimated model cost, when available.
- Retrieval API call count by provider.
- End-to-end per-query latency.

Unknown usage is not the same as zero. If an external service cannot expose tokens or cost,
document that limitation in experiment metadata/reporting.

### Experiment artifacts

Every successful run produces:

```text
results/<run_id>/
├── manifest.json
├── predictions.jsonl
├── per_query_metrics.jsonl
├── errors.jsonl
├── summary.json
├── summary.csv
├── report.html
└── artifacts/
```

Per-query files are flushed during execution so a long benchmark does not lose all work
after one failure. Preserve configuration, model revision, dataset revision, Git commit,
matching protocol, and execution environment in the experiment manifest whenever those
values are available.

## PaSa baseline continuation guide

Official source:

- GitHub: `https://github.com/bytedance/pasa`
- Crawler: `bytedance-research/pasa-7b-crawler`
- Selector: `bytedance-research/pasa-7b-selector`
- Dataset: `CarlanLark/pasa-dataset`

On the original development Mac, the source clone was located at:

```text
/Users/qwj_mac/study/cpipc2026/opensource_project/pasa
```

Do not hard-code this path. Use configuration or an environment variable such as
`PASA_ROOT` on the server.

### Findings from the initial PaSa audit

- Official commit inspected: `2aaa6a9b1e48d24a2b7e21e8551f863dad9eeb84`.
- `PaperAgent` uses a crawler and selector and returns a nested `PaperNode` search tree.
- Final selected papers are nodes whose `select_score > 0.5` in the official metrics code.
- Candidate discovery includes Google/Serper search, arXiv retrieval, and citation expansion.
- The official metrics normalize titles by removing all non-letter characters. This must be
  retained only as a separately named PaSa legacy compatibility metric; canonical framework
  evaluation must use the versioned framework matcher.
- The official runner inserts benchmark answers into the output tree under `extra.answer`.
  The adapter must not do this. Ground truth belongs only in the Evaluation Harness.
- The official repository loads paper database files from relative paths during `utils.py`
  import and reads `agent_prompt.json` at agent construction time.
- The official model code calls `.cuda()` directly and is designed for a CUDA environment.
- The two official BF16 model repositories are approximately 15 GB each.
- The RealScholarQuery dataset repository is gated on Hugging Face and requires license
  acceptance plus an authenticated token.
- PaSa also requires the paper database distributed with the dataset and a search API key.

The model download attempted on the Mac was interrupted before files were created. No model
or dataset files are included in this repository.

### Recommended PaSa implementation order

1. Provision a CUDA server with enough GPU memory/disk for both 7B models, or decide on a
   verified model-placement strategy before downloading all resources.
2. Accept the Hugging Face dataset terms and authenticate with `hf auth login` or an
   environment-provided token.
3. Store local-only assets under `resources/pasa/` or configured external storage. Never
   commit them.
4. Install PaSa's required/custom Transformers version in an optional PaSa environment.
5. Add a RealScholarQuery dataset adapter that preserves `question`, `answer`,
   `source_meta.published_time`, and the complete raw row.
6. Add `PasaAgent(BaseAgent)` with configurable source root, crawler/selector paths,
   prompts path, data paths, thresholds, expansion limits, thread counts, and search key.
7. Prefer a process-isolated PaSa worker if its global imports or dependency pins conflict
   with the core harness. Keep models loaded across queries.
8. Add `PasaOutputParser` that traverses the `PaperNode` tree, deduplicates candidates, and
   emits selected nodes as ranked canonical `Prediction` objects. Preserve the full tree in
   `artifacts/`.
9. Instrument crawler generation, selector scoring, retrieval calls, latency, and tokens.
10. First run one RealScholarQuery case with minimal expansion, then a small subset, then the
    full 50-query benchmark.
11. Generate canonical results and separately report PaSa legacy metrics for reproduction.

Do not modify the upstream PaSa source unless an unavoidable compatibility patch is clearly
documented. Prefer adapters, injected configuration, or a small worker wrapper maintained in
this repository.

## Secrets and large files

Never commit:

- Hugging Face tokens.
- Serper/Google/API keys.
- `.env` files.
- Model weights (`*.safetensors`, `*.bin`, `*.pt`, etc.).
- Gated benchmark or paper-database files unless their license explicitly permits it and the
  repository owner explicitly requests it.
- Generated `results/` runs, unless a small sanitized fixture is intentionally added.

Read secrets from environment variables. Do not print secret values in logs, tests, reports,
or tool output.

## Coding standards

- Target Python 3.10+.
- Prefer typed dataclasses and explicit interfaces.
- Keep imports side-effect free, especially optional Agent integrations.
- Use `pathlib.Path`, UTF-8, JSON with `ensure_ascii=False`, and deterministic output.
- Use standard-library dependencies in the core when practical.
- Validate external input at module boundaries and raise actionable errors.
- Escape all dynamic content included in HTML reports.
- Preserve per-query failures instead of aborting an entire experiment by default.
- Add unit tests for success, empty output, duplicates, malformed output, and failure paths.
- Avoid broad refactors while adding a baseline adapter.
- Do not weaken the canonical schema to accommodate one external system; adapt the system.

## Git and handoff expectations

- Do not commit generated models, datasets, caches, virtual environments, or experiment runs.
- Keep commits focused and explain protocol/metric changes explicitly.
- Before pushing, inspect `git status`, run the test suite, and review staged file sizes.
- In handoff notes, distinguish implemented, tested, and merely planned functionality.
- If a real benchmark cannot run, state the exact blocker (credentials, hardware, API key,
  data license, or dependency conflict) and leave the offline adapter/test path reproducible.
