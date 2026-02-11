"""Tests for chat_start_service — enqueue failure, dedup, error paths."""
from __future__ import annotations

import threading
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from services.api.chat_start_service import ChatStartDeps, start_chat_orchestration


class _FakeRequest:
    def __init__(self, **kwargs):
        self.request_id = kwargs.get("request_id", "req-001")
        self.session_id = kwargs.get("session_id", None)
        self.role = kwargs.get("role", "student")
        self.skill_id = kwargs.get("skill_id", "")
        self.teacher_id = kwargs.get("teacher_id", "")
        self.student_id = kwargs.get("student_id", "stu-1")
        self.assignment_id = kwargs.get("assignment_id", "")
        self.assignment_date = kwargs.get("assignment_date", "")
        self.auto_generate_assignment = None
        self.messages = kwargs.get("messages", [_FakeMsg("user", "hello")])


class _FakeMsg:
    def __init__(self, role, content):
        self.role = role
        self.content = content


def _make_deps(**overrides):
    """Build ChatStartDeps with sensible defaults."""
    jobs = {}
    defaults = dict(
        http_error=lambda code, msg: ValueError(f"{code}: {msg}"),
        get_chat_job_id_by_request=lambda rid: None,
        load_chat_job=lambda jid: jobs.get(jid, {"job_id": jid, "status": "queued"}),
        detect_role_hint=lambda req: req.role or "student",
        resolve_student_session_id=lambda sid, aid, ad: f"sess-{sid}",
        resolve_teacher_id=lambda tid: tid or "teacher-default",
        resolve_chat_lane_id=lambda *a, **kw: "lane-test",
        chat_last_user_text=lambda msgs: (msgs[-1]["content"] if msgs else ""),
        chat_text_fingerprint=lambda s: f"fp-{hash(s) % 10000}",
        chat_job_lock=threading.Lock(),
        chat_recent_job_locked=lambda lid, fp: None,
        upsert_chat_request_index=lambda rid, jid: None,
        chat_lane_load_locked=lambda lid: {"total": 0},
        chat_lane_max_queue=10,
        chat_request_map_set_if_absent=lambda rid, jid: True,
        new_job_id=lambda: "job-test-001",
        now_iso=lambda: "2026-02-11T00:00:00Z",
        write_chat_job=lambda jid, data, overwrite: data,
        enqueue_chat_job=lambda jid, lid: {"lane_queue_position": 0, "lane_queue_size": 1},
        chat_register_recent_locked=lambda lid, fp, jid: None,
        append_student_session_message=lambda *a, **kw: None,
        update_student_session_index=lambda *a, **kw: None,
        append_teacher_session_message=lambda *a, **kw: None,
        update_teacher_session_index=lambda *a, **kw: None,
        parse_date_str=lambda s: s or "",
    )
    defaults.update(overrides)
    return ChatStartDeps(**defaults), jobs


class ChatStartServiceTest(unittest.TestCase):

    def test_happy_path(self):
        deps, _ = _make_deps()
        req = _FakeRequest()
        result = start_chat_orchestration(req, deps=deps)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "queued")

    def test_enqueue_failure_marks_job_failed(self):
        """When enqueue_chat_job raises, job should be marked failed, not crash."""
        written = {}

        def track_write(jid, data, overwrite):
            written.update(data)
            return data

        def bad_enqueue(jid, lid):
            raise ConnectionError("Redis down")

        deps, _ = _make_deps(
            enqueue_chat_job=bad_enqueue,
            write_chat_job=track_write,
        )
        req = _FakeRequest()
        result = start_chat_orchestration(req, deps=deps)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(written.get("error"), "enqueue_failed")

    def test_missing_request_id_raises_400(self):
        deps, _ = _make_deps()
        req = _FakeRequest(request_id="")
        with self.assertRaises(ValueError) as ctx:
            start_chat_orchestration(req, deps=deps)
        self.assertIn("400", str(ctx.exception))

    def test_idempotent_return_on_existing_request(self):
        deps, _ = _make_deps(
            get_chat_job_id_by_request=lambda rid: "existing-job",
        )
        req = _FakeRequest()
        result = start_chat_orchestration(req, deps=deps)
        self.assertTrue(result["ok"])
        self.assertEqual(result["job_id"], "existing-job")

    def test_load_chat_job_failure_returns_queued_stub(self):
        """When load_chat_job fails, should return queued stub, not crash."""
        def bad_load(jid):
            raise IOError("corrupt file")

        deps, _ = _make_deps(
            get_chat_job_id_by_request=lambda rid: "corrupt-job",
            load_chat_job=bad_load,
        )
        req = _FakeRequest()
        result = start_chat_orchestration(req, deps=deps)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "queued")

    def test_lane_capacity_exceeded_raises_429(self):
        deps, _ = _make_deps(
            chat_lane_load_locked=lambda lid: {"total": 100},
            chat_lane_max_queue=10,
        )
        req = _FakeRequest()
        with self.assertRaises(ValueError) as ctx:
            start_chat_orchestration(req, deps=deps)
        self.assertIn("429", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
