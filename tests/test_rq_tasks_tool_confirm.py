from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from services.api.workers import rq_tasks


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def enqueue(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})


def test_run_chat_job_skips_finish_when_confirm_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    finish_calls: List[str] = []
    refresh_calls: List[Dict[str, Any]] = []

    class _Store:
        def finish(self, job_id: str, lane_id: str) -> str | None:
            finish_calls.append(f"{job_id}:{lane_id}")
            return "next"

        def refresh_claim(self, job_id: str, lane_id: str, *, ttl_sec: int | None = None) -> bool:
            refresh_calls.append({"job_id": job_id, "lane_id": lane_id, "ttl_sec": ttl_sec})
            return True

    mod = SimpleNamespace(
        process_chat_job=lambda job_id: None,
        load_chat_job=lambda job_id: {
            "confirm_pending": {"confirm_id": "abc", "exp": int(time.time()) + 200},
        },
    )
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: _Store())
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)

    rq_tasks.run_chat_job("chat-1", "lane-1", tenant_id="t")
    assert finish_calls == []
    assert refresh_calls and refresh_calls[0]["job_id"] == "chat-1"
    assert queue.calls == []


def test_run_chat_job_pause_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Store:
        def finish(self, job_id: str, lane_id: str) -> str | None:
            return None

        def refresh_claim(self, job_id: str, lane_id: str, *, ttl_sec: int | None = None) -> bool:
            return True

    mod = SimpleNamespace(
        process_chat_job=lambda job_id: None,
        load_chat_job=lambda job_id: {"confirm_pending": {"exp": int(time.time()) + 10}},
    )
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: _Store())
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: _FakeQueue())
    rq_tasks.run_chat_job("chat-1", "lane-1", tenant_id="t")


def test_resume_chat_job_after_confirm_uses_raw_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    enqueue_chat_calls: List[str] = []

    class _Store:
        def __init__(self) -> None:
            self.active = "chat-1"
            self.parked: List[str] = []
            self.reacquired = False

        def get_active(self, lane_id: str) -> str | None:
            return self.active

        def reacquire_active(self, job_id: str, lane_id: str) -> bool:
            self.reacquired = True
            self.active = job_id
            return True

        def park_behind_active(self, job_id: str, lane_id: str) -> None:
            self.parked.append(job_id)

    store = _Store()
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: SimpleNamespace())
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: store)
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)
    monkeypatch.setattr(rq_tasks, "enqueue_chat_job", lambda *a, **k: enqueue_chat_calls.append("called"))

    result = rq_tasks.resume_chat_job_after_confirm("chat-1", "lane-1", tenant_id="t")
    assert result["mode"] == "active"
    assert enqueue_chat_calls == []
    assert queue.calls[0]["func"] is rq_tasks.run_chat_job
    assert queue.calls[0]["args"] == ("chat-1", "lane-1")
    assert "retry" not in queue.calls[0]["kwargs"]

    store.active = None
    queue.calls.clear()
    result = rq_tasks.resume_chat_job_after_confirm("chat-1", "lane-1", tenant_id="t")
    assert result["mode"] == "reacquire"
    assert store.reacquired is True
    assert queue.calls[0]["func"] is rq_tasks.run_chat_job

    store.active = "other-job"
    queue.calls.clear()
    result = rq_tasks.resume_chat_job_after_confirm("chat-1", "lane-1", tenant_id="t")
    assert result["mode"] == "park"
    assert store.parked == ["chat-1"]
    assert queue.calls == []
    assert enqueue_chat_calls == []


def test_enqueue_chat_job_after_pause_does_not_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()

    class _Store:
        def enqueue(self, job_id: str, lane_id: str):
            return {"lane_queue_position": 0, "lane_queue_size": 0, "lane_active": True}, False

    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: SimpleNamespace())
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: _Store())
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)
    result = rq_tasks.enqueue_chat_job("chat-1", "lane-1", tenant_id="t")
    assert result["lane_active"] is True
    assert queue.calls == []
