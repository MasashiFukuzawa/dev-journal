import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
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
