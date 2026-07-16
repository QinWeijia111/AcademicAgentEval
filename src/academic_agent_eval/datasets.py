"""Dataset abstractions and loaders for the canonical benchmark format."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Mapping

from academic_agent_eval.schemas import BenchmarkCase


class DatasetError(ValueError):
    """Raised when a benchmark file violates the canonical data contract."""


class BaseDataset(ABC, Sequence[BenchmarkCase]):
    """Read-only sequence of normalized benchmark cases."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable dataset name."""

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __getitem__(self, index: int) -> BenchmarkCase: ...

    def __iter__(self) -> Iterator[BenchmarkCase]:
        for index in range(len(self)):
            yield self[index]


class JsonDataset(BaseDataset):
    """Load canonical benchmark cases from JSON or JSONL.

    JSON files may contain a top-level list or ``{"cases": [...]}``. JSONL files
    contain one benchmark case per non-empty line.
    """

    def __init__(self, path: str | Path, *, name: str | None = None) -> None:
        self.path = Path(path)
        self._name = name or self.path.stem
        self._cases = self._load()
        self._validate_unique_query_ids()

    @property
    def name(self) -> str:
        return self._name

    def __len__(self) -> int:
        return len(self._cases)

    def __getitem__(self, index: int) -> BenchmarkCase:
        return self._cases[index]

    def _load(self) -> list[BenchmarkCase]:
        if not self.path.is_file():
            raise DatasetError(f"dataset file does not exist: {self.path}")

        try:
            if self.path.suffix.lower() == ".jsonl":
                records = self._read_jsonl()
            elif self.path.suffix.lower() == ".json":
                records = self._read_json()
            else:
                raise DatasetError("dataset must use .json or .jsonl")
            return [BenchmarkCase.from_dict(record) for record in records]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, DatasetError):
                raise
            raise DatasetError(f"invalid dataset {self.path}: {exc}") from exc

    def _read_jsonl(self) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DatasetError(
                        f"invalid JSON at {self.path}:{line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(value, Mapping):
                    raise DatasetError(f"record at line {line_number} must be a JSON object")
                records.append(value)
        return records

    def _read_json(self) -> list[Mapping[str, Any]]:
        with self.path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, Mapping):
            value = value.get("cases")
        if not isinstance(value, list):
            raise DatasetError("JSON dataset must be a list or an object containing 'cases'")
        if not all(isinstance(item, Mapping) for item in value):
            raise DatasetError("every dataset record must be a JSON object")
        return value

    def _validate_unique_query_ids(self) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for case in self._cases:
            if case.query.query_id in seen:
                duplicates.add(case.query.query_id)
            seen.add(case.query.query_id)
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise DatasetError(f"duplicate query_id values: {joined}")
