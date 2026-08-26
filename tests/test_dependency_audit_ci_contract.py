from __future__ import annotations

from pathlib import Path

OCR_PACKAGES = ("deepseek-ocr", "multi-ocr-sdk")
API_REQUIREMENTS = Path("services/api/requirements.txt")
BACKEND_DEP_AUDIT = Path("scripts/quality/check_backend_dep_audit.sh")


def test_ci_contains_dependency_audit_steps() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/quality/check_frontend_prod_audit.sh" in text
    assert "scripts/quality/check_backend_dep_audit.sh" in text


def test_api_requirements_pin_ocr_packages_exactly() -> None:
    text = API_REQUIREMENTS.read_text(encoding="utf-8")
    for package in OCR_PACKAGES:
        assert f"{package}==" in text, f"{package} must use == in {API_REQUIREMENTS}"
        assert f"{package}>=" not in text, f"{package} must not use >= in {API_REQUIREMENTS}"


def test_backend_dep_audit_rejects_floating_ocr_pins() -> None:
    text = BACKEND_DEP_AUDIT.read_text(encoding="utf-8")
    for package in OCR_PACKAGES:
        assert package in text, f"{BACKEND_DEP_AUDIT} must mention {package}"
    assert ">=" in text, f"{BACKEND_DEP_AUDIT} must reject floating >= OCR pins"
