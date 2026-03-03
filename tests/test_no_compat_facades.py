from __future__ import annotations

from pathlib import Path


def test_compat_facades_are_removed() -> None:
    removed = [
        "services/api/context_application_facade.py",
        "services/api/context_runtime_facade.py",
        "services/api/context_io_facade.py",
        "services/api/app_core_service_imports.py",
    ]
    for path in removed:
        assert not Path(path).exists()


def test_app_core_has_no_star_imports() -> None:
    text = Path("services/api/app_core.py").read_text(encoding="utf-8")
    assert "import *" not in text
