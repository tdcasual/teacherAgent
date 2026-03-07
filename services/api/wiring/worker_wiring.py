# mypy: disable-error-code=no-untyped-def
"""Worker deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "upload_worker_deps",
    "exam_worker_deps",
    "survey_worker_deps",
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
from services.api.workers.exam_worker_service import ExamWorkerDeps
from services.api.workers.survey_worker_service import SurveyWorkerDeps
from services.api.workers.profile_update_worker_service import ProfileUpdateWorkerDeps
from services.api.workers.upload_worker_service import UploadWorkerDeps

from . import CURRENT_CORE
from . import get_app_core as _app_core


def _runtime_backend_is_rq(core: Any | None = None) -> bool:
    _ac = _app_core(core)
    backend = queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )
    return str(getattr(backend, "name", "")).startswith("rq")


def _thread_factory_for_core(core: Any):
    def _factory(*args, **kwargs):
        target = kwargs.get("target")
        if callable(target):

            def _target_with_core(*inner_args, **inner_kwargs):
                token = CURRENT_CORE.set(core)
                try:
                    return target(*inner_args, **inner_kwargs)
                finally:
                    CURRENT_CORE.reset(token)

            kwargs["target"] = _target_with_core
        return threading.Thread(*args, **kwargs)

    return _factory


def _upload_worker_started_get(core: Any | None = None) -> bool:
    return bool(_app_core(core).UPLOAD_JOB_WORKER_STARTED)


def _upload_worker_started_set(core: Any | None = None, value: bool = False) -> None:
    _ac = _app_core(core)
    _ac.UPLOAD_JOB_WORKER_STARTED = bool(value)


def _upload_worker_thread_get(core: Any | None = None):
    return _app_core(core).UPLOAD_JOB_WORKER_THREAD


def _upload_worker_thread_set(core: Any | None = None, value: Any = None) -> None:
    _ac = _app_core(core)
    _ac.UPLOAD_JOB_WORKER_THREAD = value


def upload_worker_deps(core: Any | None = None) -> UploadWorkerDeps:
    _ac = _app_core(core)
    return UploadWorkerDeps(
        job_queue=_ac.UPLOAD_JOB_QUEUE,
        job_lock=_ac.UPLOAD_JOB_LOCK,
        job_event=_ac.UPLOAD_JOB_EVENT,
        job_dir=_ac.UPLOAD_JOB_DIR,
        stop_event=_ac.UPLOAD_JOB_STOP_EVENT,
        worker_started_get=lambda: _upload_worker_started_get(_ac),
        worker_started_set=lambda value: _upload_worker_started_set(_ac, value),
        worker_thread_get=lambda: _upload_worker_thread_get(_ac),
        worker_thread_set=lambda value: _upload_worker_thread_set(_ac, value),
        process_job=_ac.process_upload_job,
        write_job=lambda job_id, updates: _ac.write_upload_job(job_id, updates),
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=_thread_factory_for_core(_ac),
        rq_enabled=lambda: _runtime_backend_is_rq(_ac),
    )


def _exam_worker_started_get(core: Any | None = None) -> bool:
    return bool(_app_core(core).EXAM_JOB_WORKER_STARTED)


def _exam_worker_started_set(core: Any | None = None, value: bool = False) -> None:
    _ac = _app_core(core)
    _ac.EXAM_JOB_WORKER_STARTED = bool(value)


def _exam_worker_thread_get(core: Any | None = None):
    return _app_core(core).EXAM_JOB_WORKER_THREAD


def _exam_worker_thread_set(core: Any | None = None, value: Any = None) -> None:
    _ac = _app_core(core)
    _ac.EXAM_JOB_WORKER_THREAD = value


def exam_worker_deps(core: Any | None = None) -> ExamWorkerDeps:
    _ac = _app_core(core)
    return ExamWorkerDeps(
        job_queue=_ac.EXAM_JOB_QUEUE,
        job_lock=_ac.EXAM_JOB_LOCK,
        job_event=_ac.EXAM_JOB_EVENT,
        job_dir=_ac.EXAM_UPLOAD_JOB_DIR,
        stop_event=_ac.EXAM_JOB_STOP_EVENT,
        worker_started_get=lambda: _exam_worker_started_get(_ac),
        worker_started_set=lambda value: _exam_worker_started_set(_ac, value),
        worker_thread_get=lambda: _exam_worker_thread_get(_ac),
        worker_thread_set=lambda value: _exam_worker_thread_set(_ac, value),
        process_job=_ac.process_exam_upload_job,
        write_job=lambda job_id, updates: _ac.write_exam_job(job_id, updates),
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=_thread_factory_for_core(_ac),
        rq_enabled=lambda: _runtime_backend_is_rq(_ac),
    )



def _survey_worker_started_get(core: Any | None = None) -> bool:
    return bool(_app_core(core).SURVEY_JOB_WORKER_STARTED)


def _survey_worker_started_set(core: Any | None = None, value: bool = False) -> None:
    _ac = _app_core(core)
    _ac.SURVEY_JOB_WORKER_STARTED = bool(value)


def _survey_worker_thread_get(core: Any | None = None):
    return _app_core(core).SURVEY_JOB_WORKER_THREAD


def _survey_worker_thread_set(core: Any | None = None, value: Any = None) -> None:
    _ac = _app_core(core)
    _ac.SURVEY_JOB_WORKER_THREAD = value


def survey_worker_deps(core: Any | None = None) -> SurveyWorkerDeps:
    _ac = _app_core(core)
    return SurveyWorkerDeps(
        job_queue=_ac.SURVEY_JOB_QUEUE,
        job_lock=_ac.SURVEY_JOB_LOCK,
        job_event=_ac.SURVEY_JOB_EVENT,
        job_dir=_ac.SURVEY_JOB_DIR,
        stop_event=_ac.SURVEY_JOB_STOP_EVENT,
        worker_started_get=lambda: _survey_worker_started_get(_ac),
        worker_started_set=lambda value: _survey_worker_started_set(_ac, value),
        worker_thread_get=lambda: _survey_worker_thread_get(_ac),
        worker_thread_set=lambda value: _survey_worker_thread_set(_ac, value),
        process_job=getattr(_ac, "process_survey_job", lambda _job_id: None),
        write_job=lambda job_id, updates: _ac.write_survey_job(job_id, updates, core=_ac),
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=_thread_factory_for_core(_ac),
        rq_enabled=lambda: _runtime_backend_is_rq(_ac),
    )

def _profile_update_worker_started_get(core: Any | None = None) -> bool:
    return bool(_app_core(core)._PROFILE_UPDATE_WORKER_STARTED)


def _profile_update_worker_started_set(core: Any | None = None, value: bool = False) -> None:
    _ac = _app_core(core)
    _ac._PROFILE_UPDATE_WORKER_STARTED = bool(value)


def _profile_update_worker_thread_get(core: Any | None = None):
    return _app_core(core)._PROFILE_UPDATE_WORKER_THREAD


def _profile_update_worker_thread_set(core: Any | None = None, value: Any = None) -> None:
    _ac = _app_core(core)
    _ac._PROFILE_UPDATE_WORKER_THREAD = value


def profile_update_worker_deps(core: Any | None = None) -> ProfileUpdateWorkerDeps:
    _ac = _app_core(core)
    return ProfileUpdateWorkerDeps(
        update_queue=_ac._PROFILE_UPDATE_QUEUE,
        update_lock=_ac._PROFILE_UPDATE_LOCK,
        update_event=_ac._PROFILE_UPDATE_EVENT,
        stop_event=_ac._PROFILE_UPDATE_STOP_EVENT,
        worker_started_get=lambda: _profile_update_worker_started_get(_ac),
        worker_started_set=lambda value: _profile_update_worker_started_set(_ac, value),
        worker_thread_get=lambda: _profile_update_worker_thread_get(_ac),
        worker_thread_set=lambda value: _profile_update_worker_thread_set(_ac, value),
        queue_max=_ac.PROFILE_UPDATE_QUEUE_MAX,
        student_profile_update=_ac.student_profile_update,
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=_thread_factory_for_core(_ac),
        rq_enabled=lambda: _runtime_backend_is_rq(_ac),
        monotonic=time.monotonic,
    )


def _chat_worker_started_get(core: Any | None = None) -> bool:
    return bool(_app_core(core).CHAT_JOB_WORKER_STARTED)


def _chat_worker_started_set(core: Any | None = None, value: bool = False) -> None:
    _ac = _app_core(core)
    _ac.CHAT_JOB_WORKER_STARTED = bool(value)
