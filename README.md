# AcademicAgentEval

AcademicAgentEval 是一个面向学术论文搜索 Agent 的统一评测框架。当前 `v0.1`
只包含 Evaluation Core，不实现 PaSa、SPAR 或 Ai2 Paper Finder。

框架通过三个稳定边界实现解耦：

```text
canonical dataset -> BaseAgent -> OutputParser -> F1Evaluator -> reports
```

Evaluator 只依赖统一的 `BenchmarkCase` 和 `AgentResult`，因此未来的 Agent
只需实现 `BaseAgent.search()`，或额外提供专用的 `BaseOutputParser`。

## 当前功能

- JSON/JSONL Benchmark Loader，并校验统一数据格式和 Query ID 唯一性。
- 面向 PaSa、SPAR、Ai2 和自研 Agent 的统一 `BaseAgent` 接口。
- 支持标准结果、论文列表和 JSON 映射的 Output Parser。
- 基于论文 ID 与规范化标题的 Precision、Recall、F1 评测。
- Macro/Micro 指标和逐 Query 匹配明细。
- LLM 调用、检索 API、Token、成本和端到端延迟统计。
- 实验 Runner，以及 JSON、JSONL、CSV、HTML 自动报告。
- Agent 异常隔离：单 Query 失败不会丢失整个实验结果。

## 环境

项目使用 `uv` 管理，运行时没有第三方依赖。

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

支持 Python 3.10 及以上版本。

## 统一 Benchmark 格式

JSONL 文件每行表示一个查询：

```json
{
  "schema_version": "1.0",
  "query": {
    "query_id": "demo-001",
    "text": "Find papers about reinforcement learning for LLM agents",
    "constraints": {"published_after": 2022},
    "metadata": {},
    "raw": {}
  },
  "ground_truth": {
    "papers": [
      {
        "paper_id": "arxiv:2301.00001",
        "external_ids": {"arxiv": "2301.00001"},
        "title": "Reinforcement Learning for Language Model Agents",
        "authors": ["Alice Example"],
        "year": 2023
      }
    ]
  },
  "metadata": {"dataset": "demo", "split": "test"}
}
```

可参考 [examples/demo_dataset.jsonl](examples/demo_dataset.jsonl)。原始 Benchmark
如 RealScholarQuery 应由独立 Dataset Adapter 转换到该格式，不能让 Evaluator
直接依赖原始字段。

## 接入一个 Agent

Agent 只接收 Query 和不含 Ground Truth 的运行上下文：

```python
from academic_agent_eval import BaseAgent, Paper


class MyAgent(BaseAgent):
    name = "my-agent"
    version = "0.1"

    def search(self, query, context):
        context.tracker.record_llm_call(
            prompt_tokens=100,
            completion_tokens=20,
            provider="example-llm",
        )
        context.tracker.record_api_call("arxiv")
        return [
            Paper(
                paper_id="arxiv:2301.00001",
                external_ids={"arxiv": "2301.00001"},
                title="Reinforcement Learning for Language Model Agents",
            )
        ]
```

允许的返回值包括：

- `AgentResult`
- `list[Paper]`
- `list[Prediction]`
- 标准 JSON Mapping，论文数组字段名为 `papers` 或 `results`

PaSa 搜索树、SPAR 查询链等非标准输出应由各自的 Output Parser 转换，原始轨迹
可以写入 `context.artifacts_dir`。

## 运行实验

```python
from pathlib import Path

from academic_agent_eval import ExperimentRunner, JsonDataset, RunnerConfig

dataset = JsonDataset("examples/demo_dataset.jsonl", name="demo")
runner = ExperimentRunner(
    dataset=dataset,
    agent=MyAgent(),
    config=RunnerConfig(
        output_dir=Path("results"),
        experiment_name="my-agent-demo",
    ),
)
report = runner.run()
print(report.summary.macro_f1)
```

也可以直接运行完整示例：

```bash
uv run python examples/run_demo.py
```

每次实验生成独立目录：

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

`report.html` 是无需联网即可打开的自包含报告，提供总体指标卡、Macro/Micro
对比、TP/FP/FN、延迟与调用成本，以及支持搜索和状态筛选的逐 Query 明细。

## 论文匹配协议

当前协议为 `canonical-v1`，按以下顺序匹配：

1. DOI、ArXiv 等相同命名空间的标准化 ID 完全一致。
2. Unicode、大小写、标点和空白规范化后的标题完全一致。

匹配是一对一的；重复 Prediction 在计算指标前会去重。当前版本不使用模糊标题
阈值，以避免评测结果随算法或阈值变化。后续协议变更必须使用新的协议版本。

## 为外部 Agent 扩展

- `PaSaAgent`：实现 `BaseAgent`，返回搜索树；由 `PaSaOutputParser` 提取最终论文。
- `SPARAgent`：保留 Query Evolution 轨迹到 artifacts，返回标准结果。
- `Ai2Agent`：保留 Citation Graph 到 artifacts，返回标准结果。

三者均不需要修改 Dataset Loader、Evaluator 或 Experiment Runner。
