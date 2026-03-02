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
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)

    created = []

    def inline_factory():
        backend = DummyBackend("inline")
        created.append(backend)
        return backend

    def failing_backend(**_kwargs):
        raise RuntimeError("rq unavailable")

    with pytest.raises(RuntimeError, match="rq unavailable"):
        get_app_queue_backend(
            tenant_id="prod-tenant",
            is_pytest=False,
            inline_backend_factory=inline_factory,
            get_backend=failing_backend,
        )
    assert created == []


def test_non_pytest_inline_mode_bypasses_rq_backend(monkeypatch):
    reset_queue_backend()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "inline")

    calls = {"rq": 0}
    def failing_backend(**_kwargs):
        calls["rq"] += 1
        raise RuntimeError("rq unavailable")

    backend = get_app_queue_backend(
        tenant_id="prod-tenant",
        is_pytest=False,
        inline_backend_factory=lambda: DummyBackend("inline"),
        get_backend=failing_backend,
    )

    assert backend.label == "inline"
    assert calls["rq"] == 0


def test_pytest_backend_cache_isolated_by_data_dir(monkeypatch):
    reset_queue_backend()
    created = []

    def inline_factory():
        backend = DummyBackend(f"inline-{len(created)}")
        created.append(backend)
        return backend

    monkeypatch.setenv("DATA_DIR", "/tmp/case-a")
    backend_a = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    monkeypatch.setenv("DATA_DIR", "/tmp/case-b")
    backend_b = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_a is not backend_b


def test_pytest_backend_cache_keeps_same_instance_across_phase_suffix(monkeypatch):
    reset_queue_backend()
    created = []

    def inline_factory():
        backend = DummyBackend(f"inline-{len(created)}")
        created.append(backend)
        return backend

    monkeypatch.setenv("DATA_DIR", "/tmp/case-phase")
    monkeypatch.setenv("UPLOADS_DIR", "/tmp/case-phase/uploads")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_case.py::test_sample (setup)")
    backend_setup = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_case.py::test_sample (teardown)")
    backend_teardown = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_setup is backend_teardown


def test_pytest_backend_cache_key_avoids_pipe_delimiter_collisions(monkeypatch):
    reset_queue_backend()
    created = []

    def inline_factory():
        backend = DummyBackend(f"inline-{len(created)}")
        created.append(backend)
        return backend

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
    monkeypatch.setenv("DATA_DIR", "/tmp/scope-a|scope-b")
    monkeypatch.delenv("UPLOADS_DIR", raising=False)
    backend_pipe_in_data = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    monkeypatch.setenv("DATA_DIR", "/tmp/scope-a")
    monkeypatch.setenv("UPLOADS_DIR", "scope-b")
    backend_split_scopes = get_app_queue_backend(
        tenant_id="t-same",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_pipe_in_data is not backend_split_scopes
