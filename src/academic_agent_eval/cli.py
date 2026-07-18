"""Command line entry point for configuration and dataset validation."""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from academic_agent_eval.config import ConfigError, load_config
from academic_agent_eval.dataset_adapters import load_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="academic-agent-eval", description="Academic paper-agent evaluation harness"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-config", "validate-dataset", "doctor"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            print(json.dumps(config.redacted_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate-dataset":
            dataset = load_dataset(
                config.dataset.path,
                config.dataset.adapter,
                max_cases=config.dataset.max_cases,
            )
            print(
                json.dumps(
                    {
                        "dataset": dataset.name,
                        "cases_to_run": len(dataset),
                        "split": config.dataset.split,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        missing = [name for name in config.agent.secret_env if not os.environ.get(name)]
        print(
            json.dumps(
                {
                    "agent_kind": config.agent.kind,
                    "command_configured": bool(config.agent.command),
                    "missing_secret_env": missing,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not missing else 2
    except (ConfigError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
