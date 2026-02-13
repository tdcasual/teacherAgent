from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_markdown_absolutize_uses_validated_api_base() -> None:
    source = _read("frontend/apps/shared/markdown.ts")
    assert "normalizeApiBase" in source
    assert "const base = normalizeApiBase(apiBase)" in source


def test_teacher_routing_and_persona_apis_use_safe_error_mapping() -> None:
    routing = _read("frontend/apps/teacher/src/features/routing/routingApi.ts")
    persona = _read("frontend/apps/teacher/src/features/persona/personaApi.ts")
    assert "toUserFacingErrorMessage" in routing
    assert "toUserFacingErrorMessage" in persona
    assert "JSON.stringify(detail || data || {})" not in routing
    assert "JSON.stringify(detail || data || {})" not in persona


def test_student_and_teacher_error_helpers_use_shared_user_facing_mapper() -> None:
    student = _read("frontend/apps/student/src/hooks/useStudentState.ts")
    teacher = _read("frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts")
    assert "toUserFacingErrorMessage" in student
    assert "toUserFacingErrorMessage" in teacher


def test_markdown_katex_schema_disallows_unbounded_style_attrs() -> None:
    source = _read("frontend/apps/shared/markdown.ts")
    assert "span: [...(defaultSchema.attributes?.span || []), 'className', 'style']" not in source
    assert "div: [...(defaultSchema.attributes?.div || []), 'className', 'style']" not in source
