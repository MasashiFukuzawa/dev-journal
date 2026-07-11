from pathlib import Path

from scripts.prune_backups import prune


def test_backup_pruning_keeps_newest_48(tmp_path: Path) -> None:
    for hour in range(60):
        (tmp_path / f"journal_202601{hour:04d}.db").touch()
    assert prune(tmp_path) == 12
    remaining = sorted(tmp_path.glob("journal_*.db"))
    assert len(remaining) == 48
    assert remaining[0].name == "journal_2026010012.db"
