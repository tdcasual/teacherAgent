from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api.assignment_meta_ownership_migrate_service import (
    AssignmentClaimError,
    MigrationPreflightError,
    claim_assignment,
    migrate_assignment_meta_ownership,
)
from services.api.auth_registry_service import AuthRegistryStore
from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "migrate_assignment_meta_ownership.py"


@pytest.fixture(autouse=True)
def _restore_auth_required() -> None:
    previous = os.environ.get("AUTH_REQUIRED")
    yield
    if previous is None:
        os.environ.pop("AUTH_REQUIRED", None)
    else:
        os.environ["AUTH_REQUIRED"] = previous


def _load_script():
    spec = importlib.util.spec_from_file_location("migrate_assignment_meta_ownership_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _auth_headers(actor_id: str, role: str, *, secret: str) -> dict[str, str]:
    now = int(time.time())
    claims = {"sub": actor_id, "role": role, "exp": now + 3600}
    if role == "admin":
        claims["tv"] = 1
    token = mint_test_token(claims, secret=secret)
    return {"Authorization": f"Bearer {token}"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _create_tables(db_path: Path, *, seed: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS teacher_roster (
                teacher_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                PRIMARY KEY (teacher_id, subject_id, class_name)
            );
            CREATE TABLE IF NOT EXISTS student_enrollments (
                student_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                PRIMARY KEY (student_id, subject_id, class_name)
            );
            """
        )
        if seed:
            conn.execute(
                "INSERT INTO subjects(subject_id, display_name, pack_id, created_at) "
                "VALUES ('generic', '通用', 'generic', '2026-08-28T00:00:00')"
            )
            conn.execute(
                "INSERT INTO subjects(subject_id, display_name, pack_id, created_at) "
                "VALUES ('physics', '物理', 'physics', '2026-08-28T00:00:00')"
            )
        conn.commit()
    finally:
        conn.close()


def _store(tmp_path: Path) -> AuthRegistryStore:
    data_dir = tmp_path / "data"
    return AuthRegistryStore(db_path=data_dir / "auth" / "auth_registry.sqlite3", data_dir=data_dir)


def _seed_teacher_class(tmp_path: Path) -> AuthRegistryStore:
    store = _store(tmp_path)
    store._ensure_teacher_auth(
        teacher_id="t_zhang", teacher_name="张老师", email=None, regenerate_token=False
    )
    store._ensure_student_auth(
        student_id="S001", student_name="刘昊然", class_name="高二2403班", regenerate_token=False
    )
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2403班",
        teacher_id="t_zhang",
    )
    return store


def _run_cli(tmp_path: Path, *extra: str) -> tuple[int, str]:
    mod = _load_script()
    argv = [
        "--data-dir",
        str(tmp_path / "data"),
        "--uploads-dir",
        str(tmp_path / "uploads"),
        *extra,
    ]
    try:
        code = mod.main(argv)
    except SystemExit as exc:
        code = int(exc.code or 0)
    return int(code or 0), ""


def test_exit_2_when_roster_tables_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_script()
    with pytest.raises(SystemExit) as exc:
        mod.main(["--data-dir", str(tmp_path / "data"), "--uploads-dir", str(tmp_path / "uploads")])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "roster_tables_missing" in (captured.out + captured.err)

    with pytest.raises(MigrationPreflightError) as err:
        migrate_assignment_meta_ownership(
            data_dir=tmp_path / "data",
            uploads_dir=tmp_path / "uploads",
            apply=False,
        )
    assert err.value.code == "roster_tables_missing"


def test_exit_2_when_subjects_seed_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "data" / "auth" / "auth_registry.sqlite3"
    _create_tables(db_path, seed=False)
    mod = _load_script()
    with pytest.raises(SystemExit) as exc:
        mod.main(["--data-dir", str(tmp_path / "data"), "--uploads-dir", str(tmp_path / "uploads")])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "subjects_seed_missing" in (captured.out + captured.err)


def test_dry_run_default_does_not_write(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    meta_path = tmp_path / "data" / "assignments" / "HW_old" / "meta.json"
    original = {
        "assignment_id": "HW_old",
        "job_id": "job_1",
        "scope": "public",
        "source": "teacher",
        "due_at": "",
    }
    _write_json(meta_path, original)
    _write_json(
        tmp_path / "uploads" / "assignment_jobs" / "job_1" / "job.json",
        {"teacher_id": "t_zhang", "subject_id": "physics"},
    )
    _write_json(
        tmp_path / "data" / "assignments" / "HW_old" / "requirements.json",
        {"subject": "物理"},
    )

    db_path = tmp_path / "data" / "auth" / "auth_registry.sqlite3"
    db_before = db_path.read_bytes()
    result = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data",
        uploads_dir=tmp_path / "uploads",
        apply=False,
    )
    assert result["ok"] is True
    assert result["apply"] is False
    assert result["counts"]["migrated"] == 1
    assert meta_path.read_text(encoding="utf-8")
    assert _read_json(meta_path) == original
    assert not (meta_path.parent / "meta.json.bak").exists()
    assert db_path.read_bytes() == db_before

    code, _ = _run_cli(tmp_path)
    assert code == 0
    assert _read_json(meta_path) == original


def test_apply_writes_owner_fields_and_bak(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    folder = tmp_path / "data" / "assignments" / "HW_owned"
    meta_path = folder / "meta.json"
    original = {
        "assignment_id": "HW_owned",
        "job_id": "job_owned",
        "scope": "public",
        "source": "teacher",
        "due_at": "",
        "date": "",
    }
    _write_json(meta_path, original)
    _write_json(
        tmp_path / "uploads" / "assignment_jobs" / "job_owned" / "job.json",
        {"teacher_id": "t_zhang"},
    )
    _write_json(folder / "requirements.json", {"subject": "物理"})

    result = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data",
        uploads_dir=tmp_path / "uploads",
        apply=True,
    )
    assert result["ok"] is True
    assert result["apply"] is True
    assert result["counts"]["migrated"] == 1
    assert result["counts"]["skipped"] == 0

    bak = _read_json(folder / "meta.json.bak")
    assert bak == original
    meta = _read_json(meta_path)
    assert meta["teacher_id"] == "t_zhang"
    assert meta["subject_id"] == "physics"
    assert meta["visibility_status"] == "published"
    assert meta["due_at"] == ""
    assert meta["teacher_id"] != "teacher"
    assert "teacher" != meta["teacher_id"]
    assert meta["expected_students"] == ["S001"]
    assert meta.get("needs_subject_review") not in {True, "true"}
    assert meta.get("needs_roster_review") not in {True, "true"}
    policy = meta.get("completion_policy") or {}
    assert policy.get("requires_discussion") is False
    assert policy.get("version") == 2
    assert policy.get("requires_submission") is True


def test_second_apply_skips_and_does_not_overwrite_bak(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    folder = tmp_path / "data" / "assignments" / "HW_owned"
    meta_path = folder / "meta.json"
    original = {
        "assignment_id": "HW_owned",
        "job_id": "job_owned",
        "scope": "public",
        "source": "teacher",
        "due_at": "",
    }
    _write_json(meta_path, original)
    _write_json(
        tmp_path / "uploads" / "assignment_jobs" / "job_owned" / "job.json",
        {"teacher_id": "t_zhang"},
    )
    _write_json(folder / "requirements.json", {"subject": "物理"})

    first = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert first["counts"]["migrated"] == 1
    bak_text = (folder / "meta.json.bak").read_text(encoding="utf-8")
    migrated = _read_json(meta_path)

    second = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert second["counts"]["skipped"] == 1
    assert second["counts"]["migrated"] == 0
    assert (folder / "meta.json.bak").read_text(encoding="utf-8") == bak_text
    assert _read_json(meta_path) == migrated
    assert json.loads(bak_text) == original


def test_unmapped_subject_stays_unpublished_on_second_apply(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    folder = tmp_path / "data" / "assignments" / "HW_chem"
    meta_path = folder / "meta.json"
    _write_json(
        meta_path,
        {
            "assignment_id": "HW_chem",
            "teacher_id": "t_zhang",
            "scope": "class",
            "class_name": "高二2403班",
            "source": "teacher",
            "due_at": "",
        },
    )
    _write_json(folder / "requirements.json", {"subject": "化学"})

    first = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert first["counts"]["needs_subject_review"] == 1
    meta = _read_json(meta_path)
    assert meta["subject_id"] == "generic"
    assert meta["needs_subject_review"] is True
    assert meta["visibility_status"] != "published"
    assert meta["visibility_status"] in {"draft", "orphan_draft"}
    assert meta["teacher_id"] == "t_zhang"
    assert meta["teacher_id"] != "teacher"

    second = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    again = _read_json(meta_path)
    assert again["visibility_status"] != "published"
    assert again["needs_subject_review"] is True
    assert again["subject_id"] == "generic"
    assert second["counts"]["needs_subject_review"] == 1


def test_rerun_after_roster_clears_review_flags_but_does_not_publish(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._ensure_teacher_auth(
        teacher_id="t_zhang", teacher_name="张老师", email=None, regenerate_token=False
    )
    folder = tmp_path / "data" / "assignments" / "HW_public"
    meta_path = folder / "meta.json"
    _write_json(
        meta_path,
        {
            "assignment_id": "HW_public",
            "teacher_id": "t_zhang",
            "subject_id": "physics",
            "scope": "public",
            "source": "teacher",
            "due_at": "",
        },
    )

    first = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert first["counts"]["needs_roster_review"] == 1
    meta = _read_json(meta_path)
    assert meta["needs_roster_review"] is True
    assert meta["visibility_status"] != "published"

    store._ensure_student_auth(
        student_id="S001", student_name="刘昊然", class_name="高二2403班", regenerate_token=False
    )
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2403班",
        teacher_id="t_zhang",
    )

    second = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    again = _read_json(meta_path)
    assert again.get("needs_roster_review") not in {True, "true"}
    assert again["expected_students"] == ["S001"]
    assert again["visibility_status"] != "published"
    assert second["counts"]["needs_roster_review"] == 0


def test_explicit_requires_discussion_true_is_kept(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    folder = tmp_path / "data" / "assignments" / "HW_discuss"
    _write_json(
        folder / "meta.json",
        {
            "assignment_id": "HW_discuss",
            "teacher_id": "t_zhang",
            "subject_id": "physics",
            "scope": "class",
            "class_name": "高二2403班",
            "source": "teacher",
            "due_at": "",
            "completion_policy": {"requires_discussion": True, "version": 1},
        },
    )
    migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    policy = _read_json(folder / "meta.json").get("completion_policy") or {}
    assert policy.get("requires_discussion") is True
    assert policy.get("version") == 1


def test_missing_teacher_is_orphan_and_auto_is_retired(tmp_path: Path) -> None:
    _seed_teacher_class(tmp_path)
    orphan_path = tmp_path / "data" / "assignments" / "HW_orphan" / "meta.json"
    auto_path = tmp_path / "data" / "assignments" / "HW_auto" / "meta.json"
    _write_json(
        orphan_path,
        {"assignment_id": "HW_orphan", "scope": "public", "source": "teacher", "due_at": ""},
    )
    _write_json(
        auto_path,
        {
            "assignment_id": "HW_auto",
            "source": "auto",
            "scope": "student",
            "due_at": "",
            "teacher_id": "teacher",
        },
    )

    result = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert result["counts"]["orphan"] == 1
    assert result["counts"]["retired_auto"] == 1
    orphan = _read_json(orphan_path)
    auto = _read_json(auto_path)
    assert orphan["visibility_status"] == "orphan_draft"
    assert "teacher_id" not in orphan or not str(orphan.get("teacher_id") or "").strip()
    assert auto["visibility_status"] == "retired_auto"
    assert auto.get("teacher_id") != "teacher"
    assert orphan.get("due_at") == ""
    assert auto.get("due_at") == ""


def test_never_writes_default_teacher_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_TEACHER_ID", "teacher")
    _seed_teacher_class(tmp_path)
    meta_path = tmp_path / "data" / "assignments" / "HW_default" / "meta.json"
    _write_json(
        meta_path,
        {
            "assignment_id": "HW_default",
            "teacher_id": "teacher",
            "job_id": "job_default",
            "scope": "public",
            "source": "teacher",
            "due_at": "",
        },
    )
    _write_json(
        tmp_path / "uploads" / "assignment_jobs" / "job_default" / "job.json",
        {"teacher_id": "teacher"},
    )
    result = migrate_assignment_meta_ownership(
        data_dir=tmp_path / "data", uploads_dir=tmp_path / "uploads", apply=True
    )
    assert result["counts"]["orphan"] == 1
    meta = _read_json(meta_path)
    assert meta.get("teacher_id") not in {"teacher", "DEFAULT_TEACHER_ID"}
    assert meta["visibility_status"] == "orphan_draft"
    dumped = json.dumps(meta)
    assert '"teacher_id": "teacher"' not in dumped


def _load_app(tmp_path: Path, *, secret: str, auth_required: str = "1"):
    return create_test_app(
        tmp_path,
        env_overrides={
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
            "AUTH_REQUIRED": auth_required,
            "AUTH_TOKEN_SECRET": secret,
            "ADMIN_USERNAME": "admin",
        },
        env_unset=["ADMIN_PASSWORD"],
    )


def test_orphans_and_claim_admin_only(tmp_path: Path) -> None:
    secret = "migrate-claim-secret"
    store = _seed_teacher_class(tmp_path)
    store.add_subject(subject_id="math", display_name="数学", pack_id="math")
    orphan_id = "HW_claim"
    leftover_id = "HW_public_stale_class"
    _write_json(
        tmp_path / "data" / "assignments" / orphan_id / "meta.json",
        {
            "assignment_id": orphan_id,
            "visibility_status": "orphan_draft",
            "scope": "public",
            "source": "teacher",
            "due_at": "",
            "subject_id": "generic",
            "needs_subject_review": True,
        },
    )
    _write_json(
        tmp_path / "data" / "assignments" / leftover_id / "meta.json",
        {
            "assignment_id": leftover_id,
            "visibility_status": "orphan_draft",
            "scope": "public",
            "class_name": "高二9999班",
            "source": "teacher",
            "due_at": "",
        },
    )
    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin = _auth_headers("admin", "admin", secret=secret)
    teacher = _auth_headers("t_zhang", "teacher", secret=secret)

    denied = client.get("/auth/admin/assignments/orphans", headers=teacher)
    assert denied.status_code == 403

    unauth = client.get("/auth/admin/assignments/orphans")
    assert unauth.status_code == 401

    listed = client.get("/auth/admin/assignments/orphans", headers=admin)
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    assert {item["assignment_id"] for item in items} == {orphan_id, leftover_id}

    forbidden_claim = client.post(
        f"/auth/admin/assignments/{orphan_id}/claim",
        headers=admin,
        json={"teacher_id": "teacher", "subject_id": "physics", "visibility_status": "published"},
    )
    assert forbidden_claim.status_code == 400
    assert forbidden_claim.json().get("detail") in {
        "default_teacher_id_forbidden",
        "teacher_id_forbidden",
    }

    teacher_claim = client.post(
        f"/auth/admin/assignments/{orphan_id}/claim",
        headers=teacher,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "visibility_status": "draft"},
    )
    assert teacher_claim.status_code == 403

    no_roster = client.post(
        f"/auth/admin/assignments/{orphan_id}/claim",
        headers=admin,
        json={"teacher_id": "t_zhang", "subject_id": "math", "visibility_status": "draft"},
    )
    assert no_roster.status_code == 400
    assert no_roster.json().get("detail") == "roster_required"

    claimed = client.post(
        f"/auth/admin/assignments/{orphan_id}/claim",
        headers=admin,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "visibility_status": "published"},
    )
    assert claimed.status_code == 200
    payload = claimed.json()
    assert payload.get("ok") is True
    assert payload.get("teacher_id") == "t_zhang"
    assert payload.get("subject_id") == "physics"
    assert payload.get("visibility_status") == "published"

    meta = _read_json(tmp_path / "data" / "assignments" / orphan_id / "meta.json")
    assert meta["teacher_id"] == "t_zhang"
    assert meta["subject_id"] == "physics"
    assert meta["visibility_status"] == "published"
    assert meta.get("needs_subject_review") not in {True, "true"}
    assert meta["teacher_id"] != "teacher"
    assert "S001" in (meta.get("expected_students") or [])

    already = client.post(
        f"/auth/admin/assignments/{orphan_id}/claim",
        headers=admin,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "visibility_status": "draft"},
    )
    assert already.status_code == 409
    assert already.json().get("detail") == "not_orphan"

    leftover = client.post(
        f"/auth/admin/assignments/{leftover_id}/claim",
        headers=admin,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "visibility_status": "published"},
    )
    assert leftover.status_code == 200
    leftover_meta = _read_json(tmp_path / "data" / "assignments" / leftover_id / "meta.json")
    assert leftover_meta["teacher_id"] == "t_zhang"
    assert leftover_meta["visibility_status"] == "published"
    assert "S001" in (leftover_meta.get("expected_students") or [])

    gone = client.get("/auth/admin/assignments/orphans", headers=admin)
    assert gone.status_code == 200
    assert gone.json().get("items") == []

    with pytest.raises(AssignmentClaimError) as claim_exc:
        claim_assignment(
            leftover_id,
            teacher_id="teacher",
            subject_id="physics",
            visibility_status="draft",
            data_dir=tmp_path / "data",
            principal_actor_id="admin",
            principal_role="admin",
        )
    assert claim_exc.value.detail == "default_teacher_id_forbidden"


def test_orphans_reject_admin_local_when_auth_off(tmp_path: Path) -> None:
    secret = "migrate-local-secret"
    _store(tmp_path)
    app_mod = _load_app(tmp_path, secret=secret, auth_required="0")
    client = TestClient(app_mod.app)
    response = client.get("/auth/admin/assignments/orphans")
    assert response.status_code == 401
    assert response.json().get("detail") != "admin_local"
