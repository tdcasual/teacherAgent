from pathlib import Path
import re


def test_governance_artifacts_exist() -> None:
    assert Path("CONTRIBUTING.md").exists()
    assert Path("SECURITY.md").exists()
    assert Path(".github/pull_request_template.md").exists()
    assert Path(".github/CODEOWNERS").exists()
    assert Path("docs/operations/change-management-and-governance.md").exists()
    assert Path("docs/operations/security-incident-response-runbook.md").exists()


def test_readme_links_to_governance_artifacts() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "CONTRIBUTING.md" in text
    assert "SECURITY.md" in text
    assert ".github/pull_request_template.md" in text
    assert "docs/operations/change-management-and-governance.md" in text
    assert "docs/operations/security-incident-response-runbook.md" in text


def test_docs_index_links_to_governance_artifacts() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "CONTRIBUTING.md" in text
    assert "SECURITY.md" in text
    assert ".github/pull_request_template.md" in text
    assert "docs/operations/change-management-and-governance.md" in text
    assert "docs/operations/security-incident-response-runbook.md" in text


def test_codeowners_covers_core_scopes() -> None:
    text = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    assert "/services/api/" in text
    assert "/frontend/" in text
    assert "/docs/" in text


def test_risk_register_entries_include_owner_review_and_exit() -> None:
    text = Path("docs/reference/risk-register.md").read_text(encoding="utf-8")
    sections = [part for part in text.split("### RISK-")[1:] if part.strip()]
    assert sections, "risk register should include at least one RISK-* entry"

    for section in sections:
        assert "Owner：" in section
        assert "下次复审日期：" in section
        assert "退出条件：" in section
        assert re.search(r"下次复审日期：\d{4}-\d{2}-\d{2}", section)
