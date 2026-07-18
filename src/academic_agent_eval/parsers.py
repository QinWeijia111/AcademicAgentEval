"""Normalize heterogeneous agent outputs into the canonical AgentResult."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from academic_agent_eval.schemas import AgentResult, Paper, Prediction, Query


class OutputParseError(ValueError):
    """Raised when agent output cannot be converted safely."""


class BaseOutputParser(ABC):
    @abstractmethod
    def parse(self, raw_output: Any, query: Query) -> AgentResult: ...


class DefaultOutputParser(BaseOutputParser):
    """Parser for canonical results, paper lists, and common JSON mappings."""

    def parse(self, raw_output: Any, query: Query) -> AgentResult:
        try:
            if isinstance(raw_output, AgentResult):
                result = raw_output
            elif isinstance(raw_output, Mapping):
                result = AgentResult.from_dict(raw_output, query_id=query.query_id)
            elif self._is_sequence(raw_output):
                result = AgentResult(
                    query_id=query.query_id,
                    papers=[
                        self._parse_item(item, rank) for rank, item in enumerate(raw_output, 1)
                    ],
                )
            else:
                raise OutputParseError(f"unsupported output type: {type(raw_output).__name__}")
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, OutputParseError):
                raise
            raise OutputParseError(f"invalid agent output: {exc}") from exc

        if result.query_id != query.query_id:
            raise OutputParseError(
                f"query_id mismatch: expected {query.query_id!r}, got {result.query_id!r}"
            )
        self._normalize_ranks(result)
        return result

    @staticmethod
    def _is_sequence(value: Any) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))

    @staticmethod
    def _parse_item(item: Any, rank: int) -> Prediction:
        if isinstance(item, Prediction):
            return item
        if isinstance(item, Paper):
            return Prediction(paper=item, rank=rank)
        if isinstance(item, str):
            return Prediction(paper=Paper(title=item), rank=rank)
        if isinstance(item, Mapping):
            return Prediction.from_dict(item, default_rank=rank)
        raise OutputParseError(f"unsupported paper item type: {type(item).__name__}")

    @staticmethod
    def _normalize_ranks(result: AgentResult) -> None:
        result.papers.sort(key=lambda item: item.rank)
        ranks = [item.rank for item in result.papers]
        if len(ranks) != len(set(ranks)):
            raise OutputParseError("prediction ranks must be unique")
        for expected_rank, prediction in enumerate(result.papers, start=1):
            prediction.rank = expected_rank
