from pathlib import Path

from fastapi.testclient import TestClient


def test_health_api_with_collection_disabled(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text(
        "github:\n  repositories: []\nserver:\n  collection_enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEV_JOURNAL_CONFIG", str(config))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    from server.main import app

    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert (tmp_path / "data/dev-journal/journal.db").exists()
