from __future__ import annotations

import json
import shlex
import sqlite3
import subprocess
from pathlib import Path

from scripts.backup.sqlite_snapshot import collect_and_snapshot, snapshot_sqlite

_REPO = Path(__file__).resolve().parent.parent
_COMMON_SH = _REPO / "scripts" / "backup" / "common.sh"


def test_backup_domains_include_auth_and_student_submissions() -> None:
    result = subprocess.run(
        ["bash", "-c", "source scripts/backup/common.sh && domain_paths_json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    paths = {item["path"] for item in payload}
    assert "data/auth" in paths
    assert "data/student_submissions" in paths


def test_snapshot_sqlite_copies_rows_without_reading_live_file_bytes(tmp_path: Path) -> None:
    live = tmp_path / "data" / "auth" / "auth_registry.sqlite3"
    live.parent.mkdir(parents=True)
    conn = sqlite3.connect(live)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users(name) VALUES ('admin')")
    conn.commit()
    conn.close()

    dest = tmp_path / "overlay" / "data" / "auth" / "auth_registry.sqlite3"
    snapshot_sqlite(live, dest)
    copied = sqlite3.connect(dest)
    try:
        rows = copied.execute("SELECT name FROM users").fetchall()
    finally:
        copied.close()
    assert rows == [("admin",)]


def test_collect_and_snapshot_only_copies_sqlite_under_domain_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    db = project / "data" / "auth" / "auth_registry.sqlite3"
    db.parent.mkdir(parents=True)
    other = project / "data" / "auth" / "notes.txt"
    other.write_text("not-db", encoding="utf-8")
    submissions = project / "data" / "student_submissions" / "HW1" / "S001" / "photo.jpg"
    submissions.parent.mkdir(parents=True)
    submissions.write_bytes(b"jpeg")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('ok')")
    conn.commit()
    conn.close()

    overlay = tmp_path / "overlay"
    written = collect_and_snapshot(
        project,
        [
            {"domain": "serving", "path": "data/auth", "required": False},
            {"domain": "raw", "path": "data/student_submissions", "required": False},
        ],
        overlay,
    )
    assert written == ["data/auth/auth_registry.sqlite3"]
    snap = sqlite3.connect(overlay / "data" / "auth" / "auth_registry.sqlite3")
    try:
        assert snap.execute("SELECT v FROM t").fetchall() == [("ok",)]
    finally:
        snap.close()
    assert not (overlay / "data" / "auth" / "notes.txt").exists()
    assert not (overlay / "data" / "student_submissions").exists()


def test_payload_archive_includes_overlay_sqlite_not_live_or_wal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    live = project / "data" / "auth" / "auth_registry.sqlite3"
    live.parent.mkdir(parents=True)
    (project / "data" / "auth" / "notes.txt").write_text("keep-me", encoding="utf-8")
    (project / "data" / "auth" / "auth_registry.sqlite3-wal").write_text("wal", encoding="utf-8")
    (project / "data" / "auth" / "auth_registry.sqlite3-shm").write_bytes(b"shm")
    conn = sqlite3.connect(live)
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('LIVE')")
    conn.commit()
    conn.close()

    overlay = tmp_path / "overlay"
    written = collect_and_snapshot(
        project,
        [{"domain": "serving", "path": "data/auth", "required": False}],
        overlay,
    )
    assert written == ["data/auth/auth_registry.sqlite3"]

    mutated = sqlite3.connect(live)
    mutated.execute("UPDATE t SET v='MUTATED'")
    mutated.commit()
    mutated.close()

    include = tmp_path / "include.list"
    include.write_text("data/auth\n", encoding="utf-8")
    overlay_list = tmp_path / "overlay.list"
    overlay_list.write_text("\n".join(written) + "\n", encoding="utf-8")
    archive = tmp_path / "payload.tar.gz"
    script = (
        f"source {shlex.quote(str(_COMMON_SH))} && "
        'build_payload_archive "$1" "$2" "$3" "$4" "$5"'
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            script,
            "_",
            str(archive),
            str(project),
            str(include),
            str(overlay),
            str(overlay_list),
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=str(_REPO),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    members = subprocess.check_output(["tar", "-tzf", str(archive)], text=True)
    assert "data/auth/auth_registry.sqlite3" in members
    assert "data/auth/notes.txt" in members
    assert "sqlite3-wal" not in members
    assert "sqlite3-shm" not in members

    extract = tmp_path / "extract"
    extract.mkdir()
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(extract)], check=True)
    copied = sqlite3.connect(extract / "data" / "auth" / "auth_registry.sqlite3")
    try:
        assert copied.execute("SELECT v FROM t").fetchall() == [("LIVE",)]
    finally:
        copied.close()
    assert (extract / "data" / "auth" / "notes.txt").read_text(encoding="utf-8") == "keep-me"
