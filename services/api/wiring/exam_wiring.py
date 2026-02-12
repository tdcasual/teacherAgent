"""Exam domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "_exam_upload_handlers_deps",
    "_exam_range_deps",
    "_exam_analysis_charts_deps",
    "_exam_longform_deps",
    "_exam_upload_parse_deps",
    "_exam_upload_confirm_deps",
    "_exam_upload_start_deps",
    "_exam_upload_api_deps",
    "_exam_overview_deps",
    "_exam_catalog_deps",
    "_exam_api_deps",
    "_exam_detail_deps",
]

import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..exam_api_service import ExamApiDeps
from ..exam_analysis_charts_service import ExamAnalysisChartsDeps
from ..exam_catalog_service import ExamCatalogDeps
from ..exam_detail_service import ExamDetailDeps
from ..exam_longform_service import ExamLongformDeps
from ..exam_overview_service import ExamOverviewDeps
from ..exam_range_service import ExamRangeDeps
from ..exam_upload_api_service import (
    ExamUploadApiDeps,
    exam_upload_confirm as _exam_upload_confirm_api_impl,
    exam_upload_draft as _exam_upload_draft_api_impl,
    exam_upload_draft_save as _exam_upload_draft_save_api_impl,
    exam_upload_status as _exam_upload_status_api_impl,
)
from ..exam_upload_confirm_service import (
    ExamUploadConfirmDeps,
    confirm_exam_upload as _confirm_exam_upload_impl,
)
from ..exam_upload_draft_service import (
    build_exam_upload_draft as _build_exam_upload_draft_impl,
    exam_upload_not_ready_detail as _exam_upload_not_ready_detail_impl,
    load_exam_draft_override as _load_exam_draft_override_impl,
    save_exam_draft_override as _save_exam_draft_override_impl,
)
from ..exam_upload_parse_service import ExamUploadParseDeps
from ..exam_upload_start_service import (
    ExamUploadStartDeps,
    start_exam_upload as _start_exam_upload_impl,
)
from ..exam_utils import _parse_xlsx_with_script, _safe_int_arg
from ..core_utils import _non_ws_len
from ..chart_executor import execute_chart_exec
from ..handlers import exam_upload_handlers
from services.api.runtime import queue_runtime


from . import get_app_core as _app_core


def _exam_upload_handlers_deps() -> exam_upload_handlers.ExamUploadHandlerDeps:
    return exam_upload_handlers.ExamUploadHandlerDeps(
        start_exam_upload=lambda exam_id, date, class_name, paper_files, score_files, answer_files, ocr_mode, language, deps=None: _start_exam_upload_impl(
            exam_id=exam_id,
            date=date,
            class_name=class_name,
            paper_files=paper_files,
            score_files=score_files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=_exam_upload_start_deps(),
        ),
        exam_upload_status=lambda job_id: _exam_upload_status_api_impl(job_id, deps=_exam_upload_api_deps()),
        exam_upload_draft=lambda job_id: _exam_upload_draft_api_impl(job_id, deps=_exam_upload_api_deps()),
        exam_upload_draft_save=lambda **kwargs: _exam_upload_draft_save_api_impl(**kwargs, deps=_exam_upload_api_deps()),
        exam_upload_confirm=lambda job_id: _exam_upload_confirm_api_impl(job_id, deps=_exam_upload_api_deps()),
    )


def _exam_range_deps():
    _ac = _app_core()
    return ExamRangeDeps(
        load_exam_manifest=_ac.load_exam_manifest,
        exam_responses_path=_ac.exam_responses_path,
        exam_questions_path=_ac.exam_questions_path,
        read_questions_csv=_ac.read_questions_csv,
        parse_score_value=_ac.parse_score_value,
        safe_int_arg=_safe_int_arg,
        exam_question_detail=_ac.exam_question_detail,
    )


def _exam_analysis_charts_deps():
    _ac = _app_core()
    return ExamAnalysisChartsDeps(
        app_root=_ac.APP_ROOT,
        uploads_dir=_ac.UPLOADS_DIR,
        safe_int_arg=_safe_int_arg,
        load_exam_manifest=_ac.load_exam_manifest,
        exam_responses_path=_ac.exam_responses_path,
        compute_exam_totals=_ac.compute_exam_totals,
        exam_analysis_get=_ac.exam_analysis_get,
        parse_score_value=_ac.parse_score_value,
        exam_questions_path=_ac.exam_questions_path,
        read_questions_csv=_ac.read_questions_csv,
        execute_chart_exec=_ac.execute_chart_exec,
    )


def _exam_longform_deps():
    _ac = _app_core()
    return ExamLongformDeps(
        data_dir=_ac.DATA_DIR,
        exam_students_list=_ac.exam_students_list,
        exam_get=_ac.exam_get,
        exam_analysis_get=_ac.exam_analysis_get,
        call_llm=_ac.call_llm,
        non_ws_len=_non_ws_len,
    )


def _exam_upload_parse_deps():
    _ac = _app_core()
    return ExamUploadParseDeps(
        app_root=_ac.APP_ROOT,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        now_date_compact=lambda: datetime.now().date().isoformat().replace("-", ""),
        load_exam_job=_ac.load_exam_job,
        exam_job_path=_ac.exam_job_path,
        write_exam_job=_ac.write_exam_job,
        extract_text_from_file=_ac.extract_text_from_file,
        extract_text_from_pdf=_ac.extract_text_from_pdf,
        extract_text_from_image=_ac.extract_text_from_image,
        parse_xlsx_with_script=_parse_xlsx_with_script,
        xlsx_to_table_preview=_ac.xlsx_to_table_preview,
        xls_to_table_preview=_ac.xls_to_table_preview,
        llm_parse_exam_scores=_ac.llm_parse_exam_scores,
        build_exam_rows_from_parsed_scores=_ac.build_exam_rows_from_parsed_scores,
        parse_score_value=_ac.parse_score_value,
        write_exam_responses_csv=_ac.write_exam_responses_csv,
        parse_exam_answer_key_text=_ac.parse_exam_answer_key_text,
        write_exam_answers_csv=_ac.write_exam_answers_csv,
        compute_max_scores_from_rows=_ac.compute_max_scores_from_rows,
        write_exam_questions_csv=_ac.write_exam_questions_csv,
        apply_answer_key_to_responses_csv=_ac.apply_answer_key_to_responses_csv,
        compute_exam_totals=_ac.compute_exam_totals,
        copy2=shutil.copy2,
        diag_log=_ac.diag_log,
        parse_date_str=_ac.parse_date_str,
    )


def _exam_upload_confirm_deps():
    _ac = _app_core()
    return ExamUploadConfirmDeps(
        app_root=_ac.APP_ROOT,
        data_dir=_ac.DATA_DIR,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        write_exam_job=_ac.write_exam_job,
        load_exam_draft_override=_load_exam_draft_override_impl,
        parse_exam_answer_key_text=_ac.parse_exam_answer_key_text,
        write_exam_questions_csv=_ac.write_exam_questions_csv,
        write_exam_answers_csv=_ac.write_exam_answers_csv,
        load_exam_answer_key_from_csv=_ac.load_exam_answer_key_from_csv,
        ensure_questions_max_score=_ac.ensure_questions_max_score,
        apply_answer_key_to_responses_csv=_ac.apply_answer_key_to_responses_csv,
        run_script=_ac.run_script,
        diag_log=_ac.diag_log,
        copy2=shutil.copy2,
    )


def _exam_upload_start_deps():
    _ac = _app_core()
    backend = queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )
    return ExamUploadStartDeps(
        parse_date_str=_ac.parse_date_str,
        exam_job_path=_ac.exam_job_path,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        write_exam_job=lambda job_id, updates, overwrite=False: _ac.write_exam_job(job_id, updates, overwrite=overwrite),
        enqueue_exam_job=lambda job_id: queue_runtime.enqueue_exam_job(
            job_id,
            backend=backend,
        ),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        diag_log=_ac.diag_log,
        uuid_hex=lambda: uuid.uuid4().hex,
    )


def _exam_upload_api_deps():
    _ac = _app_core()
    backend = queue_runtime.app_queue_backend(
        tenant_id=_ac.TENANT_ID or None,
        is_pytest=_ac._settings.is_pytest(),
        inline_backend_factory=_ac._inline_backend_factory,
    )
    return ExamUploadApiDeps(
        load_exam_job=_ac.load_exam_job,
        exam_job_path=_ac.exam_job_path,
        load_exam_draft_override=_load_exam_draft_override_impl,
        save_exam_draft_override=_save_exam_draft_override_impl,
        build_exam_upload_draft=_build_exam_upload_draft_impl,
        exam_upload_not_ready_detail=_exam_upload_not_ready_detail_impl,
        parse_exam_answer_key_text=_ac.parse_exam_answer_key_text,
        read_text_safe=_ac.read_text_safe,
        write_exam_job=lambda job_id, updates: _ac.write_exam_job(job_id, updates),
        enqueue_exam_job=lambda job_id: queue_runtime.enqueue_exam_job(job_id, backend=backend),
        confirm_exam_upload=lambda job_id, job, job_dir: _confirm_exam_upload_impl(
            job_id,
            job,
            job_dir,
            deps=_exam_upload_confirm_deps(),
        ),
    )


def _exam_overview_deps():
    _ac = _app_core()
    return ExamOverviewDeps(
        data_dir=_ac.DATA_DIR,
        load_exam_manifest=_ac.load_exam_manifest,
        exam_responses_path=_ac.exam_responses_path,
        exam_questions_path=_ac.exam_questions_path,
        exam_analysis_draft_path=_ac.exam_analysis_draft_path,
        read_questions_csv=_ac.read_questions_csv,
        compute_exam_totals=_ac.compute_exam_totals,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        parse_xlsx_with_script=_parse_xlsx_with_script,
    )


def _exam_catalog_deps():
    _ac = _app_core()
    return ExamCatalogDeps(
        data_dir=_ac.DATA_DIR,
        load_profile_file=_ac.load_profile_file,
    )


def _exam_api_deps():
    _ac = _app_core()
    return ExamApiDeps(exam_get=_ac.exam_get)


def _exam_detail_deps():
    _ac = _app_core()
    return ExamDetailDeps(
        load_exam_manifest=_ac.load_exam_manifest,
        exam_responses_path=_ac.exam_responses_path,
        exam_questions_path=_ac.exam_questions_path,
        read_questions_csv=_ac.read_questions_csv,
        parse_score_value=_ac.parse_score_value,
        safe_int_arg=_safe_int_arg,
    )
