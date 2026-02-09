from services.api.queue_backend_factory import get_app_queue_backend, reset_queue_backend


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
