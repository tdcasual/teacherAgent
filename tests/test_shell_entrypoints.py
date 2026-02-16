from __future__ import annotations

import subprocess
from pathlib import Path


def _copy_executable(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    dst.chmod(0o755)


def test_backup_scripts_support_symlink_entrypoint_outside_repo_cwd(tmp_path: Path) -> None:
    repo_scripts = Path("scripts/backup")
    local_scripts = tmp_path / "scripts" / "backup"

    for name in ("common.sh", "run_backup.sh", "verify_restore.sh", "pre_upgrade_snapshot.sh"):
        _copy_executable(repo_scripts / name, local_scripts / name)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    run_symlink = bin_dir / "run_backup"
    verify_symlink = bin_dir / "verify_restore"
    pre_snapshot_symlink = bin_dir / "pre_upgrade_snapshot"
    run_symlink.symlink_to(local_scripts / "run_backup.sh")
    verify_symlink.symlink_to(local_scripts / "verify_restore.sh")
    pre_snapshot_symlink.symlink_to(local_scripts / "pre_upgrade_snapshot.sh")

    other_cwd = tmp_path / "other"
    other_cwd.mkdir(parents=True, exist_ok=True)

    for cmd in (
        [str(run_symlink), "--help"],
        [str(verify_symlink), "--help"],
        [str(pre_snapshot_symlink), "--help"],
    ):
        result = subprocess.run(
            cmd,
            cwd=str(other_cwd),
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "Usage:" in result.stdout


def test_collect_backend_quality_script_is_cwd_independent(tmp_path: Path) -> None:
    local_quality = tmp_path / "scripts" / "quality"
    _copy_executable(Path("scripts/quality/collect_backend_quality.sh"), local_quality / "collect_backend_quality.sh")
    checker = local_quality / "check_backend_quality_budget.py"
    checker.write_text(
        "#!/usr/bin/env python3\n"
        "print('quality-ok')\n",
        encoding="utf-8",
    )
    checker.chmod(0o755)

    other_cwd = tmp_path / "other"
    other_cwd.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [str(local_quality / "collect_backend_quality.sh")],
        cwd=str(other_cwd),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "quality-ok" in result.stdout
