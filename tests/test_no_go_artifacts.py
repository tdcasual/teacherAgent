"""Guardrails to keep Go runtime artifacts fully removed from this repository."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_REMOVED_PATHS = (
    _ROOT / "services" / "go-api",
    _ROOT / "docker-compose.go-exclusive.yml",
    _ROOT / "scripts" / "release" / "smoke_go_api_v2.sh",
    _ROOT / "scripts" / "release" / "check_frontend_api_v2_only.sh",
)

_SCAN_DIRS = (
    _ROOT / "docs",
    _ROOT / "scripts",
    _ROOT / "frontend",
    _ROOT / "services",
    _ROOT / ".github",
)

_FORBIDDEN_SNIPPETS = (
    "services/go-api",
    "docker-compose.go-exclusive.yml",
    "smoke_go_api_v2.sh",
    "check_frontend_api_v2_only.sh",
    "/api/v2",
)

_SKIP_PARTS = {
    ".git",
    ".worktrees",
    "node_modules",
    "dist",
    "dist-student",
    "dist-teacher",
    ".playwright",
    "playwright-report",
    "test-results",
    "__pycache__",
    ".pytest_cache",
}


def test_go_artifact_paths_absent() -> None:
    for path in _REMOVED_PATHS:
        assert not path.exists(), f"Go artifact must stay removed: {path}"


def test_no_go_runtime_strings_in_source_tree() -> None:
    offenders: list[str] = []
    for scan_dir in _SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in scan_dir.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_PARTS for part in path.parts):
                continue
            if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ico", ".zip"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(snippet in text for snippet in _FORBIDDEN_SNIPPETS):
                rel = path.relative_to(_ROOT).as_posix()
                offenders.append(rel)
    assert offenders == [], f"forbidden go/v2 snippets remain: {offenders}"
