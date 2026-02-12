from __future__ import annotations

from pathlib import Path


def test_no_duplicate_route_module_files() -> None:
    routes_dir = Path("services/api/routes")
    duplicate_files = sorted(str(path) for path in routes_dir.glob("* 2.py"))
    assert duplicate_files == [], f"duplicate route modules must be removed: {duplicate_files}"
