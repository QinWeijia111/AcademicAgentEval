"""Versioned local scoring helpers; none of these values are official contest scores."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from academic_agent_eval.evaluator import normalize_title
from academic_agent_eval.schemas import AgentResult, Prediction


@dataclass(frozen=True, slots=True)
class ScoreProfile:
    profile_id: str
    quality_weight: float = 0.7
    efficiency_weight: float = 0.2
    structure_weight: float = 0.1
    official_score: bool = False

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be empty")
        if any(weight < 0 for weight in self.weights):
            raise ValueError("score weights must be non-negative")
        if not math.isclose(sum(self.weights), 1.0, abs_tol=1e-9):
            raise ValueError("score weights must sum to 1")

    @property
    def weights(self) -> tuple[float, float, float]:
        return self.quality_weight, self.efficiency_weight, self.structure_weight


@dataclass(frozen=True, slots=True)
class StructuredSchemaScore:
    valid: bool
    score: float
    errors: tuple[str, ...]
    protocol: str = "structured-schema-v1"


def ranking_metrics(
    predictions: Iterable[Prediction],
    relevant_titles: set[str],
    cutoffs: Iterable[int] = (1, 5, 10),
) -> dict[str, float]:
    ranked = sorted(enumerate(predictions), key=lambda item: (item[1].rank, item[0]))
    relevant = {normalize_title(title) for title in relevant_titles}
    matched = [normalize_title(item.paper.title) in relevant for _, item in ranked]
    result: dict[str, float] = {}
    for cutoff in sorted(set(cutoffs)):
        if cutoff < 1:
            raise ValueError("cutoffs must be >= 1")
        hits, denominator = sum(matched[:cutoff]), min(cutoff, len(matched))
        result[f"precision_at_{cutoff}"] = hits / denominator if denominator else 0.0
        result[f"recall_at_{cutoff}"] = hits / len(relevant) if relevant else 0.0
        ideal = min(cutoff, len(relevant))
        dcg = sum(1 / math.log2(index + 2) for index, hit in enumerate(matched[:cutoff]) if hit)
        ideal_dcg = sum(1 / math.log2(index + 2) for index in range(ideal))
        result[f"ndcg_at_{cutoff}"] = dcg / ideal_dcg if ideal_dcg else 0.0
    first = next((index + 1 for index, hit in enumerate(matched) if hit), None)
    result["mrr"] = 1 / first if first else 0.0
    return result


def structured_schema_score(result: AgentResult) -> StructuredSchemaScore:
    response = result.metadata.get("structured_response")
    if not isinstance(response, dict):
        return StructuredSchemaScore(False, 0.0, ("missing structured_response",))
    errors: list[str] = []
    if response.get("format_version") != "structured-v1":
        errors.append("format_version must be structured-v1")
    ranks = {item.rank for item in result.papers}
    if not result.papers or ranks != set(range(1, len(result.papers) + 1)):
        errors.append("final papers require contiguous ranks")
    if any(
        not (item.paper.title or item.paper.paper_id) or not item.provenance
        for item in result.papers
    ):
        errors.append("each paper requires identity and provenance")
    sections = response.get("summary_sections", [])
    if not isinstance(sections, list) or any(
        not isinstance(item, dict) or not item.get("title") or not item.get("text")
        for item in sections
    ):
        errors.append("summary_sections must contain title and text")
    relations = response.get("relations", [])
    if not isinstance(relations, list):
        errors.append("relations must be an array")
    elif any(
        not isinstance(item, dict)
        or item.get("source_rank") not in ranks
        or item.get("target_rank") not in ranks
        or not item.get("type")
        for item in relations
    ):
        errors.append("relations must reference ranks and have type")
    return StructuredSchemaScore(not errors, 1.0 if not errors else 0.0, tuple(errors))
