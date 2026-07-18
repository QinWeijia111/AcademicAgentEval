# Adding a new system

1. Convert source rows into `BenchmarkCase`; keep gold labels evaluator-only.
2. Implement `BaseAgent.search(AgentQuery, AgentContext)` or a JSONL worker in an isolated environment.
3. Record observable calls through `context.tracker`; store raw traces under `context.artifacts_dir`.
4. Return final papers only; provide a parser for nonstandard trees, graphs or chains.
5. Add JSON config, public synthetic fixture, parser/leakage/timeout/failure tests.
6. Complete offline contract → one-query live smoke → locked formal protocol.

Workers read secrets from their environment, emit protocol JSON only to stdout, log to stderr, and never receive raw benchmark records or ground truth.
