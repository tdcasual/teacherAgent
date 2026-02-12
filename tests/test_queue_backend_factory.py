import pytest

from services.api.queue.queue_backend_factory import get_app_queue_backend, reset_queue_backend


class DummyBackend:
    name = "dummy"

    def __init__(self, label: str):
        self.label = label

    def enqueue_upload_job(self, job_id: str) -> None:
        return None

    def enqueue_exam_job(self, job_id: str) -> None:
        return None

    def enqueue_profile_update(self, payload: dict) -> None:
        return None

    def enqueue_chat_job(self, job_id: str, lane_id=None) -> dict:
        return {"job_id": job_id, "lane_id": lane_id}

    def scan_pending_upload_jobs(self) -> int:
        return 0

    def scan_pending_exam_jobs(self) -> int:
        return 0

    def scan_pending_chat_jobs(self) -> int:
        return 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def test_get_app_queue_backend_uses_inline_in_pytest():
    reset_queue_backend()
    created = []

    def inline_factory():
        backend = DummyBackend("inline")
        created.append(backend)
        return backend

    backend = get_app_queue_backend(
        tenant_id="t1",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend is created[0]
    assert backend.label == "inline"


def test_get_app_queue_backend_caches_and_resets():
    reset_queue_backend()
    created = []

    def inline_factory():
        backend = DummyBackend(f"inline-{len(created)}")
        created.append(backend)
        return backend

    backend_1 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )
    backend_2 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_1 is backend_2

    reset_queue_backend()

    backend_3 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_3 is not backend_1


def test_prod_mode_does_not_fallback_to_inline_backend(monkeypatch):
    reset_queue_backend()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOW_INLINE_FALLBACK_IN_PROD", raising=False)

    created = []

    def inline_factory():
        backend = DummyBackend("inline")
        created.append(backend)
        return backend

    def failing_backend(**_kwargs):
        raise RuntimeError("rq unavailable")

    with pytest.raises(RuntimeError, match="inline fallback disabled"):
        get_app_queue_backend(
            tenant_id="prod-tenant",
            is_pytest=False,
            inline_backend_factory=inline_factory,
            get_backend=failing_backend,
        )
    assert created == []


def test_prod_mode_can_enable_inline_fallback_explicitly(monkeypatch):
    reset_queue_backend()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_INLINE_FALLBACK_IN_PROD", "1")

    def failing_backend(**_kwargs):
        raise RuntimeError("rq unavailable")

    backend = get_app_queue_backend(
        tenant_id="prod-tenant",
        is_pytest=False,
        inline_backend_factory=lambda: DummyBackend("inline"),
        get_backend=failing_backend,
    )

    assert backend.label == "inline"
