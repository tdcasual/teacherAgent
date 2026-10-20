#!/usr/bin/env python3
"""Consistent SQLite snapshots for backup archives.

Live *.sqlite3 files are copied with sqlite3.Connection.backup so a concurrent
writer cannot produce a torn database file in the tarball.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, List


def snapshot_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    uri = f"file:{src.resolve().as_posix()}?mode=ro"
    src_conn = sqlite3.connect(uri, uri=True)
    try:
        dest_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def _iter_sqlite_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def collect_and_snapshot(
    project: Path, domains: List[dict[str, Any]], overlay: Path
) -> List[str]:
    overlay.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for item in domains:
        rel = str(item.get("path") or "").strip()
        if not rel:
            continue
        root = project / rel
        if not root.exists():
            continue
        for path in _iter_sqlite_files(root):
            if path.suffix != ".sqlite3":
                continue
            rel_path = path.relative_to(project).as_posix()
            snapshot_sqlite(path, overlay / rel_path)
            written.append(rel_path)
    return written


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot live SQLite files into an overlay tree")
    parser.add_argument("--project", required=True)
    parser.add_argument("--domains", required=True)
    parser.add_argument("--overlay", required=True)
    args = parser.parse_args(argv)
    project = Path(args.project)
    domains = json.loads(Path(args.domains).read_text(encoding="utf-8"))
    if not isinstance(domains, list):
        print("domains json must be a list", file=sys.stderr)
        return 1
    overlay = Path(args.overlay)
    for rel in collect_and_snapshot(project, domains, overlay):
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
