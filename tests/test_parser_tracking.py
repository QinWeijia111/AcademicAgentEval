import time
import unittest

from academic_agent_eval.parsers import DefaultOutputParser, OutputParseError
from academic_agent_eval.schemas import Query
from academic_agent_eval.tracking import EfficiencyTracker


class ParserAndTrackingTest(unittest.TestCase):
    def test_parses_list_and_normalizes_rank(self) -> None:
        result = DefaultOutputParser().parse(
            [{"title": "Second", "rank": 8}, {"title": "First", "rank": 3}],
            Query(query_id="q1", text="query"),
        )
        self.assertEqual([item.rank for item in result.papers], [1, 2])
        self.assertEqual([item.paper.title for item in result.papers], ["First", "Second"])

    def test_rejects_mismatched_query_id(self) -> None:
        with self.assertRaisesRegex(OutputParseError, "query_id mismatch"):
            DefaultOutputParser().parse(
                {"query_id": "wrong", "papers": []}, Query(query_id="q1", text="query")
            )

    def test_parses_mapping_with_title_strings(self) -> None:
        result = DefaultOutputParser().parse(
            {"query_id": "q1", "papers": ["Paper A"]},
            Query(query_id="q1", text="query"),
        )
        self.assertEqual(result.papers[0].paper.title, "Paper A")

    def test_tracks_usage_and_latency(self) -> None:
        tracker = EfficiencyTracker()
        with tracker.measure():
            tracker.record_llm_call(prompt_tokens=10, completion_tokens=2, provider="llm")
            tracker.record_api_call("arxiv", count=2)
            time.sleep(0.001)
        usage = tracker.snapshot()

        self.assertEqual(usage.llm_calls, 1)
        self.assertEqual(usage.api_calls, 2)
        self.assertEqual(usage.total_tokens, 12)
        self.assertEqual(usage.llm_calls_by_provider, {"llm": 1})
        self.assertEqual(usage.api_calls_by_provider, {"arxiv": 2})
        self.assertGreater(usage.latency_ms, 0)


if __name__ == "__main__":
    unittest.main()
