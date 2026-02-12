from __future__ import annotations

import json
from pathlib import Path

from services.api import chat_history_store as chs


def _safe_fs_id(value: str, prefix: str = "id") -> str:
    text = str(value or "").strip().replace("/", "_").replace(" ", "_")
    return text or f"{prefix}_empty"


def _atomic_write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _deps(tmp_path, now_iso=lambda: "2026-02-12T12:00:00", session_index_max_items=500):
    return chs.ChatHistoryStoreDeps(
        student_sessions_dir=tmp_path / "student",
        teacher_sessions_dir=tmp_path / "teacher",
        safe_fs_id=_safe_fs_id,
        atomic_write_json=_atomic_write_json,
        now_iso=now_iso,
        session_index_max_items=session_index_max_items,
    )


def test_default_now_iso_returns_iso_like_text():
    value = chs._default_now_iso()
    assert "T" in value
    assert len(value) >= 19


def test_load_indexes_return_empty_on_corrupt_json(tmp_path):
    deps = _deps(tmp_path)

    student_index = chs.student_sessions_index_path("s1", deps)
    student_index.parent.mkdir(parents=True, exist_ok=True)
    student_index.write_text("{bad", encoding="utf-8")

    teacher_index = chs.teacher_sessions_index_path("t1", deps)
    teacher_index.parent.mkdir(parents=True, exist_ok=True)
    teacher_index.write_text("{bad", encoding="utf-8")

    assert chs.load_student_sessions_index("s1", deps) == []
    assert chs.load_teacher_sessions_index("t1", deps) == []


def test_to_int_falls_back_for_non_integer_values():
    assert chs._to_int("not-int", 7) == 7


def test_update_student_session_index_updates_existing_item(tmp_path):
    ticks = iter(["2026-02-12T10:00:00", "2026-02-12T10:00:01"])
    deps = _deps(tmp_path, now_iso=lambda: next(ticks), session_index_max_items=2)

    chs.save_student_sessions_index(
        "s1",
        [{"session_id": "main", "message_count": "1", "preview": "old"}],
        deps,
    )

    chs.update_student_session_index(
        "s1",
        "main",
        assignment_id="a1",
        date_str="2026-02-12",
        preview="new-preview",
        message_increment=2,
        deps=deps,
    )

    items = chs.load_student_sessions_index("s1", deps)
    assert len(items) == 1
    assert items[0]["session_id"] == "main"
    assert items[0]["message_count"] == 3
    assert items[0]["assignment_id"] == "a1"
    assert items[0]["date"] == "2026-02-12"


def test_update_teacher_session_index_updates_existing_item(tmp_path):
    ticks = iter(["2026-02-12T11:00:00", "2026-02-12T11:00:01"])
    deps = _deps(tmp_path, now_iso=lambda: next(ticks), session_index_max_items=2)

    chs.save_teacher_sessions_index(
        "t1",
        [{"session_id": "main", "message_count": "2", "preview": "old"}],
        deps,
    )

    chs.update_teacher_session_index(
        "t1",
        "main",
        preview="new-preview",
        message_increment=3,
        deps=deps,
    )

    items = chs.load_teacher_sessions_index("t1", deps)
    assert len(items) == 1
    assert items[0]["session_id"] == "main"
    assert items[0]["message_count"] == 5
    assert items[0]["preview"] == "new-preview"
