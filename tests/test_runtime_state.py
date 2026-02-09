from types import SimpleNamespace
from collections import deque

from services.api import runtime_state


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
    runtime_state.reset_runtime_state(mod, create_chat_idempotency_store=lambda _: object())

    assert list(mod.UPLOAD_JOB_QUEUE) == []
    assert mod._QUEUE_BACKEND is None
    assert mod.CHAT_IDEMPOTENCY_STATE is not None
