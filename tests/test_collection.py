from datetime import datetime, timedelta, timezone
from pathlib import Path

import collect
import pytest


def _config(monkeypatch, tmp_path: Path, body: str) -> None:
    path = tmp_path / "config.yml"
    path.write_text(body, encoding="utf-8")
    monkeypatch.setenv("DEV_JOURNAL_CONFIG", str(path))


def test_scoped_project_paginates_and_filters_repository(monkeypatch, tmp_path: Path) -> None:
    _config(
        monkeypatch,
        tmp_path,
        "github:\n  repositories: [allowed/repo]\n  project_owner: example\n"
        "  project_number: 7\n  done_status: Done\n",
    )
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    pages = [
        {
            "nodes": [
                {
                    "content": {
                        "number": 1,
                        "url": "https://github.com/allowed/repo/issues/1",
                        "closedAt": recent,
                        "repository": {"nameWithOwner": "allowed/repo"},
                    },
                    "fieldValues": {
                        "nodes": [{"name": "Done", "field": {"name": "Status"}}]
                    },
                }
            ],
            "pageInfo": {"hasNextPage": True, "endCursor": "next"},
        },
        {
            "nodes": [
                {
                    "content": {
                        "number": 2,
                        "url": "https://github.com/other/repo/issues/2",
                        "closedAt": recent,
                        "repository": {"nameWithOwner": "other/repo"},
                    },
                    "fieldValues": {
                        "nodes": [{"name": "Done", "field": {"name": "Status"}}]
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    ]
    calls: list[str | None] = []

    def page(owner: str, number: int, cursor: str | None):
        calls.append(cursor)
        return pages[len(calls) - 1]

    monkeypatch.setattr(collect, "_project_page", page)
    items = collect._get_done_items()
    assert [item["content"]["number"] for item in items] == [1]
    assert calls == [None, "next"]


def test_scoped_project_applies_lookback_cutoff(monkeypatch, tmp_path: Path) -> None:
    _config(
        monkeypatch,
        tmp_path,
        "github:\n  project_owner: example\n  project_number: 7\n  lookback_days: 14\n",
    )
    recent = (datetime.now(timezone.utc) - timedelta(days=13)).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    nodes = []
    for number, closed_at in ((1, recent), (2, old)):
        nodes.append(
            {
                "content": {
                    "number": number,
                    "url": f"https://github.com/example/repo/issues/{number}",
                    "closedAt": closed_at,
                    "repository": {"nameWithOwner": "example/repo"},
                },
                "fieldValues": {
                    "nodes": [{"name": "Done", "field": {"name": "Status"}}]
                },
            }
        )
    monkeypatch.setattr(
        collect,
        "_project_page",
        lambda *_: {"nodes": nodes, "pageInfo": {"hasNextPage": False}},
    )
    assert [item["content"]["number"] for item in collect._get_done_items()] == [1]


def test_legacy_mode_warns_and_uses_paginated_api(monkeypatch, tmp_path: Path) -> None:
    _config(monkeypatch, tmp_path, "github:\n  repositories: [example/repo]\n")
    calls: list[tuple[str, ...]] = []

    def run(*args: str):
        calls.append(args)
        if args[0] == "api":
            return [[]]
        return {}

    monkeypatch.setattr(collect, "_run_gh", run)
    with pytest.warns(UserWarning, match="legacy"):
        assert collect._get_done_items() == []
    assert "--paginate" in calls[0]
    assert "--slurp" in calls[0]


def test_legacy_mode_prefers_browser_url_for_issue_reference(monkeypatch, tmp_path: Path) -> None:
    _config(monkeypatch, tmp_path, "github:\n  repositories: [example/repo]\n")
    issue = {
        "number": 42,
        "url": "https://api.github.com/repos/example/repo/issues/42",
        "html_url": "https://github.com/example/repo/issues/42",
        "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    def run(*args: str):
        if "--paginate" in args:
            return [[issue]]
        return {"projectItems": [{"status": {"name": "Done"}}]}

    monkeypatch.setattr(collect, "_run_gh", run)
    with pytest.warns(UserWarning, match="legacy"):
        items = collect._get_done_items()
    assert collect._extract_issue_ref(items[0]) == (42, "example/repo")


def test_raw_model_output_is_opt_in(monkeypatch, tmp_path: Path) -> None:
    _config(monkeypatch, tmp_path, "analysis:\n  save_raw_output: false\n")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        collect.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Result", (), {"returncode": 0, "stdout": "not-json", "stderr": ""}
        )(),
    )
    assert collect.generate_deep_dive_via_claude_cli({"issue_number": 1}) is None
    assert not (tmp_path / "state/dev-journal/analysis-raw.log").exists()
