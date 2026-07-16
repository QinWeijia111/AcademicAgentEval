import json
import tempfile
import unittest
from pathlib import Path

from academic_agent_eval import BaseAgent, ExperimentRunner, JsonDataset, Paper, RunnerConfig


class FixtureAgent(BaseAgent):
    name = "fixture"
    version = "1"

    def search(self, query, context):
        context.tracker.record_api_call("fixture-index")
        return [Paper(title="Expected Paper")]


class RunnerTest(unittest.TestCase):
    def test_query_id_cannot_escape_artifacts_directory(self) -> None:
        name = ExperimentRunner._safe_artifact_name("../../outside")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)

    def test_end_to_end_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset_path = root / "dataset.jsonl"
            dataset_path.write_text(
                json.dumps(
                    {
                        "query": {
                            "query_id": "q1",
                            "text": "query <script>alert('unsafe')</script>",
                        },
                        "ground_truth": {"papers": [{"title": "Expected Paper"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            report = ExperimentRunner(
                dataset=JsonDataset(dataset_path, name="fixture"),
                agent=FixtureAgent(),
                config=RunnerConfig(
                    output_dir=root / "results", experiment_name="test", run_id="fixed-run"
                ),
            ).run()

            self.assertEqual(report.summary.macro_f1, 1.0)
            self.assertEqual(report.summary.total_api_calls, 1)
            for filename in (
                "manifest.json",
                "predictions.jsonl",
                "per_query_metrics.jsonl",
                "errors.jsonl",
                "summary.json",
                "summary.csv",
                "report.html",
            ):
                self.assertTrue((report.output_dir / filename).is_file())

            html = (report.output_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("AcademicAgentEval", html)
            self.assertIn("Macro F1", html)
            self.assertIn("Expected Paper", html)
            self.assertIn("canonical-v1", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("<script>alert('unsafe')</script>", html)
            self.assertNotIn("{{QUERY_ROWS}}", html)


if __name__ == "__main__":
    unittest.main()
