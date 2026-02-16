from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.chat_event_stream_service import ChatEventStreamDeps, append_chat_event
from services.api.routes.chat_routes import build_router


def _deps(tmp_path: Path) -> ChatEventStreamDeps:
    return ChatEventStreamDeps(
        chat_job_path=lambda job_id: tmp_path / "chat_jobs" / str(job_id),
        chat_job_lock=threading.Lock(),
        now_iso=lambda: "2026-02-15T12:00:00",
    )


def _deps_with_wait(
    tmp_path: Path,
    *,
    wait_job_event,
) -> ChatEventStreamDeps:
    return ChatEventStreamDeps(
        chat_job_path=lambda job_id: tmp_path / "chat_jobs" / str(job_id),
        chat_job_lock=threading.Lock(),
        now_iso=lambda: "2026-02-15T12:00:00",
        wait_job_event=wait_job_event,
    )


def _build_app_with_core(deps: ChatEventStreamDeps, *, job_status: str = "done") -> FastAPI:
    class _Core:
        def __init__(self, *, status: str) -> None:
            self._status = status

        def load_chat_job(self, job_id: str):
            return {
                "job_id": job_id,
                "status": self._status,
                "role": "teacher",
                "teacher_id": "teacher-1",
            }

        def _chat_event_stream_deps(self):
            return deps

    app = FastAPI()
    app.include_router(build_router(_Core(status=job_status)))
    return app


def _stream_text(
    app: FastAPI,
    *,
    job_id: str,
    last_event_id: int | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    params: dict[str, str] = {"job_id": job_id}
    if last_event_id is not None:
        params["last_event_id"] = str(last_event_id)
    with TestClient(app).stream("GET", "/chat/stream", params=params, headers=headers or {}) as response:
        assert response.status_code == 200
        return response.read().decode("utf-8", errors="ignore")


def _event_ids(text: str) -> list[int]:
    out: list[int] = []
    for line in text.splitlines():
        if not line.startswith("id:"):
            continue
        try:
            out.append(int(line.split(":", 1)[1].strip()))
        except Exception:
            continue
    return out


def _append_terminal_events(job_id: str, *, deps: ChatEventStreamDeps) -> None:
    append_chat_event(job_id, "job.processing", {"status": "processing"}, deps=deps)
    append_chat_event(job_id, "assistant.delta", {"delta": "hello "}, deps=deps)
    append_chat_event(job_id, "assistant.done", {"text": "hello world"}, deps=deps)
    append_chat_event(
        job_id,
        "job.done",
        {"status": "done", "reply": "hello world"},
        deps=deps,
    )


def test_chat_stream_route_replays_and_finishes(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    _append_terminal_events("job-stream-1", deps=deps)

    app = _build_app_with_core(deps)
    text = _stream_text(app, job_id="job-stream-1")

    assert "event: job.processing" in text
    assert "event: assistant.delta" in text
    assert "event: assistant.done" in text
    assert "event: job.done" in text


def test_chat_stream_route_resumes_from_query_last_event_id(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    _append_terminal_events("job-stream-2", deps=deps)
    app = _build_app_with_core(deps)

    text = _stream_text(app, job_id="job-stream-2", last_event_id=2)

    assert "event: job.processing" not in text
    assert "event: assistant.delta" not in text
    assert "event: assistant.done" in text
    assert "event: job.done" in text
    assert _event_ids(text) == [3, 4]


def test_chat_stream_route_uses_max_of_query_and_header_cursor(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    _append_terminal_events("job-stream-3", deps=deps)
    app = _build_app_with_core(deps)

    text = _stream_text(
        app,
        job_id="job-stream-3",
        last_event_id=1,
        headers={"Last-Event-ID": "3"},
    )

    assert "event: job.done" in text
    assert "event: assistant.done" not in text
    assert _event_ids(text) == [4]


def test_chat_stream_route_ignores_invalid_header_cursor_and_uses_query(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    _append_terminal_events("job-stream-3b", deps=deps)
    app = _build_app_with_core(deps)

    text = _stream_text(
        app,
        job_id="job-stream-3b",
        last_event_id=2,
        headers={"Last-Event-ID": "not-a-number"},
    )

    assert "event: assistant.done" in text
    assert "event: job.done" in text
    assert _event_ids(text) == [3, 4]


def test_chat_stream_route_no_replay_when_cursor_catches_up(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    _append_terminal_events("job-stream-4", deps=deps)
    app = _build_app_with_core(deps)

    text = _stream_text(app, job_id="job-stream-4", last_event_id=4)

    assert "retry: 1000" in text
    assert "event:" not in text


def test_chat_stream_route_uses_wait_callback_when_no_events(tmp_path: Path) -> None:
    wait_calls: list[tuple[str, int, float]] = []

    def _wait_job_event(job_id: str, last_seen: int, timeout_sec: float) -> int:
        wait_calls.append((job_id, int(last_seen), float(timeout_sec)))
        return int(last_seen)

    deps = _deps_with_wait(tmp_path, wait_job_event=_wait_job_event)
    _append_terminal_events("job-stream-5", deps=deps)
    app = _build_app_with_core(deps)

    text = _stream_text(app, job_id="job-stream-5", last_event_id=4)

    assert "retry: 1000" in text
    assert "event:" not in text
    assert len(wait_calls) >= 1
