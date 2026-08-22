from __future__ import annotations

import subprocess
from pathlib import Path


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_gitignore_covers_admin_bootstrap_txt() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    active_rules = {
        line.strip()
        for line in gitignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "data/auth/admin_bootstrap.txt" in active_rules
    assert "data/auth/*bootstrap*" in active_rules

    listed = _git("ls-files", "--", "data/auth/admin_bootstrap.txt")
    assert listed.returncode == 0
    assert listed.stdout.strip() == ""

    ignored = _git("check-ignore", "-q", "--", "data/auth/admin_bootstrap.txt")
    assert ignored.returncode == 0


def test_tracked_auth_dir_has_no_plaintext_password() -> None:
    listed = _git("ls-files", "-z", "--", "data/auth/")
    assert listed.returncode == 0
    tracked = [path for path in listed.stdout.split("\0") if path]
    for relpath in tracked:
        blob = _git("show", f":{relpath}")
        assert blob.returncode == 0, f"failed to read index blob for {relpath}"
        for line in blob.stdout.splitlines():
            assert not line.strip().lower().startswith("password="), (
                f"tracked file {relpath} contains plaintext password="
            )
