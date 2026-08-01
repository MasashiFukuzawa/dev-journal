import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCAN = ROOT / "tests" / "scan_public_content.sh"
BANNED = (
    "/" + "Users/",
    "works/" + "private",
)
EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")


def test_repository_contains_no_private_identifiers() -> None:
    excluded = {".git", ".venv", "node_modules", "__pycache__", "static"}
    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if path.name == "scan_public_content.sh":
            continue
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in BANNED:
            if token.casefold() in content.casefold():
                violations.append(f"{path.relative_to(ROOT)}: {token}")
        if EMAIL.search(content):
            violations.append(f"{path.relative_to(ROOT)}: email address")
    assert not violations, "private identifiers found:\n" + "\n".join(violations)


def _scan_history(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCAN), "--stdin"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


# Built by concatenation so this file does not itself trip the scan it tests.
# The token value is a zero-entropy placeholder: the pattern only requires 8+
# non-space characters, and a realistic-looking one would trip gitleaks here.
LEAKS = {
    "email": '+owner = "alice@example' + '.com"',
    "home_path": '+path = "/' + 'Users/alice/notes"',
    "private_repo": '+remote = "works/' + 'private/thing"',
    "token": '+access_token = "xxxxxxxxxxxx"',
}


@pytest.mark.parametrize("payload", LEAKS.values(), ids=list(LEAKS))
def test_history_scan_rejects_private_identifiers(payload: str) -> None:
    """The scan must fail loudly. It once passed silently when rg was absent."""
    assert _scan_history(payload + "\n").returncode == 1


def test_history_scan_ignores_commit_metadata_and_diff_markers() -> None:
    """Author/trailer lines are already public, and a bare `+` is not a local part."""
    payload = "\n".join(
        (
            "commit 0123456789abcdef",
            "Author: A Name <1+name@users" + ".noreply.github.com>",
            "    Co-Authored-By: Someone <noreply@anthropic" + ".com>",
            "+@AGENTS" + ".md",
            '+@router' + '.get("/api/health")',
        )
    )
    assert _scan_history(payload + "\n").returncode == 0
