from types import SimpleNamespace
from collections import deque

from services.api.runtime import runtime_state
from services.api.queue import queue_backend_factory
from services.api import chat_lane_store_factory


def test_reset_runtime_state_resets_queues_and_caches(tmp_path):
    mod = SimpleNamespace()
    mod.DATA_DIR = tmp_path / "data"
    mod.UPLOADS_DIR = tmp_path / "uploads"
    mod.UPLOAD_JOB_DIR = mod.UPLOADS_DIR / "assignment_jobs"
    mod.EXAM_UPLOAD_JOB_DIR = mod.UPLOADS_DIR / "exam_jobs"
    mod.CHAT_JOB_DIR = mod.UPLOADS_DIR / "chat_jobs"
    mod.CHAT_LANE_DEBOUNCE_MS = 0
    mod.CHAT_JOB_CLAIM_TTL_SEC = 600
    mod.OCR_MAX_CONCURRENCY = 2
    mod.LLM_MAX_CONCURRENCY = 3
    mod.LLM_MAX_CONCURRENCY_STUDENT = 1
    mod.LLM_MAX_CONCURRENCY_TEACHER = 1

    mod.UPLOAD_JOB_QUEUE = deque(["old"])

    backend = queue_backend_factory.get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=lambda: object(),
        get_backend=lambda **_kwargs: object(),
    )
    store = chat_lane_store_factory.get_chat_lane_store(
        tenant_id="default",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=600,
    )

    runtime_state.reset_runtime_state(mod, create_chat_idempotency_store=lambda _: object())

    assert list(mod.UPLOAD_JOB_QUEUE) == []
    assert mod.CHAT_IDEMPOTENCY_STATE is not None

    backend_after = queue_backend_factory.get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=lambda: object(),
        get_backend=lambda **_kwargs: object(),
    )
    store_after = chat_lane_store_factory.get_chat_lane_store(
        tenant_id="default",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=600,
    )

    assert backend_after is not backend
    assert store_after is not store
