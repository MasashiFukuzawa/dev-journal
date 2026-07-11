from pathlib import Path

import pytest
from config import config_path, data_dir, load_config, state_dir


def test_xdg_defaults_are_isolated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("DEV_JOURNAL_CONFIG", raising=False)

    assert config_path() == tmp_path / "config/dev-journal/config.yml"
    assert data_dir() == tmp_path / "data/dev-journal"
    assert state_dir() == tmp_path / "state/dev-journal"


def test_config_precedence(monkeypatch, tmp_path: Path) -> None:
    env_config = tmp_path / "env.yml"
    explicit_config = tmp_path / "explicit.yml"
    env_config.write_text("server:\n  port: 9100\n", encoding="utf-8")
    explicit_config.write_text("server:\n  port: 9200\n", encoding="utf-8")
    monkeypatch.setenv("DEV_JOURNAL_CONFIG", str(env_config))

    assert load_config().server.port == 9100
    assert load_config(str(explicit_config)).server.port == 9200
    assert config_path(str(explicit_config)) == explicit_config


def test_safe_server_defaults() -> None:
    cfg = load_config("/path/that/does/not/exist")
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.collection_enabled is True
    assert cfg.github.repositories == ()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("server:\n  collection_enabled: 'false'\n", "must be a boolean"),
        ("server:\n  port: 0\n", "positive integer"),
        ("server:\n  poll_interval_seconds: -1\n", "positive integer"),
        ("retention_days: -1\n", "positive integer"),
        ("timezone: Not/A-Timezone\n", "unknown timezone"),
        ("unexpected: true\n", "unknown root key"),
        ("github:\n  unexpected: true\n", "unknown github key"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_config(str(path))


def test_non_loopback_requires_explicit_unsafe_opt_in(tmp_path: Path) -> None:
    path = tmp_path / "bind.yml"
    path.write_text("server:\n  host: 0.0.0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="requires"):
        load_config(str(path))

    path.write_text(
        "server:\n  host: 0.0.0.0\n  allow_unsafe_non_loopback: true\n",
        encoding="utf-8",
    )
    assert load_config(str(path)).server.host == "0.0.0.0"
