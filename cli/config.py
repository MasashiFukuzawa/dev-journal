"""Portable configuration and XDG path handling for dev-journal."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


def config_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if env_path := os.environ.get("DEV_JOURNAL_CONFIG"):
        return Path(env_path).expanduser()
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "dev-journal" / "config.yml"


def data_dir() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "dev-journal"


def state_dir() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "dev-journal"


@dataclass(frozen=True)
class GitHubConfig:
    repositories: tuple[str, ...] = ()
    done_status: str = "Done"
    lookback_days: int = 14


@dataclass(frozen=True)
class AnalysisConfig:
    command: str = "claude"
    model: str = "claude-sonnet-4-6"
    timeout_seconds: int = 180


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8421
    poll_interval_seconds: int = 1800
    collection_enabled: bool = True
    allow_unsafe_non_loopback: bool = False


@dataclass(frozen=True)
class Config:
    github: GitHubConfig = field(default_factory=GitHubConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    timezone: str = "UTC"
    retention_days: int = 90


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _reject_unknown(raw: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown {context} key(s): {', '.join(sorted(unknown))}")


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def load_config(explicit: str | None = None, *, required: bool = False) -> Config:
    path = config_path(explicit)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"config file not found: {path}")
        return Config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")
    _reject_unknown(raw, {"github", "analysis", "server", "timezone", "retention_days"}, "root")
    github = _section(raw, "github")
    analysis = _section(raw, "analysis")
    server = _section(raw, "server")
    _reject_unknown(github, {"repositories", "done_status", "lookback_days"}, "github")
    _reject_unknown(analysis, {"command", "model", "timeout_seconds"}, "analysis")
    _reject_unknown(
        server,
        {
            "host",
            "port",
            "poll_interval_seconds",
            "collection_enabled",
            "allow_unsafe_non_loopback",
        },
        "server",
    )
    repositories = github.get("repositories", [])
    if not isinstance(repositories, list) or not all(isinstance(v, str) for v in repositories):
        raise ValueError("github.repositories must be a list of strings")
    timezone = raw.get("timezone", "UTC")
    if not isinstance(timezone, str):
        raise ValueError("timezone must be a string")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc
    host = _nonempty_string(server.get("host", "127.0.0.1"), "server.host")
    unsafe_bind = _bool(
        server.get("allow_unsafe_non_loopback", False),
        "server.allow_unsafe_non_loopback",
    )
    if host not in {"127.0.0.1", "localhost", "::1"} and not unsafe_bind:
        raise ValueError("non-loopback server.host requires server.allow_unsafe_non_loopback: true")
    port = _positive_int(server.get("port", 8421), "server.port")
    if port > 65535:
        raise ValueError("server.port must be at most 65535")
    return Config(
        github=GitHubConfig(
            repositories=tuple(repositories),
            done_status=_nonempty_string(github.get("done_status", "Done"), "github.done_status"),
            lookback_days=_positive_int(github.get("lookback_days", 14), "github.lookback_days"),
        ),
        analysis=AnalysisConfig(
            command=_nonempty_string(analysis.get("command", "claude"), "analysis.command"),
            model=_nonempty_string(analysis.get("model", "claude-sonnet-4-6"), "analysis.model"),
            timeout_seconds=_positive_int(
                analysis.get("timeout_seconds", 180), "analysis.timeout_seconds"
            ),
        ),
        server=ServerConfig(
            host=host,
            port=port,
            poll_interval_seconds=_positive_int(
                server.get("poll_interval_seconds", 1800), "server.poll_interval_seconds"
            ),
            collection_enabled=_bool(
                server.get("collection_enabled", True), "server.collection_enabled"
            ),
            allow_unsafe_non_loopback=unsafe_bind,
        ),
        timezone=timezone,
        retention_days=_positive_int(raw.get("retention_days", 90), "retention_days"),
    )
