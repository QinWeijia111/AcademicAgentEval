"""Paper identity matching and set-based retrieval evaluation."""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from academic_agent_eval.schemas import AgentResult, BenchmarkCase, EfficiencyStats, Paper


def _normalize_identifier(value: str) -> str:
    value = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "arxiv:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    if "v" in value and re.fullmatch(r"\d{4}\.\d{4,5}v\d+", value):
        value = value.rsplit("v", 1)[0]
    return value


def normalize_title(title: str) -> str:
    """Normalize Unicode, case, punctuation, and whitespace for exact title fallback."""

    normalized = unicodedata.normalize("NFKC", title).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def paper_identifiers(paper: Paper) -> set[tuple[str, str]]:
    identifiers: set[tuple[str, str]] = set()
    for namespace, value in paper.external_ids.items():
        normalized = _normalize_identifier(value)
        if normalized:
            identifiers.add((namespace.casefold(), normalized))
    if paper.paper_id:
        value = paper.paper_id.strip()
        if ":" in value:
            namespace, identifier = value.split(":", 1)
            identifiers.add((namespace.casefold(), _normalize_identifier(identifier)))
        else:
            identifiers.add(("paper_id", _normalize_identifier(value)))
    return identifiers


@dataclass(slots=True)
class PaperMatch:
    predicted_rank: int
    predicted_title: str
    ground_truth_title: str
    method: str


class PaperMatcher:
    """Deterministic matcher: shared identifier first, normalized exact title second."""

    protocol = "canonical-v1"

    def match_method(self, predicted: Paper, expected: Paper) -> str | None:
        predicted_ids = paper_identifiers(predicted)
        expected_ids = paper_identifiers(expected)
        shared_ids = predicted_ids & expected_ids
        if shared_ids:
            namespace = sorted(shared_ids)[0][0]
            return f"{namespace}_exact"
        predicted_title = normalize_title(predicted.title)
        expected_title = normalize_title(expected.title)
        if predicted_title and predicted_title == expected_title:
            return "title_exact"
        return None

    def equivalent(self, left: Paper, right: Paper) -> bool:
        return self.match_method(left, right) is not None


@dataclass(slots=True)
class QueryEvaluation:
    query_id: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    prediction_count: int
    ground_truth_count: int
    matches: list[PaperMatch] = field(default_factory=list)
    usage: EfficiencyStats = field(default_factory=EfficiencyStats)
    status: str = "success"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["usage"] = self.usage.to_dict()
        return result


@dataclass(slots=True)
class EvaluationSummary:
    query_count: int
    successful_queries: int
    failed_queries: int
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_llm_calls: int
    total_api_calls: int
    total_tokens: int
    total_estimated_cost_usd: float | None
    matching_protocol: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class F1Evaluator:
    """Evaluate final paper sets independently of any concrete agent."""

    def __init__(self, matcher: PaperMatcher | None = None) -> None:
        self.matcher = matcher or PaperMatcher()

    def evaluate_case(self, case: BenchmarkCase, result: AgentResult) -> QueryEvaluation:
        predictions = self._deduplicate([item.paper for item in result.papers])
        ground_truth = self._deduplicate(case.ground_truth.papers)
        unmatched_ground_truth = set(range(len(ground_truth)))
        matches: list[PaperMatch] = []

        for rank, predicted in enumerate(predictions, start=1):
            for ground_truth_index in sorted(unmatched_ground_truth):
                expected = ground_truth[ground_truth_index]
                method = self.matcher.match_method(predicted, expected)
                if method is None:
                    continue
                matches.append(
                    PaperMatch(
                        predicted_rank=rank,
                        predicted_title=predicted.title,
                        ground_truth_title=expected.title,
                        method=method,
                    )
                )
                unmatched_ground_truth.remove(ground_truth_index)
                break

        true_positives = len(matches)
        false_positives = len(predictions) - true_positives
        false_negatives = len(ground_truth) - true_positives
        precision, recall, f1 = self._scores(true_positives, false_positives, false_negatives)
        return QueryEvaluation(
            query_id=case.query.query_id,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1=f1,
            prediction_count=len(predictions),
            ground_truth_count=len(ground_truth),
            matches=matches,
            usage=result.usage,
            status=result.status,
            error=result.error,
        )

    def aggregate(self, evaluations: list[QueryEvaluation]) -> EvaluationSummary:
        if not evaluations:
            raise ValueError("cannot aggregate an empty evaluation list")
        true_positives = sum(item.true_positives for item in evaluations)
        false_positives = sum(item.false_positives for item in evaluations)
        false_negatives = sum(item.false_negatives for item in evaluations)
        micro_precision, micro_recall, micro_f1 = self._scores(
            true_positives, false_positives, false_negatives
        )
        latencies = [item.usage.latency_ms for item in evaluations]
        costs = [
            item.usage.estimated_cost_usd
            for item in evaluations
            if item.usage.estimated_cost_usd is not None
        ]
        failed = sum(item.status != "success" for item in evaluations)
        return EvaluationSummary(
            query_count=len(evaluations),
            successful_queries=len(evaluations) - failed,
            failed_queries=failed,
            macro_precision=statistics.fmean(item.precision for item in evaluations),
            macro_recall=statistics.fmean(item.recall for item in evaluations),
            macro_f1=statistics.fmean(item.f1 for item in evaluations),
            micro_precision=micro_precision,
            micro_recall=micro_recall,
            micro_f1=micro_f1,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            mean_latency_ms=statistics.fmean(latencies),
            p50_latency_ms=self._percentile(latencies, 0.50),
            p95_latency_ms=self._percentile(latencies, 0.95),
            total_llm_calls=sum(item.usage.llm_calls for item in evaluations),
            total_api_calls=sum(item.usage.api_calls for item in evaluations),
            total_tokens=sum(item.usage.total_tokens for item in evaluations),
            total_estimated_cost_usd=sum(costs) if costs else None,
            matching_protocol=self.matcher.protocol,
        )

    def _deduplicate(self, papers: list[Paper]) -> list[Paper]:
        unique: list[Paper] = []
        for paper in papers:
            if not any(self.matcher.equivalent(paper, existing) for existing in unique):
                unique.append(paper)
        return unique

    @staticmethod
    def _scores(
        true_positives: int, false_positives: int, false_negatives: int
    ) -> tuple[float, float, float]:
        precision_denominator = true_positives + false_positives
        recall_denominator = true_positives + false_negatives
        precision = true_positives / precision_denominator if precision_denominator else 0.0
        recall = true_positives / recall_denominator if recall_denominator else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return precision, recall, f1

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        weight = position - lower
        return ordered[lower] * (1 - weight) + ordered[upper] * weight
