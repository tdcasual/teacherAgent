from __future__ import annotations

# Compatibility import registry used by app_core facade.
# ruff: noqa: F401,I001

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
from .student_persona_api_service import (
    StudentPersonaApiDeps,
    resolve_student_persona_runtime as _resolve_student_persona_runtime_impl,
    resolve_student_persona_avatar_path as _resolve_student_persona_avatar_path_impl,
    student_persona_activate_api as _student_persona_activate_api_impl,
    student_persona_avatar_upload_api as _student_persona_avatar_upload_api_impl,
    student_persona_custom_create_api as _student_persona_custom_create_api_impl,
    student_persona_custom_update_api as _student_persona_custom_update_api_impl,
    student_persona_custom_delete_api as _student_persona_custom_delete_api_impl,
    student_personas_get_api as _student_personas_get_api_impl,
)
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
from .teacher_persona_api_service import (
    TeacherPersonaApiDeps,
    resolve_teacher_persona_avatar_path as _resolve_teacher_persona_avatar_path_impl,
    teacher_persona_assign_api as _teacher_persona_assign_api_impl,
    teacher_persona_avatar_upload_api as _teacher_persona_avatar_upload_api_impl,
    teacher_persona_create_api as _teacher_persona_create_api_impl,
    teacher_persona_update_api as _teacher_persona_update_api_impl,
    teacher_persona_visibility_api as _teacher_persona_visibility_api_impl,
    teacher_personas_get_api as _teacher_personas_get_api_impl,
)
from .tool_dispatch_service import ToolDispatchDeps, tool_dispatch as _tool_dispatch_impl
from .upload_io_service import sanitize_filename_io
from .chat_lane_store_factory import get_chat_lane_store
from services.api.queue.queue_backend import rq_enabled as _rq_enabled_impl
from services.api.runtime import queue_runtime
from services.api.runtime.inline_backend_factory import build_inline_backend
from services.api.runtime.runtime_state import reset_runtime_state as _reset_runtime_state
from services.api.workers.inline_runtime import start_inline_workers, stop_inline_workers

__all__ = [name for name in globals() if not name.startswith("__")]
