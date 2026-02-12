from __future__ import annotations

import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from collections import deque

_log = logging.getLogger(__name__)

from llm_gateway import LLMGateway
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

from .assignment_api_service import AssignmentApiDeps, get_assignment_detail_api as _get_assignment_detail_api_impl
from .api_models import (
    AssignmentRequirementsRequest,
    ChatResponse,
    ChatRequest,
    ChatStartRequest,
    ExamUploadConfirmRequest,
    ExamUploadDraftSaveRequest,
    RoutingProposalCreateRequest,
    RoutingProposalReviewRequest,
    RoutingRollbackRequest,
    RoutingSimulateRequest,
    StudentImportRequest,
    StudentVerifyRequest,
    TeacherProviderRegistryCreateRequest,
    TeacherProviderRegistryDeleteRequest,
    TeacherProviderRegistryProbeRequest,
    TeacherProviderRegistryUpdateRequest,
    TeacherMemoryProposalReviewRequest,
    UploadConfirmRequest,
    UploadDraftSaveRequest,
)
from .assignment_context_service import build_assignment_context as _build_assignment_context_impl
from .assignment_catalog_service import (
    AssignmentCatalogDeps,
    AssignmentMetaPostprocessDeps,
    assignment_specificity as _assignment_specificity_impl,
    build_assignment_detail as _build_assignment_detail_impl,
    find_assignment_for_date as _find_assignment_for_date_impl,
    list_assignments as _list_assignments_impl,
    parse_iso_timestamp as _parse_iso_timestamp_impl,
    postprocess_assignment_meta as _postprocess_assignment_meta_impl,
    read_text_safe as _read_text_safe_impl,
    resolve_assignment_date as _resolve_assignment_date_impl,
)
from .assignment_generate_service import (
    AssignmentGenerateDeps,
    generate_assignment as _generate_assignment_impl,
)
from .assignment_generate_tool_service import (
    AssignmentGenerateToolDeps,
    assignment_generate as _assignment_generate_tool_impl,
)
from .assignment_progress_service import (
    AssignmentProgressDeps,
    compute_assignment_progress as _compute_assignment_progress_impl,
)
from .assignment_intent_service import (
    detect_assignment_intent as _detect_assignment_intent_impl,
    extract_assignment_id as _extract_assignment_id_impl,
    extract_date as _extract_date_impl,
    extract_kp_list as _extract_kp_list_impl,
    extract_numbered_item as _extract_numbered_item_impl,
    extract_per_kp as _extract_per_kp_impl,
    extract_question_ids as _extract_question_ids_impl,
    extract_requirements_from_text as _extract_requirements_from_text_impl,
    normalize_numbered_block as _normalize_numbered_block_impl,
    parse_grade_and_level as _parse_grade_and_level_impl,
    parse_subject_topic as _parse_subject_topic_impl,
)
from .assignment_llm_gate_service import (
    AssignmentLlmGateDeps,
    llm_assignment_gate as _llm_assignment_gate_impl,
    parse_json_from_text as _parse_json_from_text_impl,
)
from .assignment_requirements_service import (
    AssignmentRequirementsDeps,
    compute_requirements_missing as _compute_requirements_missing_impl,
    ensure_requirements_for_assignment as _ensure_requirements_for_assignment_impl,
    format_requirements_prompt as _format_requirements_prompt_impl,
    merge_requirements as _merge_requirements_impl,
    normalize_class_level as _normalize_class_level_impl,
    normalize_difficulty as _normalize_difficulty_impl,
    normalize_preferences as _normalize_preferences_impl,
    parse_duration as _parse_duration_impl,
    parse_list_value as _parse_list_value_impl,
    save_assignment_requirements as _save_assignment_requirements_impl,
    validate_requirements as _validate_requirements_impl,
)
from .assignment_upload_confirm_gate_service import (
    AssignmentUploadConfirmGateError,
    ensure_assignment_upload_confirm_ready as _ensure_assignment_upload_confirm_ready_impl,
)
from .assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    AssignmentUploadConfirmError,
    confirm_assignment_upload as _confirm_assignment_upload_impl,
)
from .assignment_upload_draft_save_service import (
    AssignmentUploadDraftSaveDeps,
    AssignmentUploadDraftSaveError,
    save_assignment_upload_draft as _save_assignment_upload_draft_impl,
)
from .assignment_upload_legacy_service import (
    AssignmentUploadLegacyDeps,
    AssignmentUploadLegacyError,
    assignment_upload as _assignment_upload_legacy_impl,
)
from .assignment_upload_draft_service import (
    assignment_upload_not_ready_detail as _assignment_upload_not_ready_detail_impl,
    build_assignment_upload_draft as _build_assignment_upload_draft_impl,
    clean_assignment_draft_questions as _clean_assignment_draft_questions_impl,
    load_assignment_draft_override as _load_assignment_draft_override_impl,
    save_assignment_draft_override as _save_assignment_draft_override_impl,
)
from .assignment_questions_ocr_service import (
    AssignmentQuestionsOcrDeps,
    assignment_questions_ocr as _assignment_questions_ocr_impl,
)
from .assignment_upload_query_service import (
    AssignmentUploadQueryDeps,
    AssignmentUploadQueryError,
    get_assignment_upload_draft as _get_assignment_upload_draft_impl,
    get_assignment_upload_status as _get_assignment_upload_status_impl,
)
from .assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    best_submission_attempt as _best_submission_attempt_impl,
    compute_submission_attempt as _compute_submission_attempt_impl,
    counted_grade_item as _counted_grade_item_impl,
    list_submission_attempts as _list_submission_attempts_impl,
)
from .assignment_today_service import AssignmentTodayDeps, assignment_today as _assignment_today_impl
from .assignment_upload_start_service import (
    AssignmentUploadStartDeps,
    AssignmentUploadStartError,
    start_assignment_upload as _start_assignment_upload_impl,
)
from .agent_service import (
    AgentRuntimeDeps,
    default_load_skill_runtime as _default_load_skill_runtime_impl,
    default_teacher_tools_to_openai as _default_teacher_tools_to_openai_impl,
    parse_tool_json as _parse_tool_json_impl,
    run_agent_runtime as _run_agent_runtime_impl,
)
from .chat_api_service import ChatApiDeps, start_chat_api as _start_chat_api_impl
from .chat_job_repository import ChatJobRepositoryDeps
from .chat_job_service import (
    chat_job_path as _chat_job_path_impl,
    load_chat_job as _load_chat_job_impl,
    write_chat_job as _write_chat_job_impl,
)
from .chat_job_processing_service import (
    ChatJobProcessDeps,
    ComputeChatReplyDeps,
    compute_chat_reply_sync as _compute_chat_reply_sync_impl,
    detect_role_hint as _detect_role_hint_impl,
    process_chat_job as _process_chat_job_impl,
)
from .chat_runtime_service import ChatRuntimeDeps, call_llm_runtime as _call_llm_runtime_impl
from .chat_session_history_service import load_session_messages as _load_session_messages_impl
from .chat_session_utils import (
    paginate_session_items as _paginate_session_items_impl,
    resolve_student_session_id as _resolve_student_session_id_impl,
)
from .chat_start_service import ChatStartDeps, start_chat_orchestration as _start_chat_orchestration_impl
from .chat_state_store import create_chat_idempotency_store
from .chat_status_service import ChatStatusDeps, get_chat_status as _get_chat_status_impl
from services.api.workers import exam_worker_service, profile_update_worker_service, upload_worker_service
from services.api.workers.chat_worker_service import (
    ChatWorkerDeps,
    enqueue_chat_job as _enqueue_chat_job_impl,
    scan_pending_chat_jobs as _scan_pending_chat_jobs_impl,
)
from services.api.workers.exam_worker_service import ExamWorkerDeps
from services.api.workers.profile_update_worker_service import ProfileUpdateWorkerDeps
from services.api.workers.upload_worker_service import UploadWorkerDeps
from .skill_auto_router import resolve_effective_skill as _resolve_effective_skill_impl
from .chat_support_service import (
    ChatSupportDeps,
    allowed_tools as _allowed_tools_impl,
    build_interaction_note as _build_interaction_note_impl,
    build_system_prompt as _build_system_prompt_impl,
    build_verified_student_context as _build_verified_student_context_impl,
    detect_latex_tokens as _detect_latex_tokens_impl,
    detect_math_delimiters as _detect_math_delimiters_impl,
    detect_student_study_trigger as _detect_student_study_trigger_impl,
    extract_exam_id as _extract_exam_id_impl,
    extract_min_chars_requirement as _extract_min_chars_requirement_impl,
    is_exam_analysis_request as _is_exam_analysis_request_impl,
    normalize_math_delimiters as _normalize_math_delimiters_impl,
)
from .chart_agent_run_service import (
    ChartAgentRunDeps,
    chart_agent_bool as _chart_agent_bool_impl,
    chart_agent_default_code as _chart_agent_default_code_impl,
    chart_agent_engine as _chart_agent_engine_impl,
    chart_agent_generate_candidate as _chart_agent_generate_candidate_impl,
    chart_agent_generate_candidate_opencode as _chart_agent_generate_candidate_opencode_impl,
    chart_agent_opencode_overrides as _chart_agent_opencode_overrides_impl,
    chart_agent_packages as _chart_agent_packages_impl,
    chart_agent_run as _chart_agent_run_impl,
)
from .chart_api_service import ChartApiDeps, chart_exec_api as _chart_exec_api_impl
from .chart_executor import execute_chart_exec, resolve_chart_image_path, resolve_chart_run_meta_path
from .handlers import assignment_handlers, assignment_io_handlers, assignment_upload_handlers, chat_handlers, exam_upload_handlers
from .content_catalog_service import (
    ContentCatalogDeps,
    list_lessons as _list_lessons_impl,
    list_skills as _list_skills_impl,
)
from .core_example_tool_service import (
    CoreExampleToolDeps,
    core_example_register as _core_example_register_impl,
    core_example_render as _core_example_render_impl,
    core_example_search as _core_example_search_impl,
)
from .exam_api_service import ExamApiDeps, get_exam_detail_api as _get_exam_detail_api_impl
from .exam_detail_service import (
    ExamDetailDeps,
    exam_question_detail as _exam_question_detail_impl,
    exam_student_detail as _exam_student_detail_impl,
)
from .exam_analysis_charts_service import (
    ExamAnalysisChartsDeps,
    exam_analysis_charts_generate as _exam_analysis_charts_generate_impl,
)
from .exam_catalog_service import ExamCatalogDeps, list_exams as _list_exams_impl
from .exam_longform_service import (
    ExamLongformDeps,
    build_exam_longform_context as _build_exam_longform_context_impl,
    calc_longform_max_tokens as _calc_longform_max_tokens_impl,
    generate_longform_reply as _generate_longform_reply_impl,
    summarize_exam_students as _summarize_exam_students_impl,
)
from .exam_overview_service import (
    ExamOverviewDeps,
    exam_analysis_get as _exam_analysis_get_impl,
    exam_get as _exam_get_impl,
    exam_students_list as _exam_students_list_impl,
)
from .exam_range_service import (
    ExamRangeDeps,
    exam_question_batch_detail as _exam_question_batch_detail_impl,
    exam_range_summary_batch as _exam_range_summary_batch_impl,
    exam_range_top_students as _exam_range_top_students_impl,
)
from .exam_upload_confirm_service import (
    ExamUploadConfirmDeps,
    confirm_exam_upload as _confirm_exam_upload_impl,
)
from .exam_upload_api_service import (
    ExamUploadApiDeps,
    ExamUploadApiError,
    exam_upload_confirm as _exam_upload_confirm_api_impl,
    exam_upload_draft as _exam_upload_draft_api_impl,
    exam_upload_draft_save as _exam_upload_draft_save_api_impl,
    exam_upload_status as _exam_upload_status_api_impl,
)
from .exam_upload_draft_service import (
    build_exam_upload_draft as _build_exam_upload_draft_impl,
    exam_upload_not_ready_detail as _exam_upload_not_ready_detail_impl,
    load_exam_draft_override as _load_exam_draft_override_impl,
    save_exam_draft_override as _save_exam_draft_override_impl,
)
from .exam_upload_start_service import ExamUploadStartDeps, start_exam_upload as _start_exam_upload_impl
from .lesson_core_tool_service import LessonCaptureDeps, lesson_capture as _lesson_capture_impl
from .opencode_executor import resolve_opencode_status, run_opencode_codegen
from .prompt_builder import compile_system_prompt
from .session_view_state import (
    compare_iso_ts as _compare_iso_ts_impl,
    default_session_view_state as _default_session_view_state_impl,
    load_session_view_state as _load_session_view_state_impl,
    normalize_session_view_state_payload as _normalize_session_view_state_payload_impl,
    save_session_view_state as _save_session_view_state_impl,
)
from .session_history_api_service import (
    SessionHistoryApiDeps,
    SessionHistoryApiError,
    student_history_session as _student_history_session_api_impl,
    student_history_sessions as _student_history_sessions_api_impl,
    student_session_view_state as _student_session_view_state_api_impl,
    teacher_history_session as _teacher_history_session_api_impl,
    teacher_history_sessions as _teacher_history_sessions_api_impl,
    teacher_session_view_state as _teacher_session_view_state_api_impl,
    update_student_session_view_state as _update_student_session_view_state_api_impl,
    update_teacher_session_view_state as _update_teacher_session_view_state_api_impl,
)
from .session_discussion_service import (
    SessionDiscussionDeps,
    session_discussion_pass as _session_discussion_pass_impl,
)
from .student_profile_api_service import StudentProfileApiDeps, get_profile_api as _get_profile_api_impl
from .student_import_service import (
    StudentImportDeps,
    import_students_from_responses as _import_students_from_responses_impl,
    resolve_responses_file as _resolve_responses_file_impl,
    student_import as _student_import_impl,
)
from .student_ops_api_service import (
    StudentOpsApiDeps,
    update_profile as _update_profile_api_impl,
    upload_files as _upload_files_api_impl,
    verify_student as _verify_student_api_impl,
)
from .student_directory_service import (
    StudentDirectoryDeps,
    list_all_student_ids as _list_all_student_ids_impl,
    list_all_student_profiles as _list_all_student_profiles_impl,
    list_student_ids_by_class as _list_student_ids_by_class_impl,
    student_candidates_by_name as _student_candidates_by_name_impl,
    student_search as _student_search_impl,
)
from .student_submit_service import StudentSubmitDeps, submit as _student_submit_impl
from .teacher_assignment_preflight_service import (
    TeacherAssignmentPreflightDeps,
    teacher_assignment_preflight as _teacher_assignment_preflight_impl,
)
from .teacher_routing_api_service import TeacherRoutingApiDeps, get_routing_api as _get_routing_api_impl
from .teacher_llm_routing_service import (
    TeacherLlmRoutingDeps,
    ensure_teacher_routing_file as _ensure_teacher_routing_file_impl,
    teacher_llm_routing_apply as _teacher_llm_routing_apply_impl,
    teacher_llm_routing_get as _teacher_llm_routing_get_impl,
    teacher_llm_routing_proposal_get as _teacher_llm_routing_proposal_get_impl,
    teacher_llm_routing_propose as _teacher_llm_routing_propose_impl,
    teacher_llm_routing_rollback as _teacher_llm_routing_rollback_impl,
    teacher_llm_routing_simulate as _teacher_llm_routing_simulate_impl,
)
from .teacher_provider_registry_service import (
    TeacherProviderRegistryDeps,
    merged_model_registry as _merged_model_registry_impl,
    resolve_provider_target as _resolve_provider_target_impl,
    teacher_provider_registry_create as _teacher_provider_registry_create_impl,
    teacher_provider_registry_delete as _teacher_provider_registry_delete_impl,
    teacher_provider_registry_get as _teacher_provider_registry_get_impl,
    teacher_provider_registry_probe_models as _teacher_provider_registry_probe_models_impl,
    teacher_provider_registry_update as _teacher_provider_registry_update_impl,
)
from .tool_dispatch_service import ToolDispatchDeps, tool_dispatch as _tool_dispatch_impl
from .upload_io_service import sanitize_filename_io
from .chat_lane_store_factory import get_chat_lane_store
from services.api.queue.queue_backend import rq_enabled as _rq_enabled_impl
from services.api.runtime import queue_runtime
from services.api.runtime.inline_backend_factory import build_inline_backend
from services.api.runtime.runtime_state import reset_runtime_state as _reset_runtime_state
from services.api.workers.inline_runtime import start_inline_workers, stop_inline_workers
try:
    from mem0_config import load_dotenv

    load_dotenv()
except Exception:
    _log.warning("failed to import or run mem0_config.load_dotenv", exc_info=True)
    pass

import importlib as _importlib
from . import config as _config_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_config_module)
from .config import *  # noqa: F401,F403 — re-export all configuration constants
from .config import (
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    _settings,
)

from . import paths as _paths_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_paths_module)
from .paths import *  # noqa: F401,F403 — re-export all path resolution functions

from . import job_repository as _job_repository_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_job_repository_module)
from .job_repository import *  # noqa: F401,F403 — re-export all job repository functions
from .job_repository import _atomic_write_json, _try_acquire_lockfile, _release_lockfile

from . import session_store as _session_store_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_session_store_module)
from .session_store import *  # noqa: F401,F403 — re-export all session store functions

from . import chat_lane_repository as _chat_lane_repository_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_chat_lane_repository_module)
from .chat_lane_repository import *  # noqa: F401,F403 — re-export all chat lane repository functions
from .chat_lane_repository import (
    _chat_last_user_text,
    _chat_text_fingerprint,
    _chat_lane_store,
    _chat_lane_load_locked,
    _chat_find_position_locked,
    _chat_enqueue_locked,
    _chat_has_pending_locked,
    _chat_pick_next_locked,
    _chat_mark_done_locked,
    _chat_register_recent_locked,
    _chat_recent_job_locked,
    _chat_request_map_path,
    _chat_request_map_get,
    _chat_request_map_set_if_absent,
)

from . import exam_utils as _exam_utils_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_exam_utils_module)
from .exam_utils import *  # noqa: F401,F403

from . import core_utils as _core_utils_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_core_utils_module)
from .core_utils import *  # noqa: F401,F403

from . import profile_service as _profile_service_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_profile_service_module)
from .profile_service import *  # noqa: F401,F403

from . import assignment_data_service as _assignment_data_service_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_assignment_data_service_module)
from .assignment_data_service import *  # noqa: F401,F403

from . import teacher_memory_core as _teacher_memory_core_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_teacher_memory_core_module)
from .teacher_memory_core import *  # noqa: F401,F403 — re-export all teacher memory functions

def _rq_enabled() -> bool:
    return _rq_enabled_impl()

_reset_runtime_state(sys.modules[__name__], create_chat_idempotency_store=create_chat_idempotency_store)

from .wiring import chat_wiring as _chat_wiring_module
from .wiring import assignment_wiring as _assignment_wiring_module
from .wiring import exam_wiring as _exam_wiring_module
from .wiring import student_wiring as _student_wiring_module
from .wiring import teacher_wiring as _teacher_wiring_module
from .wiring import worker_wiring as _worker_wiring_module
from .wiring import misc_wiring as _misc_wiring_module
from .wiring import skill_wiring as _skill_wiring_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_chat_wiring_module)
    _importlib.reload(_assignment_wiring_module)
    _importlib.reload(_exam_wiring_module)
    _importlib.reload(_student_wiring_module)
    _importlib.reload(_teacher_wiring_module)
    _importlib.reload(_worker_wiring_module)
    _importlib.reload(_misc_wiring_module)
    _importlib.reload(_skill_wiring_module)
from .wiring.chat_wiring import *  # noqa: F401,F403
from .wiring.assignment_wiring import *  # noqa: F401,F403
from .wiring.exam_wiring import *  # noqa: F401,F403
from .wiring.student_wiring import *  # noqa: F401,F403
from .wiring.teacher_wiring import *  # noqa: F401,F403
from .wiring.worker_wiring import *  # noqa: F401,F403
from .wiring.misc_wiring import *  # noqa: F401,F403
from .wiring.skill_wiring import *  # noqa: F401,F403
if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DATA_DIR") or os.getenv("UPLOADS_DIR"):
    _importlib.reload(_importlib.import_module("services.api.context_application_facade"))
    _importlib.reload(_importlib.import_module("services.api.context_runtime_facade"))
    _importlib.reload(_importlib.import_module("services.api.context_io_facade"))
from .context_application_facade import *  # noqa: F401,F403
from .context_runtime_facade import *  # noqa: F401,F403
from .context_io_facade import *  # noqa: F401,F403
from services.api.chat_limits import (
    acquire_limiters as _acquire_limiters_impl,
    student_inflight_guard as _student_inflight_guard_impl,
    trim_messages as _trim_messages_impl,
)


def _limit(limiter: Any):
    return _acquire_limiters_impl(limiter)

def _trim_messages(messages: List[Dict[str, Any]], role_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    return _trim_messages_impl(
        messages,
        role_hint=role_hint,
        max_messages=CHAT_MAX_MESSAGES,
        max_messages_student=CHAT_MAX_MESSAGES_STUDENT,
        max_messages_teacher=CHAT_MAX_MESSAGES_TEACHER,
        max_chars=CHAT_MAX_MESSAGE_CHARS,
    )


def _student_inflight(student_id: Optional[str]):
    return _student_inflight_guard_impl(
        student_id=student_id,
        inflight=_STUDENT_INFLIGHT,
        lock=_STUDENT_INFLIGHT_LOCK,
        limit=CHAT_STUDENT_INFLIGHT_LIMIT,
    )

def _setup_diag_logger() -> Optional[logging.Logger]:
    if not DIAG_LOG_ENABLED:
        return None
    DIAG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("diag")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(str(DIAG_LOG_PATH), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


_DIAG_LOGGER = _setup_diag_logger()
LLM_GATEWAY = LLMGateway()

def diag_log(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if not DIAG_LOG_ENABLED or _DIAG_LOGGER is None:
        return
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
    }
    if payload:
        record.update(payload)
    try:
        _DIAG_LOGGER.info(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:
        _log.debug("diag_log serialization failed for event=%s", event)
        pass

def chat_job_path(job_id: str) -> Path:
    return _chat_job_path_impl(job_id, deps=_chat_job_repo_deps())

def load_chat_job(job_id: str) -> Dict[str, Any]:
    return _load_chat_job_impl(job_id, deps=_chat_job_repo_deps())

def write_chat_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _write_chat_job_impl(job_id, updates, deps=_chat_job_repo_deps(), overwrite=overwrite)

def _chat_job_claim_path(job_id: str) -> Path:
    return chat_job_path(job_id) / "claim.lock"

def _inline_backend_factory():
    upload_deps = upload_worker_deps()
    exam_deps = exam_worker_deps()
    profile_deps = profile_update_worker_deps()
    chat_deps = chat_worker_deps()
    return build_inline_backend(
        enqueue_upload_job_fn=lambda job_id: upload_worker_service.enqueue_upload_job_inline(job_id, deps=upload_deps),
        enqueue_exam_job_fn=lambda job_id: exam_worker_service.enqueue_exam_job_inline(job_id, deps=exam_deps),
        enqueue_profile_update_fn=lambda payload: profile_update_worker_service.enqueue_profile_update_inline(
            payload, deps=profile_deps
        ),
        enqueue_chat_job_fn=lambda job_id, lane_id=None: _enqueue_chat_job_impl(
            job_id, deps=chat_deps, lane_id=lane_id
        ),
        scan_pending_upload_jobs_fn=lambda: upload_worker_service.scan_pending_upload_jobs_inline(deps=upload_deps),
        scan_pending_exam_jobs_fn=lambda: exam_worker_service.scan_pending_exam_jobs_inline(deps=exam_deps),
        scan_pending_chat_jobs_fn=lambda: _scan_pending_chat_jobs_impl(deps=chat_deps),
        start_fn=lambda: start_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=PROFILE_UPDATE_ASYNC,
        ),
        stop_fn=lambda: stop_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=PROFILE_UPDATE_ASYNC,
        ),
    )
