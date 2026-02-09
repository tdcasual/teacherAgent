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
from contextlib import contextmanager
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from collections import deque

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
from .assignment_upload_parse_service import AssignmentUploadParseDeps, process_upload_job as _process_upload_job_impl
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
from .assignment_uploaded_question_service import (
    AssignmentUploadedQuestionDeps,
    write_uploaded_questions as _write_uploaded_questions_impl,
)
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
from .skill_auto_router import resolve_effective_skill as _resolve_effective_skill_impl
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
from .exam_score_processing_service import (
    apply_answer_key_to_responses_csv as _apply_answer_key_to_responses_csv_impl,
    build_exam_question_id as _build_exam_question_id_impl,
    build_exam_rows_from_parsed_scores as _build_exam_rows_from_parsed_scores_impl,
    compute_max_scores_from_rows as _compute_max_scores_from_rows_impl,
    ensure_questions_max_score as _ensure_questions_max_score_impl,
    load_exam_answer_key_from_csv as _load_exam_answer_key_from_csv_impl,
    load_exam_max_scores_from_questions_csv as _load_exam_max_scores_from_questions_csv_impl,
    normalize_excel_cell as _normalize_excel_cell_impl,
    normalize_objective_answer as _normalize_objective_answer_impl,
    normalize_student_id_for_exam as _normalize_student_id_for_exam_impl,
    parse_exam_answer_key_text as _parse_exam_answer_key_text_impl,
    parse_exam_question_label as _parse_exam_question_label_impl,
    score_objective_answer as _score_objective_answer_impl,
    write_exam_answers_csv as _write_exam_answers_csv_impl,
    write_exam_questions_csv as _write_exam_questions_csv_impl,
    write_exam_responses_csv as _write_exam_responses_csv_impl,
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
from .exam_upload_parse_service import ExamUploadParseDeps, process_exam_upload_job as _process_exam_upload_job_impl
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
from .teacher_assignment_preflight_service import (
    TeacherAssignmentPreflightDeps,
    teacher_assignment_preflight as _teacher_assignment_preflight_impl,
)
from .teacher_routing_api_service import TeacherRoutingApiDeps, get_routing_api as _get_routing_api_impl
from .tool_dispatch_service import ToolDispatchDeps, tool_dispatch as _tool_dispatch_impl
from .upload_io_service import sanitize_filename_io
from .upload_llm_service import (
    UploadLlmDeps,
    llm_autofill_requirements as _llm_autofill_requirements_impl,
    llm_parse_assignment_payload as _llm_parse_assignment_payload_impl,
    llm_parse_exam_scores as _llm_parse_exam_scores_impl,
    parse_llm_json as _parse_llm_json_impl,
    summarize_questions_for_prompt as _summarize_questions_for_prompt_impl,
    truncate_text as _truncate_text_impl,
    xls_to_table_preview as _xls_to_table_preview_impl,
    xlsx_to_table_preview as _xlsx_to_table_preview_impl,
)
from .upload_text_service import (
    UploadTextDeps,
    clean_ocr_text as _clean_ocr_text_impl,
    ensure_ocr_api_key_aliases as _ensure_ocr_api_key_aliases_impl,
    extract_text_from_file as _extract_text_from_file_impl,
    extract_text_from_image as _extract_text_from_image_impl,
    extract_text_from_pdf as _extract_text_from_pdf_impl,
    load_ocr_utils as _load_ocr_utils_impl,
    parse_timeout_env as _parse_timeout_env_impl,
    save_upload_file as _save_upload_file_impl,
)
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
from .teacher_memory_core import (
    _TEACHER_SESSION_COMPACT_TS,
    _TEACHER_SESSION_COMPACT_LOCK,
    _teacher_compact_key,
    _teacher_compact_allowed,
    _teacher_compact_transcript,
    _teacher_compact_summary,
    _write_teacher_session_records,
    _mark_teacher_session_compacted,
    _teacher_session_summary_text,
    _teacher_memory_context_text,
    _teacher_proposal_path,
    _teacher_memory_load_events,
    _teacher_memory_is_sensitive,
    _teacher_memory_event_log_path,
    _teacher_memory_log_event,
    _teacher_memory_parse_dt,
    _teacher_memory_record_ttl_days,
    _teacher_memory_record_expire_at,
    _teacher_memory_is_expired_record,
    _teacher_memory_age_days,
    _teacher_memory_priority_score,
    _teacher_memory_rank_score,
    _teacher_memory_load_record,
    _teacher_memory_active_applied_records,
    _teacher_memory_recent_user_turns,
    _teacher_memory_loose_match,
    _teacher_memory_auto_infer_candidate,
    _teacher_session_index_item,
    _mark_teacher_session_memory_flush,
    _teacher_memory_has_term,
    _teacher_memory_conflicts,
    _teacher_memory_find_conflicting_applied,
    _teacher_memory_mark_superseded,
    _teacher_memory_norm_text,
    _teacher_memory_stable_hash,
    _teacher_memory_recent_proposals,
    _teacher_memory_auto_quota_reached,
    _teacher_memory_find_duplicate,
    _teacher_session_compaction_cycle_no,
    _teacher_mem0_search,
    _teacher_mem0_should_index_target,
    _teacher_mem0_index_entry,
    _teacher_memory_search_deps,
    _teacher_memory_insights_deps,
    _teacher_memory_apply_deps,
    _teacher_memory_propose_deps,
    _teacher_memory_record_deps,
    _teacher_memory_store_deps,
    _teacher_memory_auto_deps,
    _teacher_context_deps,
    _teacher_session_compaction_deps,
    _teacher_memory_api_deps,
    _teacher_workspace_deps,
    _list_teacher_memory_proposals_api_impl,
    _review_teacher_memory_proposal_api_impl,
)

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
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_chat_wiring_module)
    _importlib.reload(_assignment_wiring_module)
    _importlib.reload(_exam_wiring_module)
    _importlib.reload(_student_wiring_module)
    _importlib.reload(_teacher_wiring_module)
    _importlib.reload(_worker_wiring_module)
    _importlib.reload(_misc_wiring_module)
from .wiring.chat_wiring import *  # noqa: F401,F403
from .wiring.assignment_wiring import *  # noqa: F401,F403
from .wiring.exam_wiring import *  # noqa: F401,F403
from .wiring.student_wiring import *  # noqa: F401,F403
from .wiring.teacher_wiring import *  # noqa: F401,F403
from .wiring.worker_wiring import *  # noqa: F401,F403
from .wiring.misc_wiring import *  # noqa: F401,F403


@contextmanager
def _limit(limiter: Any):
    semas: List[Any]
    if isinstance(limiter, (list, tuple)):
        semas = list(limiter)
    else:
        semas = [limiter]
    acquired: List[Any] = []
    for sema in semas:
        sema.acquire()
        acquired.append(sema)
    try:
        yield
    finally:
        for sema in reversed(acquired):
            sema.release()

def _trim_messages(messages: List[Dict[str, Any]], role_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    if not messages:
        return []
    if role_hint == "student":
        max_messages = CHAT_MAX_MESSAGES_STUDENT
    elif role_hint == "teacher":
        max_messages = CHAT_MAX_MESSAGES_TEACHER
    else:
        max_messages = CHAT_MAX_MESSAGES
    trimmed: List[Dict[str, Any]] = []
    for msg in messages[-max_messages:]:
        role = msg.get("role")
        content = msg.get("content") or ""
        if isinstance(content, str) and len(content) > CHAT_MAX_MESSAGE_CHARS:
            content = content[:CHAT_MAX_MESSAGE_CHARS] + "…"
        trimmed.append({"role": role, "content": content})
    return trimmed


@contextmanager
def _student_inflight(student_id: Optional[str]):
    if not student_id:
        yield True
        return
    allowed = True
    with _STUDENT_INFLIGHT_LOCK:
        cur = _STUDENT_INFLIGHT.get(student_id, 0)
        if cur >= CHAT_STUDENT_INFLIGHT_LIMIT:
            allowed = False
        else:
            _STUDENT_INFLIGHT[student_id] = cur + 1
    try:
        yield allowed
    finally:
        if not allowed:
            return
        with _STUDENT_INFLIGHT_LOCK:
            cur = _STUDENT_INFLIGHT.get(student_id, 0)
            if cur <= 1:
                _STUDENT_INFLIGHT.pop(student_id, None)
            else:
                _STUDENT_INFLIGHT[student_id] = cur - 1

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


def parse_timeout_env(name: str) -> Optional[float]:
    return _parse_timeout_env_impl(name)

def _ensure_ocr_api_key_aliases() -> None:
    _ensure_ocr_api_key_aliases_impl()

def load_ocr_utils():
    return _load_ocr_utils_impl()

def clean_ocr_text(text: str) -> str:
    return _clean_ocr_text_impl(text)

def extract_text_from_pdf(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_pdf_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )

def extract_text_from_file(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_file_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )

def extract_text_from_image(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_image_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )

def truncate_text(text: str, limit: int = 12000) -> str:
    return _truncate_text_impl(text, limit)

def parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    return _parse_llm_json_impl(content)

def llm_parse_assignment_payload(source_text: str, answer_text: str) -> Dict[str, Any]:
    return _llm_parse_assignment_payload_impl(source_text, answer_text, deps=_upload_llm_deps())

def summarize_questions_for_prompt(questions: List[Dict[str, Any]], limit: int = 4000) -> str:
    return _summarize_questions_for_prompt_impl(questions, limit=limit)

def compute_requirements_missing(requirements: Dict[str, Any]) -> List[str]:
    return _compute_requirements_missing_impl(requirements)

def merge_requirements(base: Dict[str, Any], update: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _merge_requirements_impl(base, update, overwrite=overwrite)

def llm_autofill_requirements(
    source_text: str,
    answer_text: str,
    questions: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    missing: List[str],
) -> Tuple[Dict[str, Any], List[str], bool]:
    return _llm_autofill_requirements_impl(
        source_text,
        answer_text,
        questions,
        requirements,
        missing,
        deps=_upload_llm_deps(),
    )

def process_upload_job(job_id: str) -> None:
    _process_upload_job_impl(job_id, deps=_assignment_upload_parse_deps())

def normalize_student_id_for_exam(class_name: str, student_name: str) -> str:
    return _normalize_student_id_for_exam_impl(class_name, student_name)

def normalize_excel_cell(value: Any) -> str:
    return _normalize_excel_cell_impl(value)

def parse_exam_question_label(label: str) -> Optional[Tuple[int, Optional[str], str]]:
    return _parse_exam_question_label_impl(label)

def build_exam_question_id(q_no: int, sub_no: Optional[str]) -> str:
    return _build_exam_question_id_impl(q_no, sub_no)

def xlsx_to_table_preview(path: Path, max_rows: int = 60, max_cols: int = 30) -> str:
    return _xlsx_to_table_preview_impl(path, deps=_upload_llm_deps(), max_rows=max_rows, max_cols=max_cols)

def xls_to_table_preview(path: Path, max_rows: int = 60, max_cols: int = 30) -> str:
    return _xls_to_table_preview_impl(path, deps=_upload_llm_deps(), max_rows=max_rows, max_cols=max_cols)

def llm_parse_exam_scores(table_text: str) -> Dict[str, Any]:
    return _llm_parse_exam_scores_impl(table_text, deps=_upload_llm_deps())

def build_exam_rows_from_parsed_scores(exam_id: str, parsed: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    return _build_exam_rows_from_parsed_scores_impl(exam_id, parsed)

def write_exam_responses_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    _write_exam_responses_csv_impl(path, rows)

def write_exam_questions_csv(path: Path, questions: List[Dict[str, Any]], max_scores: Optional[Dict[str, float]] = None) -> None:
    _write_exam_questions_csv_impl(path, questions, max_scores=max_scores)

def compute_max_scores_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    return _compute_max_scores_from_rows_impl(rows)

def normalize_objective_answer(value: str) -> str:
    return _normalize_objective_answer_impl(value)

def parse_exam_answer_key_text(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    return _parse_exam_answer_key_text_impl(text)

def write_exam_answers_csv(path: Path, answers: List[Dict[str, Any]]) -> None:
    _write_exam_answers_csv_impl(path, answers)

def load_exam_answer_key_from_csv(path: Path) -> Dict[str, str]:
    return _load_exam_answer_key_from_csv_impl(path)

def load_exam_max_scores_from_questions_csv(path: Path) -> Dict[str, float]:
    return _load_exam_max_scores_from_questions_csv_impl(path)

def ensure_questions_max_score(
    questions_csv: Path,
    qids: Iterable[str],
    default_score: float = 1.0,
) -> List[str]:
    return _ensure_questions_max_score_impl(questions_csv, qids, default_score=default_score)

def score_objective_answer(raw_answer: str, correct: str, max_score: float) -> Tuple[float, int]:
    return _score_objective_answer_impl(raw_answer, correct, max_score)

def apply_answer_key_to_responses_csv(
    responses_path: Path,
    answers_csv: Path,
    questions_csv: Path,
    out_path: Path,
) -> Dict[str, Any]:
    return _apply_answer_key_to_responses_csv_impl(responses_path, answers_csv, questions_csv, out_path)

def process_exam_upload_job(job_id: str) -> None:
    _process_exam_upload_job_impl(job_id, deps=_exam_upload_parse_deps())

def write_uploaded_questions(out_dir: Path, assignment_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _write_uploaded_questions_impl(
        out_dir,
        assignment_id,
        questions,
        deps=_assignment_uploaded_question_deps(),
    )
def student_search(query: str, limit: int = 5) -> Dict[str, Any]:
    return _student_search_impl(query, limit, _student_directory_deps())

def student_candidates_by_name(name: str) -> List[Dict[str, str]]:
    return _student_candidates_by_name_impl(name, _student_directory_deps())

def list_all_student_profiles() -> List[Dict[str, str]]:
    return _list_all_student_profiles_impl(_student_directory_deps())

def list_all_student_ids() -> List[str]:
    return _list_all_student_ids_impl(_student_directory_deps())

def list_student_ids_by_class(class_name: str) -> List[str]:
    return _list_student_ids_by_class_impl(class_name, _student_directory_deps())

def compute_expected_students(scope: str, class_name: str, student_ids: List[str]) -> List[str]:
    scope_val = resolve_scope(scope, student_ids, class_name)
    if scope_val == "student":
        return sorted(list(dict.fromkeys([s for s in student_ids if s])))
    if scope_val == "class":
        return list_student_ids_by_class(class_name)
    return list_all_student_ids()

def list_exams() -> Dict[str, Any]:
    return _list_exams_impl(deps=_exam_catalog_deps())

def exam_get(exam_id: str) -> Dict[str, Any]:
    return _exam_get_impl(exam_id, _exam_overview_deps())

def exam_analysis_get(exam_id: str) -> Dict[str, Any]:
    return _exam_analysis_get_impl(exam_id, _exam_overview_deps())

def exam_students_list(exam_id: str, limit: int = 50) -> Dict[str, Any]:
    return _exam_students_list_impl(exam_id, limit, _exam_overview_deps())

def exam_student_detail(exam_id: str, student_id: Optional[str] = None, student_name: Optional[str] = None, class_name: Optional[str] = None) -> Dict[str, Any]:
    return _exam_student_detail_impl(
        exam_id,
        deps=_exam_detail_deps(),
        student_id=student_id,
        student_name=student_name,
        class_name=class_name,
    )

def exam_question_detail(
    exam_id: str,
    question_id: Optional[str] = None,
    question_no: Optional[str] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    return _exam_question_detail_impl(
        exam_id,
        deps=_exam_detail_deps(),
        question_id=question_id,
        question_no=question_no,
        top_n=top_n,
    )

def exam_range_top_students(
    exam_id: str,
    start_question_no: Any,
    end_question_no: Any,
    top_n: int = 10,
) -> Dict[str, Any]:
    return _exam_range_top_students_impl(
        exam_id,
        start_question_no,
        end_question_no,
        top_n=top_n,
        deps=_exam_range_deps(),
    )

def exam_range_summary_batch(exam_id: str, ranges: Any, top_n: int = 5) -> Dict[str, Any]:
    return _exam_range_summary_batch_impl(
        exam_id,
        ranges,
        top_n=top_n,
        deps=_exam_range_deps(),
    )

def exam_question_batch_detail(exam_id: str, question_nos: Any, top_n: int = 5) -> Dict[str, Any]:
    return _exam_question_batch_detail_impl(
        exam_id,
        question_nos,
        top_n=top_n,
        deps=_exam_range_deps(),
    )


def exam_analysis_charts_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    return _exam_analysis_charts_generate_impl(args, deps=_exam_analysis_charts_deps())

def list_assignments() -> Dict[str, Any]:
    return _list_assignments_impl(deps=_assignment_catalog_deps())

def parse_list_value(value: Any) -> List[str]:
    return _parse_list_value_impl(value)

def normalize_preferences(values: List[str]) -> Tuple[List[str], List[str]]:
    return _normalize_preferences_impl(values)

def normalize_class_level(value: str) -> Optional[str]:
    return _normalize_class_level_impl(value)

def parse_duration(value: Any) -> Optional[int]:
    return _parse_duration_impl(value)

def normalize_difficulty(value: Any) -> str:
    return _normalize_difficulty_impl(value)

def validate_requirements(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    return _validate_requirements_impl(payload)

def save_assignment_requirements(
    assignment_id: str,
    requirements: Dict[str, Any],
    date_str: str,
    created_by: str = "teacher",
    validate: bool = True,
) -> Dict[str, Any]:
    return _save_assignment_requirements_impl(
        assignment_id,
        requirements,
        date_str,
        deps=_assignment_requirements_deps(),
        created_by=created_by,
        validate=validate,
    )

def ensure_requirements_for_assignment(
    assignment_id: str,
    date_str: str,
    requirements: Optional[Dict[str, Any]],
    source: str,
) -> Optional[Dict[str, Any]]:
    return _ensure_requirements_for_assignment_impl(
        assignment_id,
        date_str,
        requirements,
        source,
        deps=_assignment_requirements_deps(),
    )

def format_requirements_prompt(errors: Optional[List[str]] = None, include_assignment_id: bool = False) -> str:
    return _format_requirements_prompt_impl(errors, include_assignment_id=include_assignment_id)

def parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    return _parse_json_from_text_impl(text)

def llm_assignment_gate(req: ChatRequest) -> Optional[Dict[str, Any]]:
    return _llm_assignment_gate_impl(req, deps=_assignment_llm_gate_deps())

def normalize_numbered_block(text: str) -> str:
    return _normalize_numbered_block_impl(text)

def extract_numbered_item(text: str, idx: int) -> Optional[str]:
    return _extract_numbered_item_impl(text, idx)

def parse_subject_topic(text: str) -> Tuple[str, str]:
    return _parse_subject_topic_impl(text)

def parse_grade_and_level(text: str) -> Tuple[str, str]:
    return _parse_grade_and_level_impl(text)

def extract_requirements_from_text(text: str) -> Dict[str, Any]:
    return _extract_requirements_from_text_impl(text)

def detect_assignment_intent(text: str) -> bool:
    return _detect_assignment_intent_impl(text)

def extract_assignment_id(text: str) -> Optional[str]:
    return _extract_assignment_id_impl(text)

def extract_date(text: str) -> Optional[str]:
    return _extract_date_impl(text)

def extract_kp_list(text: str) -> List[str]:
    return _extract_kp_list_impl(text)

def extract_question_ids(text: str) -> List[str]:
    return _extract_question_ids_impl(text)

def extract_per_kp(text: str) -> Optional[int]:
    return _extract_per_kp_impl(text)

def teacher_assignment_preflight(req: ChatRequest) -> Optional[str]:
    return _teacher_assignment_preflight_impl(req, deps=_teacher_assignment_preflight_deps())

def resolve_assignment_date(meta: Dict[str, Any], folder: Path) -> Optional[str]:
    return _resolve_assignment_date_impl(meta, folder)

def assignment_specificity(meta: Dict[str, Any], student_id: Optional[str], class_name: Optional[str]) -> int:
    return _assignment_specificity_impl(meta, student_id, class_name)

def parse_iso_timestamp(value: Optional[str]) -> float:
    return _parse_iso_timestamp_impl(value)

def find_assignment_for_date(
    date_str: str,
    student_id: Optional[str] = None,
    class_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return _find_assignment_for_date_impl(
        date_str=date_str,
        student_id=student_id,
        class_name=class_name,
        deps=_assignment_catalog_deps(),
    )

def read_text_safe(path: Path, limit: int = 4000) -> str:
    return _read_text_safe_impl(path, limit=limit)

def build_assignment_detail(folder: Path, include_text: bool = True) -> Dict[str, Any]:
    return _build_assignment_detail_impl(
        folder=folder,
        include_text=include_text,
        deps=_assignment_catalog_deps(),
    )

def postprocess_assignment_meta(
    assignment_id: str,
    *,
    due_at: Optional[str] = None,
    expected_students: Optional[List[str]] = None,
    completion_policy: Optional[Dict[str, Any]] = None,
) -> None:
    return _postprocess_assignment_meta_impl(
        assignment_id=assignment_id,
        due_at=due_at,
        expected_students=expected_students,
        completion_policy=completion_policy,
        deps=_assignment_meta_postprocess_deps(),
    )

def _session_discussion_pass(student_id: str, assignment_id: str) -> Dict[str, Any]:
    return _session_discussion_pass_impl(
        student_id,
        assignment_id,
        deps=SessionDiscussionDeps(
            marker=DISCUSSION_COMPLETE_MARKER,
            load_student_sessions_index=load_student_sessions_index,
            student_session_file=student_session_file,
        ),
    )

def _counted_grade_item(item: Dict[str, Any]) -> bool:
    return _counted_grade_item_impl(item, deps=_assignment_submission_attempt_deps())

def _compute_submission_attempt(attempt_dir: Path) -> Optional[Dict[str, Any]]:
    return _compute_submission_attempt_impl(attempt_dir, deps=_assignment_submission_attempt_deps())

def _list_submission_attempts(assignment_id: str, student_id: str) -> List[Dict[str, Any]]:
    return _list_submission_attempts_impl(assignment_id, student_id, deps=_assignment_submission_attempt_deps())

def _best_submission_attempt(attempts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return _best_submission_attempt_impl(attempts)

def compute_assignment_progress(assignment_id: str, include_students: bool = True) -> Dict[str, Any]:
    return _compute_assignment_progress_impl(
        assignment_id,
        deps=_assignment_progress_deps(),
        include_students=include_students,
    )

def build_assignment_context(detail: Optional[Dict[str, Any]], study_mode: bool = False) -> Optional[str]:
    return _build_assignment_context_impl(
        detail,
        study_mode=study_mode,
        discussion_complete_marker=DISCUSSION_COMPLETE_MARKER,
    )

def build_verified_student_context(student_id: str, profile: Optional[Dict[str, Any]] = None) -> str:
    return _build_verified_student_context_impl(student_id, profile=profile)

def detect_student_study_trigger(text: str) -> bool:
    return _detect_student_study_trigger_impl(text)

def build_interaction_note(last_user: str, reply: str, assignment_id: Optional[str] = None) -> str:
    return _build_interaction_note_impl(last_user, reply, assignment_id=assignment_id)

def detect_math_delimiters(text: str) -> bool:
    return _detect_math_delimiters_impl(text)

def detect_latex_tokens(text: str) -> bool:
    return _detect_latex_tokens_impl(text)

def normalize_math_delimiters(text: str) -> str:
    return _normalize_math_delimiters_impl(text)

def list_lessons() -> Dict[str, Any]:
    return _list_lessons_impl(deps=_content_catalog_deps())

def list_skills() -> Dict[str, Any]:
    return _list_skills_impl(deps=_content_catalog_deps())

def _ensure_teacher_routing_file(actor: str) -> Path:
    return _ensure_teacher_routing_file_impl(actor, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_get(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_get_impl(args, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_simulate(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_simulate_impl(args, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_propose(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_propose_impl(args, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_apply(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_apply_impl(args, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_rollback(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_rollback_impl(args, deps=_teacher_llm_routing_deps())

def teacher_llm_routing_proposal_get(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_llm_routing_proposal_get_impl(args, deps=_teacher_llm_routing_deps())

def teacher_provider_registry_get(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_provider_registry_get_impl(args, deps=_teacher_provider_registry_deps())

def teacher_provider_registry_create(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_provider_registry_create_impl(args, deps=_teacher_provider_registry_deps())

def teacher_provider_registry_update(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_provider_registry_update_impl(args, deps=_teacher_provider_registry_deps())

def teacher_provider_registry_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_provider_registry_delete_impl(args, deps=_teacher_provider_registry_deps())

def teacher_provider_registry_probe_models(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_provider_registry_probe_models_impl(args, deps=_teacher_provider_registry_deps())

def resolve_responses_file(exam_id: Optional[str], file_path: Optional[str]) -> Optional[Path]:
    return _resolve_responses_file_impl(exam_id, file_path, deps=_student_import_deps())

def import_students_from_responses(path: Path, mode: str = "merge") -> Dict[str, Any]:
    return _import_students_from_responses_impl(path, deps=_student_import_deps(), mode=mode)

def student_import(args: Dict[str, Any]) -> Dict[str, Any]:
    return _student_import_impl(args, deps=_student_import_deps())

def assignment_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    return _assignment_generate_tool_impl(args, deps=_assignment_generate_tool_deps())

def assignment_render(args: Dict[str, Any]) -> Dict[str, Any]:
    from .assignment_generate_tool_service import assignment_render as _assignment_render_impl
    return _assignment_render_impl(args, deps=_assignment_generate_tool_deps())

def chart_exec(args: Dict[str, Any]) -> Dict[str, Any]:
    return _chart_exec_api_impl(args, deps=_chart_api_deps())

def chart_agent_run(args: Dict[str, Any]) -> Dict[str, Any]:
    return _chart_agent_run_impl(args, deps=_chart_agent_run_deps())


def lesson_capture(args: Dict[str, Any]) -> Dict[str, Any]:
    return _lesson_capture_impl(args, deps=_lesson_core_tool_deps())

def core_example_search(args: Dict[str, Any]) -> Dict[str, Any]:
    return _core_example_search_impl(args, deps=_core_example_tool_deps())

def core_example_register(args: Dict[str, Any]) -> Dict[str, Any]:
    return _core_example_register_impl(args, deps=_core_example_tool_deps())

def core_example_render(args: Dict[str, Any]) -> Dict[str, Any]:
    return _core_example_render_impl(args, deps=_core_example_tool_deps())

def tool_dispatch(name: str, args: Dict[str, Any], role: Optional[str] = None) -> Dict[str, Any]:
    return _tool_dispatch_impl(name, args, role, deps=_tool_dispatch_deps())

def call_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    role_hint: Optional[str] = None,
    max_tokens: Optional[int] = None,
    skill_id: Optional[str] = None,
    kind: Optional[str] = None,
    teacher_id: Optional[str] = None,
    skill_runtime: Optional[Any] = None,
) -> Dict[str, Any]:
    return _call_llm_runtime_impl(
        messages,
        deps=_chat_runtime_deps(),
        tools=tools,
        role_hint=role_hint,
        max_tokens=max_tokens,
        skill_id=skill_id,
        kind=kind,
        teacher_id=teacher_id,
        skill_runtime=skill_runtime,
    )

def parse_tool_json(content: str) -> Optional[Dict[str, Any]]:
    return _parse_tool_json_impl(content)

def build_system_prompt(role_hint: Optional[str]) -> str:
    return _build_system_prompt_impl(role_hint, deps=_chat_support_deps())

def allowed_tools(role_hint: Optional[str]) -> set:
    return _allowed_tools_impl(role_hint)

def extract_min_chars_requirement(text: str) -> Optional[int]:
    return _extract_min_chars_requirement_impl(text)

def extract_exam_id(text: str) -> Optional[str]:
    return _extract_exam_id_impl(text)

def is_exam_analysis_request(text: str) -> bool:
    return _is_exam_analysis_request_impl(text)

def summarize_exam_students(exam_id: str, max_total: Optional[float]) -> Dict[str, Any]:
    return _summarize_exam_students_impl(exam_id, max_total, deps=_exam_longform_deps())

def load_kp_catalog() -> Dict[str, Dict[str, str]]:
    from .content_catalog_service import load_kp_catalog as _load_kp_catalog_impl
    return _load_kp_catalog_impl(DATA_DIR)

def load_question_kp_map() -> Dict[str, str]:
    from .content_catalog_service import load_question_kp_map as _load_question_kp_map_impl
    return _load_question_kp_map_impl(DATA_DIR)

def build_exam_longform_context(exam_id: str) -> Dict[str, Any]:
    return _build_exam_longform_context_impl(exam_id, deps=_exam_longform_deps())

def _calc_longform_max_tokens(min_chars: int) -> int:
    return _calc_longform_max_tokens_impl(min_chars)

def _generate_longform_reply(
    convo: List[Dict[str, Any]],
    min_chars: int,
    role_hint: Optional[str],
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    skill_runtime: Optional[Any] = None,
) -> str:
    return _generate_longform_reply_impl(
        convo,
        min_chars,
        role_hint,
        skill_id,
        teacher_id,
        skill_runtime,
        deps=_exam_longform_deps(),
    )

def run_agent(
    messages: List[Dict[str, Any]],
    role_hint: Optional[str],
    extra_system: Optional[str] = None,
    agent_id: Optional[str] = None,
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
) -> Dict[str, Any]:
    return _run_agent_runtime_impl(
        messages,
        role_hint,
        deps=_agent_runtime_deps(),
        extra_system=extra_system,
        agent_id=agent_id,
        skill_id=skill_id,
        teacher_id=teacher_id,
    )

def _detect_role_hint(req: ChatRequest) -> Optional[str]:
    return _detect_role_hint_impl(req, detect_role=detect_role)

def _compute_chat_reply_sync(
    req: ChatRequest,
    session_id: str = "main",
    teacher_id_override: Optional[str] = None,
) -> Tuple[str, Optional[str], str]:
    return _compute_chat_reply_sync_impl(
        req,
        deps=_compute_chat_reply_deps(),
        session_id=session_id,
        teacher_id_override=teacher_id_override,
    )

def resolve_student_session_id(student_id: str, assignment_id: Optional[str], assignment_date: Optional[str]) -> str:
    return _resolve_student_session_id_impl(
        student_id,
        assignment_id,
        assignment_date,
        parse_date_str=parse_date_str,
    )

def process_chat_job(job_id: str) -> None:
    _process_chat_job_impl(job_id, deps=_chat_job_process_deps())
def _chat_start_orchestration(req: ChatStartRequest) -> Dict[str, Any]:
    return _start_chat_orchestration_impl(req, deps=_chat_start_deps())


