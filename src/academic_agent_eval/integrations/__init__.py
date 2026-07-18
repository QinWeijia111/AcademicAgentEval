"""Dependency-free parsers for recorded PaSa, SPAR, and Asta outputs."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from academic_agent_eval.schemas import AgentResult, Paper, Prediction

_LABEL_FIELDS = {
    "answer",
    "answers",
    "gold",
    "ground_truth",
    "label",
    "labels",
    "relevance",
}


def parse_baseline_result(
    baseline: str, query_id: str, raw: Mapping[str, Any], *, threshold: float = 0.5
) -> AgentResult:
    """Normalize captured output without carrying evaluation label fields."""
    if baseline == "pasa":
        candidates = [node for node in _walk(raw.get("tree", raw)) if _selected(node, threshold)]
    elif baseline == "spar":
        candidates = _items(raw.get("final_papers", raw.get("papers", [])))
    elif baseline in {"asta", "asta-paper-finder", "ai2-paper-finder"}:
        candidates = _items(raw.get("papers", raw.get("results", [])))
    else:
        raise ValueError(f"unsupported baseline: {baseline}")
    return AgentResult(
        query_id=query_id,
        papers=[_prediction(item, rank) for rank, item in enumerate(candidates, 1)],
        metadata={"baseline": baseline, "raw_result_sanitized": True},
        artifacts={"raw_result": "raw_result.json"},
    )


def _items(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _walk(node: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(node, Mapping):
        return
    yield node
    for key in ("children", "nodes", "papers"):
        for child in _items(node.get(key, [])):
            yield from _walk(child)


def _selected(node: Mapping[str, Any], threshold: float) -> bool:
    score = node.get("select_score")
    return (
        isinstance(score, (int, float))
        and float(score) > threshold
        and bool(node.get("title") or node.get("paper_id") or node.get("arxiv_id"))
    )


def _strip_labels(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_labels(item)
            for key, item in value.items()
            if str(key).casefold() not in _LABEL_FIELDS
        }
    if isinstance(value, list):
        return [_strip_labels(item) for item in value]
    return value


def _prediction(item: Mapping[str, Any], rank: int) -> Prediction:
    item = _strip_labels(item)
    arxiv_id = item.get("arxiv_id")
    paper_id = item.get("paper_id") or (f"arxiv:{arxiv_id}" if arxiv_id else None)
    metadata = {
        str(key): _strip_labels(value)
        for key, value in item.items()
        if str(key).casefold() not in _LABEL_FIELDS
        and str(key) not in {"title", "paper_id", "arxiv_id", "score", "select_score", "rank"}
    }
    score = item.get("score", item.get("select_score"))
    return Prediction(
        Paper(
            title=str(item.get("title", "")),
            paper_id=str(paper_id) if paper_id else None,
            external_ids={"arxiv": str(arxiv_id)} if arxiv_id else {},
            metadata=metadata,
        ),
        int(item.get("rank", rank)),
        float(score) if isinstance(score, (int, float)) else None,
        provenance={"baseline": "captured-output"},
    )
