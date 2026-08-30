from __future__ import annotations

import pytest

from services.api.paths import (
    TeacherIdentityError,
    require_teacher_id,
    resolve_teacher_id,
    safe_fs_id,
)


def test_require_teacher_id_rejects_none_empty_and_whitespace() -> None:
    for value in (None, "", "   "):
        with pytest.raises(TeacherIdentityError) as exc:
            require_teacher_id(value)
        assert exc.value.detail == "teacher_id_required"
        assert exc.value.status_code == 400
        assert str(exc.value) == "teacher_id_required"


def test_require_teacher_id_returns_filesystem_safe_id() -> None:
    assert require_teacher_id("t_zhang") == safe_fs_id("t_zhang", prefix="teacher")
    assert require_teacher_id("teacher_a") == "teacher_a"


def test_resolve_teacher_id_none_still_bootstraps_default() -> None:
    # Bootstrap / auth_registry seed path stays on the legacy fallback.
    assert resolve_teacher_id(None)
    assert resolve_teacher_id("")
