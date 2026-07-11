import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_plugin_manifests_are_consistent() -> None:
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert claude["name"] == codex["name"] == "dev-journal"
    assert claude["version"] == codex["version"]
    assert codex["skills"] == "./skills/"
    assert codex["author"]["name"]
    assert codex["interface"]["defaultPrompt"]


def test_skill_frontmatter_matches_directory() -> None:
    skill = ROOT / "skills/dev-journal/SKILL.md"
    _, raw, _ = skill.read_text(encoding="utf-8").split("---", 2)
    frontmatter = yaml.safe_load(raw)
    assert set(frontmatter) == {"name", "description"}
    assert frontmatter["name"] == skill.parent.name
    assert 120 <= len(frontmatter["description"]) <= 500
