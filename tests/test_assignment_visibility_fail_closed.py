from __future__ import annotations

from pathlib import Path

import pytest

from services.api.assignment.application import AssignmentAccessError, require_assignment_access
from services.api.assignment.deps import AssignmentAccessDeps
from services.api.assignment.visibility import (
    effective_visibility_status,
    student_can_read_assignment,
)
from services.api.auth_service import AuthPrincipal

_MISSING_VIS_META = {"teacher_id": "t_zhang", "scope": "public"}


def _deps(*, folder: Path, specificity: int = 3, meta: dict | None = None, enrolled: bool = True) -> AssignmentAccessDeps:
    return AssignmentAccessDeps(
        resolve_assignment_dir=lambda _assignment_id: folder,
        load_assignment_meta=lambda _folder: dict(meta or {}),
        resolve_student_profile_path=lambda student_id: folder / f"{student_id}.json",
        load_profile_file=lambda _path: {},
        assignment_specificity=lambda _meta, _student_id, _class_name: specificity,
        student_enrolled=lambda *_args, **_kwargs: enrolled,
    )


def test_missing_visibility_status_is_not_published() -> None:
    assert effective_visibility_status(_MISSING_VIS_META) == ""
    assert effective_visibility_status({"teacher_id": "t1", "visibility_status": "published"}) == (
        "published"
    )


def test_student_cannot_read_missing_visibility_status() -> None:
    assert student_can_read_assignment(_MISSING_VIS_META) is False
    assert student_can_read_assignment(_MISSING_VIS_META, for_today=True) is False


def test_student_visibility_keeps_draft_archived_orphan_and_retired_semantics() -> None:
    owner = {"teacher_id": "t_zhang", "scope": "public"}
    assert student_can_read_assignment({**owner, "visibility_status": "published"}) is True
    assert student_can_read_assignment({**owner, "visibility_status": "archived"}) is True
    assert student_can_read_assignment(
        {**owner, "visibility_status": "archived"}, for_today=True
    ) is False
    for hidden in ("draft", "orphan_draft", "retired_auto", ""):
        meta = {**owner, "visibility_status": hidden} if hidden else dict(owner)
        assert student_can_read_assignment(meta) is False
        assert student_can_read_assignment(meta, for_today=True) is False


def test_require_assignment_access_hides_missing_visibility_from_student(
    monkeypatch, tmp_path
) -> None:
    folder = tmp_path / "HW_LEGACY"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_LEGACY",
            deps=_deps(folder=folder, meta=_MISSING_VIS_META),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_scope"


def test_require_assignment_access_hides_missing_visibility_from_non_owner_teacher(
    monkeypatch, tmp_path
) -> None:
    folder = tmp_path / "HW_LEGACY"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="t_li", role="teacher"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_LEGACY",
            deps=_deps(folder=folder, meta=_MISSING_VIS_META),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_owner"


def test_require_assignment_access_owner_teacher_can_read_missing_visibility(
    monkeypatch, tmp_path
) -> None:
    folder = tmp_path / "HW_LEGACY"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="t_zhang", role="teacher"),
    )
    require_assignment_access(
        "HW_LEGACY",
        deps=_deps(folder=folder, meta=_MISSING_VIS_META),
    )


def test_require_assignment_access_admin_can_read_orphan(monkeypatch, tmp_path) -> None:
    folder = tmp_path / "HW_ORPHAN"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="admin", role="admin"),
    )
    require_assignment_access("HW_ORPHAN", deps=_deps(folder=folder, specificity=0, meta={}))


def test_student_can_read_archived_when_on_frozen_snapshot(monkeypatch, tmp_path) -> None:
    folder = tmp_path / "HW_ARCHIVED"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    require_assignment_access(
        "HW_ARCHIVED",
        deps=_deps(
            folder=folder,
            enrolled=False,
            meta={
                "teacher_id": "t_zhang",
                "subject_id": "physics",
                "visibility_status": "archived",
                "expected_students": ["student_b"],
            },
        ),
    )


def test_student_cannot_read_draft_even_on_snapshot(monkeypatch, tmp_path) -> None:
    folder = tmp_path / "HW_DRAFT"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_DRAFT",
            deps=_deps(
                folder=folder,
                meta={
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                    "visibility_status": "draft",
                    "expected_students": ["student_b"],
                },
            ),
        )
    assert exc.value.status_code == 403
