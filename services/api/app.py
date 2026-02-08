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
from contextlib import asynccontextmanager, contextmanager
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
    AssignmentGenerateError,
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
from .chat_worker_service import (
    ChatWorkerDeps,
    chat_job_worker_loop as _chat_job_worker_loop_impl,
    enqueue_chat_job as _enqueue_chat_job_impl,
    scan_pending_chat_jobs as _scan_pending_chat_jobs_impl,
    start_chat_worker as _start_chat_worker_impl,
    stop_chat_worker as _stop_chat_worker_impl,
)
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
from .teacher_memory_api_service import (
    TeacherMemoryApiDeps,
    list_proposals_api as _list_teacher_memory_proposals_api_impl,
    review_proposal_api as _review_teacher_memory_proposal_api_impl,
)
from .teacher_memory_auto_service import (
    TeacherMemoryAutoDeps,
    teacher_memory_auto_flush_from_session as _teacher_memory_auto_flush_from_session_impl,
    teacher_memory_auto_propose_from_turn as _teacher_memory_auto_propose_from_turn_impl,
)
from .teacher_memory_apply_service import (
    TeacherMemoryApplyDeps,
    teacher_memory_apply as _teacher_memory_apply_impl,
)
from .teacher_memory_insights_service import (
    TeacherMemoryInsightsDeps,
    teacher_memory_insights as _teacher_memory_insights_impl,
)
from .teacher_memory_record_service import (
    TeacherMemoryRecordDeps,
    mark_teacher_session_memory_flush as _mark_teacher_session_memory_flush_impl,
    teacher_memory_auto_infer_candidate as _teacher_memory_auto_infer_candidate_impl,
    teacher_memory_auto_quota_reached as _teacher_memory_auto_quota_reached_impl,
    teacher_memory_find_conflicting_applied as _teacher_memory_find_conflicting_applied_impl,
    teacher_memory_find_duplicate as _teacher_memory_find_duplicate_impl,
    teacher_memory_mark_superseded as _teacher_memory_mark_superseded_impl,
    teacher_memory_recent_proposals as _teacher_memory_recent_proposals_impl,
    teacher_memory_recent_user_turns as _teacher_memory_recent_user_turns_impl,
    teacher_session_compaction_cycle_no as _teacher_session_compaction_cycle_no_impl,
    teacher_session_index_item as _teacher_session_index_item_impl,
)
from .teacher_memory_rules_service import (
    teacher_memory_age_days as _teacher_memory_age_days_impl,
    teacher_memory_conflicts as _teacher_memory_conflicts_impl,
    teacher_memory_has_term as _teacher_memory_has_term_impl,
    teacher_memory_is_expired_record as _teacher_memory_is_expired_record_impl,
    teacher_memory_is_sensitive as _teacher_memory_is_sensitive_impl,
    teacher_memory_loose_match as _teacher_memory_loose_match_impl,
    teacher_memory_norm_text as _teacher_memory_norm_text_impl,
    teacher_memory_parse_dt as _teacher_memory_parse_dt_impl,
    teacher_memory_priority_score as _teacher_memory_priority_score_impl,
    teacher_memory_rank_score as _teacher_memory_rank_score_impl,
    teacher_memory_record_expire_at as _teacher_memory_record_expire_at_impl,
    teacher_memory_record_ttl_days as _teacher_memory_record_ttl_days_impl,
    teacher_memory_stable_hash as _teacher_memory_stable_hash_impl,
)
from .teacher_memory_propose_service import (
    TeacherMemoryProposeDeps,
    teacher_memory_propose as _teacher_memory_propose_impl,
)
from .teacher_memory_search_service import (
    TeacherMemorySearchDeps,
    teacher_memory_search as _teacher_memory_search_impl,
)
from .teacher_memory_store_service import (
    TeacherMemoryStoreDeps,
    teacher_memory_active_applied_records as _teacher_memory_active_applied_records_impl,
    teacher_memory_event_log_path as _teacher_memory_event_log_path_impl,
    teacher_memory_load_events as _teacher_memory_load_events_impl,
    teacher_memory_load_record as _teacher_memory_load_record_impl,
    teacher_memory_log_event as _teacher_memory_log_event_impl,
)
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
    validate_master_key_policy as _validate_master_key_policy_impl,
)
from .teacher_context_service import TeacherContextDeps, build_teacher_context as _build_teacher_context_impl
from .teacher_assignment_preflight_service import (
    TeacherAssignmentPreflightDeps,
    teacher_assignment_preflight as _teacher_assignment_preflight_impl,
)
from .teacher_session_compaction_service import (
    TeacherSessionCompactionDeps,
    maybe_compact_teacher_session as _maybe_compact_teacher_session_impl,
)
from .teacher_routing_api_service import TeacherRoutingApiDeps, get_routing_api as _get_routing_api_impl
from .teacher_workspace_service import (
    TeacherWorkspaceDeps,
    ensure_teacher_workspace as _ensure_teacher_workspace_impl,
    teacher_read_text as _teacher_read_text_impl,
)
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
from . import settings as _settings
from .app_routes import register_routes
from .queue_backend import get_queue_backend, rq_enabled as _rq_enabled_impl
from .queue_backend_inline import InlineQueueBackend
try:
    from mem0_config import load_dotenv

    load_dotenv()
except Exception:
    pass

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", APP_ROOT / "uploads"))
LLM_ROUTING_PATH = Path(os.getenv("LLM_ROUTING_PATH", DATA_DIR / "llm_routing.json"))
TENANT_ID = _settings.tenant_id()
JOB_QUEUE_BACKEND = _settings.job_queue_backend()
RQ_BACKEND_ENABLED = _settings.rq_backend_enabled()
REDIS_URL = _settings.redis_url()
RQ_QUEUE_NAME = _settings.rq_queue_name()

def _rq_enabled() -> bool:
    return _rq_enabled_impl()

OCR_UTILS_DIR = APP_ROOT / "skills" / "physics-lesson-capture" / "scripts"
if OCR_UTILS_DIR.exists() and str(OCR_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(OCR_UTILS_DIR))

DIAG_LOG_ENABLED = os.getenv("DIAG_LOG", "").lower() in {"1", "true", "yes", "on"}
DIAG_LOG_PATH = Path(os.getenv("DIAG_LOG_PATH", APP_ROOT / "tmp" / "diagnostics.log"))
UPLOAD_JOB_DIR = UPLOADS_DIR / "assignment_jobs"
UPLOAD_JOB_QUEUE: deque[str] = deque()
UPLOAD_JOB_LOCK = threading.Lock()
UPLOAD_JOB_EVENT = threading.Event()
UPLOAD_JOB_WORKER_STARTED = False
UPLOAD_JOB_STOP_EVENT = threading.Event()
UPLOAD_JOB_WORKER_THREAD: Optional[threading.Thread] = None

EXAM_UPLOAD_JOB_DIR = UPLOADS_DIR / "exam_jobs"
EXAM_JOB_QUEUE: deque[str] = deque()
EXAM_JOB_LOCK = threading.Lock()
EXAM_JOB_EVENT = threading.Event()
EXAM_JOB_WORKER_STARTED = False
EXAM_JOB_STOP_EVENT = threading.Event()
EXAM_JOB_WORKER_THREAD: Optional[threading.Thread] = None
CHAT_JOB_DIR = UPLOADS_DIR / "chat_jobs"
CHAT_JOB_LOCK = threading.Lock()
CHAT_JOB_EVENT = threading.Event()
CHAT_JOB_WORKER_STARTED = False
CHAT_WORKER_STOP_EVENT = threading.Event()
CHAT_WORKER_POOL_SIZE = max(1, int(os.getenv("CHAT_WORKER_POOL_SIZE", "4") or "4"))
CHAT_LANE_MAX_QUEUE = max(1, int(os.getenv("CHAT_LANE_MAX_QUEUE", "6") or "6"))
CHAT_LANE_DEBOUNCE_MS = max(0, int(os.getenv("CHAT_LANE_DEBOUNCE_MS", "500") or "500"))
CHAT_JOB_CLAIM_TTL_SEC = max(10, int(os.getenv("CHAT_JOB_CLAIM_TTL_SEC", "600") or "600"))
CHAT_JOB_LANES: Dict[str, deque[str]] = {}
CHAT_JOB_ACTIVE_LANES: set[str] = set()
CHAT_JOB_QUEUED: set[str] = set()
CHAT_JOB_TO_LANE: Dict[str, str] = {}
CHAT_LANE_CURSOR = 0
CHAT_WORKER_THREADS: List[threading.Thread] = []
CHAT_LANE_RECENT: Dict[str, Tuple[float, str, str]] = {}
CHAT_IDEMPOTENCY_STATE = create_chat_idempotency_store(CHAT_JOB_DIR)
_CHAT_LANE_STORES: Dict[str, Any] = {}
_QUEUE_BACKEND: Any = None
STUDENT_SESSIONS_DIR = DATA_DIR / "student_chat_sessions"
TEACHER_WORKSPACES_DIR = DATA_DIR / "teacher_workspaces"
TEACHER_SESSIONS_DIR = DATA_DIR / "teacher_chat_sessions"
STUDENT_SUBMISSIONS_DIR = DATA_DIR / "student_submissions"
SESSION_INDEX_MAX_ITEMS = max(50, int(os.getenv("SESSION_INDEX_MAX_ITEMS", "500") or "500"))
TEACHER_SESSION_COMPACT_ENABLED = os.getenv("TEACHER_SESSION_COMPACT_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_SESSION_COMPACT_MAIN_ONLY = os.getenv("TEACHER_SESSION_COMPACT_MAIN_ONLY", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_SESSION_COMPACT_MAX_MESSAGES = max(4, int(os.getenv("TEACHER_SESSION_COMPACT_MAX_MESSAGES", "160") or "160"))
TEACHER_SESSION_COMPACT_KEEP_TAIL = max(1, int(os.getenv("TEACHER_SESSION_COMPACT_KEEP_TAIL", "40") or "40"))
if TEACHER_SESSION_COMPACT_KEEP_TAIL >= TEACHER_SESSION_COMPACT_MAX_MESSAGES:
    TEACHER_SESSION_COMPACT_KEEP_TAIL = max(1, TEACHER_SESSION_COMPACT_MAX_MESSAGES // 2)
TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC = max(0, int(os.getenv("TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", "60") or "60"))
TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS = max(2000, int(os.getenv("TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS", "12000") or "12000"))
_TEACHER_SESSION_COMPACT_TS: Dict[str, float] = {}
_TEACHER_SESSION_COMPACT_LOCK = threading.Lock()
_SESSION_INDEX_LOCKS: Dict[str, threading.RLock] = {}
_SESSION_INDEX_LOCKS_LOCK = threading.Lock()
TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY = os.getenv("TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS = max(0, int(os.getenv("TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS", "1500") or "1500"))
TEACHER_MEMORY_AUTO_ENABLED = os.getenv("TEACHER_MEMORY_AUTO_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS = max(6, int(os.getenv("TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS", "12") or "12"))
TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY = max(1, int(os.getenv("TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY", "8") or "8"))
TEACHER_MEMORY_FLUSH_ENABLED = os.getenv("TEACHER_MEMORY_FLUSH_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES = max(1, int(os.getenv("TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES", "24") or "24"))
TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS = max(500, int(os.getenv("TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS", "2400") or "2400"))
TEACHER_MEMORY_AUTO_APPLY_ENABLED = os.getenv("TEACHER_MEMORY_AUTO_APPLY_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
_TEACHER_MEMORY_AUTO_APPLY_TARGETS_RAW = str(os.getenv("TEACHER_MEMORY_AUTO_APPLY_TARGETS", "DAILY,MEMORY") or "DAILY,MEMORY")
TEACHER_MEMORY_AUTO_APPLY_TARGETS = {
    p.strip().upper()
    for p in _TEACHER_MEMORY_AUTO_APPLY_TARGETS_RAW.split(",")
    if str(p or "").strip()
}
if not TEACHER_MEMORY_AUTO_APPLY_TARGETS:
    TEACHER_MEMORY_AUTO_APPLY_TARGETS = {"DAILY", "MEMORY"}
TEACHER_MEMORY_AUTO_APPLY_STRICT = os.getenv("TEACHER_MEMORY_AUTO_APPLY_STRICT", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_MEMORY_AUTO_INFER_ENABLED = os.getenv("TEACHER_MEMORY_AUTO_INFER_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS = max(2, int(os.getenv("TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS", "2") or "2"))
TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS = max(
    4,
    min(80, int(os.getenv("TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS", "24") or "24")),
)
TEACHER_MEMORY_AUTO_INFER_MIN_CHARS = max(8, int(os.getenv("TEACHER_MEMORY_AUTO_INFER_MIN_CHARS", "16") or "16"))
TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY = max(
    0,
    min(100, int(os.getenv("TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY", "58") or "58")),
)
TEACHER_MEMORY_DECAY_ENABLED = os.getenv("TEACHER_MEMORY_DECAY_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
TEACHER_MEMORY_TTL_DAYS_MEMORY = max(0, int(os.getenv("TEACHER_MEMORY_TTL_DAYS_MEMORY", "180") or "180"))
TEACHER_MEMORY_TTL_DAYS_DAILY = max(0, int(os.getenv("TEACHER_MEMORY_TTL_DAYS_DAILY", "14") or "14"))
TEACHER_MEMORY_CONTEXT_MAX_ENTRIES = max(4, int(os.getenv("TEACHER_MEMORY_CONTEXT_MAX_ENTRIES", "18") or "18"))
TEACHER_MEMORY_SEARCH_FILTER_EXPIRED = os.getenv("TEACHER_MEMORY_SEARCH_FILTER_EXPIRED", "1").lower() in {"1", "true", "yes", "on"}
DISCUSSION_COMPLETE_MARKER = os.getenv("DISCUSSION_COMPLETE_MARKER", "【个性化作业】")
GRADE_COUNT_CONF_THRESHOLD = float(os.getenv("GRADE_COUNT_CONF_THRESHOLD", "0.6") or "0.6")
OCR_MAX_CONCURRENCY = max(1, int(os.getenv("OCR_MAX_CONCURRENCY", "4") or "4"))
LLM_MAX_CONCURRENCY = max(1, int(os.getenv("LLM_MAX_CONCURRENCY", "8") or "8"))
LLM_MAX_CONCURRENCY_STUDENT = max(1, int(os.getenv("LLM_MAX_CONCURRENCY_STUDENT", str(LLM_MAX_CONCURRENCY)) or str(LLM_MAX_CONCURRENCY)))
LLM_MAX_CONCURRENCY_TEACHER = max(1, int(os.getenv("LLM_MAX_CONCURRENCY_TEACHER", str(LLM_MAX_CONCURRENCY)) or str(LLM_MAX_CONCURRENCY)))
_OCR_SEMAPHORE = threading.BoundedSemaphore(OCR_MAX_CONCURRENCY)
_LLM_SEMAPHORE = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)
_LLM_SEMAPHORE_STUDENT = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY_STUDENT)
_LLM_SEMAPHORE_TEACHER = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY_TEACHER)

CHAT_MAX_MESSAGES = max(4, int(os.getenv("CHAT_MAX_MESSAGES", "14") or "14"))
CHAT_MAX_MESSAGES_STUDENT = max(4, int(os.getenv("CHAT_MAX_MESSAGES_STUDENT", str(max(CHAT_MAX_MESSAGES, 40))) or str(max(CHAT_MAX_MESSAGES, 40))))
CHAT_MAX_MESSAGES_TEACHER = max(4, int(os.getenv("CHAT_MAX_MESSAGES_TEACHER", str(max(CHAT_MAX_MESSAGES, 40))) or str(max(CHAT_MAX_MESSAGES, 40))))
CHAT_MAX_MESSAGE_CHARS = max(256, int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "2000") or "2000"))
CHAT_EXTRA_SYSTEM_MAX_CHARS = max(512, int(os.getenv("CHAT_EXTRA_SYSTEM_MAX_CHARS", "6000") or "6000"))
CHAT_MAX_TOOL_ROUNDS = max(1, int(os.getenv("CHAT_MAX_TOOL_ROUNDS", "5") or "5"))
CHAT_MAX_TOOL_CALLS = max(1, int(os.getenv("CHAT_MAX_TOOL_CALLS", "12") or "12"))
CHAT_STUDENT_INFLIGHT_LIMIT = max(1, int(os.getenv("CHAT_STUDENT_INFLIGHT_LIMIT", "1") or "1"))
_STUDENT_INFLIGHT: Dict[str, int] = {}
_STUDENT_INFLIGHT_LOCK = threading.Lock()

PROFILE_CACHE_TTL_SEC = max(0, int(os.getenv("PROFILE_CACHE_TTL_SEC", "10") or "10"))
ASSIGNMENT_DETAIL_CACHE_TTL_SEC = max(0, int(os.getenv("ASSIGNMENT_DETAIL_CACHE_TTL_SEC", "10") or "10"))
_PROFILE_CACHE: Dict[str, Tuple[float, float, Dict[str, Any]]] = {}
_PROFILE_CACHE_LOCK = threading.Lock()
_ASSIGNMENT_DETAIL_CACHE: Dict[Tuple[str, bool], Tuple[float, Tuple[float, float, float], Dict[str, Any]]] = {}
_ASSIGNMENT_DETAIL_CACHE_LOCK = threading.Lock()

PROFILE_UPDATE_ASYNC = os.getenv("PROFILE_UPDATE_ASYNC", "1").lower() in {"1", "true", "yes", "on"}
PROFILE_UPDATE_QUEUE_MAX = max(10, int(os.getenv("PROFILE_UPDATE_QUEUE_MAX", "500") or "500"))
_PROFILE_UPDATE_QUEUE: deque[Dict[str, Any]] = deque()
_PROFILE_UPDATE_LOCK = threading.Lock()
_PROFILE_UPDATE_EVENT = threading.Event()
_PROFILE_UPDATE_WORKER_STARTED = False
_PROFILE_UPDATE_STOP_EVENT = threading.Event()
_PROFILE_UPDATE_WORKER_THREAD: Optional[threading.Thread] = None

_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:请|帮我)?记住",
        r"以后(?:都|默认|统一|请)",
        r"默认(?:按|用|采用|是)",
        r"长期(?:按|使用|采用)",
        r"固定(?:格式|风格|模板|流程|做法)",
        r"偏好(?:是|为|改为)",
        r"今后(?:都|统一|默认)",
    )
]
_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"今天",
        r"本周",
        r"这次",
        r"临时",
        r"暂时",
        r"先按",
    )
]
_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:输出|回复|讲解|批改|反馈|总结)",
        r"(?:格式|结构|风格|模板|语气)",
        r"(?:结论|行动项|先.+再.+|条目|分点|markdown)",
        r"(?:难度|题量|时长|作业要求)",
    )
]
_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:这道题|这题|本题|这个题)",
        r"(?:这次|本次|今天|临时|暂时)",
        r"(?:帮我解|请解答|算一下)",
    )
]

_TEACHER_MEMORY_SENSITIVE_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"sk-[A-Za-z0-9]{16,}",
        r"AIza[0-9A-Za-z\\-_]{20,}",
        r"AKIA[0-9A-Z]{12,}",
        r"(?:api|access|secret|refresh)[-_ ]?(?:key|token)\s*[:=]\s*\S{6,}",
        r"password\s*[:=]\s*\S{4,}",
    )
]
_TEACHER_MEMORY_CONFLICT_GROUPS: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
    (("简洁", "精简", "简短"), ("详细", "展开", "长文")),
    (("中文", "汉语"), ("英文", "英语", "english")),
    (("先结论", "先总结"), ("先过程", "先推导", "先分析")),
    (("条目", "要点", "bullet"), ("段落", "叙述")),
]


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

def upload_job_path(job_id: str) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    return UPLOAD_JOB_DIR / safe

def load_upload_job(job_id: str) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))

def write_upload_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(updates)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(job_path, data)
    return data

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use unique temp names so concurrent writers don't contend on one *.tmp file.
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

def safe_fs_id(value: str, prefix: str = "id") -> str:
    raw = str(value or "").strip()
    slug = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if len(slug) < 6:
        digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10] if raw else uuid.uuid4().hex[:10]
        slug = f"{prefix}_{digest}"
    return slug

def _enqueue_upload_job_inline(job_id: str) -> None:
    with UPLOAD_JOB_LOCK:
        if job_id not in UPLOAD_JOB_QUEUE:
            UPLOAD_JOB_QUEUE.append(job_id)
    UPLOAD_JOB_EVENT.set()

def scan_pending_upload_jobs() -> int:
    return int(_queue_backend().scan_pending_upload_jobs() or 0)

def _scan_pending_upload_jobs_inline() -> int:
    UPLOAD_JOB_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in UPLOAD_JOB_DIR.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            _enqueue_upload_job_inline(job_id)
            count += 1
    return count

def enqueue_upload_job(job_id: str) -> None:
    _queue_backend().enqueue_upload_job(job_id)

def upload_job_worker_loop() -> None:
    while not UPLOAD_JOB_STOP_EVENT.is_set():
        UPLOAD_JOB_EVENT.wait(timeout=0.1)
        if UPLOAD_JOB_STOP_EVENT.is_set():
            break
        job_id = ""
        with UPLOAD_JOB_LOCK:
            if UPLOAD_JOB_QUEUE:
                job_id = UPLOAD_JOB_QUEUE.popleft()
            if not UPLOAD_JOB_QUEUE:
                UPLOAD_JOB_EVENT.clear()
        if not job_id:
            time.sleep(0.1)
            continue
        try:
            process_upload_job(job_id)
        except Exception as exc:
            diag_log("upload.job.failed", {"job_id": job_id, "error": str(exc)[:200]})
            write_upload_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(exc)[:200],
                },
            )

def start_upload_worker() -> None:
    if _rq_enabled():
        return
    global UPLOAD_JOB_WORKER_STARTED, UPLOAD_JOB_WORKER_THREAD
    if UPLOAD_JOB_WORKER_STARTED:
        return
    UPLOAD_JOB_STOP_EVENT.clear()
    scan_pending_upload_jobs()
    thread = threading.Thread(target=upload_job_worker_loop, daemon=True, name="upload-worker")
    thread.start()
    UPLOAD_JOB_WORKER_THREAD = thread
    UPLOAD_JOB_WORKER_STARTED = True

def stop_upload_worker(timeout_sec: float = 1.5) -> None:
    if _rq_enabled():
        return
    global UPLOAD_JOB_WORKER_STARTED, UPLOAD_JOB_WORKER_THREAD
    UPLOAD_JOB_STOP_EVENT.set()
    UPLOAD_JOB_EVENT.set()
    thread = UPLOAD_JOB_WORKER_THREAD
    if thread is not None:
        try:
            thread.join(max(0.0, float(timeout_sec or 0.0)))
        except Exception:
            pass
    UPLOAD_JOB_WORKER_THREAD = None
    UPLOAD_JOB_WORKER_STARTED = False

def exam_job_path(job_id: str) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    return EXAM_UPLOAD_JOB_DIR / safe

def load_exam_job(job_id: str) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"exam job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))

def write_exam_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(updates)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(job_path, data)
    return data

def _enqueue_exam_job_inline(job_id: str) -> None:
    with EXAM_JOB_LOCK:
        if job_id not in EXAM_JOB_QUEUE:
            EXAM_JOB_QUEUE.append(job_id)
    EXAM_JOB_EVENT.set()

def scan_pending_exam_jobs() -> int:
    return int(_queue_backend().scan_pending_exam_jobs() or 0)

def _scan_pending_exam_jobs_inline() -> int:
    EXAM_UPLOAD_JOB_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in EXAM_UPLOAD_JOB_DIR.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            _enqueue_exam_job_inline(job_id)
            count += 1
    return count

def enqueue_exam_job(job_id: str) -> None:
    _queue_backend().enqueue_exam_job(job_id)

def exam_job_worker_loop() -> None:
    while not EXAM_JOB_STOP_EVENT.is_set():
        EXAM_JOB_EVENT.wait(timeout=0.1)
        if EXAM_JOB_STOP_EVENT.is_set():
            break
        job_id = ""
        with EXAM_JOB_LOCK:
            if EXAM_JOB_QUEUE:
                job_id = EXAM_JOB_QUEUE.popleft()
            if not EXAM_JOB_QUEUE:
                EXAM_JOB_EVENT.clear()
        if not job_id:
            time.sleep(0.1)
            continue
        try:
            process_exam_upload_job(job_id)
        except Exception as exc:
            diag_log("exam_upload.job.failed", {"job_id": job_id, "error": str(exc)[:200]})
            write_exam_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(exc)[:200],
                },
            )

def start_exam_upload_worker() -> None:
    if _rq_enabled():
        return
    global EXAM_JOB_WORKER_STARTED, EXAM_JOB_WORKER_THREAD
    if EXAM_JOB_WORKER_STARTED:
        return
    EXAM_JOB_STOP_EVENT.clear()
    scan_pending_exam_jobs()
    thread = threading.Thread(target=exam_job_worker_loop, daemon=True, name="exam-upload-worker")
    thread.start()
    EXAM_JOB_WORKER_THREAD = thread
    EXAM_JOB_WORKER_STARTED = True

def stop_exam_upload_worker(timeout_sec: float = 1.5) -> None:
    if _rq_enabled():
        return
    global EXAM_JOB_WORKER_STARTED, EXAM_JOB_WORKER_THREAD
    EXAM_JOB_STOP_EVENT.set()
    EXAM_JOB_EVENT.set()
    thread = EXAM_JOB_WORKER_THREAD
    if thread is not None:
        try:
            thread.join(max(0.0, float(timeout_sec or 0.0)))
        except Exception:
            pass
    EXAM_JOB_WORKER_THREAD = None
    EXAM_JOB_WORKER_STARTED = False

def chat_job_path(job_id: str) -> Path:
    return _chat_job_path_impl(job_id, deps=_chat_job_repo_deps())

def load_chat_job(job_id: str) -> Dict[str, Any]:
    return _load_chat_job_impl(job_id, deps=_chat_job_repo_deps())

def write_chat_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _write_chat_job_impl(job_id, updates, deps=_chat_job_repo_deps(), overwrite=overwrite)

def _try_acquire_lockfile(path: Path, ttl_sec: int) -> bool:
    """
    Cross-process lock using O_EXCL lockfile. Used to prevent duplicate job processing
    under uvicorn multi-worker mode.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for _attempt in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = now - float(path.stat().st_mtime)
                if ttl_sec > 0 and age > float(ttl_sec):
                    path.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            return False
        except Exception:
            return False
        try:
            payload = {"pid": os.getpid(), "ts": datetime.now().isoformat(timespec="seconds")}
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore"))
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        return True
    return False

def _release_lockfile(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

def _chat_job_claim_path(job_id: str) -> Path:
    return chat_job_path(job_id) / "claim.lock"

def _chat_last_user_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role") or "") != "user":
            continue
        return str(msg.get("content") or "")
    return ""

def _chat_text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()

def resolve_chat_lane_id(
    role_hint: Optional[str],
    *,
    session_id: Optional[str] = None,
    student_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    role = str(role_hint or "unknown").strip().lower() or "unknown"
    sid = safe_fs_id(session_id or "main", prefix="session")
    if role == "student":
        student = safe_fs_id(student_id or "student", prefix="student")
        return f"student:{student}:{sid}"
    if role == "teacher":
        teacher = resolve_teacher_id(teacher_id)
        return f"teacher:{teacher}:{sid}"
    rid = safe_fs_id(request_id or "req", prefix="req")
    return f"unknown:{sid}:{rid}"

def resolve_chat_lane_id_from_job(job: Dict[str, Any]) -> str:
    lane_id = str(job.get("lane_id") or "").strip()
    if lane_id:
        return lane_id
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    role = str(job.get("role") or request.get("role") or "unknown")
    session_id = str(job.get("session_id") or "").strip() or None
    student_id = str(job.get("student_id") or request.get("student_id") or "").strip() or None
    teacher_id = str(job.get("teacher_id") or request.get("teacher_id") or "").strip() or None
    request_id = str(job.get("request_id") or "").strip() or None
    return resolve_chat_lane_id(
        role,
        session_id=session_id,
        student_id=student_id,
        teacher_id=teacher_id,
        request_id=request_id,
    )

def _chat_lane_store():
    tenant_key = str(TENANT_ID or "default").strip() or "default"
    store = _CHAT_LANE_STORES.get(tenant_key)
    if store is None:
        from .chat_redis_lane_store import RedisLaneStore
        from .redis_clients import get_redis_client

        store = RedisLaneStore(
            redis_client=get_redis_client(REDIS_URL, decode_responses=True),
            tenant_id=tenant_key,
            claim_ttl_sec=CHAT_JOB_CLAIM_TTL_SEC,
            debounce_ms=CHAT_LANE_DEBOUNCE_MS,
        )
        _CHAT_LANE_STORES[tenant_key] = store
    return store

def _inline_queue_backend() -> InlineQueueBackend:
    return InlineQueueBackend(
        enqueue_upload_job=_enqueue_upload_job_inline,
        enqueue_exam_job=_enqueue_exam_job_inline,
        enqueue_profile_update=_enqueue_profile_update_inline,
        enqueue_chat_job=_enqueue_chat_job_inline,
        scan_pending_upload_jobs=_scan_pending_upload_jobs_inline,
        scan_pending_exam_jobs=_scan_pending_exam_jobs_inline,
        scan_pending_chat_jobs=_scan_pending_chat_jobs_inline,
        start=_start_inline_workers,
        stop=_stop_inline_workers,
    )

def _queue_backend():
    global _QUEUE_BACKEND
    if _QUEUE_BACKEND is None:
        _QUEUE_BACKEND = get_queue_backend(tenant_id=TENANT_ID or None, inline_backend=_inline_queue_backend())
    return _QUEUE_BACKEND

def _chat_lane_load_locked(lane_id: str) -> Dict[str, int]:
    if _rq_enabled():
        return _chat_lane_store().lane_load(lane_id)
    q = CHAT_JOB_LANES.get(lane_id)
    queued = len(q) if q else 0
    active = 1 if lane_id in CHAT_JOB_ACTIVE_LANES else 0
    return {"queued": queued, "active": active, "total": queued + active}

def _chat_find_position_locked(lane_id: str, job_id: str) -> int:
    if _rq_enabled():
        return _chat_lane_store().find_position(lane_id, job_id)
    q = CHAT_JOB_LANES.get(lane_id)
    if not q:
        return 0
    for i, jid in enumerate(q, start=1):
        if jid == job_id:
            return i
    return 0

def _chat_enqueue_locked(job_id: str, lane_id: str) -> int:
    if job_id in CHAT_JOB_QUEUED or job_id in CHAT_JOB_TO_LANE:
        return _chat_find_position_locked(lane_id, job_id)
    q = CHAT_JOB_LANES.setdefault(lane_id, deque())
    q.append(job_id)
    CHAT_JOB_QUEUED.add(job_id)
    CHAT_JOB_TO_LANE[job_id] = lane_id
    return len(q)

def _chat_has_pending_locked() -> bool:
    return any(len(q) > 0 for q in CHAT_JOB_LANES.values())

def _chat_pick_next_locked() -> Tuple[str, str]:
    global CHAT_LANE_CURSOR
    lanes = [lane for lane, q in CHAT_JOB_LANES.items() if q]
    if not lanes:
        return "", ""
    total = len(lanes)
    start = CHAT_LANE_CURSOR % total
    for offset in range(total):
        lane_id = lanes[(start + offset) % total]
        if lane_id in CHAT_JOB_ACTIVE_LANES:
            continue
        q = CHAT_JOB_LANES.get(lane_id)
        if not q:
            continue
        job_id = q.popleft()
        CHAT_JOB_QUEUED.discard(job_id)
        CHAT_JOB_ACTIVE_LANES.add(lane_id)
        CHAT_JOB_TO_LANE[job_id] = lane_id
        CHAT_LANE_CURSOR = (start + offset + 1) % max(1, total)
        return job_id, lane_id
    return "", ""

def _chat_mark_done_locked(job_id: str, lane_id: str) -> None:
    CHAT_JOB_ACTIVE_LANES.discard(lane_id)
    CHAT_JOB_TO_LANE.pop(job_id, None)
    q = CHAT_JOB_LANES.get(lane_id)
    if q is not None and len(q) == 0:
        CHAT_JOB_LANES.pop(lane_id, None)

def _chat_register_recent_locked(lane_id: str, fingerprint: str, job_id: str) -> None:
    if _rq_enabled():
        _chat_lane_store().register_recent(lane_id, fingerprint, job_id)
        return
    CHAT_LANE_RECENT[lane_id] = (time.time(), fingerprint, job_id)

def _chat_recent_job_locked(lane_id: str, fingerprint: str) -> Optional[str]:
    if _rq_enabled():
        return _chat_lane_store().recent_job(lane_id, fingerprint)
    if CHAT_LANE_DEBOUNCE_MS <= 0:
        return None
    info = CHAT_LANE_RECENT.get(lane_id)
    if not info:
        return None
    ts, fp, job_id = info
    if fp != fingerprint:
        return None
    if (time.time() - ts) * 1000 > CHAT_LANE_DEBOUNCE_MS:
        return None
    return job_id

def _enqueue_chat_job_inline(job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
    return _enqueue_chat_job_impl(job_id, deps=_chat_worker_deps(), lane_id=lane_id)

def enqueue_chat_job(job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
    return _queue_backend().enqueue_chat_job(job_id, lane_id=lane_id)

def scan_pending_chat_jobs() -> int:
    return int(_queue_backend().scan_pending_chat_jobs() or 0)

def _scan_pending_chat_jobs_inline() -> int:
    _scan_pending_chat_jobs_impl(deps=_chat_worker_deps())
    return 0

def chat_job_worker_loop() -> None:
    if _rq_enabled():
        return
    _chat_job_worker_loop_impl(deps=_chat_worker_deps())

def start_chat_worker() -> None:
    if _rq_enabled():
        return
    _start_chat_worker_impl(deps=_chat_worker_deps())

def stop_chat_worker(timeout_sec: float = 1.5) -> None:
    if _rq_enabled():
        return
    _stop_chat_worker_impl(deps=_chat_worker_deps(), timeout_sec=timeout_sec)

def load_chat_request_index() -> Dict[str, str]:
    request_index_path = CHAT_IDEMPOTENCY_STATE.request_index_path
    if not request_index_path.exists():
        return {}
    try:
        data = json.loads(request_index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out

def _chat_request_map_path(request_id: str) -> Path:
    return CHAT_IDEMPOTENCY_STATE.request_map_dir / f"{safe_fs_id(request_id, prefix='req')}.txt"

def _chat_request_map_get(request_id: str) -> Optional[str]:
    request_id = str(request_id or "").strip()
    if not request_id:
        return None
    path = _chat_request_map_path(request_id)
    if not path.exists():
        return None
    try:
        job_id = (path.read_text(encoding="utf-8", errors="ignore") or "").strip()
    except Exception:
        return None
    if not job_id:
        return None
    # Best-effort stale cleanup (e.g., crash mid-write).
    try:
        job_path = chat_job_path(job_id) / "job.json"
        if not job_path.exists():
            path.unlink(missing_ok=True)
            return None
    except Exception:
        pass
    return job_id

def _chat_request_map_set_if_absent(request_id: str, job_id: str) -> bool:
    request_id = str(request_id or "").strip()
    job_id = str(job_id or "").strip()
    if not request_id or not job_id:
        return False
    path = _chat_request_map_path(request_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except Exception:
        return False
    try:
        os.write(fd, job_id.encode("utf-8", errors="ignore"))
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
    return True

def upsert_chat_request_index(request_id: str, job_id: str) -> None:
    """
    Best-effort idempotency mapping. Primary mapping is per-request lockfile under CHAT_REQUEST_MAP_DIR.
    request_index.json is kept as legacy/debug only.
    """
    _chat_request_map_set_if_absent(request_id, job_id)
    try:
        with CHAT_IDEMPOTENCY_STATE.request_index_lock:
            idx = load_chat_request_index()
            idx[str(request_id)] = str(job_id)
            _atomic_write_json(CHAT_IDEMPOTENCY_STATE.request_index_path, idx)
    except Exception:
        pass

def get_chat_job_id_by_request(request_id: str) -> Optional[str]:
    job_id = _chat_request_map_get(request_id)
    if job_id:
        return job_id
    # Fallback to legacy json index (e.g., old jobs created before request map existed).
    try:
        with CHAT_IDEMPOTENCY_STATE.request_index_lock:
            idx = load_chat_request_index()
            legacy = idx.get(str(request_id))
    except Exception:
        legacy = None
    if not legacy:
        return None
    try:
        if not (chat_job_path(legacy) / "job.json").exists():
            return None
    except Exception:
        return None
    return legacy

def student_sessions_base_dir(student_id: str) -> Path:
    return STUDENT_SESSIONS_DIR / safe_fs_id(student_id, prefix="student")

def student_sessions_index_path(student_id: str) -> Path:
    return student_sessions_base_dir(student_id) / "index.json"

def student_session_view_state_path(student_id: str) -> Path:
    return student_sessions_base_dir(student_id) / "view_state.json"

def teacher_session_view_state_path(teacher_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / "view_state.json"

def _session_index_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _SESSION_INDEX_LOCKS_LOCK:
        lock = _SESSION_INDEX_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SESSION_INDEX_LOCKS[key] = lock
        return lock

def _compare_iso_ts(a: Any, b: Any) -> int:
    return _compare_iso_ts_impl(a, b)

def _default_session_view_state() -> Dict[str, Any]:
    return _default_session_view_state_impl()

def _normalize_session_view_state_payload(raw: Any) -> Dict[str, Any]:
    return _normalize_session_view_state_payload_impl(raw)

def load_student_session_view_state(student_id: str) -> Dict[str, Any]:
    path = student_session_view_state_path(student_id)
    return _load_session_view_state_impl(path)

def save_student_session_view_state(student_id: str, state: Dict[str, Any]) -> None:
    path = student_session_view_state_path(student_id)
    _save_session_view_state_impl(path, state)

def load_teacher_session_view_state(teacher_id: str) -> Dict[str, Any]:
    path = teacher_session_view_state_path(teacher_id)
    return _load_session_view_state_impl(path)

def save_teacher_session_view_state(teacher_id: str, state: Dict[str, Any]) -> None:
    path = teacher_session_view_state_path(teacher_id)
    _save_session_view_state_impl(path, state)

def load_student_sessions_index(student_id: str) -> List[Dict[str, Any]]:
    path = student_sessions_index_path(student_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []

def save_student_sessions_index(student_id: str, items: List[Dict[str, Any]]) -> None:
    path = student_sessions_index_path(student_id)
    _atomic_write_json(path, items)

def student_session_file(student_id: str, session_id: str) -> Path:
    return student_sessions_base_dir(student_id) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"

def update_student_session_index(
    student_id: str,
    session_id: str,
    assignment_id: Optional[str],
    date_str: Optional[str],
    preview: str,
    message_increment: int = 0,
) -> None:
    path = student_sessions_index_path(student_id)
    with _session_index_lock(path):
        items = load_student_sessions_index(student_id)
        now = datetime.now().isoformat(timespec="seconds")
        found = None
        for item in items:
            if item.get("session_id") == session_id:
                found = item
                break
        if found is None:
            found = {"session_id": session_id, "message_count": 0}
            items.append(found)
        found["updated_at"] = now
        if assignment_id is not None:
            found["assignment_id"] = assignment_id
        if date_str is not None:
            found["date"] = date_str
        if preview:
            found["preview"] = preview[:200]
        try:
            found["message_count"] = int(found.get("message_count") or 0)
        except Exception:
            found["message_count"] = 0
        try:
            inc = int(message_increment or 0)
        except Exception:
            inc = 0
        if inc:
            found["message_count"] = max(0, int(found.get("message_count") or 0) + inc)

        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        save_student_sessions_index(student_id, items[:SESSION_INDEX_MAX_ITEMS])

def append_student_session_message(
    student_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    base = student_sessions_base_dir(student_id)
    base.mkdir(parents=True, exist_ok=True)
    path = student_session_file(student_id, session_id)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }
    if meta:
        record.update(meta)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def resolve_teacher_id(teacher_id: Optional[str] = None) -> str:
    raw = (teacher_id or os.getenv("DEFAULT_TEACHER_ID") or "teacher").strip()
    # Use a stable filesystem-safe id; keep original value in USER.md if needed.
    return safe_fs_id(raw, prefix="teacher")

def teacher_workspace_dir(teacher_id: str) -> Path:
    return TEACHER_WORKSPACES_DIR / safe_fs_id(teacher_id, prefix="teacher")

def teacher_workspace_file(teacher_id: str, name: str) -> Path:
    allowed = {"AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}
    if name not in allowed:
        raise ValueError(f"invalid teacher workspace file: {name}")
    return teacher_workspace_dir(teacher_id) / name

def teacher_llm_routing_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "llm_routing.json"

def teacher_provider_registry_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "provider_registry.json"

def teacher_provider_registry_audit_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "provider_registry_audit.jsonl"

def routing_config_path_for_role(role_hint: Optional[str], teacher_id: Optional[str] = None) -> Path:
    if role_hint == "teacher":
        return teacher_llm_routing_path(teacher_id)
    return LLM_ROUTING_PATH

def teacher_daily_memory_dir(teacher_id: str) -> Path:
    return teacher_workspace_dir(teacher_id) / "memory"

def teacher_daily_memory_path(teacher_id: str, date_str: Optional[str] = None) -> Path:
    date_final = parse_date_str(date_str)
    return teacher_daily_memory_dir(teacher_id) / f"{date_final}.md"

def ensure_teacher_workspace(teacher_id: str) -> Path:
    return _ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())

def teacher_read_text(path: Path, max_chars: int = 8000) -> str:
    return _teacher_read_text_impl(path, max_chars=max_chars)

def teacher_sessions_base_dir(teacher_id: str) -> Path:
    return TEACHER_SESSIONS_DIR / safe_fs_id(teacher_id, prefix="teacher")

def teacher_sessions_index_path(teacher_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / "index.json"

def load_teacher_sessions_index(teacher_id: str) -> List[Dict[str, Any]]:
    path = teacher_sessions_index_path(teacher_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []

def save_teacher_sessions_index(teacher_id: str, items: List[Dict[str, Any]]) -> None:
    path = teacher_sessions_index_path(teacher_id)
    _atomic_write_json(path, items)

def teacher_session_file(teacher_id: str, session_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"

def update_teacher_session_index(
    teacher_id: str,
    session_id: str,
    preview: str,
    message_increment: int = 0,
) -> None:
    path = teacher_sessions_index_path(teacher_id)
    with _session_index_lock(path):
        items = load_teacher_sessions_index(teacher_id)
        now = datetime.now().isoformat(timespec="seconds")
        found = None
        for item in items:
            if item.get("session_id") == session_id:
                found = item
                break
        if found is None:
            found = {"session_id": session_id, "message_count": 0}
            items.append(found)
        found["updated_at"] = now
        if preview:
            found["preview"] = preview[:200]
        try:
            found["message_count"] = int(found.get("message_count") or 0)
        except Exception:
            found["message_count"] = 0
        try:
            inc = int(message_increment or 0)
        except Exception:
            inc = 0
        if inc:
            found["message_count"] = max(0, int(found.get("message_count") or 0) + inc)

        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        save_teacher_sessions_index(teacher_id, items[:SESSION_INDEX_MAX_ITEMS])

def append_teacher_session_message(
    teacher_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    base = teacher_sessions_base_dir(teacher_id)
    base.mkdir(parents=True, exist_ok=True)
    path = teacher_session_file(teacher_id, session_id)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }
    if meta:
        record.update(meta)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def _teacher_compact_key(teacher_id: str, session_id: str) -> str:
    return f"{safe_fs_id(teacher_id, prefix='teacher')}:{safe_fs_id(session_id, prefix='session')}"

def _teacher_compact_allowed(teacher_id: str, session_id: str) -> bool:
    key = _teacher_compact_key(teacher_id, session_id)
    if TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC <= 0:
        return True
    now = time.time()
    with _TEACHER_SESSION_COMPACT_LOCK:
        last = float(_TEACHER_SESSION_COMPACT_TS.get(key, 0.0) or 0.0)
        if now - last < TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC:
            return False
        _TEACHER_SESSION_COMPACT_TS[key] = now
    return True

def _teacher_compact_transcript(records: List[Dict[str, Any]], max_chars: int) -> str:
    parts: List[str] = []
    used = 0
    for rec in records:
        role = str(rec.get("role") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        raw = str(rec.get("content") or "")
        content = re.sub(r"\s+", " ", raw).strip()
        if not content:
            continue
        tag = "老师" if role == "user" else "助理"
        line = f"{tag}: {content}"
        if used + len(line) > max_chars:
            remain = max(0, max_chars - used)
            if remain > 24:
                parts.append(line[:remain])
            break
        parts.append(line)
        used += len(line) + 1
    return "\n".join(parts).strip()

def _teacher_compact_summary(records: List[Dict[str, Any]], previous_summary: str) -> str:
    transcript = _teacher_compact_transcript(records, TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS)
    snippets: List[str] = []
    for line in transcript.splitlines():
        if not line.strip():
            continue
        snippets.append(f"- {line[:180]}")
        if len(snippets) >= 14:
            break
    parts: List[str] = []
    if previous_summary:
        parts.append("### 历史摘要")
        parts.append(previous_summary[:1800])
    parts.append("### 本轮新增摘要")
    if not snippets:
        snippets = ["- （无可摘要内容）"]
    parts.extend(snippets)
    return "\n".join(parts).strip()

def _write_teacher_session_records(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

def _mark_teacher_session_compacted(
    teacher_id: str,
    session_id: str,
    compacted_messages: int,
    new_message_count: Optional[int] = None,
) -> None:
    items = load_teacher_sessions_index(teacher_id)
    now = datetime.now().isoformat(timespec="seconds")
    found: Optional[Dict[str, Any]] = None
    for item in items:
        if item.get("session_id") == session_id:
            found = item
            break
    if found is None:
        found = {"session_id": session_id, "message_count": 0}
        items.append(found)
    found["updated_at"] = now
    found["compacted_at"] = now
    try:
        found["compaction_runs"] = int(found.get("compaction_runs") or 0) + 1
    except Exception:
        found["compaction_runs"] = 1
    try:
        found["compacted_messages"] = int(found.get("compacted_messages") or 0) + int(compacted_messages or 0)
    except Exception:
        found["compacted_messages"] = int(compacted_messages or 0)
    if new_message_count is not None:
        try:
            found["message_count"] = max(0, int(new_message_count))
        except Exception:
            pass
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    save_teacher_sessions_index(teacher_id, items[:SESSION_INDEX_MAX_ITEMS])

def maybe_compact_teacher_session(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _maybe_compact_teacher_session_impl(
        teacher_id,
        session_id,
        deps=_teacher_session_compaction_deps(),
    )

def _teacher_session_summary_text(teacher_id: str, session_id: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    try:
        path = teacher_session_file(teacher_id, session_id)
    except Exception:
        return ""
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8") as f:
            for _idx, line in zip(range(5), f):
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and obj.get("kind") == "session_summary":
                    text = str(obj.get("content") or "").strip()
                    return (text[:max_chars] + "…") if max_chars and len(text) > max_chars else text
                # If the first meaningful record isn't summary, don't scan the whole file.
                break
    except Exception:
        return ""
    return ""

def _teacher_memory_context_text(teacher_id: str, max_chars: int = 4000) -> str:
    active = _teacher_memory_active_applied_records(
        teacher_id,
        target="MEMORY",
        limit=TEACHER_MEMORY_CONTEXT_MAX_ENTRIES,
    )
    if not active:
        return teacher_read_text(teacher_workspace_file(teacher_id, "MEMORY.md"), max_chars=max_chars).strip()

    lines: List[str] = []
    used = 0
    for rec in active:
        text = str(rec.get("content") or "").strip()
        if not text:
            continue
        brief = re.sub(r"\s+", " ", text).strip()[:240]
        score = int(round(_teacher_memory_rank_score(rec)))
        source = str(rec.get("source") or "manual")
        line = f"- [{source}|{score}] {brief}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines).strip()

def teacher_build_context(teacher_id: str, query: Optional[str] = None, max_chars: int = 6000, session_id: str = "main") -> str:
    return _build_teacher_context_impl(
        teacher_id,
        deps=_teacher_context_deps(),
        query=query,
        max_chars=max_chars,
        session_id=session_id,
    )

def teacher_memory_search(teacher_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    return _teacher_memory_search_impl(
        teacher_id,
        query,
        deps=_teacher_memory_search_deps(),
        limit=limit,
    )

def _teacher_proposal_path(teacher_id: str, proposal_id: str) -> Path:
    ensure_teacher_workspace(teacher_id)
    base = teacher_workspace_dir(teacher_id) / "proposals"
    return base / f"{safe_fs_id(proposal_id, prefix='proposal')}.json"

def teacher_memory_list_proposals(
    teacher_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    ensure_teacher_workspace(teacher_id)
    proposals_dir = teacher_workspace_dir(teacher_id) / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    status_norm = (status or "").strip().lower() or None
    if status_norm and status_norm not in {"proposed", "applied", "rejected"}:
        return {"ok": False, "error": "invalid_status", "teacher_id": teacher_id}

    take = max(1, min(int(limit or 20), 200))
    files = sorted(
        proposals_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    items: List[Dict[str, Any]] = []
    for path in files:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        rec_status = str(rec.get("status") or "").strip().lower()
        if status_norm and rec_status != status_norm:
            continue
        if "proposal_id" not in rec:
            rec["proposal_id"] = path.stem
        items.append(rec)
        if len(items) >= take:
            break
    return {"ok": True, "teacher_id": teacher_id, "proposals": items}

def _teacher_memory_load_events(teacher_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    return _teacher_memory_load_events_impl(teacher_id, deps=_teacher_memory_store_deps(), limit=limit)

def teacher_memory_insights(teacher_id: str, days: int = 14) -> Dict[str, Any]:
    return _teacher_memory_insights_impl(
        teacher_id,
        deps=_teacher_memory_insights_deps(),
        days=days,
    )

def _teacher_memory_is_sensitive(content: str) -> bool:
    return _teacher_memory_is_sensitive_impl(content, patterns=_TEACHER_MEMORY_SENSITIVE_PATTERNS)

def _teacher_memory_event_log_path(teacher_id: str) -> Path:
    return _teacher_memory_event_log_path_impl(teacher_id, deps=_teacher_memory_store_deps())

def _teacher_memory_log_event(teacher_id: str, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    _teacher_memory_log_event_impl(teacher_id, event, payload=payload, deps=_teacher_memory_store_deps())

def _teacher_memory_parse_dt(raw: Any) -> Optional[datetime]:
    return _teacher_memory_parse_dt_impl(raw)

def _teacher_memory_record_ttl_days(rec: Dict[str, Any]) -> int:
    return _teacher_memory_record_ttl_days_impl(
        rec,
        ttl_days_daily=TEACHER_MEMORY_TTL_DAYS_DAILY,
        ttl_days_memory=TEACHER_MEMORY_TTL_DAYS_MEMORY,
    )

def _teacher_memory_record_expire_at(rec: Dict[str, Any]) -> Optional[datetime]:
    return _teacher_memory_record_expire_at_impl(
        rec,
        parse_dt=_teacher_memory_parse_dt,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )

def _teacher_memory_is_expired_record(rec: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    return _teacher_memory_is_expired_record_impl(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        record_expire_at=_teacher_memory_record_expire_at,
        now=now,
    )

def _teacher_memory_age_days(rec: Dict[str, Any], now: Optional[datetime] = None) -> int:
    return _teacher_memory_age_days_impl(rec, parse_dt=_teacher_memory_parse_dt, now=now)

def _teacher_memory_priority_score(
    *,
    target: str,
    title: str,
    content: str,
    source: str,
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    return _teacher_memory_priority_score_impl(
        target=target,
        title=title,
        content=content,
        source=source,
        meta=meta,
        durable_intent_patterns=_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
        auto_infer_stable_patterns=_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        is_sensitive=_teacher_memory_is_sensitive,
        norm_text=_teacher_memory_norm_text,
    )

def _teacher_memory_rank_score(rec: Dict[str, Any]) -> float:
    return _teacher_memory_rank_score_impl(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        priority_score=_teacher_memory_priority_score,
        age_days=_teacher_memory_age_days,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )

def _teacher_memory_load_record(teacher_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
    return _teacher_memory_load_record_impl(teacher_id, proposal_id, deps=_teacher_memory_store_deps())

def _teacher_memory_active_applied_records(
    teacher_id: str,
    *,
    target: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return _teacher_memory_active_applied_records_impl(
        teacher_id,
        deps=_teacher_memory_store_deps(),
        target=target,
        limit=limit,
    )

def _teacher_memory_recent_user_turns(teacher_id: str, session_id: str, limit: int = 24) -> List[str]:
    return _teacher_memory_recent_user_turns_impl(teacher_id, session_id, deps=_teacher_memory_record_deps(), limit=limit)

def _teacher_memory_loose_match(a: str, b: str) -> bool:
    return _teacher_memory_loose_match_impl(a, b, norm_text=_teacher_memory_norm_text)

def _teacher_memory_auto_infer_candidate(teacher_id: str, session_id: str, user_text: str) -> Optional[Dict[str, Any]]:
    return _teacher_memory_auto_infer_candidate_impl(teacher_id, session_id, user_text, deps=_teacher_memory_record_deps())

def _teacher_session_index_item(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _teacher_session_index_item_impl(teacher_id, session_id, deps=_teacher_memory_record_deps())

def _mark_teacher_session_memory_flush(teacher_id: str, session_id: str, cycle_no: int) -> None:
    _mark_teacher_session_memory_flush_impl(teacher_id, session_id, cycle_no, deps=_teacher_memory_record_deps())

def _teacher_memory_has_term(text: str, terms: Tuple[str, ...]) -> bool:
    return _teacher_memory_has_term_impl(text, terms)

def _teacher_memory_conflicts(new_text: str, old_text: str) -> bool:
    return _teacher_memory_conflicts_impl(
        new_text,
        old_text,
        norm_text=_teacher_memory_norm_text,
        conflict_groups=_TEACHER_MEMORY_CONFLICT_GROUPS,
    )

def _teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
) -> List[str]:
    return _teacher_memory_find_conflicting_applied_impl(
        teacher_id,
        proposal_id=proposal_id,
        target=target,
        content=content,
        deps=_teacher_memory_record_deps(),
    )

def _teacher_memory_mark_superseded(teacher_id: str, proposal_ids: List[str], by_proposal_id: str) -> None:
    _teacher_memory_mark_superseded_impl(teacher_id, proposal_ids, by_proposal_id, deps=_teacher_memory_record_deps())

def teacher_memory_propose(
    teacher_id: str,
    target: str,
    title: str,
    content: str,
    *,
    source: str = "manual",
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> Dict[str, Any]:
    return _teacher_memory_propose_impl(
        teacher_id,
        target,
        title,
        content,
        deps=_teacher_memory_propose_deps(),
        source=source,
        meta=meta,
        dedupe_key=dedupe_key,
    )

def teacher_memory_apply(teacher_id: str, proposal_id: str, approve: bool = True) -> Dict[str, Any]:
    return _teacher_memory_apply_impl(
        teacher_id,
        proposal_id,
        deps=_teacher_memory_apply_deps(),
        approve=approve,
    )

def _teacher_memory_norm_text(text: str) -> str:
    return _teacher_memory_norm_text_impl(text)

def _teacher_memory_stable_hash(*parts: str) -> str:
    return _teacher_memory_stable_hash_impl(*parts)

def _teacher_memory_recent_proposals(teacher_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return _teacher_memory_recent_proposals_impl(teacher_id, deps=_teacher_memory_record_deps(), limit=limit)

def _teacher_memory_auto_quota_reached(teacher_id: str) -> bool:
    return _teacher_memory_auto_quota_reached_impl(teacher_id, deps=_teacher_memory_record_deps())

def _teacher_memory_find_duplicate(
    teacher_id: str,
    *,
    target: str,
    content: str,
    dedupe_key: str,
) -> Optional[Dict[str, Any]]:
    return _teacher_memory_find_duplicate_impl(
        teacher_id,
        target=target,
        content=content,
        dedupe_key=dedupe_key,
        deps=_teacher_memory_record_deps(),
    )

def _teacher_session_compaction_cycle_no(teacher_id: str, session_id: str) -> int:
    return _teacher_session_compaction_cycle_no_impl(teacher_id, session_id, deps=_teacher_memory_record_deps())

def teacher_memory_auto_propose_from_turn(
    teacher_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
) -> Dict[str, Any]:
    return _teacher_memory_auto_propose_from_turn_impl(
        teacher_id,
        session_id,
        user_text,
        assistant_text,
        deps=_teacher_memory_auto_deps(),
    )

def teacher_memory_auto_flush_from_session(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _teacher_memory_auto_flush_from_session_impl(
        teacher_id,
        session_id,
        deps=_teacher_memory_auto_deps(),
    )

@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    start_tenant_runtime()
    try:
        yield
    finally:
        stop_tenant_runtime()


def _start_inline_workers() -> None:
    start_upload_worker()
    if PROFILE_UPDATE_ASYNC:
        start_profile_update_worker()
    start_exam_upload_worker()
    start_chat_worker()


def _stop_inline_workers() -> None:
    # Stop in reverse order of startup. Best-effort only.
    stop_chat_worker()
    stop_exam_upload_worker()
    stop_upload_worker()
    if PROFILE_UPDATE_ASYNC:
        stop_profile_update_worker()


def start_tenant_runtime() -> None:
    _validate_master_key_policy_impl(getenv=os.getenv)
    backend = _queue_backend()
    from .rq_tasks import require_redis

    require_redis()
    backend.start()


def stop_tenant_runtime() -> None:
    _queue_backend().stop()


app = FastAPI(title="Physics Agent API", version="0.2.0", lifespan=_app_lifespan)

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def model_dump_compat(model: BaseModel, *, exclude_none: bool = False) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=exclude_none)  # type: ignore[attr-defined]
    return model.dict(exclude_none=exclude_none)

def run_script(args: List[str]) -> str:
    env = os.environ.copy()
    root = str(APP_ROOT)
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{root}{os.pathsep}{current}" if current else root
    proc = subprocess.run(args, capture_output=True, text=True, env=env, cwd=root)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout

def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()

def parse_ids_value(value: Any) -> List[str]:
    parts = parse_list_value(value)
    return [p for p in parts if p]

def parse_timeout_env(name: str) -> Optional[float]:
    return _parse_timeout_env_impl(name)

async def save_upload_file(upload: UploadFile, dest: Path, chunk_size: int = 1024 * 1024) -> int:
    return await _save_upload_file_impl(
        upload,
        dest,
        chunk_size=chunk_size,
        run_in_threadpool=run_in_threadpool,
    )

def sanitize_filename(name: str) -> str:
    return sanitize_filename_io(name)

def safe_slug(value: str) -> str:
    return re.sub(r"[^\w-]+", "_", value or "").strip("_") or "assignment"

def resolve_assignment_dir(assignment_id: str) -> Path:
    assignments_root = (DATA_DIR / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise ValueError("assignment_id is required")
    folder = (assignments_root / aid).resolve()
    if folder != assignments_root and assignments_root not in folder.parents:
        raise ValueError("invalid assignment_id")
    return folder

def resolve_exam_dir(exam_id: str) -> Path:
    exams_root = (DATA_DIR / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (exams_root / eid).resolve()
    if folder != exams_root and exams_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder

def resolve_analysis_dir(exam_id: str) -> Path:
    analysis_root = (DATA_DIR / "analysis").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (analysis_root / eid).resolve()
    if folder != analysis_root and analysis_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder

def resolve_student_profile_path(student_id: str) -> Path:
    profiles_root = (DATA_DIR / "student_profiles").resolve()
    sid = str(student_id or "").strip()
    if not sid:
        raise ValueError("student_id is required")
    path = (profiles_root / f"{sid}.json").resolve()
    if path != profiles_root and profiles_root not in path.parents:
        raise ValueError("invalid student_id")
    return path

def resolve_scope(scope: str, student_ids: List[str], class_name: str) -> str:
    scope_norm = (scope or "").strip().lower()
    if scope_norm in {"public", "class", "student"}:
        return scope_norm
    if student_ids:
        return "student"
    if class_name:
        return "class"
    return "public"

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

def _parse_xlsx_with_script(
    xlsx_path: Path,
    out_csv: Path,
    exam_id: str,
    class_name_hint: str,
) -> Optional[List[Dict[str, Any]]]:
    script = APP_ROOT / "skills" / "physics-teacher-ops" / "scripts" / "parse_scores.py"
    cmd = ["python3", str(script), "--scores", str(xlsx_path), "--exam-id", exam_id, "--out", str(out_csv)]
    if class_name_hint:
        cmd += ["--class-name", class_name_hint]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), cwd=str(APP_ROOT))
    if proc.returncode != 0 or not out_csv.exists():
        return None
    file_rows: List[Dict[str, Any]] = []
    with out_csv.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            item = dict(row)
            item["score"] = parse_score_value(row.get("score"))
            item["is_correct"] = row.get("is_correct") or ""
            file_rows.append(item)
    return file_rows

def process_exam_upload_job(job_id: str) -> None:
    _process_exam_upload_job_impl(job_id, deps=_exam_upload_parse_deps())

def write_uploaded_questions(out_dir: Path, assignment_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _write_uploaded_questions_impl(
        out_dir,
        assignment_id,
        questions,
        deps=_assignment_uploaded_question_deps(),
    )
def detect_role(text: str) -> Optional[str]:
    normalized = normalize(text)
    if "老师" in normalized or "教师" in normalized:
        return "teacher"
    if "学生" in normalized:
        return "student"
    return None

def load_profile_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if PROFILE_CACHE_TTL_SEC > 0:
        key = str(path)
        now = time.monotonic()
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0
        with _PROFILE_CACHE_LOCK:
            cached = _PROFILE_CACHE.get(key)
            if cached:
                ts, cached_mtime, data = cached
                if (now - ts) <= PROFILE_CACHE_TTL_SEC and cached_mtime == mtime:
                    return data
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if PROFILE_CACHE_TTL_SEC > 0:
            key = str(path)
            now = time.monotonic()
            try:
                mtime = path.stat().st_mtime
            except Exception:
                mtime = 0.0
            with _PROFILE_CACHE_LOCK:
                _PROFILE_CACHE[key] = (now, mtime, data)
        return data
    except Exception:
        return {}

def student_search(query: str, limit: int = 5) -> Dict[str, Any]:
    return _student_search_impl(query, limit, _student_directory_deps())

def student_profile_get(student_id: str) -> Dict[str, Any]:
    try:
        profile_path = resolve_student_profile_path(student_id)
    except ValueError:
        return {"error": "invalid_student_id", "student_id": student_id}
    if not profile_path.exists():
        return {"error": "profile not found", "student_id": student_id}
    return json.loads(profile_path.read_text(encoding="utf-8"))

def student_profile_update(args: Dict[str, Any]) -> Dict[str, Any]:
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    cmd = ["python3", str(script), "--student-id", args.get("student_id", "")]
    for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note"):
        if args.get(key) is not None:
            cmd += [f"--{key.replace('_', '-')}", str(args.get(key))]
    out = run_script(cmd)
    return {"ok": True, "output": out}

def _enqueue_profile_update_inline(args: Dict[str, Any]) -> None:
    # Best-effort queue: coalesce on the worker side.
    with _PROFILE_UPDATE_LOCK:
        if len(_PROFILE_UPDATE_QUEUE) >= PROFILE_UPDATE_QUEUE_MAX:
            diag_log("profile_update.queue_full", {"size": len(_PROFILE_UPDATE_QUEUE)})
            return
        _PROFILE_UPDATE_QUEUE.append(args)
        _PROFILE_UPDATE_EVENT.set()

def enqueue_profile_update(args: Dict[str, Any]) -> None:
    _queue_backend().enqueue_profile_update(args)

def profile_update_worker_loop() -> None:
    while not _PROFILE_UPDATE_STOP_EVENT.is_set():
        _PROFILE_UPDATE_EVENT.wait(timeout=0.1)
        if _PROFILE_UPDATE_STOP_EVENT.is_set():
            break
        batch: List[Dict[str, Any]] = []
        with _PROFILE_UPDATE_LOCK:
            while _PROFILE_UPDATE_QUEUE:
                batch.append(_PROFILE_UPDATE_QUEUE.popleft())
            _PROFILE_UPDATE_EVENT.clear()
        if not batch:
            time.sleep(0.05)
            continue

        # Coalesce by student_id to reduce subprocess churn under bursty chat traffic.
        merged: Dict[str, Dict[str, Any]] = {}
        for item in batch:
            student_id = str(item.get("student_id") or "").strip()
            if not student_id:
                continue
            cur = merged.get(student_id) or {"student_id": student_id, "interaction_note": ""}
            note = str(item.get("interaction_note") or "").strip()
            if note:
                if cur.get("interaction_note"):
                    cur["interaction_note"] = str(cur["interaction_note"]) + "\n" + note
                else:
                    cur["interaction_note"] = note
            merged[student_id] = cur

        for student_id, payload in merged.items():
            try:
                t0 = time.monotonic()
                # Reuse existing implementation (runs update_profile.py) but off the hot path.
                student_profile_update(payload)
                diag_log(
                    "profile_update.async.done",
                    {"student_id": student_id, "duration_ms": int((time.monotonic() - t0) * 1000)},
                )
            except Exception as exc:
                diag_log("profile_update.async.failed", {"student_id": student_id, "error": str(exc)[:200]})

def start_profile_update_worker() -> None:
    if _rq_enabled():
        return
    global _PROFILE_UPDATE_WORKER_STARTED, _PROFILE_UPDATE_WORKER_THREAD
    if _PROFILE_UPDATE_WORKER_STARTED:
        return
    _PROFILE_UPDATE_STOP_EVENT.clear()
    thread = threading.Thread(target=profile_update_worker_loop, daemon=True, name="profile-update-worker")
    thread.start()
    _PROFILE_UPDATE_WORKER_THREAD = thread
    _PROFILE_UPDATE_WORKER_STARTED = True

def stop_profile_update_worker(timeout_sec: float = 1.5) -> None:
    if _rq_enabled():
        return
    global _PROFILE_UPDATE_WORKER_STARTED, _PROFILE_UPDATE_WORKER_THREAD
    _PROFILE_UPDATE_STOP_EVENT.set()
    _PROFILE_UPDATE_EVENT.set()
    thread = _PROFILE_UPDATE_WORKER_THREAD
    if thread is not None:
        try:
            thread.join(max(0.0, float(timeout_sec or 0.0)))
        except Exception:
            pass
    _PROFILE_UPDATE_WORKER_THREAD = None
    _PROFILE_UPDATE_WORKER_STARTED = False

def student_candidates_by_name(name: str) -> List[Dict[str, str]]:
    return _student_candidates_by_name_impl(name, _student_directory_deps())

def list_all_student_profiles() -> List[Dict[str, str]]:
    return _list_all_student_profiles_impl(_student_directory_deps())

def list_all_student_ids() -> List[str]:
    return _list_all_student_ids_impl(_student_directory_deps())

def list_student_ids_by_class(class_name: str) -> List[str]:
    return _list_student_ids_by_class_impl(class_name, _student_directory_deps())

def normalize_due_at(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    # Accept date-only inputs and treat them as end-of-day to match common homework expectations.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw + "T23:59:59"
    try:
        # Validate basic ISO format. Keep the original string for readability.
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return raw
    except Exception:
        return None

def compute_expected_students(scope: str, class_name: str, student_ids: List[str]) -> List[str]:
    scope_val = resolve_scope(scope, student_ids, class_name)
    if scope_val == "student":
        return sorted(list(dict.fromkeys([s for s in student_ids if s])))
    if scope_val == "class":
        return list_student_ids_by_class(class_name)
    return list_all_student_ids()

def count_csv_rows(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            count = -1
            for count, _ in enumerate(reader):
                pass
        return max(count, 0)
    except Exception:
        return 0

def list_exams() -> Dict[str, Any]:
    return _list_exams_impl(deps=_exam_catalog_deps())

def load_exam_manifest(exam_id: str) -> Dict[str, Any]:
    exam_id = str(exam_id or "").strip()
    if not exam_id:
        return {}
    try:
        manifest_path = resolve_exam_dir(exam_id) / "manifest.json"
    except ValueError:
        return {}
    return load_profile_file(manifest_path)

def resolve_manifest_path(path_value: Any) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (APP_ROOT / path).resolve()
    return path

def exam_file_path(manifest: Dict[str, Any], key: str) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    return resolve_manifest_path(files.get(key))

def exam_responses_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("responses_scored", "responses", "responses_csv"):
        path = resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None

def exam_questions_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("questions", "questions_csv"):
        path = resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None

def exam_analysis_draft_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if isinstance(files, dict):
        path = resolve_manifest_path(files.get("analysis_draft_json"))
        if path and path.exists():
            return path
    exam_id = str(manifest.get("exam_id") or "").strip()
    if not exam_id:
        return None
    try:
        fallback = resolve_analysis_dir(exam_id) / "draft.json"
    except ValueError:
        return None
    return fallback if fallback.exists() else None

def parse_score_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None

def read_questions_csv(path: Path) -> Dict[str, Dict[str, Any]]:
    questions: Dict[str, Dict[str, Any]] = {}
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                if not qid:
                    continue
                max_score = parse_score_value(row.get("max_score"))
                questions[qid] = {
                    "question_id": qid,
                    "question_no": str(row.get("question_no") or "").strip(),
                    "sub_no": str(row.get("sub_no") or "").strip(),
                    "order": str(row.get("order") or "").strip(),
                    "max_score": max_score,
                }
    except Exception:
        return questions
    return questions

def compute_exam_totals(responses_path: Path) -> Dict[str, Any]:
    totals: Dict[str, float] = {}
    student_meta: Dict[str, Dict[str, str]] = {}
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            score = parse_score_value(row.get("score"))
            if score is None:
                continue
            student_id = str(row.get("student_id") or row.get("student_name") or "").strip()
            if not student_id:
                continue
            totals[student_id] = totals.get(student_id, 0.0) + score
            if student_id not in student_meta:
                student_meta[student_id] = {
                    "student_id": student_id,
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                }
    return {"totals": totals, "students": student_meta}

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

def _parse_question_no_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        out = int(text)
        return out if out > 0 else None
    except Exception:
        pass
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    try:
        out = int(match.group(1))
    except Exception:
        return None
    return out if out > 0 else None

def _median_float(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    size = len(ordered)
    mid = size // 2
    if size % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)

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

def _normalize_question_no_list(value: Any, maximum: int = 200) -> List[int]:
    raw_items: List[Any] = []
    if isinstance(value, list):
        raw_items = list(value)
    elif value is not None:
        raw_items = [x for x in re.split(r"[,\s，;；]+", str(value)) if x]
    normalized: List[int] = []
    seen: set[int] = set()
    for item in raw_items:
        q_no = _parse_question_no_int(item)
        if q_no is None or q_no in seen:
            continue
        seen.add(q_no)
        normalized.append(q_no)
        if len(normalized) >= maximum:
            break
    return normalized

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


_EXAM_CHART_DEFAULT_TYPES = ["score_distribution", "knowledge_radar", "class_compare", "question_discrimination"]
_EXAM_CHART_TYPE_ALIASES = {
    "score_distribution": "score_distribution",
    "distribution": "score_distribution",
    "histogram": "score_distribution",
    "成绩分布": "score_distribution",
    "分布": "score_distribution",
    "knowledge_radar": "knowledge_radar",
    "radar": "knowledge_radar",
    "knowledge": "knowledge_radar",
    "知识点雷达": "knowledge_radar",
    "雷达图": "knowledge_radar",
    "class_compare": "class_compare",
    "class": "class_compare",
    "group_compare": "class_compare",
    "班级对比": "class_compare",
    "对比": "class_compare",
    "question_discrimination": "question_discrimination",
    "discrimination": "question_discrimination",
    "区分度": "question_discrimination",
    "题目区分度": "question_discrimination",
}

def _safe_int_arg(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        out = int(value)
    except Exception:
        out = default
    if out < minimum:
        return minimum
    if out > maximum:
        return maximum
    return out

def _normalize_exam_chart_types(value: Any) -> List[str]:
    raw_items: List[str] = []
    if isinstance(value, list):
        raw_items = [str(v or "").strip() for v in value]
    elif isinstance(value, str):
        raw_items = [x.strip() for x in re.split(r"[,\s，;；]+", value) if x.strip()]
    normalized: List[str] = []
    for item in raw_items:
        key = _EXAM_CHART_TYPE_ALIASES.get(item.lower()) or _EXAM_CHART_TYPE_ALIASES.get(item)
        if not key:
            continue
        if key not in normalized:
            normalized.append(key)
    return normalized or list(_EXAM_CHART_DEFAULT_TYPES)

def exam_analysis_charts_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    return _exam_analysis_charts_generate_impl(args, deps=_exam_analysis_charts_deps())

def list_assignments() -> Dict[str, Any]:
    return _list_assignments_impl(deps=_assignment_catalog_deps())

def today_iso() -> str:
    return datetime.now().date().isoformat()

def parse_date_str(date_str: Optional[str]) -> str:
    if not date_str:
        return today_iso()
    try:
        return datetime.fromisoformat(date_str).date().isoformat()
    except Exception:
        return today_iso()

def load_assignment_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if meta_path.exists():
        return load_profile_file(meta_path)
    return {}

def load_assignment_requirements(folder: Path) -> Dict[str, Any]:
    req_path = folder / "requirements.json"
    if req_path.exists():
        return load_profile_file(req_path)
    return {}

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

def _assignment_detail_fingerprint(folder: Path) -> Tuple[float, float, float]:
    # Fast invalidation: if key files change, refresh cache.
    meta_path = folder / "meta.json"
    req_path = folder / "requirements.json"
    q_path = folder / "questions.csv"
    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime if p.exists() else 0.0
        except Exception:
            return 0.0
    return (mtime(meta_path), mtime(req_path), mtime(q_path))

def build_assignment_detail_cached(folder: Path, include_text: bool = True) -> Dict[str, Any]:
    if ASSIGNMENT_DETAIL_CACHE_TTL_SEC <= 0:
        return build_assignment_detail(folder, include_text=include_text)
    key = (str(folder), bool(include_text))
    now = time.monotonic()
    fp = _assignment_detail_fingerprint(folder)
    with _ASSIGNMENT_DETAIL_CACHE_LOCK:
        cached = _ASSIGNMENT_DETAIL_CACHE.get(key)
        if cached:
            ts, cached_fp, data = cached
            if (now - ts) <= ASSIGNMENT_DETAIL_CACHE_TTL_SEC and cached_fp == fp:
                return data
    data = build_assignment_detail(folder, include_text=include_text)
    with _ASSIGNMENT_DETAIL_CACHE_LOCK:
        _ASSIGNMENT_DETAIL_CACHE[key] = (now, fp, data)
    return data

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

def derive_kp_from_profile(profile: Dict[str, Any]) -> List[str]:
    kp_list = []
    next_focus = profile.get("next_focus")
    if next_focus:
        kp_list.append(str(next_focus))
    for key in ("recent_weak_kp", "recent_medium_kp"):
        for kp in profile.get(key) or []:
            if kp not in kp_list:
                kp_list.append(kp)
    return [kp for kp in kp_list if kp]

def safe_assignment_id(student_id: str, date_str: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", student_id).strip("_") if student_id else "student"
    return f"AUTO_{slug}_{date_str}"

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
    script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
    assignment_id = str(args.get("assignment_id", ""))
    cmd = ["python3", str(script), "--assignment-id", assignment_id]
    if args.get("assignment_questions"):
        p = _resolve_app_path(args.get("assignment_questions"), must_exist=True)
        if not p:
            return {"error": "assignment_questions_not_found_or_outside_app_root"}
        cmd += ["--assignment-questions", str(p)]
    out_pdf = None
    if args.get("out"):
        p = _resolve_app_path(args.get("out"), must_exist=False)
        if not p:
            return {"error": "out_outside_app_root"}
        out_pdf = p
        cmd += ["--out", str(p)]
    out = run_script(cmd)
    pdf_path = str(out_pdf) if out_pdf else f"output/pdf/assignment_{assignment_id}.pdf"
    return {"ok": True, "output": out, "pdf": pdf_path}

def chart_exec(args: Dict[str, Any]) -> Dict[str, Any]:
    return _chart_exec_api_impl(args, deps=_chart_api_deps())

def chart_agent_run(args: Dict[str, Any]) -> Dict[str, Any]:
    return _chart_agent_run_impl(args, deps=_chart_agent_run_deps())


_SAFE_TOOL_ID_RE = re.compile(r"^[^\x00/\\\\]+$")

def _is_safe_tool_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and bool(_SAFE_TOOL_ID_RE.match(text))

def _resolve_app_path(path_value: Any, must_exist: bool = True) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (APP_ROOT / p).resolve()
    else:
        p = p.resolve()
    root = APP_ROOT.resolve()
    if root not in p.parents and p != root:
        return None
    if must_exist and not p.exists():
        return None
    return p

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

def _non_ws_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))

def extract_min_chars_requirement(text: str) -> Optional[int]:
    return _extract_min_chars_requirement_impl(text)

def extract_exam_id(text: str) -> Optional[str]:
    return _extract_exam_id_impl(text)

def is_exam_analysis_request(text: str) -> bool:
    return _is_exam_analysis_request_impl(text)

def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    p = max(0.0, min(1.0, float(p)))
    idx = (len(sorted_vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    if lo == hi:
        return float(sorted_vals[lo])
    frac = idx - lo
    return float(sorted_vals[lo]) * (1.0 - frac) + float(sorted_vals[hi]) * frac

def _score_band_label(percent: float) -> str:
    p = max(0.0, min(100.0, float(percent)))
    if p >= 100.0:
        return "90–100%"
    start = int(p // 10) * 10
    end = 100 if start >= 90 else (start + 9)
    return f"{start}–{end}%"

def summarize_exam_students(exam_id: str, max_total: Optional[float]) -> Dict[str, Any]:
    return _summarize_exam_students_impl(exam_id, max_total, deps=_exam_longform_deps())

def load_kp_catalog() -> Dict[str, Dict[str, str]]:
    path = DATA_DIR / "knowledge" / "knowledge_points.csv"
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kp_id = str(row.get("kp_id") or "").strip()
                if not kp_id:
                    continue
                out[kp_id] = {
                    "name": str(row.get("name") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "notes": str(row.get("notes") or "").strip(),
                }
    except Exception:
        return {}
    return out

def load_question_kp_map() -> Dict[str, str]:
    path = DATA_DIR / "knowledge" / "knowledge_point_map.csv"
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                kp_id = str(row.get("kp_id") or "").strip()
                if qid and kp_id:
                    out[qid] = kp_id
    except Exception:
        return {}
    return out

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

async def health():
    return {"status": "ok"}

async def chat(req: ChatRequest):
    reply_text, role_hint, last_user_text = await run_in_threadpool(_compute_chat_reply_sync, req)
    if role_hint == "student" and req.student_id and reply_text != "正在生成上一条回复，请稍候再试。":
        try:
            has_math = detect_math_delimiters(reply_text)
            has_latex = detect_latex_tokens(reply_text)
            diag_log(
                "student_chat.out",
                {
                    "student_id": req.student_id,
                    "assignment_id": req.assignment_id,
                    "has_math_delim": has_math,
                    "has_latex_tokens": has_latex,
                    "reply_preview": reply_text[:500],
                },
            )
            note = build_interaction_note(last_user_text, reply_text, assignment_id=req.assignment_id)
            payload = {"student_id": req.student_id, "interaction_note": note}
            if PROFILE_UPDATE_ASYNC:
                enqueue_profile_update(payload)
            else:
                await run_in_threadpool(student_profile_update, payload)
        except Exception as exc:
            diag_log("student.profile.update_failed", {"student_id": req.student_id, "error": str(exc)[:200]})
    return ChatResponse(reply=reply_text, role=role_hint)

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

async def chat_start(req: ChatStartRequest):
    return _start_chat_api_impl(req, deps=_chat_api_deps())

async def chat_status(job_id: str):
    try:
        return _get_chat_status_impl(job_id, deps=_chat_status_deps())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")

async def student_history_sessions(student_id: str, limit: int = 20, cursor: int = 0):
    try:
        return _student_history_sessions_api_impl(student_id, limit=limit, cursor=cursor, deps=_session_history_api_deps())
    except SessionHistoryApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def student_session_view_state(student_id: str):
    try:
        return _student_session_view_state_api_impl(student_id, deps=_session_history_api_deps())
    except SessionHistoryApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def update_student_session_view_state(req: Dict[str, Any]):
    try:
        return _update_student_session_view_state_api_impl(req, deps=_session_history_api_deps())
    except SessionHistoryApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def student_history_session(
    student_id: str,
    session_id: str,
    cursor: int = -1,
    limit: int = 50,
    direction: str = "backward",
):
    try:
        return _student_history_session_api_impl(
            student_id,
            session_id,
            cursor=cursor,
            limit=limit,
            direction=direction,
            deps=_session_history_api_deps(),
        )
    except SessionHistoryApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def teacher_history_sessions(teacher_id: Optional[str] = None, limit: int = 20, cursor: int = 0):
    return _teacher_history_sessions_api_impl(teacher_id, limit=limit, cursor=cursor, deps=_session_history_api_deps())

async def teacher_session_view_state(teacher_id: Optional[str] = None):
    return _teacher_session_view_state_api_impl(teacher_id, deps=_session_history_api_deps())

async def update_teacher_session_view_state(req: Dict[str, Any]):
    return _update_teacher_session_view_state_api_impl(req, deps=_session_history_api_deps())

async def teacher_history_session(
    session_id: str,
    teacher_id: Optional[str] = None,
    cursor: int = -1,
    limit: int = 50,
    direction: str = "backward",
):
    try:
        return _teacher_history_session_api_impl(
            session_id,
            teacher_id,
            cursor=cursor,
            limit=limit,
            direction=direction,
            deps=_session_history_api_deps(),
        )
    except SessionHistoryApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def teacher_memory_proposals(teacher_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20):
    result = _list_teacher_memory_proposals_api_impl(
        teacher_id,
        status=status,
        limit=limit,
        deps=_teacher_memory_api_deps(),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "invalid_request")
    return result

async def teacher_memory_insights_api(teacher_id: Optional[str] = None, days: int = 14):
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_memory_insights(teacher_id_final, days=days)

async def teacher_memory_proposal_review(proposal_id: str, req: TeacherMemoryProposalReviewRequest):
    result = _review_teacher_memory_proposal_api_impl(
        proposal_id,
        teacher_id=req.teacher_id,
        approve=bool(req.approve),
        deps=_teacher_memory_api_deps(),
    )
    if result.get("error"):
        code = 404 if str(result.get("error")) == "proposal not found" else 400
        raise HTTPException(status_code=code, detail=result.get("error"))
    return result

async def upload(files: list[UploadFile] = File(...)):
    return await _upload_files_api_impl(files, deps=_student_ops_api_deps())

async def get_profile(student_id: str):
    result = _get_profile_api_impl(student_id, deps=_student_profile_api_deps())
    if result.get("error") in {"profile not found", "profile_not_found"}:
        raise HTTPException(status_code=404, detail="profile not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def update_profile(
    student_id: str = Form(...),
    weak_kp: Optional[str] = Form(""),
    strong_kp: Optional[str] = Form(""),
    medium_kp: Optional[str] = Form(""),
    next_focus: Optional[str] = Form(""),
    interaction_note: Optional[str] = Form(""),
):
    payload = _update_profile_api_impl(
        student_id=student_id,
        weak_kp=weak_kp,
        strong_kp=strong_kp,
        medium_kp=medium_kp,
        next_focus=next_focus,
        interaction_note=interaction_note,
        deps=_student_ops_api_deps(),
    )
    return JSONResponse(payload)

async def import_students(req: StudentImportRequest):
    result = student_import(req.dict())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

async def verify_student(req: StudentVerifyRequest):
    return _verify_student_api_impl(req.name, req.class_name, deps=_student_ops_api_deps())

def _tool_dispatch_deps():
    return ToolDispatchDeps(
        tool_registry=DEFAULT_TOOL_REGISTRY,
        list_exams=list_exams,
        exam_get=exam_get,
        exam_analysis_get=exam_analysis_get,
        exam_analysis_charts_generate=exam_analysis_charts_generate,
        exam_students_list=exam_students_list,
        exam_student_detail=exam_student_detail,
        exam_question_detail=exam_question_detail,
        exam_range_top_students=exam_range_top_students,
        exam_range_summary_batch=exam_range_summary_batch,
        exam_question_batch_detail=exam_question_batch_detail,
        list_assignments=list_assignments,
        list_lessons=list_lessons,
        lesson_capture=lesson_capture,
        student_search=student_search,
        student_profile_get=student_profile_get,
        student_profile_update=student_profile_update,
        student_import=student_import,
        assignment_generate=assignment_generate,
        assignment_render=assignment_render,
        save_assignment_requirements=save_assignment_requirements,
        parse_date_str=parse_date_str,
        core_example_search=core_example_search,
        core_example_register=core_example_register,
        core_example_render=core_example_render,
        chart_agent_run=chart_agent_run,
        chart_exec=chart_exec,
        resolve_teacher_id=resolve_teacher_id,
        ensure_teacher_workspace=ensure_teacher_workspace,
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_workspace_file=teacher_workspace_file,
        teacher_daily_memory_path=teacher_daily_memory_path,
        teacher_read_text=lambda path, max_chars=8000: read_text_safe(path, limit=max_chars),
        teacher_memory_search=teacher_memory_search,
        teacher_memory_propose=teacher_memory_propose,
        teacher_memory_apply=teacher_memory_apply,
        teacher_llm_routing_get=teacher_llm_routing_get,
        teacher_llm_routing_simulate=teacher_llm_routing_simulate,
        teacher_llm_routing_propose=teacher_llm_routing_propose,
        teacher_llm_routing_apply=teacher_llm_routing_apply,
        teacher_llm_routing_rollback=teacher_llm_routing_rollback,
    )

def _exam_range_deps():
    return ExamRangeDeps(
        load_exam_manifest=load_exam_manifest,
        exam_responses_path=exam_responses_path,
        exam_questions_path=exam_questions_path,
        read_questions_csv=read_questions_csv,
        parse_score_value=parse_score_value,
        safe_int_arg=_safe_int_arg,
        exam_question_detail=exam_question_detail,
    )

def _exam_analysis_charts_deps():
    return ExamAnalysisChartsDeps(
        app_root=APP_ROOT,
        uploads_dir=UPLOADS_DIR,
        safe_int_arg=_safe_int_arg,
        load_exam_manifest=load_exam_manifest,
        exam_responses_path=exam_responses_path,
        compute_exam_totals=compute_exam_totals,
        exam_analysis_get=exam_analysis_get,
        parse_score_value=parse_score_value,
        exam_questions_path=exam_questions_path,
        read_questions_csv=read_questions_csv,
        execute_chart_exec=execute_chart_exec,
    )

def _exam_longform_deps():
    return ExamLongformDeps(
        data_dir=DATA_DIR,
        exam_students_list=exam_students_list,
        exam_get=exam_get,
        exam_analysis_get=exam_analysis_get,
        call_llm=call_llm,
        non_ws_len=_non_ws_len,
    )

def _exam_upload_parse_deps():
    return ExamUploadParseDeps(
        app_root=APP_ROOT,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        now_date_compact=lambda: datetime.now().date().isoformat().replace("-", ""),
        load_exam_job=load_exam_job,
        exam_job_path=exam_job_path,
        write_exam_job=write_exam_job,
        extract_text_from_file=extract_text_from_file,
        extract_text_from_pdf=extract_text_from_pdf,
        extract_text_from_image=extract_text_from_image,
        parse_xlsx_with_script=_parse_xlsx_with_script,
        xlsx_to_table_preview=xlsx_to_table_preview,
        xls_to_table_preview=xls_to_table_preview,
        llm_parse_exam_scores=llm_parse_exam_scores,
        build_exam_rows_from_parsed_scores=build_exam_rows_from_parsed_scores,
        parse_score_value=parse_score_value,
        write_exam_responses_csv=write_exam_responses_csv,
        parse_exam_answer_key_text=parse_exam_answer_key_text,
        write_exam_answers_csv=write_exam_answers_csv,
        compute_max_scores_from_rows=compute_max_scores_from_rows,
        write_exam_questions_csv=write_exam_questions_csv,
        apply_answer_key_to_responses_csv=apply_answer_key_to_responses_csv,
        compute_exam_totals=compute_exam_totals,
        copy2=shutil.copy2,
        diag_log=diag_log,
        parse_date_str=parse_date_str,
    )

def _exam_upload_confirm_deps():
    return ExamUploadConfirmDeps(
        app_root=APP_ROOT,
        data_dir=DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_exam_job=write_exam_job,
        load_exam_draft_override=_load_exam_draft_override_impl,
        parse_exam_answer_key_text=parse_exam_answer_key_text,
        write_exam_questions_csv=write_exam_questions_csv,
        write_exam_answers_csv=write_exam_answers_csv,
        load_exam_answer_key_from_csv=load_exam_answer_key_from_csv,
        ensure_questions_max_score=ensure_questions_max_score,
        apply_answer_key_to_responses_csv=apply_answer_key_to_responses_csv,
        run_script=run_script,
        diag_log=diag_log,
        copy2=shutil.copy2,
    )

def _exam_upload_start_deps():
    return ExamUploadStartDeps(
        parse_date_str=parse_date_str,
        exam_job_path=exam_job_path,
        sanitize_filename=sanitize_filename,
        save_upload_file=save_upload_file,
        write_exam_job=lambda job_id, updates, overwrite=False: write_exam_job(job_id, updates, overwrite=overwrite),
        enqueue_exam_job=enqueue_exam_job,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        diag_log=diag_log,
        uuid_hex=lambda: uuid.uuid4().hex,
    )

def _exam_upload_api_deps():
    return ExamUploadApiDeps(
        load_exam_job=load_exam_job,
        exam_job_path=exam_job_path,
        load_exam_draft_override=_load_exam_draft_override_impl,
        save_exam_draft_override=_save_exam_draft_override_impl,
        build_exam_upload_draft=_build_exam_upload_draft_impl,
        exam_upload_not_ready_detail=_exam_upload_not_ready_detail_impl,
        parse_exam_answer_key_text=parse_exam_answer_key_text,
        read_text_safe=read_text_safe,
        write_exam_job=lambda job_id, updates: write_exam_job(job_id, updates),
        confirm_exam_upload=lambda job_id, job, job_dir: _confirm_exam_upload_impl(
            job_id,
            job,
            job_dir,
            deps=_exam_upload_confirm_deps(),
        ),
    )

def _upload_llm_deps():
    return UploadLlmDeps(
        app_root=APP_ROOT,
        call_llm=call_llm,
        diag_log=diag_log,
        parse_list_value=parse_list_value,
        compute_requirements_missing=_compute_requirements_missing_impl,
        merge_requirements=lambda base, update, overwrite=False: _merge_requirements_impl(
            base,
            update,
            overwrite=overwrite,
        ),
        normalize_excel_cell=_normalize_excel_cell_impl,
    )

def _upload_text_deps():
    from .global_limits import GLOBAL_OCR_SEMAPHORE

    return UploadTextDeps(
        diag_log=diag_log,
        limit=_limit,
        ocr_semaphore=(_OCR_SEMAPHORE, GLOBAL_OCR_SEMAPHORE),
    )

def _content_catalog_deps():
    from .skills.loader import load_skills

    return ContentCatalogDeps(
        data_dir=DATA_DIR,
        app_root=APP_ROOT,
        load_profile_file=load_profile_file,
        load_skills=load_skills,
    )

def _chat_support_deps():
    return ChatSupportDeps(
        compile_system_prompt=compile_system_prompt,
        diag_log=diag_log,
        getenv=os.getenv,
    )

def _exam_overview_deps():
    return ExamOverviewDeps(
        data_dir=DATA_DIR,
        load_exam_manifest=load_exam_manifest,
        exam_responses_path=exam_responses_path,
        exam_questions_path=exam_questions_path,
        exam_analysis_draft_path=exam_analysis_draft_path,
        read_questions_csv=read_questions_csv,
        compute_exam_totals=compute_exam_totals,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _exam_catalog_deps():
    return ExamCatalogDeps(
        data_dir=DATA_DIR,
        load_profile_file=load_profile_file,
    )

def _assignment_submission_attempt_deps():
    return AssignmentSubmissionAttemptDeps(
        student_submissions_dir=STUDENT_SUBMISSIONS_DIR,
        grade_count_conf_threshold=GRADE_COUNT_CONF_THRESHOLD,
    )

def _assignment_progress_deps():
    return AssignmentProgressDeps(
        data_dir=DATA_DIR,
        load_assignment_meta=load_assignment_meta,
        postprocess_assignment_meta=postprocess_assignment_meta,
        normalize_due_at=normalize_due_at,
        list_all_student_profiles=list_all_student_profiles,
        session_discussion_pass=_session_discussion_pass,
        list_submission_attempts=_list_submission_attempts,
        best_submission_attempt=_best_submission_attempt,
        resolve_assignment_date=resolve_assignment_date,
        atomic_write_json=_atomic_write_json,
        time_time=time.time,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _assignment_requirements_deps():
    return AssignmentRequirementsDeps(
        data_dir=DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _assignment_llm_gate_deps():
    return AssignmentLlmGateDeps(
        diag_log=diag_log,
        call_llm=call_llm,
    )

def _assignment_catalog_deps():
    return AssignmentCatalogDeps(
        data_dir=DATA_DIR,
        app_root=APP_ROOT,
        load_assignment_meta=load_assignment_meta,
        load_assignment_requirements=load_assignment_requirements,
        count_csv_rows=count_csv_rows,
        sanitize_filename=sanitize_filename,
    )

def _assignment_meta_postprocess_deps():
    return AssignmentMetaPostprocessDeps(
        data_dir=DATA_DIR,
        discussion_complete_marker=DISCUSSION_COMPLETE_MARKER,
        load_profile_file=load_profile_file,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        normalize_due_at=normalize_due_at,
        compute_expected_students=compute_expected_students,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _assignment_upload_parse_deps():
    return AssignmentUploadParseDeps(
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        now_monotonic=time.monotonic,
        load_upload_job=load_upload_job,
        upload_job_path=upload_job_path,
        write_upload_job=write_upload_job,
        extract_text_from_file=extract_text_from_file,
        llm_parse_assignment_payload=llm_parse_assignment_payload,
        compute_requirements_missing=compute_requirements_missing,
        llm_autofill_requirements=llm_autofill_requirements,
        diag_log=diag_log,
    )

def _assignment_upload_legacy_deps():
    return AssignmentUploadLegacyDeps(
        data_dir=DATA_DIR,
        parse_date_str=parse_date_str,
        sanitize_filename=sanitize_filename,
        save_upload_file=save_upload_file,
        extract_text_from_pdf=extract_text_from_pdf,
        extract_text_from_image=extract_text_from_image,
        llm_parse_assignment_payload=llm_parse_assignment_payload,
        write_uploaded_questions=write_uploaded_questions,
        compute_requirements_missing=compute_requirements_missing,
        llm_autofill_requirements=llm_autofill_requirements,
        save_assignment_requirements=save_assignment_requirements,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        load_assignment_meta=load_assignment_meta,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _assignment_today_deps():
    return AssignmentTodayDeps(
        data_dir=DATA_DIR,
        parse_date_str=parse_date_str,
        has_llm_key=lambda: bool(os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")),
        load_profile_file=load_profile_file,
        find_assignment_for_date=find_assignment_for_date,
        derive_kp_from_profile=derive_kp_from_profile,
        safe_assignment_id=safe_assignment_id,
        assignment_generate=assignment_generate,
        load_assignment_meta=load_assignment_meta,
        build_assignment_detail=build_assignment_detail,
    )

def _assignment_generate_deps():
    return AssignmentGenerateDeps(
        app_root=APP_ROOT,
        parse_date_str=parse_date_str,
        ensure_requirements_for_assignment=ensure_requirements_for_assignment,
        run_script=run_script,
        postprocess_assignment_meta=postprocess_assignment_meta,
        diag_log=diag_log,
    )

def _assignment_generate_tool_deps():
    return AssignmentGenerateToolDeps(
        app_root=APP_ROOT,
        parse_date_str=parse_date_str,
        ensure_requirements_for_assignment=ensure_requirements_for_assignment,
        run_script=run_script,
        postprocess_assignment_meta=postprocess_assignment_meta,
        diag_log=diag_log,
    )

def _assignment_uploaded_question_deps():
    return AssignmentUploadedQuestionDeps(
        safe_slug=safe_slug,
        normalize_difficulty=normalize_difficulty,
    )

def _assignment_questions_ocr_deps():
    return AssignmentQuestionsOcrDeps(
        uploads_dir=UPLOADS_DIR,
        app_root=APP_ROOT,
        run_script=run_script,
        sanitize_filename=sanitize_filename,
        sanitize_assignment_id=safe_slug,
    )

def _student_submit_deps():
    return StudentSubmitDeps(
        uploads_dir=UPLOADS_DIR,
        app_root=APP_ROOT,
        student_submissions_dir=STUDENT_SUBMISSIONS_DIR,
        run_script=run_script,
        sanitize_filename=sanitize_filename,
    )

def _assignment_upload_start_deps():
    return AssignmentUploadStartDeps(
        new_job_id=lambda: f"job_{uuid.uuid4().hex[:12]}",
        parse_date_str=parse_date_str,
        upload_job_path=upload_job_path,
        sanitize_filename=sanitize_filename,
        save_upload_file=save_upload_file,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        normalize_due_at=normalize_due_at,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_upload_job=lambda job_id, updates, overwrite=False: write_upload_job(job_id, updates, overwrite=overwrite),
        enqueue_upload_job=enqueue_upload_job,
        diag_log=diag_log,
    )

def _assignment_upload_query_deps():
    return AssignmentUploadQueryDeps(
        load_upload_job=load_upload_job,
        upload_job_path=upload_job_path,
        assignment_upload_not_ready_detail=_assignment_upload_not_ready_detail_impl,
        load_assignment_draft_override=_load_assignment_draft_override_impl,
        build_assignment_upload_draft=_build_assignment_upload_draft_impl,
        merge_requirements=merge_requirements,
        compute_requirements_missing=compute_requirements_missing,
        parse_list_value=parse_list_value,
    )

def _assignment_upload_draft_save_deps():
    return AssignmentUploadDraftSaveDeps(
        load_upload_job=load_upload_job,
        upload_job_path=upload_job_path,
        assignment_upload_not_ready_detail=_assignment_upload_not_ready_detail_impl,
        clean_assignment_draft_questions=_clean_assignment_draft_questions_impl,
        save_assignment_draft_override=_save_assignment_draft_override_impl,
        merge_requirements=merge_requirements,
        compute_requirements_missing=compute_requirements_missing,
        write_upload_job=write_upload_job,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _assignment_upload_confirm_deps():
    return AssignmentUploadConfirmDeps(
        data_dir=DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        discussion_complete_marker=DISCUSSION_COMPLETE_MARKER,
        write_upload_job=write_upload_job,
        merge_requirements=merge_requirements,
        compute_requirements_missing=compute_requirements_missing,
        write_uploaded_questions=write_uploaded_questions,
        parse_date_str=parse_date_str,
        save_assignment_requirements=save_assignment_requirements,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        normalize_due_at=normalize_due_at,
        compute_expected_students=compute_expected_students,
        atomic_write_json=_atomic_write_json,
        copy2=shutil.copy2,
    )

def _exam_api_deps():
    return ExamApiDeps(exam_get=exam_get)

def _exam_detail_deps():
    return ExamDetailDeps(
        load_exam_manifest=load_exam_manifest,
        exam_responses_path=exam_responses_path,
        exam_questions_path=exam_questions_path,
        read_questions_csv=read_questions_csv,
        parse_score_value=parse_score_value,
        safe_int_arg=_safe_int_arg,
    )

def _assignment_api_deps():
    def _assignment_exists(assignment_id: str) -> bool:
        try:
            return resolve_assignment_dir(str(assignment_id or "")).exists()
        except ValueError:
            return False

    return AssignmentApiDeps(
        build_assignment_detail=lambda assignment_id, include_text=True: build_assignment_detail(
            resolve_assignment_dir(str(assignment_id or "")),
            include_text=include_text,
        ),
        assignment_exists=_assignment_exists,
    )

def _student_profile_api_deps():
    return StudentProfileApiDeps(student_profile_get=student_profile_get)

def _student_import_deps():
    return StudentImportDeps(
        app_root=APP_ROOT,
        data_dir=DATA_DIR,
        load_profile_file=load_profile_file,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _student_directory_deps():
    return StudentDirectoryDeps(
        data_dir=DATA_DIR,
        load_profile_file=load_profile_file,
        normalize=normalize,
    )

def _student_ops_api_deps():
    return StudentOpsApiDeps(
        uploads_dir=UPLOADS_DIR,
        app_root=APP_ROOT,
        sanitize_filename=sanitize_filename,
        save_upload_file=save_upload_file,
        run_script=run_script,
        student_candidates_by_name=student_candidates_by_name,
        normalize=normalize,
        diag_log=diag_log,
    )

def _teacher_provider_registry_deps():
    return TeacherProviderRegistryDeps(
        model_registry=LLM_GATEWAY.registry,
        resolve_teacher_id=resolve_teacher_id,
        teacher_workspace_dir=teacher_workspace_dir,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        getenv=os.getenv,
    )

def _teacher_llm_routing_deps():
    return TeacherLlmRoutingDeps(
        model_registry=LLM_GATEWAY.registry,
        resolve_model_registry=lambda teacher_id: _merged_model_registry_impl(teacher_id, deps=_teacher_provider_registry_deps()),
        resolve_teacher_id=resolve_teacher_id,
        teacher_llm_routing_path=teacher_llm_routing_path,
        legacy_routing_path=LLM_ROUTING_PATH,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _teacher_routing_api_deps():
    return TeacherRoutingApiDeps(teacher_llm_routing_get=teacher_llm_routing_get)

def _chart_api_deps():
    return ChartApiDeps(
        chart_exec=lambda args: execute_chart_exec(args, app_root=APP_ROOT, uploads_dir=UPLOADS_DIR)
    )

def _chart_agent_run_deps():
    return ChartAgentRunDeps(
        safe_int_arg=_safe_int_arg,
        chart_bool=_chart_agent_bool_impl,
        chart_engine=_chart_agent_engine_impl,
        chart_packages=_chart_agent_packages_impl,
        chart_opencode_overrides=_chart_agent_opencode_overrides_impl,
        resolve_opencode_status=resolve_opencode_status,
        app_root=APP_ROOT,
        uploads_dir=UPLOADS_DIR,
        generate_candidate=lambda task, input_data, last_error, previous_code, attempt, max_retries: _chart_agent_generate_candidate_impl(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            max_retries,
            call_llm=call_llm,
            parse_json_from_text=parse_json_from_text,
        ),
        generate_candidate_opencode=lambda task, input_data, last_error, previous_code, attempt, max_retries, opencode_overrides: _chart_agent_generate_candidate_opencode_impl(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            max_retries,
            opencode_overrides,
            app_root=APP_ROOT,
            run_opencode_codegen=run_opencode_codegen,
        ),
        execute_chart_exec=execute_chart_exec,
        default_code=_chart_agent_default_code_impl,
    )

def _lesson_core_tool_deps():
    return LessonCaptureDeps(
        is_safe_tool_id=_is_safe_tool_id,
        resolve_app_path=_resolve_app_path,
        app_root=APP_ROOT,
        run_script=run_script,
    )

def _core_example_tool_deps():
    return CoreExampleToolDeps(
        data_dir=DATA_DIR,
        app_root=APP_ROOT,
        is_safe_tool_id=_is_safe_tool_id,
        resolve_app_path=_resolve_app_path,
        run_script=run_script,
    )

def _chat_runtime_deps():
    from .global_limits import (
        GLOBAL_LLM_SEMAPHORE,
        GLOBAL_LLM_SEMAPHORE_STUDENT,
        GLOBAL_LLM_SEMAPHORE_TEACHER,
    )

    return ChatRuntimeDeps(
        gateway=LLM_GATEWAY,
        limit=_limit,
        # Order is important: tenant -> global, and within each: total -> role.
        default_limiter=(
            _LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE,
        ),
        student_limiter=(
            _LLM_SEMAPHORE,
            _LLM_SEMAPHORE_STUDENT,
            GLOBAL_LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE_STUDENT,
        ),
        teacher_limiter=(
            _LLM_SEMAPHORE,
            _LLM_SEMAPHORE_TEACHER,
            GLOBAL_LLM_SEMAPHORE,
            GLOBAL_LLM_SEMAPHORE_TEACHER,
        ),
        resolve_teacher_id=resolve_teacher_id,
        resolve_teacher_model_registry=lambda teacher_id: _merged_model_registry_impl(teacher_id, deps=_teacher_provider_registry_deps()),
        resolve_teacher_provider_target=lambda teacher_id, provider, mode, model: _resolve_provider_target_impl(
            teacher_id,
            provider,
            mode,
            model,
            deps=_teacher_provider_registry_deps(),
        ),
        ensure_teacher_routing_file=_ensure_teacher_routing_file,
        routing_config_path_for_role=routing_config_path_for_role,
        diag_log=diag_log,
        monotonic=time.monotonic,
    )

def _chat_job_repo_deps():
    return ChatJobRepositoryDeps(
        chat_job_dir=CHAT_JOB_DIR,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _chat_worker_started_get() -> bool:
    return bool(CHAT_JOB_WORKER_STARTED)

def _chat_worker_started_set(value: bool) -> None:
    global CHAT_JOB_WORKER_STARTED
    CHAT_JOB_WORKER_STARTED = bool(value)

def _chat_worker_deps():
    return ChatWorkerDeps(
        chat_job_dir=CHAT_JOB_DIR,
        chat_job_lock=CHAT_JOB_LOCK,
        chat_job_event=CHAT_JOB_EVENT,
        stop_event=CHAT_WORKER_STOP_EVENT,
        chat_worker_threads=CHAT_WORKER_THREADS,
        chat_worker_pool_size=CHAT_WORKER_POOL_SIZE,
        worker_started_get=_chat_worker_started_get,
        worker_started_set=_chat_worker_started_set,
        load_chat_job=load_chat_job,
        write_chat_job=lambda job_id, updates: write_chat_job(job_id, updates),
        resolve_chat_lane_id_from_job=resolve_chat_lane_id_from_job,
        chat_enqueue_locked=_chat_enqueue_locked,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_pick_next_locked=_chat_pick_next_locked,
        chat_mark_done_locked=_chat_mark_done_locked,
        chat_has_pending_locked=_chat_has_pending_locked,
        process_chat_job=process_chat_job,
        diag_log=diag_log,
        sleep=time.sleep,
        thread_factory=lambda *args, **kwargs: threading.Thread(*args, **kwargs),
    )

def _chat_start_deps():
    return ChatStartDeps(
        http_error=lambda code, detail: HTTPException(status_code=code, detail=detail),
        get_chat_job_id_by_request=get_chat_job_id_by_request,
        load_chat_job=load_chat_job,
        detect_role_hint=_detect_role_hint,
        resolve_student_session_id=resolve_student_session_id,
        resolve_teacher_id=resolve_teacher_id,
        resolve_chat_lane_id=resolve_chat_lane_id,
        chat_last_user_text=_chat_last_user_text,
        chat_text_fingerprint=_chat_text_fingerprint,
        chat_job_lock=CHAT_JOB_LOCK,
        chat_recent_job_locked=_chat_recent_job_locked,
        upsert_chat_request_index=upsert_chat_request_index,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_lane_max_queue=CHAT_LANE_MAX_QUEUE,
        chat_request_map_set_if_absent=_chat_request_map_set_if_absent,
        new_job_id=lambda: f"cjob_{uuid.uuid4().hex[:12]}",
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_chat_job=lambda job_id, updates, overwrite=False: write_chat_job(job_id, updates, overwrite=overwrite),
        enqueue_chat_job=lambda job_id, lane_id=None: enqueue_chat_job(job_id, lane_id=lane_id),
        chat_register_recent_locked=_chat_register_recent_locked,
        append_student_session_message=append_student_session_message,
        update_student_session_index=update_student_session_index,
        append_teacher_session_message=append_teacher_session_message,
        update_teacher_session_index=update_teacher_session_index,
        parse_date_str=parse_date_str,
    )

def _chat_status_deps():
    return ChatStatusDeps(
        load_chat_job=load_chat_job,
        enqueue_chat_job=lambda job_id, lane_id: enqueue_chat_job(job_id, lane_id=lane_id),
        resolve_chat_lane_id_from_job=resolve_chat_lane_id_from_job,
        chat_job_lock=CHAT_JOB_LOCK,
        chat_lane_load_locked=_chat_lane_load_locked,
        chat_find_position_locked=_chat_find_position_locked,
    )

def _session_history_api_deps():
    return SessionHistoryApiDeps(
        load_student_sessions_index=load_student_sessions_index,
        load_teacher_sessions_index=load_teacher_sessions_index,
        paginate_session_items=lambda items, cursor, limit: _paginate_session_items_impl(items, cursor=cursor, limit=limit),
        load_student_session_view_state=load_student_session_view_state,
        load_teacher_session_view_state=load_teacher_session_view_state,
        normalize_session_view_state_payload=_normalize_session_view_state_payload_impl,
        compare_iso_ts=_compare_iso_ts_impl,
        now_iso_millis=lambda: datetime.now().isoformat(timespec="milliseconds"),
        save_student_session_view_state=save_student_session_view_state,
        save_teacher_session_view_state=save_teacher_session_view_state,
        student_session_file=student_session_file,
        teacher_session_file=teacher_session_file,
        load_session_messages=_load_session_messages_impl,
        resolve_teacher_id=resolve_teacher_id,
    )

def _compute_chat_reply_deps():
    return ComputeChatReplyDeps(
        detect_role=detect_role,
        diag_log=diag_log,
        teacher_assignment_preflight=teacher_assignment_preflight,
        resolve_teacher_id=resolve_teacher_id,
        teacher_build_context=lambda teacher_id, query, max_chars, session_id: teacher_build_context(
            teacher_id,
            query=query,
            max_chars=max_chars,
            session_id=session_id,
        ),
        detect_student_study_trigger=detect_student_study_trigger,
        load_profile_file=load_profile_file,
        data_dir=DATA_DIR,
        build_verified_student_context=build_verified_student_context,
        build_assignment_detail_cached=build_assignment_detail_cached,
        find_assignment_for_date=find_assignment_for_date,
        parse_date_str=parse_date_str,
        build_assignment_context=build_assignment_context,
        chat_extra_system_max_chars=CHAT_EXTRA_SYSTEM_MAX_CHARS,
        trim_messages=lambda messages, role_hint=None: _trim_messages(messages, role_hint=role_hint),
        student_inflight=_student_inflight,
        run_agent=run_agent,
        normalize_math_delimiters=normalize_math_delimiters,
        resolve_effective_skill=lambda role_hint, requested_skill_id, last_user_text: _resolve_effective_skill_impl(
            app_root=APP_ROOT,
            role_hint=role_hint,
            requested_skill_id=requested_skill_id,
            last_user_text=last_user_text,
            detect_assignment_intent=detect_assignment_intent,
        ),
    )

def _chat_job_process_deps():
    return ChatJobProcessDeps(
        chat_job_claim_path=_chat_job_claim_path,
        try_acquire_lockfile=_try_acquire_lockfile,
        chat_job_claim_ttl_sec=CHAT_JOB_CLAIM_TTL_SEC,
        load_chat_job=load_chat_job,
        write_chat_job=lambda job_id, updates: write_chat_job(job_id, updates),
        chat_request_model=ChatRequest,
        compute_chat_reply_sync=lambda req, session_id, teacher_id_override: _compute_chat_reply_sync(
            req,
            session_id=session_id,
            teacher_id_override=teacher_id_override,
        ),
        monotonic=time.monotonic,
        build_interaction_note=build_interaction_note,
        profile_update_async=PROFILE_UPDATE_ASYNC,
        enqueue_profile_update=enqueue_profile_update,
        student_profile_update=student_profile_update,
        resolve_student_session_id=resolve_student_session_id,
        append_student_session_message=append_student_session_message,
        update_student_session_index=update_student_session_index,
        parse_date_str=parse_date_str,
        resolve_teacher_id=resolve_teacher_id,
        ensure_teacher_workspace=ensure_teacher_workspace,
        append_teacher_session_message=append_teacher_session_message,
        update_teacher_session_index=update_teacher_session_index,
        teacher_memory_auto_propose_from_turn=teacher_memory_auto_propose_from_turn,
        teacher_memory_auto_flush_from_session=teacher_memory_auto_flush_from_session,
        maybe_compact_teacher_session=maybe_compact_teacher_session,
        diag_log=diag_log,
        release_lockfile=_release_lockfile,
    )

def _teacher_mem0_search(teacher_id: str, query: str, limit: int) -> Dict[str, Any]:
    try:
        from .mem0_adapter import teacher_mem0_search
    except Exception:
        return {"ok": False, "matches": []}
    return teacher_mem0_search(teacher_id, query, limit=limit)

def _teacher_mem0_should_index_target(target: str) -> bool:
    try:
        from .mem0_adapter import teacher_mem0_should_index_target
    except Exception:
        return False
    try:
        return bool(teacher_mem0_should_index_target(target))
    except Exception:
        return False

def _teacher_mem0_index_entry(teacher_id: str, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    from .mem0_adapter import teacher_mem0_index_entry

    return teacher_mem0_index_entry(teacher_id, text, metadata=metadata)

def _teacher_memory_search_deps():
    return TeacherMemorySearchDeps(
        ensure_teacher_workspace=ensure_teacher_workspace,
        mem0_search=_teacher_mem0_search,
        search_filter_expired=TEACHER_MEMORY_SEARCH_FILTER_EXPIRED,
        load_record=_teacher_memory_load_record,
        is_expired_record=lambda rec: _teacher_memory_is_expired_record(rec),
        diag_log=diag_log,
        log_event=_teacher_memory_log_event,
        teacher_workspace_file=teacher_workspace_file,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )

def _teacher_memory_insights_deps():
    return TeacherMemoryInsightsDeps(
        ensure_teacher_workspace=ensure_teacher_workspace,
        recent_proposals=lambda teacher_id, limit: _teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: _teacher_memory_is_expired_record(rec, now=now),
        priority_score=_teacher_memory_priority_score,
        rank_score=_teacher_memory_rank_score,
        age_days=lambda rec, now: _teacher_memory_age_days(rec, now=now),
        load_events=lambda teacher_id, limit: _teacher_memory_load_events(teacher_id, limit=limit),
        parse_dt=_teacher_memory_parse_dt,
    )

def _teacher_memory_apply_deps():
    return TeacherMemoryApplyDeps(
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        log_event=_teacher_memory_log_event,
        is_sensitive=_teacher_memory_is_sensitive,
        auto_apply_strict=TEACHER_MEMORY_AUTO_APPLY_STRICT,
        teacher_daily_memory_path=teacher_daily_memory_path,
        teacher_workspace_file=teacher_workspace_file,
        find_conflicting_applied=lambda teacher_id, proposal_id, target, content: _teacher_memory_find_conflicting_applied(
            teacher_id,
            proposal_id=proposal_id,
            target=target,
            content=content,
        ),
        record_ttl_days=_teacher_memory_record_ttl_days,
        record_expire_at=_teacher_memory_record_expire_at,
        is_expired_record=_teacher_memory_is_expired_record,
        mark_superseded=lambda teacher_id, proposal_ids, by_proposal_id: _teacher_memory_mark_superseded(
            teacher_id,
            proposal_ids,
            by_proposal_id=by_proposal_id,
        ),
        diag_log=diag_log,
        mem0_should_index_target=_teacher_mem0_should_index_target,
        mem0_index_entry=_teacher_mem0_index_entry,
    )

def _teacher_memory_propose_deps():
    return TeacherMemoryProposeDeps(
        ensure_teacher_workspace=ensure_teacher_workspace,
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        uuid_hex=lambda: uuid.uuid4().hex,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        priority_score=_teacher_memory_priority_score,
        record_ttl_days=_teacher_memory_record_ttl_days,
        record_expire_at=_teacher_memory_record_expire_at,
        auto_apply_enabled=TEACHER_MEMORY_AUTO_APPLY_ENABLED,
        auto_apply_targets=TEACHER_MEMORY_AUTO_APPLY_TARGETS,
        apply=lambda teacher_id, proposal_id, approve: teacher_memory_apply(
            teacher_id,
            proposal_id,
            approve=approve,
        ),
    )

def _teacher_memory_record_deps():
    return TeacherMemoryRecordDeps(
        ensure_teacher_workspace=ensure_teacher_workspace,
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_session_file=teacher_session_file,
        load_teacher_sessions_index=load_teacher_sessions_index,
        save_teacher_sessions_index=save_teacher_sessions_index,
        session_index_max_items=SESSION_INDEX_MAX_ITEMS,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        norm_text=_teacher_memory_norm_text,
        loose_match=_teacher_memory_loose_match,
        conflicts=_teacher_memory_conflicts,
        auto_infer_enabled=TEACHER_MEMORY_AUTO_INFER_ENABLED,
        auto_infer_min_chars=TEACHER_MEMORY_AUTO_INFER_MIN_CHARS,
        auto_infer_block_patterns=_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        auto_infer_stable_patterns=_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
        auto_infer_lookback_turns=TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS,
        auto_infer_min_repeats=TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS,
        auto_max_proposals_per_day=TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
    )

def _teacher_memory_store_deps():
    return TeacherMemoryStoreDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        proposal_path=_teacher_proposal_path,
        recent_proposals=lambda teacher_id, limit: _teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: _teacher_memory_is_expired_record(rec, now=now),
        rank_score=_teacher_memory_rank_score,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )

def _teacher_memory_auto_deps():
    return TeacherMemoryAutoDeps(
        auto_enabled=TEACHER_MEMORY_AUTO_ENABLED,
        auto_min_content_chars=TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS,
        auto_infer_min_priority=TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY,
        auto_flush_enabled=TEACHER_MEMORY_FLUSH_ENABLED,
        session_compact_enabled=TEACHER_SESSION_COMPACT_ENABLED,
        session_compact_max_messages=TEACHER_SESSION_COMPACT_MAX_MESSAGES,
        memory_flush_margin_messages=TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES,
        memory_flush_max_source_chars=TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS,
        durable_intent_patterns=_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        norm_text=_teacher_memory_norm_text,
        auto_infer_candidate=_teacher_memory_auto_infer_candidate,
        auto_quota_reached=_teacher_memory_auto_quota_reached,
        stable_hash=_teacher_memory_stable_hash,
        priority_score=_teacher_memory_priority_score,
        log_event=_teacher_memory_log_event,
        find_duplicate=_teacher_memory_find_duplicate,
        memory_propose=teacher_memory_propose,
        session_compaction_cycle_no=_teacher_session_compaction_cycle_no,
        session_index_item=_teacher_session_index_item,
        teacher_session_file=teacher_session_file,
        compact_transcript=_teacher_compact_transcript,
        mark_session_memory_flush=_mark_teacher_session_memory_flush,
    )

def _teacher_workspace_deps():
    return TeacherWorkspaceDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )

def _teacher_context_deps():
    return TeacherContextDeps(
        ensure_teacher_workspace=ensure_teacher_workspace,
        teacher_read_text=teacher_read_text,
        teacher_workspace_file=teacher_workspace_file,
        teacher_memory_context_text=_teacher_memory_context_text,
        include_session_summary=TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
        session_summary_max_chars=TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
        teacher_session_summary_text=_teacher_session_summary_text,
        teacher_memory_log_event=_teacher_memory_log_event,
    )

def _teacher_assignment_preflight_deps():
    return TeacherAssignmentPreflightDeps(
        app_root=APP_ROOT,
        detect_assignment_intent=detect_assignment_intent,
        llm_assignment_gate=llm_assignment_gate,
        diag_log=diag_log,
        allowed_tools=allowed_tools,
        parse_date_str=parse_date_str,
        today_iso=today_iso,
        format_requirements_prompt=format_requirements_prompt,
        save_assignment_requirements=save_assignment_requirements,
        assignment_generate=assignment_generate,
    )

def _teacher_session_compaction_deps():
    return TeacherSessionCompactionDeps(
        compact_enabled=TEACHER_SESSION_COMPACT_ENABLED,
        compact_main_only=TEACHER_SESSION_COMPACT_MAIN_ONLY,
        compact_max_messages=TEACHER_SESSION_COMPACT_MAX_MESSAGES,
        compact_keep_tail=TEACHER_SESSION_COMPACT_KEEP_TAIL,
        chat_max_messages_teacher=CHAT_MAX_MESSAGES_TEACHER,
        teacher_compact_allowed=_teacher_compact_allowed,
        teacher_session_file=teacher_session_file,
        teacher_compact_summary=_teacher_compact_summary,
        write_teacher_session_records=_write_teacher_session_records,
        mark_teacher_session_compacted=_mark_teacher_session_compacted,
        diag_log=diag_log,
    )

def _agent_runtime_deps():
    return AgentRuntimeDeps(
        app_root=APP_ROOT,
        build_system_prompt=build_system_prompt,
        diag_log=diag_log,
        load_skill_runtime=lambda role_hint, skill_id: _default_load_skill_runtime_impl(APP_ROOT, role_hint, skill_id),
        allowed_tools=allowed_tools,
        max_tool_rounds=CHAT_MAX_TOOL_ROUNDS,
        max_tool_calls=CHAT_MAX_TOOL_CALLS,
        extract_min_chars_requirement=extract_min_chars_requirement,
        extract_exam_id=extract_exam_id,
        is_exam_analysis_request=is_exam_analysis_request,
        build_exam_longform_context=build_exam_longform_context,
        generate_longform_reply=_generate_longform_reply,
        call_llm=call_llm,
        tool_dispatch=tool_dispatch,
        teacher_tools_to_openai=_default_teacher_tools_to_openai_impl,
    )

def _chat_api_deps():
    return ChatApiDeps(start_chat=_chat_start_orchestration)

def _teacher_memory_api_deps():
    return TeacherMemoryApiDeps(
        resolve_teacher_id=resolve_teacher_id,
        teacher_memory_list_proposals=teacher_memory_list_proposals,
        teacher_memory_apply=teacher_memory_apply,
    )

async def exams():
    return list_exams()

async def exam_detail(exam_id: str):
    result = _get_exam_detail_api_impl(exam_id, deps=_exam_api_deps())
    if result.get("error") == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def exam_analysis(exam_id: str):
    result = exam_analysis_get(exam_id)
    if result.get("error") == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def exam_students(exam_id: str, limit: int = 50):
    result = exam_students_list(exam_id, limit=limit)
    if result.get("error") == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def exam_student(exam_id: str, student_id: str):
    result = exam_student_detail(exam_id, student_id=student_id)
    if result.get("error") == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def exam_question(exam_id: str, question_id: str):
    result = exam_question_detail(exam_id, question_id=question_id)
    if result.get("error") == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def assignments():
    return list_assignments()

async def teacher_assignment_progress(assignment_id: str, include_students: bool = True):
    assignment_id = (assignment_id or "").strip()
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    result = compute_assignment_progress(assignment_id, include_students=bool(include_students))
    if not result.get("ok") and result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    return result

async def teacher_assignments_progress(date: Optional[str] = None):
    date_str = parse_date_str(date)
    items = list_assignments().get("assignments") or []
    out: List[Dict[str, Any]] = []
    for it in items:
        if (it.get("date") or "") != date_str:
            continue
        aid = str(it.get("assignment_id") or "")
        if not aid:
            continue
        prog = compute_assignment_progress(aid, include_students=False)
        if prog.get("ok"):
            out.append(prog)
    out.sort(key=lambda x: (x.get("updated_at") or ""), reverse=True)
    return {"ok": True, "date": date_str, "assignments": out}

async def assignment_requirements(req: AssignmentRequirementsRequest):
    date_str = parse_date_str(req.date)
    result = save_assignment_requirements(
        req.assignment_id,
        req.requirements,
        date_str,
        created_by=req.created_by or "teacher",
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def assignment_requirements_get(assignment_id: str):
    try:
        folder = resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment not found")
    requirements = load_assignment_requirements(folder)
    if not requirements:
        return {"assignment_id": assignment_id, "requirements": None}
    return {"assignment_id": assignment_id, "requirements": requirements}

async def assignment_upload(
    assignment_id: str = Form(...),
    date: Optional[str] = Form(""),
    scope: Optional[str] = Form(""),
    class_name: Optional[str] = Form(""),
    student_ids: Optional[str] = Form(""),
    files: list[UploadFile] = File(...),
    answer_files: Optional[list[UploadFile]] = File(None),
    ocr_mode: Optional[str] = Form("FREE_OCR"),
    language: Optional[str] = Form("zh"),
):
    try:
        return await _assignment_upload_legacy_impl(
            deps=_assignment_upload_legacy_deps(),
            assignment_id=assignment_id,
            date=date,
            scope=scope,
            class_name=class_name,
            student_ids=student_ids,
            files=files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
        )
    except AssignmentUploadLegacyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def exam_upload_start(
    exam_id: Optional[str] = Form(""),
    date: Optional[str] = Form(""),
    class_name: Optional[str] = Form(""),
    paper_files: list[UploadFile] = File(...),
    score_files: list[UploadFile] = File(...),
    answer_files: Optional[list[UploadFile]] = File(None),
    ocr_mode: Optional[str] = Form("FREE_OCR"),
    language: Optional[str] = Form("zh"),
):
    try:
        return await _start_exam_upload_impl(
            exam_id,
            date,
            class_name,
            paper_files,
            score_files,
            answer_files,
            ocr_mode,
            language,
            deps=_exam_upload_start_deps(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

async def exam_upload_status(job_id: str):
    try:
        return _exam_upload_status_api_impl(job_id, deps=_exam_upload_api_deps())
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def exam_upload_draft(job_id: str):
    try:
        return _exam_upload_draft_api_impl(job_id, deps=_exam_upload_api_deps())
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest):
    try:
        return _exam_upload_draft_save_api_impl(
            job_id=req.job_id,
            meta=req.meta,
            questions=req.questions,
            score_schema=req.score_schema,
            answer_key_text=req.answer_key_text,
            deps=_exam_upload_api_deps(),
        )
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def exam_upload_confirm(req: ExamUploadConfirmRequest):
    try:
        return _exam_upload_confirm_api_impl(req.job_id, deps=_exam_upload_api_deps())
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_upload_start(
    assignment_id: str = Form(...),
    date: Optional[str] = Form(""),
    due_at: Optional[str] = Form(""),
    scope: Optional[str] = Form(""),
    class_name: Optional[str] = Form(""),
    student_ids: Optional[str] = Form(""),
    files: list[UploadFile] = File(...),
    answer_files: Optional[list[UploadFile]] = File(None),
    ocr_mode: Optional[str] = Form("FREE_OCR"),
    language: Optional[str] = Form("zh"),
):
    try:
        return await _start_assignment_upload_impl(
            assignment_id=assignment_id,
            date=date,
            due_at=due_at,
            scope=scope,
            class_name=class_name,
            student_ids=student_ids,
            files=files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=_assignment_upload_start_deps(),
        )
    except AssignmentUploadStartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_upload_status(job_id: str):
    try:
        return _get_assignment_upload_status_impl(job_id, deps=_assignment_upload_query_deps())
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_upload_draft(job_id: str):
    try:
        return _get_assignment_upload_draft_impl(job_id, deps=_assignment_upload_query_deps())
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_upload_draft_save(req: UploadDraftSaveRequest):
    try:
        return _save_assignment_upload_draft_impl(
            req.job_id,
            req.requirements,
            req.questions,
            deps=_assignment_upload_draft_save_deps(),
        )
    except AssignmentUploadDraftSaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_upload_confirm(req: UploadConfirmRequest):
    try:
        job = load_upload_job(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")

    try:
        ready = _ensure_assignment_upload_confirm_ready_impl(job)
    except AssignmentUploadConfirmGateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if ready is not None:
        return ready

    strict = True if req.strict_requirements is None else bool(req.strict_requirements)
    job_dir = upload_job_path(req.job_id)
    try:
        return _confirm_assignment_upload_impl(
            req.job_id,
            job,
            job_dir,
            requirements_override=req.requirements_override,
            strict_requirements=strict,
            deps=_assignment_upload_confirm_deps(),
        )
    except AssignmentUploadConfirmError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def assignment_download(assignment_id: str, file: str):
    try:
        assignment_dir = resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    folder = (assignment_dir / "source").resolve()
    if assignment_dir not in folder.parents:
        raise HTTPException(status_code=400, detail="invalid assignment_id path")
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment source not found")
    safe_name = sanitize_filename(file)
    if not safe_name:
        raise HTTPException(status_code=400, detail="invalid file")
    path = (folder / safe_name).resolve()
    if path != folder and folder not in path.parents:
        raise HTTPException(status_code=400, detail="invalid file path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)

async def assignment_today(
    student_id: str,
    date: Optional[str] = None,
    auto_generate: bool = False,
    generate: bool = True,
    per_kp: int = 5,
):
    return _assignment_today_impl(
        student_id=student_id,
        date=date,
        auto_generate=auto_generate,
        generate=generate,
        per_kp=per_kp,
        deps=_assignment_today_deps(),
    )

async def assignment_detail(assignment_id: str):
    result = _get_assignment_detail_api_impl(assignment_id, deps=_assignment_api_deps())
    if result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def lessons():
    return list_lessons()

async def skills():
    return list_skills()

async def chart_image_file(run_id: str, file_name: str):
    path = resolve_chart_image_path(UPLOADS_DIR, run_id, file_name)
    if not path:
        raise HTTPException(status_code=404, detail="chart file not found")
    return FileResponse(path)

async def chart_run_meta(run_id: str):
    path = resolve_chart_run_meta_path(UPLOADS_DIR, run_id)
    if not path:
        raise HTTPException(status_code=404, detail="chart run not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="failed to read chart run meta")

async def teacher_llm_routing(
    teacher_id: Optional[str] = None,
    history_limit: int = 20,
    proposal_limit: int = 20,
    proposal_status: Optional[str] = None,
):
    result = _get_routing_api_impl(
        {
            "teacher_id": teacher_id,
            "history_limit": history_limit,
            "proposal_limit": proposal_limit,
            "proposal_status": proposal_status,
        },
        deps=_teacher_routing_api_deps(),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def teacher_llm_routing_simulate_api(req: RoutingSimulateRequest):
    result = teacher_llm_routing_simulate(model_dump_compat(req, exclude_none=True))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def teacher_llm_routing_proposals_api(req: RoutingProposalCreateRequest):
    result = teacher_llm_routing_propose(model_dump_compat(req, exclude_none=True))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def teacher_llm_routing_proposal_api(proposal_id: str, teacher_id: Optional[str] = None):
    result = teacher_llm_routing_proposal_get({"proposal_id": proposal_id, "teacher_id": teacher_id})
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def teacher_llm_routing_proposal_review_api(proposal_id: str, req: RoutingProposalReviewRequest):
    payload = model_dump_compat(req, exclude_none=True)
    payload["proposal_id"] = proposal_id
    result = teacher_llm_routing_apply(payload)
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def teacher_llm_routing_rollback_api(req: RoutingRollbackRequest):
    result = teacher_llm_routing_rollback(model_dump_compat(req, exclude_none=True))
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() in {"history_not_found", "target_version_not_found"} else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def teacher_provider_registry_api(teacher_id: Optional[str] = None):
    result = teacher_provider_registry_get({"teacher_id": teacher_id})
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def teacher_provider_registry_create_api(req: TeacherProviderRegistryCreateRequest):
    result = teacher_provider_registry_create(model_dump_compat(req, exclude_none=True))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

async def teacher_provider_registry_update_api(provider_id: str, req: TeacherProviderRegistryUpdateRequest):
    payload = model_dump_compat(req, exclude_none=True)
    payload["provider_id"] = provider_id
    result = teacher_provider_registry_update(payload)
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def teacher_provider_registry_delete_api(provider_id: str, req: TeacherProviderRegistryDeleteRequest):
    payload = model_dump_compat(req, exclude_none=True)
    payload["provider_id"] = provider_id
    result = teacher_provider_registry_delete(payload)
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def teacher_provider_registry_probe_models_api(provider_id: str, req: TeacherProviderRegistryProbeRequest):
    payload = model_dump_compat(req, exclude_none=True)
    payload["provider_id"] = provider_id
    result = teacher_provider_registry_probe_models(payload)
    if not result.get("ok"):
        status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result

async def generate_assignment(
    assignment_id: str = Form(...),
    kp: str = Form(""),
    question_ids: Optional[str] = Form(""),
    per_kp: int = Form(5),
    core_examples: Optional[str] = Form(""),
    generate: bool = Form(False),
    mode: Optional[str] = Form(""),
    date: Optional[str] = Form(""),
    due_at: Optional[str] = Form(""),
    class_name: Optional[str] = Form(""),
    student_ids: Optional[str] = Form(""),
    source: Optional[str] = Form(""),
    requirements_json: Optional[str] = Form(""),
):
    try:
        return _generate_assignment_impl(
            assignment_id=assignment_id,
            kp=kp,
            question_ids=question_ids,
            per_kp=per_kp,
            core_examples=core_examples,
            generate=generate,
            mode=mode,
            date=date,
            due_at=due_at,
            class_name=class_name,
            student_ids=student_ids,
            source=source,
            requirements_json=requirements_json,
            deps=_assignment_generate_deps(),
        )
    except AssignmentGenerateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

async def render_assignment(assignment_id: str = Form(...)):
    script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
    out = run_script(["python3", str(script), "--assignment-id", assignment_id])
    return {"ok": True, "output": out}

async def assignment_questions_ocr(
    assignment_id: str = Form(...),
    files: list[UploadFile] = File(...),
    kp_id: Optional[str] = Form("uncategorized"),
    difficulty: Optional[str] = Form("basic"),
    tags: Optional[str] = Form("ocr"),
    ocr_mode: Optional[str] = Form("FREE_OCR"),
    language: Optional[str] = Form("zh"),
):
    return await _assignment_questions_ocr_impl(
        assignment_id=assignment_id,
        files=files,
        kp_id=kp_id,
        difficulty=difficulty,
        tags=tags,
        ocr_mode=ocr_mode,
        language=language,
        deps=_assignment_questions_ocr_deps(),
    )

async def submit(
    student_id: str = Form(...),
    files: list[UploadFile] = File(...),
    assignment_id: Optional[str] = Form(None),
    auto_assignment: bool = Form(False),
):
    return await _student_submit_impl(
        student_id=student_id,
        files=files,
        assignment_id=assignment_id,
        auto_assignment=auto_assignment,
        deps=_student_submit_deps(),
    )


register_routes(app, sys.modules[__name__])

# ---- Dynamic tenants root wiring (in-process multi-tenancy) ----
#
# Keep the existing FastAPI instance (with all legacy routes) as the default tenant,
# and expose a root ASGI dispatcher as the module-level `app`.
#
# Important: this MUST only run for the canonical module name. Tenant app instances
# are loaded as separate module copies (e.g. "services.api._tenant_xxx") and must
# keep `app` as the tenant FastAPI instance (no recursion to dispatcher).
if __name__ == "services.api.app":
    _DEFAULT_APP = app

    TENANT_ADMIN_KEY = str(os.getenv("TENANT_ADMIN_KEY", "") or "").strip()
    TENANT_DB_PATH = Path(
        os.getenv(
            "TENANT_DB_PATH",
            str(APP_ROOT / "data" / "_system" / "tenants.sqlite3"),
        )
    )

    try:
        from .tenant_admin_api import TenantAdminDeps, create_admin_app
        from .tenant_config_store import TenantConfigStore
        from .tenant_dispatcher import MultiTenantDispatcher
        from .tenant_registry import TenantRegistry

        _TENANT_STORE = TenantConfigStore(TENANT_DB_PATH)
        _TENANT_REGISTRY = TenantRegistry(_TENANT_STORE)
        _ADMIN_APP = create_admin_app(
            deps=TenantAdminDeps(
                admin_key=TENANT_ADMIN_KEY,
                store=_TENANT_STORE,
                registry=_TENANT_REGISTRY,
            )
        )

        app = MultiTenantDispatcher(default_app=_DEFAULT_APP, admin_app=_ADMIN_APP, registry=_TENANT_REGISTRY)
    except Exception:
        # Fall back to legacy single-tenant behavior if tenant modules fail to load.
        app = _DEFAULT_APP
