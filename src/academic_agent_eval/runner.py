"""Experiment orchestration and durable JSON/JSONL/CSV/HTML reporting."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import re
import sys
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from academic_agent_eval.agents import AgentContext, BaseAgent
from academic_agent_eval.datasets import BaseDataset
from academic_agent_eval.evaluator import EvaluationSummary, F1Evaluator, QueryEvaluation
from academic_agent_eval.parsers import BaseOutputParser, DefaultOutputParser
from academic_agent_eval.reporting import HtmlReporter
from academic_agent_eval.schemas import AgentQuery, AgentResult
from academic_agent_eval.tracking import EfficiencyTracker, merge_efficiency


@dataclass(slots=True)
class RunnerConfig:
    output_dir: Path
    experiment_name: str = "experiment"
    run_id: str | None = None
    fail_fast: bool = False
    save_tracebacks: bool = True


@dataclass(slots=True)
class ExperimentReport:
    run_id: str
    output_dir: Path
    summary: EvaluationSummary
    evaluations: list[QueryEvaluation]


class ExperimentRunner:
    """Run one agent against one normalized dataset and persist every result."""

    def __init__(
        self,
        *,
        dataset: BaseDataset,
        agent: BaseAgent,
        config: RunnerConfig,
        parser: BaseOutputParser | None = None,
        evaluator: F1Evaluator | None = None,
        html_reporter: HtmlReporter | None = None,
    ) -> None:
        self.dataset = dataset
        self.agent = agent
        self.config = config
        self.parser = parser or DefaultOutputParser()
        self.evaluator = evaluator or F1Evaluator()
        self.html_reporter = html_reporter or HtmlReporter()

    def run(self) -> ExperimentReport:
        if not self.dataset:
            raise ValueError("cannot run an empty dataset")
        run_id = self.config.run_id or self._new_run_id()
        output_dir = self.config.output_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=False)
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir()
        started_at = datetime.now(timezone.utc)
        self._write_json(
            output_dir / "manifest.json",
            self._manifest(run_id, started_at, status="running"),
        )

        evaluations: list[QueryEvaluation] = []
        try:
            self.agent.setup()
            predictions_path = output_dir / "predictions.jsonl"
            with (
                predictions_path.open("w", encoding="utf-8") as predictions_file,
                (output_dir / "per_query_metrics.jsonl").open(
                    "w", encoding="utf-8"
                ) as metrics_file,
                (output_dir / "errors.jsonl").open("w", encoding="utf-8") as errors_file,
            ):
                for case in self.dataset:
                    result = self._run_case(case.query, run_id, artifacts_dir)
                    evaluation = self.evaluator.evaluate_case(case, result)
                    evaluations.append(evaluation)
                    self._write_jsonl(predictions_file, result.to_dict())
                    self._write_jsonl(metrics_file, evaluation.to_dict())
                    if result.error:
                        self._write_jsonl(
                            errors_file,
                            {"query_id": result.query_id, "error": result.error},
                        )
                    if self.config.fail_fast and result.status != "success":
                        raise RuntimeError(result.error or "agent execution failed")
        finally:
            self.agent.teardown()

        summary = self.evaluator.aggregate(evaluations)
        self._write_json(output_dir / "summary.json", summary.to_dict())
        self._write_summary_csv(output_dir / "summary.csv", run_id, summary)
        self.html_reporter.write(
            output_dir / "report.html",
            run_id=run_id,
            experiment_name=self.config.experiment_name,
            agent_name=self.agent.name,
            agent_version=self.agent.version,
            dataset_name=self.dataset.name,
            summary=summary,
            evaluations=evaluations,
            query_texts={case.query.query_id: case.query.text for case in self.dataset},
        )
        self._write_json(
            output_dir / "manifest.json",
            self._manifest(
                run_id,
                started_at,
                status="completed",
                completed_at=datetime.now(timezone.utc),
            ),
        )
        return ExperimentReport(run_id, output_dir, summary, evaluations)

    def _run_case(self, query: Any, run_id: str, artifacts_dir: Path) -> AgentResult:
        tracker = EfficiencyTracker()
        context = AgentContext(
            run_id=run_id,
            tracker=tracker,
            artifacts_dir=artifacts_dir / self._safe_artifact_name(query.query_id),
        )
        context.artifacts_dir.mkdir(parents=True, exist_ok=True)
        raw_output: Any = None
        error: str | None = None
        try:
            agent_query = AgentQuery.from_query(query)
            with tracker.measure():
                raw_output = self.agent.search(agent_query, context)
            result = self.parser.parse(raw_output, query)
        except Exception as exc:  # the harness must preserve later benchmark cases
            if tracker.snapshot().latency_ms == 0.0:
                # Exceptions raised inside measure are already stopped by the context manager.
                pass
            error = f"{type(exc).__name__}: {exc}"
            if self.config.save_tracebacks:
                error = f"{error}\n{traceback.format_exc()}"
            result = AgentResult(query_id=query.query_id, papers=[], status="failed", error=error)
        result.usage = merge_efficiency(tracker.snapshot(), result.usage)
        return result

    def _manifest(
        self,
        run_id: str,
        started_at: datetime,
        *,
        status: str,
        completed_at: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "experiment_name": self.config.experiment_name,
            "status": status,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "agent": {"name": self.agent.name, "version": self.agent.version},
            "dataset": {"name": self.dataset.name, "size": len(self.dataset)},
            "evaluation": {"matching_protocol": self.evaluator.matcher.protocol},
            "environment": {"python": sys.version, "platform": platform.platform()},
            "runner_config": {
                **asdict(self.config),
                "output_dir": str(self.config.output_dir),
            },
        }

    def _new_run_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid.uuid4().hex[:8]
        return f"{self.config.experiment_name}-{timestamp}-{suffix}"

    @staticmethod
    def _safe_artifact_name(query_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", query_id).strip("._")
        if safe == query_id and safe:
            return safe
        digest = hashlib.sha256(query_id.encode("utf-8")).hexdigest()[:10]
        return f"{safe or 'query'}-{digest}"

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    @staticmethod
    def _write_jsonl(handle: Any, data: dict[str, Any]) -> None:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")
        handle.flush()

    def _write_summary_csv(self, path: Path, run_id: str, summary: EvaluationSummary) -> None:
        row = {
            "run_id": run_id,
            "experiment": self.config.experiment_name,
            "agent": self.agent.name,
            "agent_version": self.agent.version,
            "dataset": self.dataset.name,
            **summary.to_dict(),
        }
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
