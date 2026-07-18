"""Evaluation core for academic paper search agents."""

from academic_agent_eval.agents import AgentContext, BaseAgent
from academic_agent_eval.datasets import BaseDataset, JsonDataset
from academic_agent_eval.evaluator import F1Evaluator
from academic_agent_eval.runner import ExperimentRunner, RunnerConfig
from academic_agent_eval.scoring import ScoreProfile, ranking_metrics, structured_schema_score
from academic_agent_eval.schemas import (
    AgentQuery,
    AgentResult,
    BenchmarkCase,
    EfficiencyStats,
    GroundTruth,
    Paper,
    Prediction,
    Query,
)

__all__ = [
    "AgentContext",
    "AgentQuery",
    "AgentResult",
    "BaseAgent",
    "BaseDataset",
    "BenchmarkCase",
    "EfficiencyStats",
    "ExperimentRunner",
    "F1Evaluator",
    "GroundTruth",
    "JsonDataset",
    "Paper",
    "Prediction",
    "Query",
    "RunnerConfig",
    "ScoreProfile",
    "ranking_metrics",
    "structured_schema_score",
]

__version__ = "0.1.0"
