from __future__ import annotations

import time

from services.api.chat_job_processing_service import ChatJobProcessDeps, process_chat_job


class _Req:
    def __init__(self, **payload):
        self.messages = []
        for item in payload.get("messages") or []:
            self.messages.append(type("M", (), {"role": item.get("role"), "content": item.get("content")})())
        self.role = payload.get("role")
        self.skill_id = payload.get("skill_id")
        self.teacher_id = payload.get("teacher_id")
        self.student_id = payload.get("student_id")
        self.assignment_id = payload.get("assignment_id")
        self.assignment_date = payload.get("assignment_date")
        self.auto_generate_assignment = payload.get("auto_generate_assignment")


def _deps(*, state, events, compute):
    def _write(_job_id, updates):
        if "status" in updates:
            events.append(f"write:{updates.get('status')}")
        if "confirm_pending" in updates:
            events.append("write:confirm_pending")
        if updates.get("confirm_resume_result") is not None:
            events.append("write:resume")
        state.update(dict(updates or {}))

    return ChatJobProcessDeps(
        chat_job_claim_path=lambda _job_id: "/tmp/claim.lock",
        try_acquire_lockfile=lambda _path, _ttl: True,
        chat_job_claim_ttl_sec=600,
        load_chat_job=lambda _job_id: dict(state),
        write_chat_job=_write,
        chat_request_model=lambda **payload: _Req(**payload),
        compute_chat_reply_sync=compute,
        monotonic=lambda: 0.0,
        build_interaction_note=lambda *_a, **_k: "",
        profile_update_async=False,
        enqueue_profile_update=lambda _payload: None,
        student_profile_update=lambda _payload: None,
        resolve_student_session_id=lambda *_a, **_k: "s",
        append_student_session_message=lambda *a, **k: None,
        update_student_session_index=lambda *a, **k: None,
        parse_date_str=lambda raw: str(raw or ""),
        resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
        ensure_teacher_workspace=lambda _teacher_id: None,
        append_teacher_session_message=lambda *a, **k: events.append("append:history"),
        update_teacher_session_index=lambda *a, **k: events.append("index"),
        teacher_memory_auto_propose_from_turn=lambda *a, **k: {},
        teacher_memory_auto_flush_from_session=lambda *a, **k: {},
        maybe_compact_teacher_session=lambda *a, **k: None,
        student_memory_auto_propose_from_turn=lambda **_k: {"ok": False, "created": False},
        compute_assignment_progress=lambda *_a, **_k: {"ok": False},
        student_memory_auto_propose_from_assignment_evidence=lambda **_k: {"ok": False, "created": False},
        diag_log=lambda *_a, **_k: None,
        release_lockfile=lambda _path: None,
        append_chat_event=lambda _job_id, event_type, _payload: events.append(f"event:{event_type}") or {},
    )


def _base_state() -> dict:
    return {
        "job_id": "cjob_confirm",
        "status": "queued",
        "session_id": "session_1",
        "teacher_id": "teacher",
        "lane_id": "lane-1",
        "request_id": "req_1",
        "skill_id": "",
        "request": {
            "messages": [{"role": "user", "content": "更新画像"}],
            "role": "teacher",
            "skill_id": "",
            "teacher_id": "teacher",
        },
    }


def test_process_chat_job_pause_keeps_processing_and_skips_done() -> None:
    events: list[str] = []
    state = _base_state()

    def compute(_req, session_id=None, teacher_id_override=None, event_sink=None, extra_out=None, **_kwargs):
        if extra_out is not None:
            extra_out.update(
                {
                    "pause": "confirmation_required",
                    "confirm_id": "abc",
                    "tool": "student.profile.update",
                    "preview": "student.profile.update: {}",
                    "tool_call_id": "call-1",
                    "convo": [{"role": "assistant", "tool_calls": [{"id": "call-1"}]}],
                    "exp": int(time.time()) + 300,
                }
            )
        return ("", "teacher", "更新画像")

    process_chat_job("cjob_confirm", deps=_deps(state=state, events=events, compute=compute))
    assert "write:done" not in events
    assert "write:confirm_pending" in events
    assert "event:tool.confirm_required" in events
    assert state.get("status") == "processing"
    assert (state.get("confirm_pending") or {}).get("confirm_id") == "abc"
    assert state.get("confirm_tool_call_id") == "call-1"


def test_process_chat_job_resume_injects_result_then_finishes() -> None:
    events: list[str] = []
    state = _base_state()
    state["status"] = "processing"
    state["confirm_pending"] = {"confirm_id": "abc", "exp": int(time.time()) + 100}
    state["confirm_resume_result"] = {"ok": True}
    state["confirm_tool_call_id"] = "call-1"
    state["agent_convo"] = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "tool_calls": [{"id": "call-1", "function": {"name": "student.profile.update"}}]},
    ]
    seen: dict = {}

    def compute(_req, session_id=None, teacher_id_override=None, event_sink=None, extra_out=None, initial_convo=None, **_kwargs):
        seen["initial_convo"] = initial_convo
        return ("完成", "teacher", "更新画像")

    process_chat_job("cjob_confirm", deps=_deps(state=state, events=events, compute=compute))
    convo = seen.get("initial_convo") or []
    assert convo[-1]["role"] == "tool"
    assert convo[-1]["tool_call_id"] == "call-1"
    assert "write:done" in events
    assert state.get("confirm_pending") is None
