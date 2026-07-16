import unittest

from academic_agent_eval.evaluator import F1Evaluator
from academic_agent_eval.schemas import (
    AgentResult,
    BenchmarkCase,
    GroundTruth,
    Paper,
    Prediction,
    Query,
)


class F1EvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.case = BenchmarkCase(
            query=Query(query_id="q1", text="query"),
            ground_truth=GroundTruth(
                papers=[
                    Paper(title="Paper A", external_ids={"arxiv": "2301.00001"}),
                    Paper(title="Paper B"),
                ]
            ),
        )

    def test_id_and_title_matching_with_duplicate_removal(self) -> None:
        result = AgentResult(
            query_id="q1",
            papers=[
                Prediction(
                    Paper(title="Different metadata title", external_ids={"arxiv": "2301.00001v2"}),
                    rank=1,
                ),
                Prediction(Paper(title="Paper B!"), rank=2),
                Prediction(Paper(title="paper b"), rank=3),
                Prediction(Paper(title="Unrelated"), rank=4),
            ],
        )

        evaluation = F1Evaluator().evaluate_case(self.case, result)

        self.assertEqual(evaluation.true_positives, 2)
        self.assertEqual(evaluation.false_positives, 1)
        self.assertEqual(evaluation.false_negatives, 0)
        self.assertAlmostEqual(evaluation.precision, 2 / 3)
        self.assertEqual(evaluation.recall, 1.0)
        self.assertAlmostEqual(evaluation.f1, 0.8)

    def test_empty_prediction(self) -> None:
        evaluation = F1Evaluator().evaluate_case(
            self.case, AgentResult(query_id="q1", papers=[])
        )
        self.assertEqual((evaluation.precision, evaluation.recall, evaluation.f1), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
