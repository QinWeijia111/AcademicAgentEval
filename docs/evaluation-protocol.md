# Evaluation protocol

`canonical-v1` first matches normalized stable IDs within a namespace, then normalized exact titles; papers are deduplicated and one-to-one matched. Always report both Macro and Micro F1.

`local-proxy-v1` mirrors the problem's 70/20/10 weights but is **not official**. Calculate it only when the config fixes F1 aggregation, Top-K, efficiency budget/normalization, failure/cache/cold-start policy and structure requirements; otherwise show raw measurements.

Runner wall-clock is the authoritative per-query latency. Record API/LLM logical calls, retry attempts, token/cost source, cache state, startup/warmup, provider/model/revision and unknown fields. Unknown is not zero.

`structured-schema-v1` validates machine-readable ranked papers, identity, provenance, sections and optional relation endpoints. It never judges semantic correctness.

Comparable runs require the same dataset hash/split/query list, matcher/profile, model/upstream revision, cache policy and measurement scope.
