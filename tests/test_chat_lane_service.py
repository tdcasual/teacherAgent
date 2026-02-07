import unittest

from services.api.chat_lane_service import resolve_chat_lane_id, resolve_chat_lane_id_from_job


def _safe_fs_id(value: str, prefix: str = "id") -> str:
    text = str(value or "").strip().replace("/", "_").replace(" ", "_")
    if not text:
        return f"{prefix}_empty"
    return text


def _resolve_teacher_id(value):
    return _safe_fs_id(value or "teacher", prefix="teacher")


class ChatLaneServiceTest(unittest.TestCase):
    def test_resolve_chat_lane_id_for_student_teacher_unknown(self):
        student = resolve_chat_lane_id(
            "student",
            safe_fs_id=_safe_fs_id,
            resolve_teacher_id=_resolve_teacher_id,
            session_id="main",
            student_id="S001",
            request_id="req_a",
        )
        teacher = resolve_chat_lane_id(
            "teacher",
            safe_fs_id=_safe_fs_id,
            resolve_teacher_id=_resolve_teacher_id,
            session_id="main",
            teacher_id="Teacher A",
            request_id="req_b",
        )
        unknown = resolve_chat_lane_id(
            "unknown",
            safe_fs_id=_safe_fs_id,
            resolve_teacher_id=_resolve_teacher_id,
            session_id="",
            request_id="req_c",
        )
        self.assertEqual(student, "student:S001:main")
        self.assertEqual(teacher, "teacher:Teacher_A:main")
        self.assertTrue(unknown.startswith("unknown:"))

    def test_resolve_chat_lane_id_from_job_prefers_existing_lane(self):
        lane = resolve_chat_lane_id_from_job(
            {"lane_id": "lane_existing"},
            safe_fs_id=_safe_fs_id,
            resolve_teacher_id=_resolve_teacher_id,
        )
        self.assertEqual(lane, "lane_existing")

    def test_resolve_chat_lane_id_from_job_builds_from_request(self):
        lane = resolve_chat_lane_id_from_job(
            {
                "job_id": "job_1",
                "role": "teacher",
                "teacher_id": "Teacher A",
                "session_id": "main",
                "request_id": "req_1",
                "request": {"role": "teacher"},
            },
            safe_fs_id=_safe_fs_id,
            resolve_teacher_id=_resolve_teacher_id,
        )
        self.assertEqual(lane, "teacher:Teacher_A:main")


if __name__ == "__main__":
    unittest.main()
