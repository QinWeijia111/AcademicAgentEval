import unittest

from academic_agent_eval.integrations import parse_baseline_result


class IntegrationParserTest(unittest.TestCase):
    def test_pasa_parser_only_returns_selected_nodes(self) -> None:
        raw = {
            "tree": {
                "children": [
                    {"title": "Keep", "arxiv_id": "2401.00001", "select_score": 0.8},
                    {"title": "Discard", "select_score": 0.2},
                ]
            }
        }
        result = parse_baseline_result("pasa", "q1", raw, threshold=0.5)
        self.assertEqual([item.paper.title for item in result.papers], ["Keep"])
        self.assertIn("raw_result", result.artifacts)

    def test_spar_and_asta_drop_label_fields(self) -> None:
        spar = parse_baseline_result(
            "spar",
            "q1",
            {
                "final_papers": [
                    {
                        "title": "Safe",
                        "Answer": "leak",
                        "label": "gold",
                        "extra": {"Label": "nested leak", "safe": "yes"},
                        "score": 0.9,
                    }
                ]
            },
        )
        asta = parse_baseline_result(
            "asta-paper-finder",
            "q1",
            {"papers": [{"title": "Also safe", "ground_truth": "leak"}]},
        )
        self.assertEqual(spar.papers[0].paper.title, "Safe")
        self.assertNotIn("answer", spar.papers[0].paper.metadata)
        self.assertEqual(spar.papers[0].paper.metadata["extra"], {"safe": "yes"})
        self.assertEqual(asta.papers[0].paper.title, "Also safe")
        self.assertNotIn("ground_truth", asta.papers[0].paper.metadata)


if __name__ == "__main__":
    unittest.main()
