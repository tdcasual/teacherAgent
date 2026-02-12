from __future__ import annotations

from typing import Any, Dict, Optional

from services.api.queue import queue_backend, queue_backend_rq


class _FakeTasks:
    def __init__(self) -> None:
        self.calls = []

    def enqueue_upload_job(self, job_id: str, *, tenant_id: Optional[str] = None) -> None:
        self.calls.append(("upload", job_id, tenant_id))

    def enqueue_exam_job(self, job_id: str, *, tenant_id: Optional[str] = None) -> None:
        self.calls.append(("exam", job_id, tenant_id))

    def enqueue_profile_update(self, payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
        self.calls.append(("profile", payload, tenant_id))

    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None, *, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        self.calls.append(("chat", job_id, lane_id, tenant_id))
        return {"ok": True, "job_id": job_id, "lane_id": lane_id}

    def scan_pending_upload_jobs(self, *, tenant_id: Optional[str] = None) -> int:
        self.calls.append(("scan_upload", tenant_id))
        return 1

    def scan_pending_exam_jobs(self, *, tenant_id: Optional[str] = None) -> int:
        self.calls.append(("scan_exam", tenant_id))
        return 2

    def scan_pending_chat_jobs(self, *, tenant_id: Optional[str] = None) -> int:
        self.calls.append(("scan_chat", tenant_id))
        return 3


def test_rq_tasks_import_helper_returns_module() -> None:
    mod = queue_backend_rq._rq_tasks()
    assert hasattr(mod, "enqueue_upload_job")
    assert hasattr(mod, "scan_pending_chat_jobs")


def test_rq_queue_backend_delegates_all_methods(monkeypatch) -> None:
    fake = _FakeTasks()
    monkeypatch.setattr(queue_backend_rq, "_rq_tasks", lambda: fake)

    backend = queue_backend_rq.RqQueueBackend(tenant_id="tenant-1")
    backend.enqueue_upload_job("u-1")
    backend.enqueue_exam_job("e-1")
    backend.enqueue_profile_update({"id": "s-1"})
    chat = backend.enqueue_chat_job("c-1", lane_id="lane-a")
    assert chat["ok"] is True
    assert backend.scan_pending_upload_jobs() == 1
    assert backend.scan_pending_exam_jobs() == 2
    assert backend.scan_pending_chat_jobs() == 3
    assert backend.start() is None
    assert backend.stop() is None

    assert fake.calls == [
        ("upload", "u-1", "tenant-1"),
        ("exam", "e-1", "tenant-1"),
        ("profile", {"id": "s-1"}, "tenant-1"),
        ("chat", "c-1", "lane-a", "tenant-1"),
        ("scan_upload", "tenant-1"),
        ("scan_exam", "tenant-1"),
        ("scan_chat", "tenant-1"),
    ]


def test_queue_backend_rq_enabled_and_factory_paths(monkeypatch) -> None:
    monkeypatch.setattr(queue_backend.settings, "rq_backend_enabled", lambda: True)
    monkeypatch.setattr(queue_backend.settings, "job_queue_backend", lambda: "inline")
    assert queue_backend.rq_enabled() is True

    backend = queue_backend.get_queue_backend(tenant_id="tenant-2")
    assert backend.name == "rq"
    assert isinstance(backend, queue_backend_rq.RqQueueBackend)

    monkeypatch.setattr(queue_backend.settings, "rq_backend_enabled", lambda: False)
    monkeypatch.setattr(queue_backend.settings, "job_queue_backend", lambda: "redis-rq")
    assert queue_backend.rq_enabled() is True

    monkeypatch.setattr(queue_backend.settings, "job_queue_backend", lambda: "inline")
    try:
        queue_backend.get_queue_backend(tenant_id=None)
    except RuntimeError as exc:
        assert "RQ backend required" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when RQ disabled")
