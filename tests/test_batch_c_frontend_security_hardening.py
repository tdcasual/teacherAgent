from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_markdown_absolutize_uses_validated_api_base() -> None:
    source = _read("frontend/apps/shared/markdown.ts")
    assert "normalizeApiBase" in source
    assert "const base = normalizeApiBase(apiBase)" in source


def test_teacher_legacy_routing_and_persona_frontend_files_removed() -> None:
    assert not (_ROOT / "frontend/apps/teacher/src/features/routing").exists()
    assert not (_ROOT / "frontend/apps/teacher/src/features/persona").exists()


def test_student_and_teacher_error_helpers_use_shared_user_facing_mapper() -> None:
    student = _read("frontend/apps/student/src/hooks/useStudentState.ts")
    teacher = _read("frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts")
    assert "toUserFacingErrorMessage" in student
    assert "toUserFacingErrorMessage" in teacher


def test_markdown_katex_schema_disallows_unbounded_style_attrs() -> None:
    source = _read("frontend/apps/shared/markdown.ts")
    assert "span: [...(defaultSchema.attributes?.span || []), 'className', 'style']" not in source
    assert "div: [...(defaultSchema.attributes?.div || []), 'className', 'style']" not in source
