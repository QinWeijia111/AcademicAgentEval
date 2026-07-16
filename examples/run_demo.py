"""Run the evaluation core with a deterministic toy agent."""

from pathlib import Path

from academic_agent_eval import BaseAgent, ExperimentRunner, JsonDataset, Paper, RunnerConfig


class DemoAgent(BaseAgent):
    name = "demo-agent"
    version = "0.1"

    def search(self, query, context):
        context.tracker.record_api_call("demo-index")
        if query.query_id == "demo-001":
            return [
                Paper(
                    title="Reinforcement Learning for Language Model Agents",
                    external_ids={"arxiv": "2301.00001v2"},
                )
            ]
        return [Paper(title="An unrelated result")]


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = ExperimentRunner(
        dataset=JsonDataset(root / "examples" / "demo_dataset.jsonl", name="demo"),
        agent=DemoAgent(),
        config=RunnerConfig(output_dir=root / "results", experiment_name="demo"),
    ).run()
    print(f"run: {report.run_id}")
    print(f"macro F1: {report.summary.macro_f1:.4f}")
    print(f"report: {report.output_dir}")
