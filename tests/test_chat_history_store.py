import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_history_store import (
    ChatHistoryStoreDeps,
    append_student_session_message,
    append_teacher_session_message,
    load_student_sessions_index,
    load_teacher_sessions_index,
    save_student_sessions_index,
    save_teacher_sessions_index,
    student_session_file,
    student_session_view_state_path,
    student_sessions_base_dir,
    student_sessions_index_path,
    teacher_session_file,
    teacher_session_view_state_path,
    teacher_sessions_base_dir,
    teacher_sessions_index_path,
    update_student_session_index,
    update_teacher_session_index,
)


def _safe_fs_id(value: str, prefix: str = "id") -> str:
    text = str(value or "").strip().replace("/", "_").replace(" ", "_")
    if not text:
        return f"{prefix}_empty"
    return text


def _atomic_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ChatHistoryStoreTest(unittest.TestCase):
    def test_path_builders_use_safe_ids(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatHistoryStoreDeps(
                student_sessions_dir=root / "student",
                teacher_sessions_dir=root / "teacher",
                safe_fs_id=_safe_fs_id,
                atomic_write_json=_atomic_write_json,
            )
            self.assertTrue(str(student_sessions_base_dir("S 001", deps)).endswith("student/S_001"))
            self.assertTrue(str(teacher_sessions_base_dir("T/001", deps)).endswith("teacher/T_001"))
            self.assertTrue(str(student_sessions_index_path("S 001", deps)).endswith("index.json"))
            self.assertTrue(str(teacher_sessions_index_path("T/001", deps)).endswith("index.json"))
            self.assertTrue(str(student_session_view_state_path("S 001", deps)).endswith("view_state.json"))
            self.assertTrue(str(teacher_session_view_state_path("T/001", deps)).endswith("view_state.json"))
            self.assertTrue(str(student_session_file("S 001", "main", deps)).endswith("main.jsonl"))
            self.assertTrue(str(teacher_session_file("T/001", "main", deps)).endswith("main.jsonl"))

    def test_index_load_save_roundtrip(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatHistoryStoreDeps(
                student_sessions_dir=root / "student",
                teacher_sessions_dir=root / "teacher",
                safe_fs_id=_safe_fs_id,
                atomic_write_json=_atomic_write_json,
            )
            self.assertEqual(load_student_sessions_index("S001", deps), [])
            self.assertEqual(load_teacher_sessions_index("T001", deps), [])

            student_items = [{"session_id": "main", "title": "学生"}]
            teacher_items = [{"session_id": "main", "title": "老师"}]
            save_student_sessions_index("S001", student_items, deps)
            save_teacher_sessions_index("T001", teacher_items, deps)
            self.assertEqual(load_student_sessions_index("S001", deps), student_items)
            self.assertEqual(load_teacher_sessions_index("T001", deps), teacher_items)

    def test_update_student_session_index_updates_fields_and_message_count(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            ticks = iter(
                [
                    "2026-02-07T10:00:00",
                    "2026-02-07T10:00:01",
                    "2026-02-07T10:00:02",
                ]
            )
            deps = ChatHistoryStoreDeps(
                student_sessions_dir=root / "student",
                teacher_sessions_dir=root / "teacher",
                safe_fs_id=_safe_fs_id,
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: next(ticks),
                session_index_max_items=2,
            )
            update_student_session_index(
                "S001",
                "main",
                "A001",
                "2026-02-01",
                "第一次预览",
                2,
                deps,
            )
            update_student_session_index("S001", "other", None, None, "第二次预览", 1, deps)
            update_student_session_index("S001", "third", None, None, "第三次预览", 1, deps)
            items = load_student_sessions_index("S001", deps)
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["session_id"], "third")
            self.assertEqual(items[1]["session_id"], "other")

    def test_update_teacher_session_index_and_append_messages(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatHistoryStoreDeps(
                student_sessions_dir=root / "student",
                teacher_sessions_dir=root / "teacher",
                safe_fs_id=_safe_fs_id,
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-02-07T10:00:00",
                session_index_max_items=10,
            )
            update_teacher_session_index("T001", "main", "老师预览", 3, deps)
            teacher_items = load_teacher_sessions_index("T001", deps)
            self.assertEqual(len(teacher_items), 1)
            self.assertEqual(teacher_items[0]["session_id"], "main")
            self.assertEqual(teacher_items[0]["message_count"], 3)
            self.assertEqual(teacher_items[0]["preview"], "老师预览")

            append_student_session_message("S001", "main", "user", "学生消息", {"kind": "msg"}, deps)
            append_teacher_session_message("T001", "main", "assistant", "老师回复", {"kind": "msg"}, deps)
            student_lines = student_session_file("S001", "main", deps).read_text(encoding="utf-8").strip().splitlines()
            teacher_lines = teacher_session_file("T001", "main", deps).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(student_lines), 1)
            self.assertEqual(len(teacher_lines), 1)
            student_record = json.loads(student_lines[0])
            teacher_record = json.loads(teacher_lines[0])
            self.assertEqual(student_record["role"], "user")
            self.assertEqual(student_record["content"], "学生消息")
            self.assertEqual(student_record["kind"], "msg")
            self.assertEqual(teacher_record["role"], "assistant")
            self.assertEqual(teacher_record["content"], "老师回复")
            self.assertEqual(teacher_record["kind"], "msg")


if __name__ == "__main__":
    unittest.main()
