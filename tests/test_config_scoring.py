import json
import tempfile
import unittest
from pathlib import Path

from academic_agent_eval.config import ConfigError, load_config
from academic_agent_eval.scoring import ScoreProfile, ranking_metrics, structured_schema_score
from academic_agent_eval.schemas import AgentResult, Paper, Prediction


class ConfigAndScoringTest(unittest.TestCase):
    def test_load_config_redacts_secret_values_and_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "eval-config-v1",
                        "run": {"name": "smoke", "output_dir": "results", "seed": 7},
                        "dataset": {"adapter": "canonical-jsonl", "path": "fixture.jsonl"},
                        "agent": {
                            "kind": "external-process",
                            "command": ["python", "worker.py"],
                            "secret_env": ["API_KEY"],
                            "options": {"base_url_env": "API_BASE_URL"},
                        },
                        "scoring": {"profile": "local-proxy-v1"},
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.run.seed, 7)
            self.assertEqual(config.redacted_dict()["agent"]["secret_env"], ["API_KEY"])
            self.assertEqual(config.redacted_dict()["agent"]["command"]["argument_count"], 2)

            path.write_text('{"unknown": true}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_rejects_inline_credentials_in_commands_and_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            base = {
                "schema_version": "eval-config-v1",
                "run": {"name": "smoke", "output_dir": "results"},
                "dataset": {"adapter": "canonical-jsonl", "path": "fixture.jsonl"},
                "agent": {"kind": "external-process", "command": ["worker"]},
                "scoring": {"profile": "local-proxy-v1"},
            }
            for command in (
                ["worker", "--token=credential-value"],
                ["worker", "--api-key", "credential-value"],
                ["worker", "--header=Authorization: Bearer credential-value"],
            ):
                base["agent"]["command"] = command
                path.write_text(json.dumps(base), encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_config(path)
            base["agent"]["command"] = ["worker"]
            base["agent"]["options"] = {"credential": "credential-value"}
            path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_ranking_and_structured_schema_scores_are_deterministic(self) -> None:
        predictions = [
            Prediction(Paper(title="A"), rank=1, provenance={"source": "test"}),
            Prediction(Paper(title="B"), rank=2, provenance={"source": "test"}),
        ]
        metrics = ranking_metrics(predictions, {"a"}, (1, 2))
        self.assertEqual(metrics["precision_at_1"], 1.0)
        self.assertEqual(metrics["recall_at_2"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)

        result = AgentResult(
            query_id="q",
            papers=predictions,
            metadata={
                "structured_response": {
                    "format_version": "structured-v1",
                    "summary_sections": [{"title": "Findings", "text": "..."}],
                    "relations": [{"source_rank": 1, "target_rank": 2, "type": "related"}],
                }
            },
        )
        score = structured_schema_score(result)
        self.assertTrue(score.valid)
        self.assertEqual(score.score, 1.0)

        invalid = AgentResult(query_id="q", papers=predictions)
        self.assertFalse(structured_schema_score(invalid).valid)

    def test_profile_requires_competition_weights_to_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            ScoreProfile("bad", 0.7, 0.2, 0.2)


if __name__ == "__main__":
    unittest.main()
