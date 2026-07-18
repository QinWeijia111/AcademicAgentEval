"""Explicit conversion helpers for supported public benchmark formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from academic_agent_eval.datasets import BaseDataset, JsonDataset
from academic_agent_eval.schemas import BenchmarkCase, GroundTruth, Paper, Query


class ConvertedDataset(BaseDataset):
    def __init__(self, cases: list[BenchmarkCase], name: str) -> None:
        self._cases = cases
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def __len__(self) -> int:
        return len(self._cases)

    def __getitem__(self, index: int) -> BenchmarkCase:
        return self._cases[index]


def realscholar_case(record: Mapping[str, Any], index: int = 0) -> BenchmarkCase:
    text = _string(record.get("question") or record.get("query"), "question")
    query_id = str(record.get("id") or record.get("query_id") or f"realscholar-{index:04d}")
    answers = record.get("answer") or record.get("answers") or []
    return BenchmarkCase(
        Query(
            query_id=query_id,
            text=text,
            metadata={key: value for key, value in record.items() if key == "source_meta"},
        ),
        GroundTruth([_paper(item) for item in answers if isinstance(item, Mapping)]),
        {"dataset": "realscholarquery", "conversion": "realscholar-v1"},
    )


def sparbench_case(record: Mapping[str, Any], index: int = 0) -> BenchmarkCase:
    text = _string(record.get("question") or record.get("query"), "question")
    query_id = str(record.get("id") or record.get("query_id") or f"sparbench-{index:04d}")
    candidates = record.get("papers") or record.get("documents") or record.get("answer") or []
    papers = [
        _paper(item)
        for item in candidates
        if isinstance(item, Mapping) and float(item.get("relevance", item.get("label", 1)) or 0) > 0
    ]
    return BenchmarkCase(
        Query(query_id=query_id, text=text),
        GroundTruth(papers),
        {"dataset": "sparbench", "conversion": "sparbench-v1"},
    )


def load_dataset(path: str | Path, adapter: str, *, max_cases: int | None = None) -> BaseDataset:
    """Load a canonical or supported raw JSON/JSONL benchmark with an explicit adapter."""

    if adapter == "canonical-jsonl":
        dataset: BaseDataset = JsonDataset(path, name=adapter)
        return _limited(dataset, max_cases)
    converters: dict[str, Callable[[Mapping[str, Any], int], BenchmarkCase]] = {
        "realscholarquery": realscholar_case,
        "sparbench": sparbench_case,
    }
    if adapter not in converters:
        raise ValueError(f"unsupported dataset adapter: {adapter}")
    source = Path(path)
    records = _read_records(source)
    cases = [converters[adapter](record, index) for index, record in enumerate(records)]
    if max_cases is not None:
        cases = cases[:max_cases]
    return ConvertedDataset(cases, adapter)


def _limited(dataset: BaseDataset, max_cases: int | None) -> BaseDataset:
    if max_cases is None:
        return dataset
    return ConvertedDataset(
        [dataset[index] for index in range(min(len(dataset), max_cases))], dataset.name
    )


def _read_records(path: Path) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif path.suffix == ".json":
        values = json.loads(text)
        if isinstance(values, Mapping):
            values = values.get("cases", values.get("records", []))
    else:
        raise ValueError("raw benchmark path must end in .json or .jsonl")
    if not isinstance(values, list) or not all(isinstance(value, Mapping) for value in values):
        raise ValueError("raw benchmark must contain JSON objects")
    return values


def _paper(value: Mapping[str, Any]) -> Paper:
    ids = dict(value.get("external_ids") or {})
    for key in ("arxiv", "arxiv_id", "doi", "openalex", "semantic_scholar"):
        if value.get(key):
            ids.setdefault(key.replace("_id", ""), str(value[key]))
    return Paper(
        title=str(value.get("title", "")),
        paper_id=str(value["paper_id"]) if value.get("paper_id") else None,
        external_ids={str(key): str(item) for key, item in ids.items()},
        year=int(value["year"]) if value.get("year") is not None else None,
    )


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value
