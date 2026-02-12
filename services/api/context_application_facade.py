from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .api_models import ChatRequest
from .assignment_catalog_service import (
    assignment_specificity as _assignment_specificity_impl,
    build_assignment_detail as _build_assignment_detail_impl,
    find_assignment_for_date as _find_assignment_for_date_impl,
    list_assignments as _list_assignments_impl,
    parse_iso_timestamp as _parse_iso_timestamp_impl,
    read_text_safe as _read_text_safe_impl,
    resolve_assignment_date as _resolve_assignment_date_impl,
    postprocess_assignment_meta as _postprocess_assignment_meta_impl,
)
from .assignment_context_service import build_assignment_context as _build_assignment_context_impl
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
    llm_assignment_gate as _llm_assignment_gate_impl,
    parse_json_from_text as _parse_json_from_text_impl,
)
from .assignment_progress_service import compute_assignment_progress as _compute_assignment_progress_impl
from .assignment_requirements_service import (
    ensure_requirements_for_assignment as _ensure_requirements_for_assignment_impl,
    format_requirements_prompt as _format_requirements_prompt_impl,
    normalize_class_level as _normalize_class_level_impl,
    normalize_difficulty as _normalize_difficulty_impl,
    normalize_preferences as _normalize_preferences_impl,
    parse_duration as _parse_duration_impl,
    parse_list_value as _parse_list_value_impl,
    save_assignment_requirements as _save_assignment_requirements_impl,
    validate_requirements as _validate_requirements_impl,
)
from .assignment_submission_attempt_service import (
    best_submission_attempt as _best_submission_attempt_impl,
    compute_submission_attempt as _compute_submission_attempt_impl,
    counted_grade_item as _counted_grade_item_impl,
    list_submission_attempts as _list_submission_attempts_impl,
)
from .config import DISCUSSION_COMPLETE_MARKER
from .core_utils import resolve_scope
from .exam_analysis_charts_service import exam_analysis_charts_generate as _exam_analysis_charts_generate_impl
from .exam_catalog_service import list_exams as _list_exams_impl
from .exam_detail_service import (
    exam_question_detail as _exam_question_detail_impl,
    exam_student_detail as _exam_student_detail_impl,
)
from .exam_overview_service import (
    exam_analysis_get as _exam_analysis_get_impl,
    exam_get as _exam_get_impl,
    exam_students_list as _exam_students_list_impl,
)
from .exam_range_service import (
    exam_question_batch_detail as _exam_question_batch_detail_impl,
    exam_range_summary_batch as _exam_range_summary_batch_impl,
    exam_range_top_students as _exam_range_top_students_impl,
)
from .student_directory_service import (
    list_all_student_ids as _list_all_student_ids_impl,
    list_all_student_profiles as _list_all_student_profiles_impl,
    list_student_ids_by_class as _list_student_ids_by_class_impl,
    student_candidates_by_name as _student_candidates_by_name_impl,
    student_search as _student_search_impl,
)
from .session_discussion_service import (
    SessionDiscussionDeps,
    session_discussion_pass as _session_discussion_pass_impl,
)
from .session_store import load_student_sessions_index, student_session_file
from .teacher_assignment_preflight_service import (
    teacher_assignment_preflight as _teacher_assignment_preflight_impl,
)
from .wiring.assignment_wiring import (
    _assignment_catalog_deps,
    _assignment_llm_gate_deps,
    _assignment_meta_postprocess_deps,
    _assignment_progress_deps,
    _assignment_requirements_deps,
    _assignment_submission_attempt_deps,
)
from .wiring.exam_wiring import (
    _exam_analysis_charts_deps,
    _exam_catalog_deps,
    _exam_detail_deps,
    _exam_overview_deps,
    _exam_range_deps,
)
from .wiring.student_wiring import _student_directory_deps
from .wiring.teacher_wiring import _teacher_assignment_preflight_deps


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


def exam_student_detail(
    exam_id: str,
    student_id: Optional[str] = None,
    student_name: Optional[str] = None,
    class_name: Optional[str] = None,
) -> Dict[str, Any]:
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
