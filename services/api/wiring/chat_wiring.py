# mypy: disable-error-code=no-untyped-def
"""Chat domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "chat_handlers_deps",
    "chat_start_deps",
    "chat_status_deps",
    "chat_runtime_deps",
    "chat_event_stream_deps",
    "chat_job_repo_deps",
    "chat_worker_deps",
    "chat_job_process_deps",
    "compute_chat_reply_deps",
    "chat_support_deps",
    "session_history_deps",
    "_chat_handlers_deps",
    "_chat_start_deps",
    "_chat_status_deps",
    "_chat_runtime_deps",
    "_chat_event_stream_deps",
    "_chat_job_repo_deps",
    "_chat_worker_deps",
    "chat_worker_deps",
    "_chat_job_process_deps",
    "_compute_chat_reply_deps",
    "_chat_support_deps",
    "_session_history_deps",
]

import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from services.api.runtime import queue_runtime
from services.api.workers.chat_worker_service import (
    ChatWorkerDeps,
)

from ..api_models import ChatRequest
from ..chat_attachment_service import (
    ChatAttachmentDeps,
)
from ..chat_attachment_service import (
    resolve_chat_attachment_context as _resolve_chat_attachment_context_impl,
)
from ..chat_event_stream_service import (
    ChatEventStreamDeps,
)
from ..chat_event_stream_service import (
    append_chat_event as _append_chat_event_impl,
)
from ..chat_event_stream_service import (
    notify_chat_stream_event as _notify_chat_stream_event_impl,
)
from ..chat_event_stream_service import (
    wait_for_chat_stream_event as _wait_for_chat_stream_event_impl,
)
from ..chat_job_processing_service import (
    ChatJobProcessDeps,
    ComputeChatReplyDeps,
)
from ..chat_job_processing_service import (
    detect_role_hint as _detect_role_hint_impl,
)
from ..chat_job_repository import ChatJobRepositoryDeps
from ..chat_job_service import chat_job_path as _chat_job_path_impl
from ..chat_lane_repository import (
    _chat_enqueue_locked,
    _chat_find_position_locked,
    _chat_has_pending_locked,
    _chat_lane_load_locked,
    _chat_last_user_text,
    _chat_mark_done_locked,
    _chat_pick_next_locked,
    _chat_recent_job_locked,
    _chat_register_recent_locked,
    _chat_request_map_set_if_absent,
    _chat_text_fingerprint,
    resolve_chat_lane_id,
    resolve_chat_lane_id_from_job,
)
from ..chat_runtime_service import ChatRuntimeDeps
from ..chat_session_history_service import load_session_messages as _load_session_messages_impl
from ..chat_session_utils import paginate_session_items as _paginate_session_items_impl
from ..chat_start_service import ChatStartDeps
from ..chat_start_service import start_chat_orchestration as _start_chat_orchestration_impl
from ..chat_status_service import ChatStatusDeps
from ..chat_status_service import get_chat_status as _get_chat_status_impl
from ..chat_support_service import ChatSupportDeps
from ..handlers import chat_handlers
from ..job_repository import _atomic_write_json, _release_lockfile, _try_acquire_lockfile
from ..prompt_builder import compile_system_prompt
from ..session_history_service import SessionHistoryDeps
from ..session_view_state import (
    compare_iso_ts as _compare_iso_ts_impl,
)
from ..session_view_state import (
    normalize_session_view_state_payload as _normalize_session_view_state_payload_impl,
)
from ..skill_auto_router import resolve_effective_skill as _resolve_effective_skill_impl
from ..student_memory_service import (
    StudentMemoryDeps,
)
from ..student_memory_service import (
    student_memory_auto_propose_from_turn_api as _student_memory_auto_propose_from_turn_api,
)
from ..teacher_model_config_service import (
    resolve_teacher_model_config as _resolve_teacher_model_config_impl,
)
from ..teacher_provider_registry_service import (
    resolve_provider_target as _resolve_provider_target_impl,
)
from . import get_app_core as _app_core
from .teacher_wiring import _teacher_model_config_deps, _teacher_provider_registry_deps
from .worker_wiring import (
    _chat_worker_started_get,
    _chat_worker_started_set,
    _thread_factory_for_core,
)


def _queue_backend_for_app_core(_ac: Any) -> Any:
    return queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )


def _chat_handlers_deps(core: Any | None = None) -> chat_handlers.ChatHandlerDeps:
    _ac = _app_core(core)
    backend = _queue_backend_for_app_core(_ac)
    return chat_handlers.ChatHandlerDeps(
        compute_chat_reply_sync=lambda req: _ac.compute_chat_reply_sync(req),
        detect_math_delimiters=_ac.detect_math_delimiters,
        detect_latex_tokens=_ac.detect_latex_tokens,
        diag_log=_ac.diag_log,
        build_interaction_note=_ac.build_interaction_note,
        enqueue_profile_update=lambda payload: queue_runtime.enqueue_profile_update(
            payload,
            backend=backend,
        ),
        student_profile_update=_ac.student_profile_update,
        profile_update_async=_ac.PROFILE_UPDATE_ASYNC,
        run_in_threadpool=run_in_threadpool,
        get_chat_status=lambda job_id: _get_chat_status_impl(job_id, deps=_chat_status_deps(core)),
        start_chat_api=lambda req: _start_chat_orchestration_impl(req, deps=_chat_start_deps(core)),
    )


def _chat_start_deps(core: Any | None = None):
    _ac = _app_core(core)
    backend = _queue_backend_for_app_core(_ac)

    def _detect_role_hint_nonnull(req: Any) -> str:
        return _detect_role_hint_impl(req, detect_role=_ac.detect_role) or "unknown"

    def _enqueue_chat_job(job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
        return queue_runtime.enqueue_chat_job(
            job_id,
            lane_id=lane_id,
            backend=backend,
        )

    attachment_deps = ChatAttachmentDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        extract_text_from_file=_ac.extract_text_from_file,
        xlsx_to_table_preview=_ac.xlsx_to_table_preview,
        xls_to_table_preview=_ac.xls_to_table_preview,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        uuid_hex=lambda: uuid.uuid4().hex,
    )

    return ChatStartDeps(
        http_error=lambda code, detail: HTTPException(status_code=code, detail=detail),
        get_chat_job_id_by_request=_ac.get_chat_job_id_by_request,
        load_chat_job=_ac.load_chat_job,
        detect_role_hint=_detect_role_hint_nonnull,
        resolve_student_session_id=_ac.resolve_student_session_id,
        resolve_teacher_id=_ac.resolve_teacher_id,
        resolve_chat_lane_id=resolve_chat_lane_id,
        chat_last_user_text=_chat_last_user_text,
        chat_text_fingerprint=_chat_text_fingerprint,
        chat_job_lock=_ac.CHAT_JOB_LOCK,
        chat_recent_job_locked=_chat_recent_job_locked,
        upsert_chat_request_index=_ac.upsert_chat_request_index,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_lane_max_queue=_ac.CHAT_LANE_MAX_QUEUE,
        chat_request_map_set_if_absent=_chat_request_map_set_if_absent,
        new_job_id=lambda: f"cjob_{uuid.uuid4().hex[:12]}",
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_chat_job=_ac.write_chat_job,
        enqueue_chat_job=_enqueue_chat_job,
        chat_register_recent_locked=_chat_register_recent_locked,
        append_student_session_message=_ac.append_student_session_message,
        update_student_session_index=_ac.update_student_session_index,
        append_teacher_session_message=_ac.append_teacher_session_message,
        update_teacher_session_index=_ac.update_teacher_session_index,
        parse_date_str=_ac.parse_date_str,
        resolve_chat_attachment_context=lambda **kwargs: _resolve_chat_attachment_context_impl(
            deps=attachment_deps,
            **kwargs,
        ),
        append_chat_event=lambda job_id, event_type, payload: _append_chat_event_impl(
            job_id,
            event_type,
            payload,
            deps=_chat_event_stream_deps(core),
        ),
    )


def _chat_status_deps(core: Any | None = None):
    _ac = _app_core(core)
    backend = _queue_backend_for_app_core(_ac)
    return ChatStatusDeps(
        load_chat_job=_ac.load_chat_job,
        enqueue_chat_job=lambda job_id, lane_id: queue_runtime.enqueue_chat_job(
            job_id,
            lane_id=lane_id,
            backend=backend,
        ),
        resolve_chat_lane_id_from_job=resolve_chat_lane_id_from_job,
        chat_job_lock=_ac.CHAT_JOB_LOCK,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_find_position_locked=_chat_find_position_locked,
    )


def _chat_runtime_deps(core: Any | None = None):
    _ac = _app_core(core)
    from ..global_limits import (
        GLOBAL_LLM_SEMAPHORE,
        GLOBAL_LLM_SEMAPHORE_STUDENT,
        GLOBAL_LLM_SEMAPHORE_TEACHER,
    )

    return ChatRuntimeDeps(
        gateway=_ac.LLM_GATEWAY,
        limit=_ac._limit,
        default_limiter=(
            _ac._LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE,
        ),
        student_limiter=(
            _ac._LLM_SEMAPHORE,
            _ac._LLM_SEMAPHORE_STUDENT,
            GLOBAL_LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE_STUDENT,
        ),
        teacher_limiter=(
            _ac._LLM_SEMAPHORE,
            _ac._LLM_SEMAPHORE_TEACHER,
            GLOBAL_LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE_TEACHER,
        ),
        resolve_teacher_id=_ac.resolve_teacher_id,
        resolve_teacher_model_config=lambda teacher_id: _resolve_teacher_model_config_impl(
            teacher_id,
            deps=_teacher_model_config_deps(core),
        ),
        resolve_teacher_provider_target=lambda teacher_id, provider, mode, model: _resolve_provider_target_impl(
            teacher_id,
            provider,
            mode,
            model,
            deps=_teacher_provider_registry_deps(core),
        ),
        diag_log=_ac.diag_log,
        monotonic=time.monotonic,
    )


def _chat_job_repo_deps(core: Any | None = None):
    _ac = _app_core(core)
    return ChatJobRepositoryDeps(
        chat_job_dir=_ac.CHAT_JOB_DIR,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _chat_event_stream_deps(core: Any | None = None) -> ChatEventStreamDeps:
    _ac = _app_core(core)
    return ChatEventStreamDeps(
        chat_job_path=lambda job_id: _chat_job_path_impl(job_id, deps=_chat_job_repo_deps(core)),
        chat_job_lock=_ac.CHAT_JOB_LOCK,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        notify_job_event=_notify_chat_stream_event_impl,
        wait_job_event=_wait_for_chat_stream_event_impl,
    )


def _chat_worker_deps(core: Any | None = None):
    _ac = _app_core(core)

    return ChatWorkerDeps(
        chat_job_dir=_ac.CHAT_JOB_DIR,
        chat_job_lock=_ac.CHAT_JOB_LOCK,
        chat_job_event=_ac.CHAT_JOB_EVENT,
        stop_event=_ac.CHAT_WORKER_STOP_EVENT,
        chat_worker_threads=_ac.CHAT_WORKER_THREADS,
        chat_worker_pool_size=_ac.CHAT_WORKER_POOL_SIZE,
        worker_started_get=lambda: _chat_worker_started_get(_ac),
        worker_started_set=lambda value: _chat_worker_started_set(_ac, value),
        load_chat_job=_ac.load_chat_job,
        write_chat_job=lambda job_id, updates: _ac.write_chat_job(job_id, updates),
        resolve_chat_lane_id_from_job=resolve_chat_lane_id_from_job,
        chat_enqueue_locked=_chat_enqueue_locked,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_pick_next_locked=_chat_pick_next_locked,
        chat_mark_done_locked=_chat_mark_done_locked,
        chat_has_pending_locked=_chat_has_pending_locked,
        process_chat_job=_ac.process_chat_job,
        diag_log=_ac.diag_log,
        sleep=time.sleep,
        thread_factory=_thread_factory_for_core(_ac),
    )


def chat_worker_deps(core: Any):
    return _chat_worker_deps(core)


def _chat_job_process_deps(core: Any | None = None):
    _ac = _app_core(core)
    backend = _queue_backend_for_app_core(_ac)
    student_memory_deps = StudentMemoryDeps(
        resolve_teacher_id=_ac.resolve_teacher_id,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )
    return ChatJobProcessDeps(
        chat_job_claim_path=lambda job_id: _chat_job_path_impl(job_id, deps=_chat_job_repo_deps(core))
        / "claim.lock",
        try_acquire_lockfile=_try_acquire_lockfile,
        chat_job_claim_ttl_sec=_ac.CHAT_JOB_CLAIM_TTL_SEC,
        load_chat_job=_ac.load_chat_job,
        write_chat_job=lambda job_id, updates: _ac.write_chat_job(job_id, updates),
        chat_request_model=ChatRequest,
        compute_chat_reply_sync=lambda req, session_id, teacher_id_override, event_sink=None: _ac.compute_chat_reply_sync(
            req,
            session_id=session_id,
            teacher_id_override=teacher_id_override,
            event_sink=event_sink,
        ),
        monotonic=time.monotonic,
        build_interaction_note=_ac.build_interaction_note,
        profile_update_async=_ac.PROFILE_UPDATE_ASYNC,
        enqueue_profile_update=lambda payload: queue_runtime.enqueue_profile_update(
            payload,
            backend=backend,
        ),
        student_profile_update=_ac.student_profile_update,
        resolve_student_session_id=_ac.resolve_student_session_id,
        append_student_session_message=_ac.append_student_session_message,
        update_student_session_index=_ac.update_student_session_index,
        parse_date_str=_ac.parse_date_str,
        resolve_teacher_id=_ac.resolve_teacher_id,
        ensure_teacher_workspace=_ac.ensure_teacher_workspace,
        append_teacher_session_message=_ac.append_teacher_session_message,
        update_teacher_session_index=_ac.update_teacher_session_index,
        teacher_memory_auto_propose_from_turn=_ac.teacher_memory_auto_propose_from_turn,
        teacher_memory_auto_flush_from_session=_ac.teacher_memory_auto_flush_from_session,
        maybe_compact_teacher_session=_ac.maybe_compact_teacher_session,
        student_memory_auto_propose_from_turn=lambda **kwargs: _student_memory_auto_propose_from_turn_api(
            deps=student_memory_deps,
            teacher_id=kwargs.get("teacher_id"),
            student_id=str(kwargs.get("student_id") or ""),
            session_id=str(kwargs.get("session_id") or ""),
            user_text=str(kwargs.get("user_text") or ""),
            assistant_text=str(kwargs.get("assistant_text") or ""),
            request_id=(str(kwargs.get("request_id") or "") or None),
        ),
        diag_log=_ac.diag_log,
        release_lockfile=_release_lockfile,
        append_chat_event=lambda job_id, event_type, payload: _append_chat_event_impl(
            job_id,
            event_type,
            payload,
            deps=_chat_event_stream_deps(core),
        ),
    )


def _compute_chat_reply_deps(core: Any | None = None):
    _ac = _app_core(core)
    return ComputeChatReplyDeps(
        detect_role=_ac.detect_role,
        diag_log=_ac.diag_log,
        teacher_assignment_preflight=_ac.teacher_assignment_preflight,
        resolve_teacher_id=_ac.resolve_teacher_id,
        teacher_build_context=lambda teacher_id, query, max_chars, session_id: _ac.teacher_build_context(
            teacher_id,
            query=query,
            max_chars=max_chars,
            session_id=session_id,
        ),
        detect_student_study_trigger=_ac.detect_student_study_trigger,
        load_profile_file=_ac.load_profile_file,
        data_dir=_ac.DATA_DIR,
        build_verified_student_context=_ac.build_verified_student_context,
        build_assignment_detail_cached=_ac.build_assignment_detail_cached,
        find_assignment_for_date=_ac.find_assignment_for_date,
        parse_date_str=_ac.parse_date_str,
        build_assignment_context=_ac.build_assignment_context,
        chat_extra_system_max_chars=_ac.CHAT_EXTRA_SYSTEM_MAX_CHARS,
        trim_messages=_ac._trim_messages,
        student_inflight=_ac._student_inflight,
        run_agent=_ac.run_agent,
        normalize_math_delimiters=_ac.normalize_math_delimiters,
        resolve_effective_skill=lambda role_hint, requested_skill_id, last_user_text: _resolve_effective_skill_impl(
            app_root=_ac.APP_ROOT,
            role_hint=role_hint,
            requested_skill_id=requested_skill_id,
            last_user_text=last_user_text,
            detect_assignment_intent=_ac.detect_assignment_intent,
        ),
    )

def _chat_support_deps(core: Any | None = None):
    _ac = _app_core(core)
    return ChatSupportDeps(
        compile_system_prompt=compile_system_prompt,
        diag_log=_ac.diag_log,
        getenv=os.getenv,
    )


def _session_history_deps(core: Any | None = None):
    _ac = _app_core(core)
    return SessionHistoryDeps(
        load_student_sessions_index=_ac.load_student_sessions_index,
        load_teacher_sessions_index=_ac.load_teacher_sessions_index,
        paginate_session_items=lambda items, cursor, limit: _paginate_session_items_impl(items, cursor=cursor, limit=limit),
        load_student_session_view_state=_ac.load_student_session_view_state,
        load_teacher_session_view_state=_ac.load_teacher_session_view_state,
        normalize_session_view_state_payload=_normalize_session_view_state_payload_impl,
        compare_iso_ts=_compare_iso_ts_impl,
        now_iso_millis=lambda: datetime.now().isoformat(timespec="milliseconds"),
        save_student_session_view_state=_ac.save_student_session_view_state,
        save_teacher_session_view_state=_ac.save_teacher_session_view_state,
        student_session_file=_ac.student_session_file,
        teacher_session_file=_ac.teacher_session_file,
        load_session_messages=_load_session_messages_impl,
        resolve_teacher_id=_ac.resolve_teacher_id,
    )


def chat_handlers_deps(core: Any) -> chat_handlers.ChatHandlerDeps:
    return _chat_handlers_deps(core)


def chat_start_deps(core: Any):
    return _chat_start_deps(core)


def chat_status_deps(core: Any):
    return _chat_status_deps(core)


def chat_runtime_deps(core: Any):
    return _chat_runtime_deps(core)


def chat_event_stream_deps(core: Any) -> ChatEventStreamDeps:
    return _chat_event_stream_deps(core)


def chat_job_repo_deps(core: Any):
    return _chat_job_repo_deps(core)


def chat_job_process_deps(core: Any):
    return _chat_job_process_deps(core)


def compute_chat_reply_deps(core: Any):
    return _compute_chat_reply_deps(core)


def chat_support_deps(core: Any):
    return _chat_support_deps(core)


def session_history_deps(core: Any):
    return _session_history_deps(core)
