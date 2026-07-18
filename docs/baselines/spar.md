# SPAR evaluation plan

Run `xiaofengShi/SPAR` from an external pinned checkout/venv. Initial local smoke is API orchestration using configured OpenAI-compatible, Serper, Semantic Scholar, OpenAlex/arXiv services; remote model use must be reported as `remote-LLM`.

Audit the actual callable path before evaluation: do not use a batch path that attaches answer/labels to its saved tree. A worker gets only a sanitized query, writes Query Evolution/search tree/Graphviz artifacts, and returns only the final selected papers for F1. Start with 3–5 fixed queries, concurrency 1, bounded depth/docs and recorded retry/cache policy. If token/API usage is unavailable, report quality but mark efficiency incomplete.

README claims MIT, but verify an actual LICENSE before redistribution.
