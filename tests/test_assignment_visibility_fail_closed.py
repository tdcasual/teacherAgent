from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.api.assignment.application import AssignmentAccessError, require_assignment_access
from services.api.assignment.deps import AssignmentAccessDeps
from services.api.assignment.store import (
    assignment_is_sql_published,
    connect,
    ensure,
    get_assignment,
)
from services.api.assignment.visibility import (
    effective_visibility_status,
    student_can_read_assignment,
)
from services.api.assignment_archive_service import archive_assignment
from services.api.assignment_student_list_service import (
    StudentAssignmentListDeps,
    list_assignments_for_student,
    list_student_assignment_history,
)
from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    confirm_assignment_upload,
)
from services.api.auth_service import AuthPrincipal
from services.api.settings import default_teacher_id
from services.api.student_submit_service import (
    StudentSubmitError,
    authorize_student_submit_assignment,
)

_MISSING_VIS_META = {"teacher_id": "t_zhang", "scope": "public"}


def _deps(
    *,
    folder: Path,
    specificity: int = 3,
    meta: dict | None = None,
    enrolled: bool = True,
    sql_visibility=None,
) -> AssignmentAccessDeps:
    return AssignmentAccessDeps(
        resolve_assignment_dir=lambda _assignment_id: folder,
        load_assignment_meta=lambda _folder: dict(meta or {}),
        resolve_student_profile_path=lambda student_id: folder / f"{student_id}.json",
        load_profile_file=lambda _path: {},
        assignment_specificity=lambda _meta, _student_id, _class_name: specificity,
        student_enrolled=lambda *_args, **_kwargs: enrolled,
        sql_visibility=sql_visibility,
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


_TODAY = "2026-08-28"


def _write_assignment_meta(data_dir: Path, assignment_id: str, meta: dict) -> Path:
    folder = data_dir / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"assignment_id": assignment_id, **meta}
    (folder / "meta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return folder


def _published_meta(**overrides: object) -> dict:
    payload: dict = {
        "teacher_id": "t_zhang",
        "subject_id": "physics",
        "pack_id": "physics",
        "visibility_status": "published",
        "scope": "public",
        "class_name": "",
        "expected_students": ["S1"],
        "date": _TODAY,
        "due_at": "2026-08-29T23:59:59",
        "completion_policy": {"version": 2, "requires_submission": True},
    }
    payload.update(overrides)
    return payload


def _list_today(data_dir: Path, student_id: str = "S1") -> list[dict]:
    deps = StudentAssignmentListDeps(
        data_dir=data_dir,
        load_assignment_meta=lambda folder: json.loads((folder / "meta.json").read_text(encoding="utf-8")),
        student_enrolled=lambda *_args, **_kwargs: True,
        list_submission_attempts=lambda *_args, **_kwargs: [],
        lookback_days=14,
    )
    return list_assignments_for_student(student_id=student_id, date_str=_TODAY, deps=deps)


def _confirm_deps(data_dir: Path) -> AssignmentUploadConfirmDeps:
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return AssignmentUploadConfirmDeps(
        data_dir=data_dir,
        now_iso=lambda: "2026-08-28T12:00:00",
        discussion_complete_marker="[[discussion_complete]]",
        write_upload_job=lambda _job_id, updates: updates,
        merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
        compute_requirements_missing=lambda req: [] if req.get("subject") else ["subject"],
        write_uploaded_questions=lambda _out, _aid, _questions: [{"question_id": "Q1"}],
        optional_assignment_date=lambda value: str(value).strip() if str(value or "").strip() else None,
        save_assignment_requirements=lambda *_args, **_kwargs: None,
        parse_ids_value=lambda value: value if isinstance(value, list) else [],
        resolve_scope=lambda scope, _student_ids, _class_name: str(scope or "") or "public",
        normalize_due_at=lambda value: str(value or ""),
        compute_expected_students=lambda *_args, **_kwargs: ["S1"],
        atomic_write_json=_write_json,
        copy2=lambda src, dst: dst.write_bytes(src.read_bytes()) if src.exists() else None,
    )


def _prepare_confirm_job(root: Path, job_id: str = "job-heal") -> Path:
    job_dir = root / "uploads" / "assignment_jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "parsed.json").write_text(
        json.dumps(
            {
                "questions": [{"stem": "x"}],
                "requirements": {"subject": "物理"},
                "missing": [],
                "warnings": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return job_dir


def test_json_only_published_is_visible_after_one_shot_migrate(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _write_assignment_meta(data_dir, "HW_LEGACY", _published_meta(title="遗产作业"))
    items = _list_today(data_dir)
    assert [item["assignment_id"] for item in items] == ["HW_LEGACY"]


def test_crash_orphan_sql_miss_stays_hidden_after_ensure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_TEACHER_ID", "teacher")
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
    finally:
        conn.close()
    _write_assignment_meta(data_dir, "HW_CRASH", _published_meta(title="COMMIT失败孤儿"))
    assert _list_today(data_dir) == []
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        row = get_assignment(conn, "HW_CRASH")
    finally:
        conn.close()
    assert row is None
    assert _list_today(data_dir) == []


def test_heal_upsert_makes_crash_orphan_visible_to_students(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
    finally:
        conn.close()
    _write_assignment_meta(data_dir, "HW_CRASH", _published_meta(title="待heal"))
    assert _list_today(data_dir) == []
    job_dir = _prepare_confirm_job(tmp_path)
    result = confirm_assignment_upload(
        "job-heal",
        {
            "assignment_id": "HW_CRASH",
            "status": "done",
            "teacher_id": "t_zhang",
            "subject_id": "physics",
            "scope": "public",
        },
        job_dir,
        requirements_override=None,
        strict_requirements=True,
        deps=_confirm_deps(data_dir),
    )
    assert result.get("ok") is True
    assert result.get("status") == "confirmed"
    items = _list_today(data_dir)
    assert [item["assignment_id"] for item in items] == ["HW_CRASH"]


def test_missing_teacher_id_migrates_to_orphan_draft_not_default_teacher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEFAULT_TEACHER_ID", "teacher")
    data_dir = tmp_path / "data"
    _write_assignment_meta(
        data_dir,
        "HW_ORPHAN",
        _published_meta(teacher_id="", title="无教师"),
    )
    assert _list_today(data_dir) == []
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        row = get_assignment(conn, "HW_ORPHAN")
    finally:
        conn.close()
    assert row is not None
    assert str(row["visibility_status"]) == "orphan_draft"
    assert str(row["teacher_id"] or "") == ""
    assert str(row["teacher_id"] or "") != default_teacher_id()
    assert str(row["teacher_id"] or "") != "teacher"


def _history(data_dir: Path, student_id: str = "S1") -> dict:
    deps = StudentAssignmentListDeps(
        data_dir=data_dir,
        load_assignment_meta=lambda folder: json.loads((folder / "meta.json").read_text(encoding="utf-8")),
        student_enrolled=lambda *_args, **_kwargs: True,
        list_submission_attempts=lambda *_args, **_kwargs: [],
        lookback_days=14,
    )
    return list_student_assignment_history(student_id=student_id, deps=deps)


def test_archive_hides_from_student_today_and_submit(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _write_assignment_meta(data_dir, "HW_1", _published_meta(title="待归档"))
    assert [item["assignment_id"] for item in _list_today(data_dir)] == ["HW_1"]
    archive_assignment(
        "HW_1",
        principal=AuthPrincipal(actor_id="t_zhang", role="teacher"),
        data_dir=data_dir,
    )
    assert _list_today(data_dir) == []
    with pytest.raises(StudentSubmitError) as exc:
        authorize_student_submit_assignment(
            "HW_1",
            "S1",
            load_meta=lambda _aid: json.loads(
                (data_dir / "assignments" / "HW_1" / "meta.json").read_text(encoding="utf-8")
            ),
            student_enrolled=lambda *_args, **_kwargs: True,
            is_sql_published=lambda aid: assignment_is_sql_published(data_dir, aid),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_scope"
    conn = connect(data_dir)
    try:
        row = get_assignment(conn, "HW_1")
    finally:
        conn.close()
    assert row is not None
    assert str(row["visibility_status"]) == "archived"


def test_history_and_detail_hide_crash_orphan(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
    finally:
        conn.close()
    folder = _write_assignment_meta(data_dir, "HW_CRASH", _published_meta(title="孤儿详情"))
    history_ids = [item["assignment_id"] for item in _history(data_dir)["assignments"]]
    assert "HW_CRASH" not in history_ids
    monkeypatch.setattr("services.api.assignment.application.auth_required", lambda: True)
    monkeypatch.setattr(
        "services.api.assignment.application.require_principal",
        lambda **_kwargs: AuthPrincipal(actor_id="S1", role="student"),
    )
    with pytest.raises(AssignmentAccessError) as exc:
        require_assignment_access(
            "HW_CRASH",
            deps=_deps(
                folder=folder,
                meta=_published_meta(expected_students=["S1"]),
                sql_visibility=lambda _aid: "",
            ),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_assignment_scope"
