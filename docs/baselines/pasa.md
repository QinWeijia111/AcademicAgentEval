# PaSa evaluation plan

Use a fixed external `bytedance/pasa` checkout and an isolated Ubuntu venv through `PASA_ROOT`; do not import its custom Transformers into the core. Required resources include crawler/selector checkpoints, paper DB, authorized data and search service credentials. The worker receives only AgentQuery, stores the PaperNode tree as an artifact, and converts selected nodes to final predictions.

## 32GB GPU gate

Do not promise complete default PaSa on a 32GB card. Two BF16 8B bare weights are about 30GiB and upstream constructs crawler plus selector. Measure crawler load, selector load, then dual-agent plus one real query peak VRAM. If dual BF16 OOMs, mark official-like mode blocked. Sequential loading/offload/quantization may be explored only as `pasa-adapted-32gb`, never as unchanged upstream reproduction. A verified >=48GB card or split placement is safer for complete baseline work. Training/PPO is out of scope.

Run parser fixture → GPU preflight → one query → 3–5 query smoke → locked public subset/full. Report canonical-v1 and any PaSa legacy metric separately.
