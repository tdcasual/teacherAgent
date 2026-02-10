import unittest
from typing import Optional

from services.api.chat_job_processing_service import ChatJobProcessDeps, process_chat_job


class _Msg:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class _Req:
    def __init__(self, **payload):
        msgs = payload.get("messages") or []
        self.messages = [_Msg(str(m.get("role") or ""), str(m.get("content") or "")) for m in msgs if isinstance(m, dict)]
        self.role = payload.get("role")
        self.skill_id = payload.get("skill_id")
        self.teacher_id = payload.get("teacher_id")
        self.student_id = payload.get("student_id")
        self.assignment_id = payload.get("assignment_id")
        self.assignment_date = payload.get("assignment_date")
        self.auto_generate_assignment = payload.get("auto_generate_assignment")


class ChatJobProcessingPersistenceTest(unittest.TestCase):
    def _deps(self, *, events, append_error: Optional[Exception] = None):
        state = {
            "job_id": "cjob_test_001",
            "status": "queued",
            "session_id": "session_test_001",
            "teacher_id": "teacher",
            "request_id": "req_test_001",
            "skill_id": "",
            "request": {
                "messages": [{"role": "user", "content": "列出考试"}],
                "role": "teacher",
                "skill_id": "",
                "teacher_id": "teacher",
                "student_id": None,
                "assignment_id": None,
                "assignment_date": None,
                "auto_generate_assignment": None,
            },
        }

        def _write_chat_job(_job_id, updates):
            if "status" in updates:
                events.append(f"write:{updates.get('status')}")
            state.update(dict(updates or {}))

        def _append_teacher_session_message(_teacher_id, _session_id, role, _content, meta=None):
            events.append(f"append:{role}")
            if append_error:
                raise append_error
            self.assertIsInstance(meta, dict)

        def _update_teacher_session_index(_teacher_id, _session_id, preview="", message_increment=0):
            self.assertIsInstance(preview, str)
            self.assertGreaterEqual(int(message_increment), 0)
            events.append("index")

        deps = ChatJobProcessDeps(
            chat_job_claim_path=lambda _job_id: "/tmp/claim.lock",
            try_acquire_lockfile=lambda _path, _ttl: True,
            chat_job_claim_ttl_sec=600,
            load_chat_job=lambda _job_id: dict(state),
            write_chat_job=_write_chat_job,
            chat_request_model=lambda **payload: _Req(**payload),
            compute_chat_reply_sync=lambda _req, session_id=None, teacher_id_override=None: ("回复内容", "teacher", "列出考试"),
            monotonic=lambda: 0.0,
            build_interaction_note=lambda _u, _a, assignment_id=None: "",
            profile_update_async=False,
            enqueue_profile_update=lambda _payload: None,
            student_profile_update=lambda _payload: None,
            resolve_student_session_id=lambda _student_id, _assignment_id, _assignment_date: "student_session",
            append_student_session_message=lambda *args, **kwargs: None,
            update_student_session_index=lambda *args, **kwargs: None,
            parse_date_str=lambda raw: str(raw or ""),
            resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
            ensure_teacher_workspace=lambda _teacher_id: None,
            append_teacher_session_message=_append_teacher_session_message,
            update_teacher_session_index=_update_teacher_session_index,
            teacher_memory_auto_propose_from_turn=lambda *args, **kwargs: {},
            teacher_memory_auto_flush_from_session=lambda *args, **kwargs: {},
            maybe_compact_teacher_session=lambda *args, **kwargs: None,
            diag_log=lambda *_args, **_kwargs: None,
            release_lockfile=lambda _path: None,
        )
        return deps

    def test_teacher_history_persisted_before_done_status(self):
        events: list[str] = []
        deps = self._deps(events=events)
        process_chat_job("cjob_test_001", deps=deps)
        self.assertIn("write:done", events)
        self.assertGreater(events.index("write:done"), events.index("append:user"))
        self.assertGreater(events.index("write:done"), events.index("append:assistant"))
        self.assertGreater(events.index("write:done"), events.index("index"))

    def test_teacher_history_persist_failure_marks_failed(self):
        events: list[str] = []
        deps = self._deps(events=events, append_error=RuntimeError("disk-full"))
        process_chat_job("cjob_test_001", deps=deps)
        self.assertIn("write:failed", events)
        self.assertNotIn("write:done", events)

    def test_student_history_persist_failure_marks_failed(self):
        events: list[str] = []
        state = {
            "job_id": "cjob_test_002",
            "status": "queued",
            "session_id": "student_session_001",
            "teacher_id": "",
            "request_id": "req_test_002",
            "skill_id": "",
            "request": {
                "messages": [{"role": "user", "content": "讲一下牛顿第二定律"}],
                "role": "student",
                "skill_id": "",
                "teacher_id": "",
                "student_id": "S001",
                "assignment_id": "HW_1",
                "assignment_date": "2026-02-08",
                "auto_generate_assignment": None,
            },
        }

        def _write_chat_job(_job_id, updates):
            if "status" in updates:
                events.append(f"write:{updates.get('status')}")
            state.update(dict(updates or {}))

        deps = ChatJobProcessDeps(
            chat_job_claim_path=lambda _job_id: "/tmp/claim.lock",
            try_acquire_lockfile=lambda _path, _ttl: True,
            chat_job_claim_ttl_sec=600,
            load_chat_job=lambda _job_id: dict(state),
            write_chat_job=_write_chat_job,
            chat_request_model=lambda **payload: _Req(**payload),
            compute_chat_reply_sync=lambda _req, session_id=None, teacher_id_override=None: ("回复内容", "student", "讲一下牛顿第二定律"),
            monotonic=lambda: 0.0,
            build_interaction_note=lambda _u, _a, assignment_id=None: "",
            profile_update_async=False,
            enqueue_profile_update=lambda _payload: None,
            student_profile_update=lambda _payload: None,
            resolve_student_session_id=lambda _student_id, _assignment_id, _assignment_date: "student_session",
            append_student_session_message=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("disk-full")),
            update_student_session_index=lambda *args, **kwargs: None,
            parse_date_str=lambda raw: str(raw or ""),
            resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
            ensure_teacher_workspace=lambda _teacher_id: None,
            append_teacher_session_message=lambda *args, **kwargs: None,
            update_teacher_session_index=lambda *args, **kwargs: None,
            teacher_memory_auto_propose_from_turn=lambda *args, **kwargs: {},
            teacher_memory_auto_flush_from_session=lambda *args, **kwargs: {},
            maybe_compact_teacher_session=lambda *args, **kwargs: None,
            diag_log=lambda *_args, **_kwargs: None,
            release_lockfile=lambda _path: None,
        )
        process_chat_job("cjob_test_002", deps=deps)
        self.assertIn("write:failed", events)
        self.assertNotIn("write:done", events)


if __name__ == "__main__":
    unittest.main()
