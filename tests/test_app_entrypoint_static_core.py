from __future__ import annotations

from pathlib import Path


def test_app_entrypoint_has_no_dynamic_module_loader() -> None:
    text = Path("services/api/app.py").read_text(encoding="utf-8")
    forbidden = ("spec_from_file_location", "exec_module(", "sys.modules.pop(")
    for item in forbidden:
        assert item not in text


def test_tenant_factory_has_no_dynamic_module_loader() -> None:
    text = Path("services/api/tenant_app_factory.py").read_text(encoding="utf-8")
    forbidden = (
        "spec_from_file_location",
        "module_from_spec(",
        "exec_module(",
        "sys.modules[",
    )
    for item in forbidden:
        assert item not in text
