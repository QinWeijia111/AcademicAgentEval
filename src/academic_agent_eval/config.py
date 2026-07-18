"""Strict, dependency-free configuration loading for reproducible evaluation runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when an evaluation configuration is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class RunSettings:
    name: str
    output_dir: Path
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class DatasetSettings:
    adapter: str
    path: Path
    split: str = "smoke"
    max_cases: int | None = None


@dataclass(frozen=True, slots=True)
class AgentSettings:
    kind: str
    command: tuple[str, ...] = ()
    secret_env: tuple[str, ...] = ()
    timeout_seconds: float = 600.0
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    schema_version: str
    run: RunSettings
    dataset: DatasetSettings
    agent: AgentSettings
    scoring_profile: str = "canonical-v1"

    def redacted_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["run"]["output_dir"] = str(self.run.output_dir)
        result["dataset"]["path"] = str(self.dataset.path)
        result["agent"]["command"] = {
            "configured": bool(self.agent.command),
            "argument_count": len(self.agent.command),
        }
        result["agent"]["secret_env"] = list(self.agent.secret_env)
        result["agent"]["options"] = {"configured": bool(self.agent.options)}
        return result


def load_config(path: str | Path) -> EvaluationConfig:
    """Load a JSON configuration, resolving local paths relative to its file."""

    config_path = Path(path).expanduser().resolve()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file does not exist: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON configuration: {exc.msg}") from exc
    if not isinstance(data, Mapping):
        raise ConfigError("configuration must be a JSON object")
    _require_keys(data, {"schema_version", "run", "dataset", "agent", "scoring"}, "config")
    if data["schema_version"] != "eval-config-v1":
        raise ConfigError("schema_version must be 'eval-config-v1'")

    root = config_path.parent
    run = _mapping(data["run"], "run")
    dataset = _mapping(data["dataset"], "dataset")
    agent = _mapping(data["agent"], "agent")
    scoring = _mapping(data["scoring"], "scoring")
    _require_keys(run, {"name", "output_dir", "seed"}, "run", required={"name", "output_dir"})
    _require_keys(
        dataset, {"adapter", "path", "split", "max_cases"}, "dataset", required={"adapter", "path"}
    )
    _require_keys(
        agent,
        {"kind", "command", "secret_env", "timeout_seconds", "options"},
        "agent",
        required={"kind"},
    )
    _require_keys(scoring, {"profile"}, "scoring", required={"profile"})

    command = agent.get("command", [])
    if not isinstance(command, list) or not all(isinstance(item, str) and item for item in command):
        raise ConfigError("agent.command must be a non-empty string array when provided")
    if agent["kind"] == "external-process" and not command:
        raise ConfigError("external-process agent requires a command array")
    if _command_has_inline_secret(command):
        raise ConfigError("agent.command must reference environment variables, not inline secrets")
    _reject_inline_secrets(agent.get("options") or {}, "agent.options")
    secret_env = agent.get("secret_env", [])
    if not isinstance(secret_env, list) or not all(
        isinstance(item, str) and item for item in secret_env
    ):
        raise ConfigError("agent.secret_env must be a string array")
    timeout = float(agent.get("timeout_seconds", 600.0))
    if timeout <= 0:
        raise ConfigError("agent.timeout_seconds must be positive")
    if dataset.get("max_cases") is not None and int(dataset["max_cases"]) < 0:
        raise ConfigError("dataset.max_cases must be non-negative")

    return EvaluationConfig(
        schema_version="eval-config-v1",
        run=RunSettings(
            _non_empty(run["name"], "run.name"),
            _resolve_path(root, run["output_dir"]),
            int(run["seed"]) if run.get("seed") is not None else None,
        ),
        dataset=DatasetSettings(
            _non_empty(dataset["adapter"], "dataset.adapter"),
            _resolve_path(root, dataset["path"]),
            str(dataset.get("split", "smoke")),
            int(dataset["max_cases"]) if dataset.get("max_cases") is not None else None,
        ),
        agent=AgentSettings(
            _non_empty(agent["kind"], "agent.kind"),
            tuple(command),
            tuple(secret_env),
            timeout,
            dict(agent.get("options") or {}),
        ),
        scoring_profile=_non_empty(scoring["profile"], "scoring.profile"),
    )


_SENSITIVE_CONFIG_TOKENS = (
    "authorization",
    "credential",
    "key",
    "password",
    "secret",
    "token",
)


def _command_has_inline_secret(command: list[str]) -> bool:
    for argument in command:
        lowered = argument.casefold()
        if _looks_inline_secret(argument):
            return True
        if lowered.startswith("--") and any(token in lowered for token in _SENSITIVE_CONFIG_TOKENS):
            return True
    return False


def _looks_inline_secret(value: str) -> bool:
    lowered = value.casefold()
    return (
        "authorization:" in lowered
        or "bearer " in lowered
        or "sk-" in lowered
        or any(f"--{token}=" in lowered for token in _SENSITIVE_CONFIG_TOKENS)
        or any(
            f"?{token}=" in lowered or f"&{token}=" in lowered for token in _SENSITIVE_CONFIG_TOKENS
        )
    )


def _reject_inline_secrets(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if any(token in str(key).casefold() for token in _SENSITIVE_CONFIG_TOKENS):
                raise ConfigError(
                    f"{item_path} must be an environment-variable reference, not a secret"
                )
            _reject_inline_secrets(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_inline_secrets(item, f"{path}[{index}]")
    elif isinstance(value, str) and _looks_inline_secret(value):
        raise ConfigError(f"{path} must not contain an inline secret")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be an object")
    return value


def _require_keys(
    data: Mapping[str, Any], allowed: set[str], name: str, *, required: set[str] | None = None
) -> None:
    unknown, missing = set(data) - allowed, (required or set()) - set(data)
    if unknown:
        raise ConfigError(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ConfigError(f"{name} is missing fields: {', '.join(sorted(missing))}")


def _non_empty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a non-empty string")
    return value


def _resolve_path(root: Path, value: Any) -> Path:
    text = _non_empty(value, "path")
    path = Path(text).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()
