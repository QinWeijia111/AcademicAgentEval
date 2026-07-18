# AI2 Asta Paper Finder evaluation plan

`allenai/asta-paper-finder` is Apache-2.0 but a frozen snapshot; production uses additional non-public data/indexes. The service path needs Python 3.12+, uv, OpenAI/Semantic Scholar/Cohere/Google credentials and may require Vespa.

Pin the commit and a local/remote FastAPI base URL, pass `/health`, then use an HTTP/worker adapter with a sanitized query. Preserve redacted request/response/round/citation traces as artifacts and send only final recommendations to F1. Start in fast mode with 1–5 smoke queries and record measured, not README-claimed, latency.

If Vespa/private index or endpoint is unavailable, mark `implementation_endpoint_unavailable` / `private_index_unavailable`; a connector fixture is not a full Paper Finder reproduction.
