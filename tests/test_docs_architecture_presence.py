from pathlib import Path


def test_architecture_docs_exist() -> None:
    assert Path("docs/architecture/module-boundaries.md").exists()
    assert Path("docs/architecture/ownership-map.md").exists()


def test_assignment_core_docs_are_indexed() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "docs/plans/2026-08-28-assignment-core-product-design.md" in text
    assert "docs/how-to/student-login-and-submit.md" in text
    assert "docs/how-to/teacher-daily-workflow.md" in text
    assert "docs/http_api.md" in text


def test_product_docs_are_assignment_only() -> None:
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "问卷多 Agent 设计" not in index_text
    assert "多域分析发布清单" not in index_text

    http_text = Path("docs/http_api.md").read_text(encoding="utf-8")
    assert "/exam/" not in http_text or "Exam HTTP 面已卸载" in http_text
    assert "/teacher/surveys" not in http_text

    mcp_text = Path("docs/mcp_api.md").read_text(encoding="utf-8")
    assert "exam.*" in mcp_text
    assert "removed" in mcp_text.lower() or "已" in mcp_text
