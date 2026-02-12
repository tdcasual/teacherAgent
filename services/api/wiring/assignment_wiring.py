"""Assignment domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "_assignment_handlers_deps",
    "_assignment_upload_handlers_deps",
    "_assignment_io_handlers_deps",
    "_assignment_submission_attempt_deps",
    "_assignment_progress_deps",
    "_assignment_requirements_deps",
    "_assignment_llm_gate_deps",
    "_assignment_catalog_deps",
    "_assignment_meta_postprocess_deps",
    "_assignment_upload_parse_deps",
    "_assignment_upload_legacy_deps",
    "_assignment_today_deps",
    "_assignment_generate_deps",
    "_assignment_generate_tool_deps",
    "_assignment_uploaded_question_deps",
    "_assignment_questions_ocr_deps",
    "_assignment_upload_start_deps",
    "_assignment_upload_query_deps",
    "_assignment_upload_draft_save_deps",
    "_assignment_upload_confirm_deps",
    "_assignment_api_deps",
]

import os
import shutil
import time
import uuid
from datetime import datetime

from services.api.runtime import queue_runtime

from ..assignment_api_service import (
    AssignmentApiDeps,
)
from ..assignment_api_service import (
    get_assignment_detail_api as _get_assignment_detail_api_impl,
)
from ..assignment_catalog_service import (
    AssignmentCatalogDeps,
    AssignmentMetaPostprocessDeps,
)
from ..assignment_generate_service import (
    AssignmentGenerateDeps,
)
from ..assignment_generate_service import (
    generate_assignment as _generate_assignment_impl,
)
from ..assignment_generate_tool_service import AssignmentGenerateToolDeps
from ..assignment_llm_gate_service import AssignmentLlmGateDeps
from ..assignment_progress_service import AssignmentProgressDeps
from ..assignment_questions_ocr_service import (
    AssignmentQuestionsOcrDeps,
)
from ..assignment_questions_ocr_service import (
    assignment_questions_ocr as _assignment_questions_ocr_impl,
)
from ..assignment_requirements_service import AssignmentRequirementsDeps
from ..assignment_submission_attempt_service import AssignmentSubmissionAttemptDeps
from ..assignment_today_service import (
    AssignmentTodayDeps,
)
from ..assignment_today_service import (
    assignment_today as _assignment_today_impl,
)
from ..assignment_upload_confirm_gate_service import (
    ensure_assignment_upload_confirm_ready as _ensure_assignment_upload_confirm_ready_impl,
)
from ..assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
)
from ..assignment_upload_confirm_service import (
    confirm_assignment_upload as _confirm_assignment_upload_impl,
)
from ..assignment_upload_draft_save_service import (
    AssignmentUploadDraftSaveDeps,
)
from ..assignment_upload_draft_save_service import (
    save_assignment_upload_draft as _save_assignment_upload_draft_impl,
)
from ..assignment_upload_draft_service import (
    assignment_upload_not_ready_detail as _assignment_upload_not_ready_detail_impl,
)
from ..assignment_upload_draft_service import (
    build_assignment_upload_draft as _build_assignment_upload_draft_impl,
)
from ..assignment_upload_draft_service import (
    clean_assignment_draft_questions as _clean_assignment_draft_questions_impl,
)
from ..assignment_upload_draft_service import (
    load_assignment_draft_override as _load_assignment_draft_override_impl,
)
from ..assignment_upload_draft_service import (
    save_assignment_draft_override as _save_assignment_draft_override_impl,
)
from ..assignment_upload_legacy_service import (
    AssignmentUploadLegacyDeps,
)
from ..assignment_upload_legacy_service import (
    assignment_upload as _assignment_upload_legacy_impl,
)
from ..assignment_upload_parse_service import AssignmentUploadParseDeps
from ..assignment_upload_query_service import (
    AssignmentUploadQueryDeps,
)
from ..assignment_upload_query_service import (
    get_assignment_upload_draft as _get_assignment_upload_draft_impl,
)
from ..assignment_upload_query_service import (
    get_assignment_upload_status as _get_assignment_upload_status_impl,
)
from ..assignment_upload_start_service import (
    AssignmentUploadStartDeps,
)
from ..assignment_upload_start_service import (
    start_assignment_upload as _start_assignment_upload_impl,
)
from ..assignment_uploaded_question_service import AssignmentUploadedQuestionDeps
from ..handlers import assignment_handlers, assignment_io_handlers, assignment_upload_handlers
from . import get_app_core as _app_core


def _assignment_handlers_deps() -> assignment_handlers.AssignmentHandlerDeps:
    _ac = _app_core()
    return assignment_handlers.AssignmentHandlerDeps(
        list_assignments=_ac.list_assignments,
        compute_assignment_progress=_ac.compute_assignment_progress,
        parse_date_str=_ac.parse_date_str,
        save_assignment_requirements=_ac.save_assignment_requirements,
        resolve_assignment_dir=_ac.resolve_assignment_dir,
        load_assignment_requirements=_ac.load_assignment_requirements,
        assignment_today=lambda student_id, date=None, auto_generate=False, generate=True, per_kp=5: _assignment_today_impl(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=_assignment_today_deps(),
        ),
        get_assignment_detail_api=lambda assignment_id: _get_assignment_detail_api_impl(
            assignment_id,
            deps=_assignment_api_deps(),
        ),
    )


def _assignment_upload_handlers_deps() -> assignment_upload_handlers.AssignmentUploadHandlerDeps:
    _ac = _app_core()
    return assignment_upload_handlers.AssignmentUploadHandlerDeps(
        assignment_upload_legacy=lambda **kwargs: _assignment_upload_legacy_impl(
            deps=_assignment_upload_legacy_deps(),
            **kwargs,
        ),
        start_assignment_upload=lambda **kwargs: _start_assignment_upload_impl(
            deps=_assignment_upload_start_deps(),
            **kwargs,
        ),
        assignment_upload_status=lambda job_id: _get_assignment_upload_status_impl(job_id, deps=_assignment_upload_query_deps()),
        assignment_upload_draft=lambda job_id: _get_assignment_upload_draft_impl(job_id, deps=_assignment_upload_query_deps()),
        assignment_upload_draft_save=lambda job_id, requirements, questions, deps=None: _save_assignment_upload_draft_impl(
            job_id,
            requirements,
            questions,
            deps=_assignment_upload_draft_save_deps(),
        ),
        load_upload_job=_ac.load_upload_job,
        ensure_assignment_upload_confirm_ready=_ensure_assignment_upload_confirm_ready_impl,
        confirm_assignment_upload=lambda job_id, job, job_dir, requirements_override=None, strict_requirements=True, deps=None: _confirm_assignment_upload_impl(
            job_id,
            job,
            job_dir,
            requirements_override=requirements_override,
            strict_requirements=strict_requirements,
            deps=_assignment_upload_confirm_deps(),
        ),
        upload_job_path=_ac.upload_job_path,
    )


def _assignment_io_handlers_deps() -> assignment_io_handlers.AssignmentIoHandlerDeps:
    _ac = _app_core()
    return assignment_io_handlers.AssignmentIoHandlerDeps(
        resolve_assignment_dir=_ac.resolve_assignment_dir,
        sanitize_filename=_ac.sanitize_filename,
        run_script=_ac.run_script,
        assignment_questions_ocr=lambda **kwargs: _assignment_questions_ocr_impl(
            deps=_assignment_questions_ocr_deps(),
            **kwargs,
        ),
        generate_assignment=lambda **kwargs: _generate_assignment_impl(
            deps=_assignment_generate_deps(),
            **kwargs,
        ),
        app_root=_ac.APP_ROOT,
    )


def _assignment_submission_attempt_deps():
    _ac = _app_core()
    return AssignmentSubmissionAttemptDeps(
        student_submissions_dir=_ac.STUDENT_SUBMISSIONS_DIR,
        grade_count_conf_threshold=_ac.GRADE_COUNT_CONF_THRESHOLD,
    )


def _assignment_progress_deps():
    _ac = _app_core()
    return AssignmentProgressDeps(
        data_dir=_ac.DATA_DIR,
        load_assignment_meta=_ac.load_assignment_meta,
        postprocess_assignment_meta=_ac.postprocess_assignment_meta,
        normalize_due_at=_ac.normalize_due_at,
        list_all_student_profiles=_ac.list_all_student_profiles,
        session_discussion_pass=_ac._session_discussion_pass,
        list_submission_attempts=_ac._list_submission_attempts,
        best_submission_attempt=_ac._best_submission_attempt,
        resolve_assignment_date=_ac.resolve_assignment_date,
        atomic_write_json=_ac._atomic_write_json,
        time_time=time.time,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _assignment_requirements_deps():
    _ac = _app_core()
    return AssignmentRequirementsDeps(
        data_dir=_ac.DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _assignment_llm_gate_deps():
    _ac = _app_core()
    return AssignmentLlmGateDeps(
        diag_log=_ac.diag_log,
        call_llm=_ac.call_llm,
    )


def _assignment_catalog_deps():
    _ac = _app_core()
    return AssignmentCatalogDeps(
        data_dir=_ac.DATA_DIR,
        app_root=_ac.APP_ROOT,
        load_assignment_meta=_ac.load_assignment_meta,
        load_assignment_requirements=_ac.load_assignment_requirements,
        count_csv_rows=_ac.count_csv_rows,
        sanitize_filename=_ac.sanitize_filename,
    )


def _assignment_meta_postprocess_deps():
    _ac = _app_core()
    return AssignmentMetaPostprocessDeps(
        data_dir=_ac.DATA_DIR,
        discussion_complete_marker=_ac.DISCUSSION_COMPLETE_MARKER,
        load_profile_file=_ac.load_profile_file,
        parse_ids_value=_ac.parse_ids_value,
        resolve_scope=_ac.resolve_scope,
        normalize_due_at=_ac.normalize_due_at,
        compute_expected_students=_ac.compute_expected_students,
        atomic_write_json=_ac._atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _assignment_upload_parse_deps():
    _ac = _app_core()
    return AssignmentUploadParseDeps(
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        now_monotonic=time.monotonic,
        load_upload_job=_ac.load_upload_job,
        upload_job_path=_ac.upload_job_path,
        write_upload_job=_ac.write_upload_job,
        extract_text_from_file=_ac.extract_text_from_file,
        llm_parse_assignment_payload=_ac.llm_parse_assignment_payload,
        compute_requirements_missing=_ac.compute_requirements_missing,
        llm_autofill_requirements=_ac.llm_autofill_requirements,
        diag_log=_ac.diag_log,
    )


def _assignment_upload_legacy_deps():
    _ac = _app_core()
    return AssignmentUploadLegacyDeps(
        data_dir=_ac.DATA_DIR,
        parse_date_str=_ac.parse_date_str,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        extract_text_from_pdf=_ac.extract_text_from_pdf,
        extract_text_from_image=_ac.extract_text_from_image,
        llm_parse_assignment_payload=_ac.llm_parse_assignment_payload,
        write_uploaded_questions=_ac.write_uploaded_questions,
        compute_requirements_missing=_ac.compute_requirements_missing,
        llm_autofill_requirements=_ac.llm_autofill_requirements,
        save_assignment_requirements=_ac.save_assignment_requirements,
        parse_ids_value=_ac.parse_ids_value,
        resolve_scope=_ac.resolve_scope,
        load_assignment_meta=_ac.load_assignment_meta,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _assignment_today_deps():
    _ac = _app_core()
    return AssignmentTodayDeps(
        data_dir=_ac.DATA_DIR,
        parse_date_str=_ac.parse_date_str,
        has_llm_key=lambda: bool(os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")),
        load_profile_file=_ac.load_profile_file,
        find_assignment_for_date=_ac.find_assignment_for_date,
        derive_kp_from_profile=_ac.derive_kp_from_profile,
        safe_assignment_id=_ac.safe_assignment_id,
        assignment_generate=_ac.assignment_generate,
        load_assignment_meta=_ac.load_assignment_meta,
        build_assignment_detail=_ac.build_assignment_detail,
    )


def _assignment_generate_deps():
    _ac = _app_core()
    return AssignmentGenerateDeps(
        app_root=_ac.APP_ROOT,
        parse_date_str=_ac.parse_date_str,
        ensure_requirements_for_assignment=_ac.ensure_requirements_for_assignment,
        run_script=_ac.run_script,
        postprocess_assignment_meta=_ac.postprocess_assignment_meta,
        diag_log=_ac.diag_log,
    )


def _assignment_generate_tool_deps():
    _ac = _app_core()
    return AssignmentGenerateToolDeps(
        app_root=_ac.APP_ROOT,
        parse_date_str=_ac.parse_date_str,
        ensure_requirements_for_assignment=_ac.ensure_requirements_for_assignment,
        run_script=_ac.run_script,
        postprocess_assignment_meta=_ac.postprocess_assignment_meta,
        diag_log=_ac.diag_log,
    )


def _assignment_uploaded_question_deps():
    _ac = _app_core()
    return AssignmentUploadedQuestionDeps(
        safe_slug=_ac.safe_slug,
        normalize_difficulty=_ac.normalize_difficulty,
    )


def _assignment_questions_ocr_deps():
    _ac = _app_core()
    return AssignmentQuestionsOcrDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        run_script=_ac.run_script,
        sanitize_filename=_ac.sanitize_filename,
        sanitize_assignment_id=_ac.safe_slug,
    )


def _assignment_upload_start_deps():
    _ac = _app_core()
    backend = queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )
    return AssignmentUploadStartDeps(
        new_job_id=lambda: f"job_{uuid.uuid4().hex[:12]}",
        parse_date_str=_ac.parse_date_str,
        upload_job_path=_ac.upload_job_path,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        parse_ids_value=_ac.parse_ids_value,
        resolve_scope=_ac.resolve_scope,
        normalize_due_at=_ac.normalize_due_at,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_upload_job=_ac.write_upload_job,
        enqueue_upload_job=lambda job_id: queue_runtime.enqueue_upload_job(
            job_id,
            backend=backend,
        ),
        diag_log=_ac.diag_log,
    )


def _assignment_upload_query_deps():
    _ac = _app_core()
    return AssignmentUploadQueryDeps(
        load_upload_job=_ac.load_upload_job,
        upload_job_path=_ac.upload_job_path,
        assignment_upload_not_ready_detail=_assignment_upload_not_ready_detail_impl,
        load_assignment_draft_override=_load_assignment_draft_override_impl,
        build_assignment_upload_draft=_build_assignment_upload_draft_impl,
        merge_requirements=_ac.merge_requirements,
        compute_requirements_missing=_ac.compute_requirements_missing,
        parse_list_value=_ac.parse_list_value,
    )


def _assignment_upload_draft_save_deps():
    _ac = _app_core()
    return AssignmentUploadDraftSaveDeps(
        load_upload_job=_ac.load_upload_job,
        upload_job_path=_ac.upload_job_path,
        assignment_upload_not_ready_detail=_assignment_upload_not_ready_detail_impl,
        clean_assignment_draft_questions=_clean_assignment_draft_questions_impl,
        save_assignment_draft_override=_save_assignment_draft_override_impl,
        merge_requirements=_ac.merge_requirements,
        compute_requirements_missing=_ac.compute_requirements_missing,
        write_upload_job=_ac.write_upload_job,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _assignment_upload_confirm_deps():
    _ac = _app_core()
    return AssignmentUploadConfirmDeps(
        data_dir=_ac.DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        discussion_complete_marker=_ac.DISCUSSION_COMPLETE_MARKER,
        write_upload_job=_ac.write_upload_job,
        merge_requirements=_ac.merge_requirements,
        compute_requirements_missing=_ac.compute_requirements_missing,
        write_uploaded_questions=_ac.write_uploaded_questions,
        parse_date_str=_ac.parse_date_str,
        save_assignment_requirements=_ac.save_assignment_requirements,
        parse_ids_value=_ac.parse_ids_value,
        resolve_scope=_ac.resolve_scope,
        normalize_due_at=_ac.normalize_due_at,
        compute_expected_students=_ac.compute_expected_students,
        atomic_write_json=_ac._atomic_write_json,
        copy2=shutil.copy2,
    )


def _assignment_api_deps():
    _ac = _app_core()

    def _assignment_exists(assignment_id: str) -> bool:
        try:
            return _ac.resolve_assignment_dir(str(assignment_id or "")).exists()
        except ValueError:
            return False

    return AssignmentApiDeps(
        build_assignment_detail=lambda assignment_id, include_text=True: _ac.build_assignment_detail(
            _ac.resolve_assignment_dir(str(assignment_id or "")),
            include_text=include_text,
        ),
        assignment_exists=_assignment_exists,
    )
