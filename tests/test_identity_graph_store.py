from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.api.auth.identity_graph_service import ExpectedStudentsError
from services.api.auth_registry_service import AuthRegistryStore
from services.api.core_services_application import compute_expected_students


def _store(tmp_path: Path) -> AuthRegistryStore:
    data_dir = tmp_path / "data"
    return AuthRegistryStore(db_path=data_dir / "auth" / "auth_registry.sqlite3", data_dir=data_dir)


def _add_teacher(store: AuthRegistryStore, teacher_id: str = "t_zhang") -> None:
    store._ensure_teacher_auth(
        teacher_id=teacher_id,
        teacher_name=teacher_id,
        email=None,
        regenerate_token=False,
    )


def _add_student(
    store: AuthRegistryStore, student_id: str, class_name: str, name: str | None = None
) -> None:
    store._ensure_student_auth(
        student_id=student_id,
        student_name=name or student_id,
        class_name=class_name,
        regenerate_token=False,
    )


def test_seed_subjects_inserts_generic_and_physics(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.list_subjects()
    ids = {item["subject_id"] for item in result["items"]}
    assert {"generic", "physics"} <= ids
    physics = next(item for item in result["items"] if item["subject_id"] == "physics")
    assert physics["display_name"] == "物理"
    assert physics["pack_id"] == "physics"
    again = store.seed_subjects()
    assert again["ok"] is True
    assert {item["subject_id"] for item in store.list_subjects()["items"]} == ids


def test_seed_subjects_pack_sync_does_not_overwrite_display_name(tmp_path: Path) -> None:
    store = _store(tmp_path)
    packs = tmp_path / "packs" / "subjects" / "math"
    packs.mkdir(parents=True)
    (packs / "pack.yaml").write_text(
        "id: math\ndisplay_name: 数学\npack_id: math\n",
        encoding="utf-8",
    )
    store.seed_subjects(packs_root=tmp_path / "packs" / "subjects")
    math_row = next(item for item in store.list_subjects()["items"] if item["subject_id"] == "math")
    assert math_row["display_name"] == "数学"
    store.add_subject(subject_id="math", display_name="数学手工", pack_id="math")
    (packs / "pack.yaml").write_text(
        "id: math\ndisplay_name: 数学课\npack_id: math-v2\n",
        encoding="utf-8",
    )
    store.seed_subjects(packs_root=tmp_path / "packs" / "subjects")
    math_row = next(item for item in store.list_subjects()["items"] if item["subject_id"] == "math")
    assert math_row["display_name"] == "数学"
    assert math_row["pack_id"] == "math-v2"


def test_unique_owner_conflict_is_class_already_owned(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store, "t_alpha")
    _add_teacher(store, "t_bravo")
    first = store.add_roster(teacher_id="t_alpha", subject_id="physics", class_name="高二2403班")
    assert first["ok"] is True
    conflict = store.add_roster(teacher_id="t_bravo", subject_id="physics", class_name="高二2403班")
    assert conflict == {"ok": False, "error": "class_already_owned"}
    same = store.add_roster(teacher_id="t_alpha", subject_id="physics", class_name="高二2403班")
    assert same["ok"] is True
    assert same.get("created") is False


def test_student_enrolled_class_scope_drops_after_bulk_move(tmp_path: Path) -> None:
    from services.api.auth.identity_graph_service import student_enrolled

    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2404班")
    store.enroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2403班",
        teacher_id="t_zhang",
    )
    assert student_enrolled(
        store,
        student_id="S001",
        teacher_id="t_zhang",
        subject_id="physics",
        class_name="高二2403班",
    )
    store.unenroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2403班",
    )
    store.enroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2404班",
        teacher_id="t_zhang",
    )
    assert not student_enrolled(
        store,
        student_id="S001",
        teacher_id="t_zhang",
        subject_id="physics",
        class_name="高二2403班",
    )
    assert student_enrolled(
        store,
        student_id="S001",
        teacher_id="t_zhang",
        subject_id="physics",
        class_name="高二2404班",
    )
    assert student_enrolled(
        store,
        student_id="S001",
        teacher_id="t_zhang",
        subject_id="physics",
    )


def test_empty_class_roster_add_is_warning_not_400(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store)
    result = store.add_roster(
        teacher_id="t_zhang",
        subject_id="physics",
        class_name="不存在的班",
        allow_empty=True,
    )
    assert result["ok"] is True
    assert result.get("warning") == "empty_class"


def test_single_enroll_and_enroll_class_bootstrap(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班", "刘昊然")
    _add_student(store, "S002", "高二2403班", "畅爽")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    boot = store.enroll_class(
        teacher_id="t_zhang", subject_id="physics", class_name="高二2403班"
    )
    assert boot["ok"] is True
    assert boot["count"] == 2
    extra = store.enroll(
        student_id="S001",
        subject_id="physics",
        class_name="高二2403班",
        teacher_id="t_zhang",
    )
    assert extra["ok"] is True
    assert extra.get("created") is False
    _add_student(store, "S003", "高二2404班", "武熙语")
    single = store.enroll(
        student_id="S003",
        subject_id="physics",
        class_name="高二2403班",
        teacher_id="t_zhang",
    )
    assert single["ok"] is True
    ids = {item["student_id"] for item in store.list_enrollments(
        subject_id="physics", class_name="高二2403班"
    )["items"]}
    assert ids == {"S001", "S002", "S003"}


def test_enroll_class_does_not_reimport_after_bootstrap(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    first = store.enroll_class(
        teacher_id="t_zhang", subject_id="physics", class_name="高二2403班"
    )
    assert first["bootstrapped"] is True
    assert first["source"] == "student_auth"
    _add_student(store, "S002", "高二2403班")
    replay = store.enroll_class(
        teacher_id="t_zhang", subject_id="physics", class_name="高二2403班"
    )
    assert replay["ok"] is True
    assert replay["bootstrapped"] is False
    assert replay["source"] == "enrollments"
    ids = {
        item["student_id"]
        for item in store.list_enrollments(subject_id="physics", class_name="高二2403班")["items"]
    }
    assert ids == {"S001"}
    resync = store.enroll_class(
        teacher_id="t_zhang",
        subject_id="physics",
        class_name="高二2403班",
        resync=True,
    )
    assert resync["bootstrapped"] is True
    resync_ids = {
        item["student_id"]
        for item in store.list_enrollments(subject_id="physics", class_name="高二2403班")["items"]
    }
    assert resync_ids == {"S001", "S002"}


def test_student_auth_class_name_is_not_visibility_source(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll_class(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store._ensure_student_auth(
        student_id="S001",
        student_name="刘昊然",
        class_name="高三2501班",
        regenerate_token=False,
    )
    ids = {item["student_id"] for item in store.list_enrollments(
        subject_id="physics", class_name="高二2403班"
    )["items"]}
    assert "S001" in ids


def test_remove_roster_blocks_when_enrollments_remain(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll(student_id="S001", subject_id="physics", class_name="高二2403班")
    blocked = store.remove_roster(
        teacher_id="t_zhang", subject_id="physics", class_name="高二2403班"
    )
    assert blocked == {"ok": False, "error": "enrollments_remain"}
    store.unenroll(student_id="S001", subject_id="physics", class_name="高二2403班")
    removed = store.remove_roster(
        teacher_id="t_zhang", subject_id="physics", class_name="高二2403班"
    )
    assert removed["ok"] is True


def test_public_expected_students_are_roster_classes_not_all_students(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    _add_teacher(store, "t_zhang")
    _add_teacher(store, "t_other")
    _add_student(store, "S001", "高二2403班")
    _add_student(store, "S002", "高二2403班")
    _add_student(store, "S999", "高二2404班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.add_roster(teacher_id="t_other", subject_id="physics", class_name="高二2404班")
    store.enroll_class(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll_class(teacher_id="t_other", subject_id="physics", class_name="高二2404班")

    def _boom() -> list[str]:
        raise AssertionError("list_all_student_ids must not be used")

    monkeypatch.setattr(
        "services.api.core_services_application.list_all_student_ids",
        _boom,
    )
    public_ids = compute_expected_students(
        "public",
        "",
        [],
        teacher_id="t_zhang",
        subject_id="physics",
    )
    assert set(public_ids) == {"S001", "S002"}
    assert "S999" not in public_ids


def test_empty_enrollments_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    _add_teacher(store)
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    with pytest.raises(ExpectedStudentsError) as empty_exc:
        compute_expected_students(
            "class",
            "高二2403班",
            [],
            teacher_id="t_zhang",
            subject_id="physics",
        )
    assert empty_exc.value.error == "enrollment_empty"
    with pytest.raises(ExpectedStudentsError) as roster_exc:
        compute_expected_students(
            "public",
            "",
            [],
            teacher_id="t_zhang",
            subject_id="math",
        )
    assert roster_exc.value.error == "roster_required"
    with pytest.raises(ExpectedStudentsError) as missing_exc:
        compute_expected_students("public", "", ["S001"])
    assert missing_exc.value.error == "roster_required"


def test_bulk_move_and_rename_class(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_teacher(store, "t_zhang")
    _add_student(store, "S001", "高二2403班")
    _add_student(store, "S002", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2404班")
    store.enroll_class(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    moved = store.bulk_move_enrollments(
        subject_id="physics",
        from_class="高二2403班",
        to_class="高二2404班",
        student_ids=["S001"],
    )
    assert moved["ok"] is True
    assert moved["count"] == 1
    remaining = {
        item["student_id"]
        for item in store.list_enrollments(subject_id="physics", class_name="高二2403班")["items"]
    }
    dest = {
        item["student_id"]
        for item in store.list_enrollments(subject_id="physics", class_name="高二2404班")["items"]
    }
    assert remaining == {"S002"}
    assert dest == {"S001"}
    renamed = store.rename_class(
        subject_id="physics",
        old_class_name="高二2404班",
        new_class_name="高三2501班",
    )
    assert renamed["ok"] is True
    assert store.list_enrollments(subject_id="physics", class_name="高三2501班")["count"] == 1
    roster_classes = {
        item["class_name"] for item in store.list_roster(teacher_id="t_zhang")["items"]
    }
    assert "高三2501班" in roster_classes
    assert "高二2404班" not in roster_classes


def test_resolve_expected_students_reuses_provided_conn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.api.auth.identity_graph_service import resolve_expected_students

    store = _store(tmp_path)
    _add_teacher(store)
    _add_student(store, "S001", "高二2403班")
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll_class(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    calls = {"n": 0}
    original = AuthRegistryStore._connect

    def _counting(self: AuthRegistryStore) -> sqlite3.Connection:
        calls["n"] += 1
        return original(self)

    monkeypatch.setattr(AuthRegistryStore, "_connect", _counting)
    conn = store._connect()
    try:
        result = resolve_expected_students(
            store,
            scope="class",
            class_name="高二2403班",
            student_ids=[],
            teacher_id="t_zhang",
            subject_id="physics",
            conn=conn,
        )
    finally:
        conn.close()
    assert result.get("ok") is True
    assert result.get("items") == ["S001"]
    assert calls["n"] == 1
