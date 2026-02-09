from __future__ import annotations

from collections import deque
import threading
from typing import Any

from services.api import chat_lane_store_factory
from services.api.queue import queue_backend_factory
from services.api import session_store as _session_store_module
from services.api import chat_lane_repository as _chat_lane_repo_module
from services.api import teacher_memory_core as _teacher_memory_core_module
from services.api import profile_service as _profile_service_module
from services.api import assignment_data_service as _assignment_data_service_module
from services.api import teacher_session_compaction_helpers as _compaction_helpers_module


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
    chat_lane_store_factory.reset_chat_lane_stores()
    queue_backend_factory.reset_queue_backend()

    # Mirror chat lane state into the extracted chat_lane_repository module
    _chat_lane_repo_module.CHAT_JOB_LOCK = mod.CHAT_JOB_LOCK
    _chat_lane_repo_module.CHAT_JOB_LANES = mod.CHAT_JOB_LANES
    _chat_lane_repo_module.CHAT_JOB_ACTIVE_LANES = mod.CHAT_JOB_ACTIVE_LANES
    _chat_lane_repo_module.CHAT_JOB_QUEUED = mod.CHAT_JOB_QUEUED
    _chat_lane_repo_module.CHAT_JOB_TO_LANE = mod.CHAT_JOB_TO_LANE
    _chat_lane_repo_module.CHAT_LANE_CURSOR = mod.CHAT_LANE_CURSOR
    _chat_lane_repo_module.CHAT_LANE_RECENT = mod.CHAT_LANE_RECENT
    _chat_lane_repo_module.CHAT_IDEMPOTENCY_STATE = mod.CHAT_IDEMPOTENCY_STATE

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
    # Mirror cache state into extracted modules
    _profile_service_module._PROFILE_CACHE = mod._PROFILE_CACHE
    _profile_service_module._PROFILE_CACHE_LOCK = mod._PROFILE_CACHE_LOCK
    _assignment_data_service_module._ASSIGNMENT_DETAIL_CACHE = mod._ASSIGNMENT_DETAIL_CACHE
    _assignment_data_service_module._ASSIGNMENT_DETAIL_CACHE_LOCK = mod._ASSIGNMENT_DETAIL_CACHE_LOCK

    mod._PROFILE_UPDATE_QUEUE = deque()
    mod._PROFILE_UPDATE_LOCK = threading.Lock()
    mod._PROFILE_UPDATE_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_STARTED = False
    mod._PROFILE_UPDATE_STOP_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_THREAD = None

    mod._TEACHER_SESSION_COMPACT_TS = {}
    mod._TEACHER_SESSION_COMPACT_LOCK = threading.Lock()
    # Mirror teacher session compact state into the extracted modules
    _teacher_memory_core_module._TEACHER_SESSION_COMPACT_TS = mod._TEACHER_SESSION_COMPACT_TS
    _teacher_memory_core_module._TEACHER_SESSION_COMPACT_LOCK = mod._TEACHER_SESSION_COMPACT_LOCK
    _compaction_helpers_module._TEACHER_SESSION_COMPACT_TS = mod._TEACHER_SESSION_COMPACT_TS
    _compaction_helpers_module._TEACHER_SESSION_COMPACT_LOCK = mod._TEACHER_SESSION_COMPACT_LOCK
    mod._SESSION_INDEX_LOCKS = {}
    mod._SESSION_INDEX_LOCKS_LOCK = threading.Lock()
    _session_store_module._SESSION_INDEX_LOCKS = {}
    _session_store_module._SESSION_INDEX_LOCKS_LOCK = threading.Lock()
