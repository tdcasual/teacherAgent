from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

BACKUP_SERVICES = ("backup_scheduler", "backup_daily_full", "backup_verify_weekly")
ROOT_MOUNT_RE = re.compile(r"(?m)^\s*-\s+\./:/workspace(?:$|:|\s)")
SERVICE_BLOCK_RE = re.compile(
    r"(?ms)^  (?P<name>[A-Za-z0-9_-]+):\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|^volumes:\n|\Z)"
)
BACKUP_SCRIPTS = (
    "scripts/backup/common.sh",
    "scripts/backup/run_backup.sh",
    "scripts/backup/verify_restore.sh",
    "scripts/backup/pre_upgrade_snapshot.sh",
)


def _compose_files() -> list[Path]:
    return sorted(Path(".").glob("docker-compose*.yml")) + sorted(Path(".").glob("docker-compose*.yaml"))


def _service_block(compose_text: str, service_name: str) -> str:
    for match in SERVICE_BLOCK_RE.finditer(compose_text):
        if match.group("name") == service_name:
            return match.group("body")
    raise AssertionError(f"service not found: {service_name}")


def _env_without_cloud_credentials() -> dict[str, str]:
    drop = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "S3_BUCKET",
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "OSS_ENDPOINT",
        "OSS_BUCKET",
    }
    return {key: value for key, value in os.environ.items() if key not in drop}


def test_compose_files_do_not_mount_repo_root() -> None:
    files = _compose_files()
    assert files, "expected docker-compose files"
    for path in files:
        text = path.read_text(encoding="utf-8")
        match = ROOT_MOUNT_RE.search(text)
        assert match is None, f"{path} mounts the whole repo: {match.group(0)!r}"


def test_backup_draft_compose_is_removed_or_has_no_root_mount() -> None:
    draft = Path("docker-compose.backup.draft.yml")
    if not draft.exists():
        return
    text = draft.read_text(encoding="utf-8")
    assert ROOT_MOUNT_RE.search(text) is None
    assert "DEPRECATED" in text or "deprecated" in text.lower()


def test_main_compose_backup_services_stay_profile_opt_in() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    for service in BACKUP_SERVICES:
        block = _service_block(text, service)
        assert 'profiles: ["backup"]' in block, f"{service} must stay on profiles: [\"backup\"]"
        assert "./:/workspace" not in block
        assert "./scripts/backup:/workspace/scripts/backup:ro" in block


def test_verify_restore_script_exists_and_is_syntactically_valid() -> None:
    script = Path("scripts/backup/verify_restore.sh")
    assert script.is_file()
    result = subprocess.run(
        ["bash", "-n", *BACKUP_SCRIPTS],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_verify_restore_dry_run_runs_without_cloud_credentials() -> None:
    result = subprocess.run(
        ["bash", "scripts/backup/verify_restore.sh", "dry-run"],
        env=_env_without_cloud_credentials(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    combined = f"{result.stdout}\n{result.stderr}"
    assert "dry-run" in combined.lower()
    report = json.loads(result.stdout[result.stdout.find("{") : result.stdout.rfind("}") + 1])
    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report.get("network") is False


def test_verify_restore_dry_run_flag_is_equivalent() -> None:
    result = subprocess.run(
        ["bash", "scripts/backup/verify_restore.sh", "--target", "s3", "--dry-run"],
        env=_env_without_cloud_credentials(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert '"dry_run": true' in result.stdout or '"dry_run":true' in result.stdout.replace(" ", "")


def test_ci_runs_backup_restore_dry_run() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/backup/verify_restore.sh dry-run" in text
    assert "bash -n" in text
    assert "scripts/backup/verify_restore.sh" in text
