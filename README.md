# AcademicAgentEval

AcademicAgentEval 是复杂科研查询、论文检索与推荐 Agent 的可复现实验 Harness。它将 PaSa、SPAR、AI2 Asta Paper Finder 和自研系统置于统一链路：

```text
授权原始 benchmark → Dataset adapter → BenchmarkCase
  → AgentQuery（无标签投影） → BaseAgent / isolated worker
  → AgentResult → canonical-v1 + ranking + structured checks → artifacts
```

> 赛题只公布 F1 70%、效率 20%、结构化输出 10%。没有公布 F1 聚合、Top-K、效率归一或结构化 rubric。因此本项目的 `local-proxy-v1` 是**研究用 proxy，不是官方分数**；默认同时报告 Macro/Micro F1 和原始效率。

## 状态

| 能力                                                             | 状态                           |
| ---------------------------------------------------------------- | ------------------------------ |
| Canonical JSON/JSONL、ID/标题匹配、F1、效率、HTML 报告           | 可用                           |
| AgentQuery 标签隔离、JSON config、CLI、ranking/structure helpers | 可用且离线测试覆盖             |
| PaSa/SPAR/Asta raw-output parser contract                        | 可用（fixture/adapter 层）     |
| 三个系统的真实 online smoke                                      | 需要各自许可、密钥、服务和硬件 |
| 官方/隐藏集评分                                                  | 未实现，等待赛方规则           |

## 安装和验证

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python examples/run_demo.py
uv run python -m academic_agent_eval --help
```

无外部调用的配置检查：

```bash
academic-agent-eval validate-config --config <config.json>
academic-agent-eval validate-dataset --config <config.json>
academic-agent-eval doctor --config <config.json>
```

从 `configs/smoke/*.template.json` 复制本机 config，并替换 `${...}` 占位符。模板只保存环境变量**名称**；不要提交 local config、`.env`、受限数据或模型。

## 安全数据边界

Canonical case：

```json
{
  "query": { "query_id": "q-001", "text": "Find papers about …" },
  "ground_truth": {
    "papers": [{ "paper_id": "arxiv:2401.00001", "title": "Example" }]
  }
}
```

`ground_truth` 只供 evaluator 使用。Runner 仅把 `AgentQuery(query_id,text,constraints,allowlisted metadata)` 传给 Agent；`raw`、`answer`、gold paper 不进入 worker/Agent artifact。最终 F1 只消费 `AgentResult.papers`；搜索树、候选池、query chain、图谱必须保存到每题 artifacts。

## 指标、产物与可比性

`canonical-v1` 依次使用同命名空间稳定 ID 和规范化标题精确匹配，并一对一去重。`scoring.py` 提供 P@K、R@K、MRR、nDCG 与 `structured-schema-v1`（机器可验证字段，不是语义 judge）。

每次运行写入 `results/<run_id>/manifest.json`、`predictions.jsonl`、`per_query_metrics.jsonl`、`errors.jsonl`、`summary.json/csv`、`report.html` 与 `artifacts/`。正式 run 还必须记录 dataset hash/split/query list、Git/upstream commit、模型/API revision、seed、缓存、预算、GPU/CUDA 与 unknown usage。只比较具有相同数据 hash、profile、模型版本与缓存策略的 runs。

## 三个系统

| 系统                  | 首轮                          | 详情                                             |
| --------------------- | ----------------------------- | ------------------------------------------------ |
| PaSa                  | Ubuntu 服务器                 | [PaSa 方案](docs/baselines/pasa.md)              |
| SPAR                  | 本机 API orchestration smoke  | [SPAR 方案](docs/baselines/spar.md)              |
| AI2 Asta Paper Finder | 本机 endpoint/connector smoke | [Asta 方案](docs/baselines/asta-paper-finder.md) |

共同门槛：离线 parser contract → 单 query online smoke → 固定公开集 formal protocol。安装成功或一次 API 请求不能称为完成复现。

## 新系统接入

1. 实现 `BaseAgent.setup/search(AgentQuery, AgentContext)/teardown`，模型/客户端在 setup 保持常驻。
2. 用 `context.tracker` 记录可观测 LLM/API usage，用 `context.artifacts_dir` 保存追踪。
3. 返回最终论文，树/图/链用专用 parser 和 artifact 保留。
4. 添加 config、public synthetic fixture、label-leakage、timeout、malformed-output 测试。
5. 先跑离线 contract，再跑 live smoke，最后锁定 formal protocol。

见 [评测协议](docs/evaluation-protocol.md) 和 [新系统手册](docs/new-system-guide.md)。

## 开发日志与文档同步

项目使用 [CHANGE_LOG.md](CHANGE_LOG.md) 的 Keep a Changelog 格式。在每项代码变更通过相应验证后，维护 **Unreleased** 段，并同步检查 `CLAUDE.md`、本 README 与 `AGENTS.md` 是否受影响。项目级 Claude Code hook 会在结束开发工作前提醒此流程。

顺序固定为：**实现 → 验证 → 文档/CHANGE_LOG → 审查 diff → 用户明确要求时才 Git commit**。项目不会自动创建 commit。

## 禁止提交与验证

禁止提交模型、HF token、Serper/API key、`.env`、gated dataset、paper DB、cache、upstream clone 和完整实验结果。真实 blocker 必须记入 manifest/report，不能伪造分数。

```bash
uv run python -m compileall -q src tests examples
uv run python -m unittest discover -s tests -v
git diff --check
```
