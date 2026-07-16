"""Thread-safe accounting for LLM, retrieval, token, cost, and latency usage."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator

from academic_agent_eval.schemas import EfficiencyStats


class EfficiencyTracker:
    """Per-query usage collector passed to agent adapters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at: float | None = None
        self._elapsed_ms = 0.0
        self._llm_calls = 0
        self._api_calls = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._cached_tokens = 0
        self._estimated_cost_usd = 0.0
        self._has_cost = False
        self._llm_calls_by_provider: dict[str, int] = {}
        self._api_calls_by_provider: dict[str, int] = {}

    def start(self) -> None:
        if self._started_at is not None:
            raise RuntimeError("tracker is already running")
        self._started_at = time.perf_counter()

    def stop(self) -> float:
        if self._started_at is None:
            raise RuntimeError("tracker is not running")
        self._elapsed_ms += (time.perf_counter() - self._started_at) * 1000
        self._started_at = None
        return self._elapsed_ms

    @contextmanager
    def measure(self) -> Iterator[EfficiencyTracker]:
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def record_llm_call(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        estimated_cost_usd: float | None = None,
        provider: str | None = None,
    ) -> None:
        values = (prompt_tokens, completion_tokens, cached_tokens)
        if any(value < 0 for value in values):
            raise ValueError("token counts must be non-negative")
        with self._lock:
            self._llm_calls += 1
            self._prompt_tokens += prompt_tokens
            self._completion_tokens += completion_tokens
            self._cached_tokens += cached_tokens
            if estimated_cost_usd is not None:
                if estimated_cost_usd < 0:
                    raise ValueError("estimated cost must be non-negative")
                self._estimated_cost_usd += estimated_cost_usd
                self._has_cost = True
            if provider:
                self._increment_provider(self._llm_calls_by_provider, provider)

    def record_api_call(self, provider: str = "unknown", *, count: int = 1) -> None:
        if count < 1:
            raise ValueError("API call count must be positive")
        with self._lock:
            self._api_calls += count
            self._increment_provider(self._api_calls_by_provider, provider, count)

    def snapshot(self) -> EfficiencyStats:
        with self._lock:
            latency_ms = self._elapsed_ms
            if self._started_at is not None:
                latency_ms += (time.perf_counter() - self._started_at) * 1000
            return EfficiencyStats(
                latency_ms=latency_ms,
                llm_calls=self._llm_calls,
                api_calls=self._api_calls,
                prompt_tokens=self._prompt_tokens,
                completion_tokens=self._completion_tokens,
                cached_tokens=self._cached_tokens,
                estimated_cost_usd=self._estimated_cost_usd if self._has_cost else None,
                llm_calls_by_provider=dict(self._llm_calls_by_provider),
                api_calls_by_provider=dict(self._api_calls_by_provider),
            )

    @staticmethod
    def _increment_provider(counters: dict[str, int], provider: str, count: int = 1) -> None:
        counters[provider] = counters.get(provider, 0) + count


def merge_efficiency(primary: EfficiencyStats, reported: EfficiencyStats) -> EfficiencyStats:
    """Combine tracker data with usage explicitly reported by an external agent.

    The Runner-owned wall-clock latency remains authoritative. Counters are added,
    which lets adapters use either the shared tracker or return additional usage.
    """

    llm_providers = dict(primary.llm_calls_by_provider)
    for provider, count in reported.llm_calls_by_provider.items():
        llm_providers[provider] = llm_providers.get(provider, 0) + count
    api_providers = dict(primary.api_calls_by_provider)
    for provider, count in reported.api_calls_by_provider.items():
        api_providers[provider] = api_providers.get(provider, 0) + count
    costs = [
        value
        for value in (primary.estimated_cost_usd, reported.estimated_cost_usd)
        if value is not None
    ]
    return EfficiencyStats(
        latency_ms=primary.latency_ms,
        llm_calls=primary.llm_calls + reported.llm_calls,
        api_calls=primary.api_calls + reported.api_calls,
        prompt_tokens=primary.prompt_tokens + reported.prompt_tokens,
        completion_tokens=primary.completion_tokens + reported.completion_tokens,
        cached_tokens=primary.cached_tokens + reported.cached_tokens,
        estimated_cost_usd=sum(costs) if costs else None,
        llm_calls_by_provider=llm_providers,
        api_calls_by_provider=api_providers,
    )
