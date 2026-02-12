from __future__ import annotations

import threading

from services.api.chat_limits import acquire_limiters, student_inflight_guard, trim_messages


def test_trim_messages_respects_student_limit() -> None:
    messages = [{"role": "user", "content": str(i)} for i in range(100)]
    out = trim_messages(
        messages,
        role_hint="student",
        max_messages=14,
        max_messages_student=40,
        max_messages_teacher=40,
        max_chars=2000,
    )
    assert len(out) == 40


def test_trim_messages_truncates_long_content() -> None:
    messages = [{"role": "user", "content": "x" * 20}]
    out = trim_messages(
        messages,
        role_hint="teacher",
        max_messages=14,
        max_messages_student=40,
        max_messages_teacher=40,
        max_chars=8,
    )
    assert out[0]["content"].endswith("…")


def test_student_inflight_guard_blocks_when_over_limit() -> None:
    inflight: dict[str, int] = {"s1": 1}
    lock = threading.Lock()
    with student_inflight_guard(student_id="s1", inflight=inflight, lock=lock, limit=1) as allowed:
        assert allowed is False
    assert inflight["s1"] == 1


def test_acquire_limiters_supports_single_and_list() -> None:
    sema = threading.BoundedSemaphore(1)
    with acquire_limiters(sema):
        pass
    with acquire_limiters([sema, sema]):
        pass
