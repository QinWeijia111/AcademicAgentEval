import json
import tempfile
import unittest
from pathlib import Path

from academic_agent_eval import (
    AgentQuery,
    BaseAgent,
    ExperimentRunner,
    JsonDataset,
    Paper,
    RunnerConfig,
)


class CapturingAgent(BaseAgent):
    name = "capturing"
    version = "1"

    def __init__(self) -> None:
        self.received: AgentQuery | None = None

    def search(self, query: AgentQuery, context):
        self.received = query
        return [Paper(title="Expected")]


class AgentQueryTest(unittest.TestCase):
    def test_from_query_excludes_raw_and_filters_metadata(self) -> None:
        from academic_agent_eval.schemas import Query

        query = Query(
            query_id="safe",
            text="Find papers",
            constraints={"year": 2024, "nested": {"gold": "never visible", "topic": "safe"}},
            metadata={"public": "yes", "answer": "gold"},
            raw={"answer": "sentinel"},
        )
        safe = AgentQuery.from_query(query, metadata_allowlist={"public"})

        self.assertEqual(
            safe.to_dict(),
            {
                "query_id": "safe",
                "text": "Find papers",
                "constraints": {"year": 2024, "nested": {"topic": "safe"}},
                "metadata": {"public": "yes"},
                "schema_version": "1.0",
            },
        )

    def test_runner_passes_sanitized_query_to_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "dataset.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "query": {
                            "query_id": "q1",
                            "text": "Safe query",
                            "metadata": {"answer": "never visible"},
                            "raw": {"answer": "sentinel"},
                        },
                        "ground_truth": {"papers": [{"title": "Expected"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            agent = CapturingAgent()
            ExperimentRunner(
                dataset=JsonDataset(path),
                agent=agent,
                config=RunnerConfig(output_dir=root / "results", run_id="safe"),
            ).run()

            self.assertIsInstance(agent.received, AgentQuery)
            self.assertEqual(agent.received.metadata, {})
            self.assertFalse(hasattr(agent.received, "raw"))


if __name__ == "__main__":
    unittest.main()
