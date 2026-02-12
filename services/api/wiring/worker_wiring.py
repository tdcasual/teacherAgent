"""Worker deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "upload_worker_deps",
    "exam_worker_deps",
    "profile_update_worker_deps",
    "_upload_worker_started_get",
    "_upload_worker_started_set",
    "_upload_worker_thread_get",
    "_upload_worker_thread_set",
    "_exam_worker_started_get",
    "_exam_worker_started_set",
    "_exam_worker_thread_get",
    "_exam_worker_thread_set",
    "_profile_update_worker_started_get",
    "_profile_update_worker_started_set",
    "_profile_update_worker_thread_get",
    "_profile_update_worker_thread_set",
    "_chat_worker_started_get",
    "_chat_worker_started_set",
]

import threading
import time
from typing import Any

from services.api.runtime import queue_runtime
from services.api.workers.upload_worker_service import UploadWorkerDeps
from services.api.workers.exam_worker_service import ExamWorkerDeps
from services.api.workers.profile_update_worker_service import ProfileUpdateWorkerDeps


from . import get_app_core as _app_core


def _runtime_backend_is_rq() -> bool:
    _ac = _app_core()
    backend = queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )
    return str(getattr(backend, "name", "")).startswith("rq")


def _upload_worker_started_get() -> bool:
    return bool(_app_core().UPLOAD_JOB_WORKER_STARTED)


def _upload_worker_started_set(value: bool) -> None:
    _ac = _app_core()
    _ac.UPLOAD_JOB_WORKER_STARTED = bool(value)


def _upload_worker_thread_get():
    return _app_core().UPLOAD_JOB_WORKER_THREAD


def _upload_worker_thread_set(value: Any) -> None:
    _ac = _app_core()
    _ac.UPLOAD_JOB_WORKER_THREAD = value


def upload_worker_deps() -> UploadWorkerDeps:
    _ac = _app_core()
    return UploadWorkerDeps(
        job_queue=_ac.UPLOAD_JOB_QUEUE,
        job_lock=_ac.UPLOAD_JOB_LOCK,
        job_event=_ac.UPLOAD_JOB_EVENT,
        job_dir=_ac.UPLOAD_JOB_DIR,
        stop_event=_ac.UPLOAD_JOB_STOP_EVENT,
        worker_started_get=_upload_worker_started_get,
        worker_started_set=_upload_worker_started_set,
        worker_thread_get=_upload_worker_thread_get,
        worker_thread_set=_upload_worker_thread_set,
        process_job=_ac.process_upload_job,
        write_job=lambda job_id, updates: _ac.write_upload_job(job_id, updates),
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=lambda *args, **kwargs: threading.Thread(*args, **kwargs),
        rq_enabled=_runtime_backend_is_rq,
    )


def _exam_worker_started_get() -> bool:
    return bool(_app_core().EXAM_JOB_WORKER_STARTED)


def _exam_worker_started_set(value: bool) -> None:
    _ac = _app_core()
    _ac.EXAM_JOB_WORKER_STARTED = bool(value)


def _exam_worker_thread_get():
    return _app_core().EXAM_JOB_WORKER_THREAD


def _exam_worker_thread_set(value: Any) -> None:
    _ac = _app_core()
    _ac.EXAM_JOB_WORKER_THREAD = value


def exam_worker_deps() -> ExamWorkerDeps:
    _ac = _app_core()
    return ExamWorkerDeps(
        job_queue=_ac.EXAM_JOB_QUEUE,
        job_lock=_ac.EXAM_JOB_LOCK,
        job_event=_ac.EXAM_JOB_EVENT,
        job_dir=_ac.EXAM_UPLOAD_JOB_DIR,
        stop_event=_ac.EXAM_JOB_STOP_EVENT,
        worker_started_get=_exam_worker_started_get,
        worker_started_set=_exam_worker_started_set,
        worker_thread_get=_exam_worker_thread_get,
        worker_thread_set=_exam_worker_thread_set,
        process_job=_ac.process_exam_upload_job,
        write_job=lambda job_id, updates: _ac.write_exam_job(job_id, updates),
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=lambda *args, **kwargs: threading.Thread(*args, **kwargs),
        rq_enabled=_runtime_backend_is_rq,
    )


def _profile_update_worker_started_get() -> bool:
    return bool(_app_core()._PROFILE_UPDATE_WORKER_STARTED)


def _profile_update_worker_started_set(value: bool) -> None:
    _ac = _app_core()
    _ac._PROFILE_UPDATE_WORKER_STARTED = bool(value)


def _profile_update_worker_thread_get():
    return _app_core()._PROFILE_UPDATE_WORKER_THREAD


def _profile_update_worker_thread_set(value: Any) -> None:
    _ac = _app_core()
    _ac._PROFILE_UPDATE_WORKER_THREAD = value


def profile_update_worker_deps() -> ProfileUpdateWorkerDeps:
    _ac = _app_core()
    return ProfileUpdateWorkerDeps(
        update_queue=_ac._PROFILE_UPDATE_QUEUE,
        update_lock=_ac._PROFILE_UPDATE_LOCK,
        update_event=_ac._PROFILE_UPDATE_EVENT,
        stop_event=_ac._PROFILE_UPDATE_STOP_EVENT,
        worker_started_get=_profile_update_worker_started_get,
        worker_started_set=_profile_update_worker_started_set,
        worker_thread_get=_profile_update_worker_thread_get,
        worker_thread_set=_profile_update_worker_thread_set,
        queue_max=_ac.PROFILE_UPDATE_QUEUE_MAX,
        student_profile_update=_ac.student_profile_update,
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=lambda *args, **kwargs: threading.Thread(*args, **kwargs),
        rq_enabled=_runtime_backend_is_rq,
        monotonic=time.monotonic,
    )


def _chat_worker_started_get() -> bool:
    return bool(_app_core().CHAT_JOB_WORKER_STARTED)


def _chat_worker_started_set(value: bool) -> None:
    _ac = _app_core()
    _ac.CHAT_JOB_WORKER_STARTED = bool(value)
