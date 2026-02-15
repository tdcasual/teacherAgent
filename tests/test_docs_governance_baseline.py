from pathlib import Path


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
    assert "docs/operations/change-management-and-governance.md" in text
    assert "docs/operations/security-incident-response-runbook.md" in text


def test_docs_index_links_to_governance_artifacts() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "CONTRIBUTING.md" in text
    assert "SECURITY.md" in text
    assert "docs/operations/change-management-and-governance.md" in text
    assert "docs/operations/security-incident-response-runbook.md" in text


def test_codeowners_covers_core_scopes() -> None:
    text = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    assert "/services/api/" in text
    assert "/frontend/" in text
    assert "/docs/" in text
