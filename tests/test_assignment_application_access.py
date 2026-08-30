from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from services.api.assignment.application import (
    AssignmentAccessError,
    download_assignment_file,
    get_assignment_detail,
    require_assignment_access,
)
from services.api.assignment.deps import AssignmentAccessDeps
from services.api.auth_service import AuthError, AuthPrincipal


def _deps(*, folder: Path, specificity: int = 0, meta: dict | None = None) -> AssignmentAccessDeps:
    return AssignmentAccessDeps(
        resolve_assignment_dir=lambda _assignment_id: folder,
        load_assignment_meta=lambda _folder: dict(meta or {}),
        resolve_student_profile_path=lambda student_id: folder / f"{student_id}.json",
        load_profile_file=lambda _path: {},
        assignment_specificity=lambda _meta, _student_id, _class_name: specificity,
    )


def test_require_assignment_access_skips_when_auth_off(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: False)
    require_assignment_access("HW_1", deps=_deps(folder=tmp_path))


def test_require_assignment_access_allows_owning_teacher(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="t1", role="teacher"),
    )
    require_assignment_access(
        "HW_1",
        deps=_deps(folder=tmp_path, specificity=0, meta={"teacher_id": "t1"}),
    )


def test_require_assignment_access_forbids_other_teacher(monkeypatch, tmp_path):
    folder = tmp_path / "HW_OTHER"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="t1", role="teacher"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_OTHER",
            deps=_deps(folder=folder, specificity=0, meta={"teacher_id": "t2"}),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_owner"


def test_require_assignment_access_teacher_missing_actor_id_is_4xx(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="", role="teacher"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_1",
            deps=_deps(folder=tmp_path, meta={"teacher_id": "t1"}),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "teacher_id_required"


def test_require_assignment_access_admin_can_read_orphan(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="admin", role="admin"),
    )
    require_assignment_access("HW_1", deps=_deps(folder=tmp_path, specificity=0, meta={}))


def test_require_assignment_access_forbids_out_of_scope_student(monkeypatch, tmp_path):
    folder = tmp_path / "HW_SEC_1"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_a", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_SEC_1",
            deps=_deps(
                folder=folder,
                specificity=0,
                meta={"scope": "student", "student_ids": ["student_b"], "teacher_id": "t1"},
            ),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_scope"


def test_require_assignment_access_allows_in_scope_student(monkeypatch, tmp_path):
    folder = tmp_path / "HW_OK"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    require_assignment_access(
        "HW_OK",
        deps=_deps(folder=folder, specificity=3, meta={"teacher_id": "t1"}),
    )


def test_require_assignment_access_hides_student_when_meta_has_no_teacher_id(monkeypatch, tmp_path):
    folder = tmp_path / "HW_ORPHAN"
    folder.mkdir()
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_ORPHAN",
            deps=_deps(folder=folder, specificity=3, meta={"scope": "public"}),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_scope"


def test_require_assignment_access_student_missing_visibility_with_owner_is_published(
    monkeypatch, tmp_path
):
    folder = tmp_path / "HW_LEGACY"
    folder.mkdir()
    logs: list[tuple[str, dict]] = []
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_b", role="student"),
    )
    monkeypatch.setattr(
        "services.api.assignment.visibility.log_missing_visibility_owner",
        lambda **payload: logs.append(("assignment.meta.missing_owner", dict(payload))),
    )
    require_assignment_access(
        "HW_LEGACY",
        deps=_deps(
            folder=folder,
            specificity=3,
            meta={"teacher_id": "t1", "scope": "public"},
        ),
    )
    assert logs
    assert logs[0][0] == "assignment.meta.missing_owner"


def test_require_assignment_access_student_draft_is_hidden(monkeypatch, tmp_path):
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
                specificity=3,
                meta={"teacher_id": "t1", "visibility_status": "draft"},
            ),
        )
    assert exc.value.status_code == 403


def test_require_assignment_access_missing_assignment_is_404(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_a", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access("missing", deps=_deps(folder=tmp_path / "nope", specificity=3))
    assert exc.value.status_code == 404
    assert exc.value.detail == "assignment not found"


def test_require_assignment_access_invalid_id_is_400(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="student_a", role="student"),
    )

    def _boom(_assignment_id: str) -> Path:
        raise ValueError("invalid assignment_id")

    deps = AssignmentAccessDeps(
        resolve_assignment_dir=_boom,
        load_assignment_meta=lambda _folder: {},
        resolve_student_profile_path=lambda student_id: tmp_path / f"{student_id}.json",
        load_profile_file=lambda _path: {},
        assignment_specificity=lambda *_args: 3,
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access("../escape", deps=deps)
    assert exc.value.status_code == 400
    assert exc.value.detail == "invalid assignment_id"


def test_require_assignment_access_wraps_auth_error(monkeypatch, tmp_path):
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)

    def _deny(**_kwargs):
        raise AuthError(401, "missing_authorization")

    monkeypatch.setattr("services.api.assignment.application.require_principal", _deny)
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access("HW_1", deps=_deps(folder=tmp_path))
    assert exc.value.status_code == 401
    assert exc.value.detail == "missing_authorization"


def test_download_assignment_file_enforces_access_before_download(monkeypatch):
    called = {"download": 0}

    def _forbid(assignment_id: str, *, deps):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")

    async def _download(_assignment_id: str, _file: str):
        called["download"] += 1
        return {"ok": True}

    monkeypatch.setattr("services.api.assignment.application.require_assignment_access", _forbid)
    deps = type("Deps", (), {"assignment_download": _download})()

    async def _run() -> None:
        with pytest.raises(AssignmentAccessError) as exc:
            await download_assignment_file("HW_SEC_1", "paper.txt", deps=deps)
        assert exc.value.status_code == 403

    asyncio.run(_run())
    assert called["download"] == 0


def test_get_assignment_detail_enforces_access(monkeypatch):
    def _forbid(assignment_id: str, *, deps):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")

    async def _detail(_assignment_id: str):
        return {"ok": True}

    monkeypatch.setattr("services.api.assignment.application.require_assignment_access", _forbid)
    deps = type("Deps", (), {"assignment_detail": _detail})()

    async def _run() -> None:
        with pytest.raises(AssignmentAccessError) as exc:
            await get_assignment_detail("HW_SEC_2", deps=deps)
        assert exc.value.status_code == 403

    asyncio.run(_run())
