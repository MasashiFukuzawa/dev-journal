import json
from pathlib import Path
from unittest.mock import Mock

import collect

from server.routers import chat


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(
        "analysis:\n  command: claude-test\n  model: test-model\n",
        encoding="utf-8",
    )
    return path


def test_chat_claude_uses_tool_free_print_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEV_JOURNAL_CONFIG", str(_write_config(tmp_path)))
    run = Mock(return_value=Mock(returncode=0, stdout="answer", stderr=""))
    monkeypatch.setattr(chat.subprocess, "run", run)

    assert chat._run_claude("question") == "answer"
    command = run.call_args.args[0]
    assert command[:3] == ["claude-test", "-p", "question"]
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--dangerously-skip-permissions" not in command
    assert "--allowedTools" not in command
    assert "Bash" not in command
    assert "shell" not in run.call_args.kwargs


def test_collection_analysis_uses_tool_free_print_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEV_JOURNAL_CONFIG", str(_write_config(tmp_path)))
    deep_dive = {
        "deep_dive_json": {"background": "ok", "decisions": [], "constraints": [], "future": []}
    }
    response = json.dumps({"result": json.dumps(deep_dive)})
    run = Mock(return_value=Mock(returncode=0, stdout=response, stderr=""))
    monkeypatch.setattr(collect.subprocess, "run", run)

    result = collect.generate_deep_dive_via_claude_cli({"issue_number": 1})
    assert result is not None
    command = run.call_args.args[0]
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--dangerously-skip-permissions" not in command


def test_github_subprocess_uses_argument_vector_without_shell(monkeypatch) -> None:
    run = Mock(return_value=Mock(stdout="[]"))
    monkeypatch.setattr(collect.subprocess, "run", run)
    assert collect._run_gh("issue", "list", "--repo", "example-org/example-repo") == []
    assert run.call_args.args[0] == ["gh", "issue", "list", "--repo", "example-org/example-repo"]
    assert "shell" not in run.call_args.kwargs
