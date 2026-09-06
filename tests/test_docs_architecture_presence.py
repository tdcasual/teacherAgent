import re
from pathlib import Path

CURRENT_PLAN_AUTHORITIES = {
    "docs/plans/2026-08-28-assignment-core-product-design.md",
    "docs/plans/2026-08-26-audit-remediation-design.md",
    "docs/plans/2026-09-05-next-phase-after-audit-design.md",
}


def test_architecture_docs_exist() -> None:
    assert Path("docs/architecture/module-boundaries.md").exists()
    assert Path("docs/architecture/ownership-map.md").exists()


def test_assignment_core_docs_are_indexed() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    for path in CURRENT_PLAN_AUTHORITIES:
        assert path in text
    assert "docs/plans/ARCHIVE.md" in text
    assert "docs/how-to/student-login-and-submit.md" in text
    assert "docs/how-to/teacher-daily-workflow.md" in text
    assert "docs/http_api.md" in text


def test_index_design_section_lists_current_plan_authorities_only() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    _, rest = text.split("## 设计与演进", 1)
    section = rest.split("\n## ", 1)[0]
    found = set(re.findall(r"docs/plans/[^\s`]+", section))
    assert found == CURRENT_PLAN_AUTHORITIES


def test_plans_archive_marks_remaining_as_historical() -> None:
    archive = Path("docs/plans/ARCHIVE.md").read_text(encoding="utf-8")
    assert "不是" in archive
    assert "运行时契约" in archive
    for path in CURRENT_PLAN_AUTHORITIES:
        assert path in archive
    assert "docs/plans/2026-03-07-agent-system-bc-evolution-implementation-plan.md" in archive


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
