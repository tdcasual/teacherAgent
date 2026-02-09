from __future__ import annotations

from collections import deque
import threading
from typing import Any


def reset_runtime_state(mod: Any, *, create_chat_idempotency_store) -> None:
    mod.UPLOAD_JOB_QUEUE = deque()
    mod.UPLOAD_JOB_LOCK = threading.Lock()
    mod.UPLOAD_JOB_EVENT = threading.Event()
    mod.UPLOAD_JOB_WORKER_STARTED = False
    mod.UPLOAD_JOB_STOP_EVENT = threading.Event()
    mod.UPLOAD_JOB_WORKER_THREAD = None

    mod.EXAM_JOB_QUEUE = deque()
    mod.EXAM_JOB_LOCK = threading.Lock()
    mod.EXAM_JOB_EVENT = threading.Event()
    mod.EXAM_JOB_WORKER_STARTED = False
    mod.EXAM_JOB_STOP_EVENT = threading.Event()
    mod.EXAM_JOB_WORKER_THREAD = None

    mod.CHAT_JOB_LOCK = threading.Lock()
    mod.CHAT_JOB_EVENT = threading.Event()
    mod.CHAT_JOB_WORKER_STARTED = False
    mod.CHAT_WORKER_STOP_EVENT = threading.Event()
    mod.CHAT_JOB_LANES = {}
    mod.CHAT_JOB_ACTIVE_LANES = set()
    mod.CHAT_JOB_QUEUED = set()
    mod.CHAT_JOB_TO_LANE = {}
    mod.CHAT_LANE_CURSOR = 0
    mod.CHAT_WORKER_THREADS = []
    mod.CHAT_LANE_RECENT = {}
    mod.CHAT_IDEMPOTENCY_STATE = create_chat_idempotency_store(mod.CHAT_JOB_DIR)
    mod._CHAT_LANE_STORES = {}
    mod._QUEUE_BACKEND = None

    mod._OCR_SEMAPHORE = threading.BoundedSemaphore(int(mod.OCR_MAX_CONCURRENCY))
    mod._LLM_SEMAPHORE = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY))
    mod._LLM_SEMAPHORE_STUDENT = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY_STUDENT))
    mod._LLM_SEMAPHORE_TEACHER = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY_TEACHER))

    mod._STUDENT_INFLIGHT = {}
    mod._STUDENT_INFLIGHT_LOCK = threading.Lock()

    mod._PROFILE_CACHE = {}
    mod._PROFILE_CACHE_LOCK = threading.Lock()
    mod._ASSIGNMENT_DETAIL_CACHE = {}
    mod._ASSIGNMENT_DETAIL_CACHE_LOCK = threading.Lock()

    mod._PROFILE_UPDATE_QUEUE = deque()
    mod._PROFILE_UPDATE_LOCK = threading.Lock()
    mod._PROFILE_UPDATE_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_STARTED = False
    mod._PROFILE_UPDATE_STOP_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_THREAD = None

    mod._TEACHER_SESSION_COMPACT_TS = {}
    mod._TEACHER_SESSION_COMPACT_LOCK = threading.Lock()
    mod._SESSION_INDEX_LOCKS = {}
    mod._SESSION_INDEX_LOCKS_LOCK = threading.Lock()
