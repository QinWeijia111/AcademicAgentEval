import json
import tempfile
import unittest
from pathlib import Path

from academic_agent_eval.datasets import DatasetError, JsonDataset


def case(query_id: str) -> dict:
    return {
        "query": {"query_id": query_id, "text": "test query"},
        "ground_truth": {"papers": [{"title": "Expected Paper"}]},
    }


class JsonDatasetTest(unittest.TestCase):
    def test_loads_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            path.write_text(json.dumps(case("q1")) + "\n", encoding="utf-8")
            dataset = JsonDataset(path, name="fixture")

            self.assertEqual(dataset.name, "fixture")
            self.assertEqual(len(dataset), 1)
            self.assertEqual(dataset[0].query.query_id, "q1")

    def test_rejects_duplicate_query_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(json.dumps([case("q1"), case("q1")]), encoding="utf-8")

            with self.assertRaisesRegex(DatasetError, "duplicate query_id"):
                JsonDataset(path)


if __name__ == "__main__":
    unittest.main()
