"""Stable interface implemented by every paper-search agent adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from academic_agent_eval.schemas import Query
from academic_agent_eval.tracking import EfficiencyTracker


@dataclass(slots=True)
class AgentContext:
    """Per-query runtime services; it intentionally contains no ground truth."""

    run_id: str
    tracker: EfficiencyTracker
    artifacts_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Adapter boundary for PaSa, SPAR, Ai2, and future agents.

    ``search`` may return an AgentResult, a list of Paper objects, or a JSON-like
    mapping. The configured OutputParser converts that value to AgentResult.
    """

    name = "base"
    version = "unknown"

    def setup(self) -> None:
        """Allocate long-lived resources before the experiment starts."""

    @abstractmethod
    def search(self, query: Query, context: AgentContext) -> Any:
        """Search papers for one query without accessing ground truth."""

    def teardown(self) -> None:
        """Release long-lived resources after the experiment finishes."""
