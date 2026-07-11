#!/usr/bin/env python3
"""Retain only the newest SQLite backup snapshots."""

from __future__ import annotations

import argparse
from pathlib import Path


def prune(directory: Path, keep: int = 48) -> int:
    backups = sorted(directory.glob("journal_*.db"), reverse=True)
    for path in backups[keep:]:
        path.unlink()
    return max(0, len(backups) - keep)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--keep", type=int, default=48)
    args = parser.parse_args()
    if args.keep < 1:
        parser.error("--keep must be positive")
    prune(args.directory, args.keep)


if __name__ == "__main__":
    main()
