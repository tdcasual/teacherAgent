from __future__ import annotations

from pathlib import Path

import pytest

from services.api.paths import (
    TeacherIdentityError,
    require_teacher_id,
    resolve_teacher_id,
    safe_fs_id,
)


def test_require_teacher_id_rejects_none_empty_and_whitespace() -> None:
    for value in (None, "", "   "):
        with pytest.raises(Exception) as exc:
            require_teacher_id(value)
        assert type(exc.value).__name__ == "TeacherIdentityError"
        assert getattr(exc.value, "detail", None) == "teacher_id_required"
        assert getattr(exc.value, "status_code", None) == 400
        assert str(exc.value) == "teacher_id_required"


def test_require_teacher_id_returns_filesystem_safe_id() -> None:
    assert require_teacher_id("t_zhang") == safe_fs_id("t_zhang", prefix="teacher")
    assert require_teacher_id("teacher_a") == "teacher_a"


def test_resolve_teacher_id_none_still_bootstraps_default() -> None:
    # Bootstrap / auth_registry seed path stays on the legacy fallback.
    assert resolve_teacher_id(None)
    assert resolve_teacher_id("")


def test_teacher_config_wiring_uses_require_teacher_id() -> None:
    source = Path("services/api/wiring/teacher_wiring.py").read_text(encoding="utf-8")
    assert "require_teacher_id" in source
    assert "resolve_teacher_id=_ac.resolve_teacher_id" not in source


def test_tool_dispatch_wiring_uses_require_teacher_id() -> None:
    source = Path("services/api/wiring/misc_wiring.py").read_text(encoding="utf-8")
    assert "resolve_teacher_id=_ac.require_teacher_id" in source
    assert "resolve_teacher_id=_ac.resolve_teacher_id" not in source


def test_student_submit_wiring_authorizes_assignment() -> None:
    source = Path("services/api/wiring/student_wiring.py").read_text(encoding="utf-8")
    assert "authorize_student_submit" in source
    assert "authorize_student_submit_assignment" in source
