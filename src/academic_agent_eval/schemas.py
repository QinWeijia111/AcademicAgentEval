"""Serializable data contracts shared by datasets, agents, and evaluators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


@dataclass(slots=True)
class Query:
    query_id: str
    text: str
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.query_id.strip():
            raise ValueError("query_id must not be empty")
        if not self.text.strip():
            raise ValueError("query text must not be empty")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Query:
        return cls(
            query_id=str(data["query_id"]),
            text=str(data["text"]),
            constraints=dict(data.get("constraints") or {}),
            metadata=dict(data.get("metadata") or {}),
            raw=dict(data.get("raw") or {}),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentQuery:
    """Safe query projection visible to agents and external workers only."""

    query_id: str
    text: str
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_query(cls, query: Query, *, metadata_allowlist: set[str] | None = None) -> AgentQuery:
        allowed = metadata_allowlist or set()
        return cls(
            query_id=query.query_id,
            text=query.text,
            constraints=_public_mapping(query.constraints),
            metadata=_public_mapping(
                {key: value for key, value in query.metadata.items() if key in allowed}
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SENSITIVE_QUERY_FIELDS = {
    "answer",
    "answers",
    "gold",
    "ground_truth",
    "label",
    "labels",
    "relevance",
}


def _public_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only query-safe values, recursively dropping evaluation label fields."""

    return {
        str(key): _public_value(item)
        for key, item in value.items()
        if str(key).casefold() not in _SENSITIVE_QUERY_FIELDS
    }


def _public_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _public_mapping(value)
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, tuple):
        return [_public_value(item) for item in value]
    return value


@dataclass(slots=True)
class Paper:
    title: str
    paper_id: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    url: str | None = None
    citation_count: int | None = None
    references: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.title.strip() and not self.paper_id:
            raise ValueError("paper requires at least a title or paper_id")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Paper:
        external_ids = {
            str(key): str(value)
            for key, value in (data.get("external_ids") or {}).items()
            if value is not None and str(value).strip()
        }
        raw_authors = data.get("authors") or []
        if isinstance(raw_authors, str):
            raw_authors = [raw_authors]
        authors = [
            str(author.get("name", "")) if isinstance(author, Mapping) else str(author)
            for author in raw_authors
        ]
        return cls(
            paper_id=str(data["paper_id"]) if data.get("paper_id") is not None else None,
            external_ids=external_ids,
            title=str(data.get("title", "")),
            authors=[author for author in authors if author],
            year=int(data["year"]) if data.get("year") is not None else None,
            abstract=data.get("abstract"),
            venue=data.get("venue"),
            url=data.get("url"),
            citation_count=(
                int(data["citation_count"]) if data.get("citation_count") is not None else None
            ),
            references=[str(item) for item in data.get("references") or []],
            citations=[str(item) for item in data.get("citations") or []],
            metadata=dict(data.get("metadata") or {}),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GroundTruth:
    papers: list[Paper]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GroundTruth:
        papers: list[Paper] = []
        for item in data.get("papers") or []:
            if isinstance(item, str):
                papers.append(Paper(title=item))
                continue
            item = _mapping(item, "ground_truth.papers[]")
            paper_data = item.get("paper", item)
            relevance = item.get("relevance", 1)
            if relevance is None or float(relevance) > 0:
                papers.append(Paper.from_dict(_mapping(paper_data, "paper")))
        return cls(papers=papers, metadata=dict(data.get("metadata") or {}))

    def to_dict(self) -> dict[str, Any]:
        return {"papers": [paper.to_dict() for paper in self.papers], "metadata": self.metadata}


@dataclass(slots=True)
class BenchmarkCase:
    query: Query
    ground_truth: GroundTruth
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BenchmarkCase:
        return cls(
            query=Query.from_dict(_mapping(data["query"], "query")),
            ground_truth=GroundTruth.from_dict(
                _mapping(data.get("ground_truth", {"papers": []}), "ground_truth")
            ),
            metadata=dict(data.get("metadata") or {}),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "query": self.query.to_dict(),
            "ground_truth": self.ground_truth.to_dict(),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Prediction:
    paper: Paper
    rank: int
    score: float | None = None
    reason: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("prediction rank must be >= 1")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], default_rank: int) -> Prediction:
        paper_data = data.get("paper", data)
        return cls(
            paper=Paper.from_dict(_mapping(paper_data, "prediction.paper")),
            rank=int(data.get("rank", default_rank)),
            score=float(data["score"]) if data.get("score") is not None else None,
            reason=data.get("reason"),
            provenance=dict(data.get("provenance") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper": self.paper.to_dict(),
            "rank": self.rank,
            "score": self.score,
            "reason": self.reason,
            "provenance": self.provenance,
        }


@dataclass(slots=True)
class EfficiencyStats:
    latency_ms: float = 0.0
    llm_calls: int = 0
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost_usd: float | None = None
    llm_calls_by_provider: dict[str, int] = field(default_factory=dict)
    api_calls_by_provider: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["total_tokens"] = self.total_tokens
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> EfficiencyStats:
        data = data or {}
        llm = data.get("llm") if isinstance(data.get("llm"), Mapping) else data
        retrieval = data.get("retrieval") if isinstance(data.get("retrieval"), Mapping) else data
        return cls(
            latency_ms=float(data.get("latency_ms", 0.0)),
            llm_calls=int(llm.get("calls", data.get("llm_calls", 0))),
            api_calls=int(retrieval.get("api_calls", data.get("api_calls", 0))),
            prompt_tokens=int(llm.get("prompt_tokens", data.get("prompt_tokens", 0))),
            completion_tokens=int(llm.get("completion_tokens", data.get("completion_tokens", 0))),
            cached_tokens=int(llm.get("cached_tokens", data.get("cached_tokens", 0))),
            estimated_cost_usd=(
                float(llm.get("estimated_cost_usd", data.get("estimated_cost_usd")))
                if llm.get("estimated_cost_usd", data.get("estimated_cost_usd")) is not None
                else None
            ),
            llm_calls_by_provider={
                str(key): int(value) for key, value in llm.get("calls_by_provider", {}).items()
            },
            api_calls_by_provider={
                str(key): int(value)
                for key, value in retrieval.get(
                    "calls_by_provider", data.get("api_calls_by_provider", {})
                ).items()
            },
        )


@dataclass(slots=True)
class AgentResult:
    query_id: str
    papers: list[Prediction]
    usage: EfficiencyStats = field(default_factory=EfficiencyStats)
    status: str = "success"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], query_id: str | None = None) -> AgentResult:
        resolved_query_id = str(data.get("query_id") or query_id or "")
        if not resolved_query_id:
            raise ValueError("agent result requires query_id")
        raw_papers = data.get("papers", data.get("results", [])) or []
        predictions: list[Prediction] = []
        for index, item in enumerate(raw_papers, start=1):
            if isinstance(item, Prediction):
                predictions.append(item)
            elif isinstance(item, Paper):
                predictions.append(Prediction(paper=item, rank=index))
            elif isinstance(item, str):
                predictions.append(Prediction(paper=Paper(title=item), rank=index))
            else:
                predictions.append(
                    Prediction.from_dict(_mapping(item, "papers[]"), default_rank=index)
                )
        return cls(
            query_id=resolved_query_id,
            papers=predictions,
            usage=EfficiencyStats.from_dict(data.get("usage")),
            status=str(data.get("status", "success")),
            error=data.get("error"),
            metadata=dict(data.get("metadata") or {}),
            artifacts={
                str(key): str(value) for key, value in (data.get("artifacts") or {}).items()
            },
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "query_id": self.query_id,
            "papers": [prediction.to_dict() for prediction in self.papers],
            "usage": self.usage.to_dict(),
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
            "artifacts": self.artifacts,
        }
