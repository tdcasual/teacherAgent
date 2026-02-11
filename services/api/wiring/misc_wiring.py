"""Miscellaneous deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "_tool_dispatch_deps",
    "_upload_llm_deps",
    "_upload_text_deps",
    "_content_catalog_deps",
    "_chart_api_deps",
    "_chart_agent_run_deps",
    "_lesson_core_tool_deps",
    "_core_example_tool_deps",
    "_agent_runtime_deps",
]

from typing import Any, Dict, List, Optional

from ..agent_service import (
    AgentRuntimeDeps,
)
from ..chart_agent_run_service import (
    ChartAgentRunDeps,
)
from ..chart_api_service import ChartApiDeps
from ..chart_executor import execute_chart_exec
from ..content_catalog_service import ContentCatalogDeps
from ..core_example_tool_service import CoreExampleToolDeps
from ..lesson_core_tool_service import LessonCaptureDeps
from ..opencode_executor import resolve_opencode_status, run_opencode_codegen
from ..tool_dispatch_service import ToolDispatchDeps
from ..upload_llm_service import UploadLlmDeps
from ..upload_text_service import UploadTextDeps
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY


from . import get_app_core as _app_core


def _tool_dispatch_deps():
    _ac = _app_core()
    return ToolDispatchDeps(
        tool_registry=DEFAULT_TOOL_REGISTRY,
        list_exams=_ac.list_exams,
        exam_get=_ac.exam_get,
        exam_analysis_get=_ac.exam_analysis_get,
        exam_analysis_charts_generate=_ac.exam_analysis_charts_generate,
        exam_students_list=_ac.exam_students_list,
        exam_student_detail=_ac.exam_student_detail,
        exam_question_detail=_ac.exam_question_detail,
        exam_range_top_students=_ac.exam_range_top_students,
        exam_range_summary_batch=_ac.exam_range_summary_batch,
        exam_question_batch_detail=_ac.exam_question_batch_detail,
        list_assignments=_ac.list_assignments,
        list_lessons=_ac.list_lessons,
        lesson_capture=_ac.lesson_capture,
        student_search=_ac.student_search,
        student_profile_get=_ac.student_profile_get,
        student_profile_update=_ac.student_profile_update,
        student_import=_ac.student_import,
        assignment_generate=_ac.assignment_generate,
        assignment_render=_ac.assignment_render,
        save_assignment_requirements=_ac.save_assignment_requirements,
        parse_date_str=_ac.parse_date_str,
        core_example_search=_ac.core_example_search,
        core_example_register=_ac.core_example_register,
        core_example_render=_ac.core_example_render,
        chart_agent_run=_ac.chart_agent_run,
        chart_exec=_ac.chart_exec,
        resolve_teacher_id=_ac.resolve_teacher_id,
        ensure_teacher_workspace=_ac.ensure_teacher_workspace,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        teacher_workspace_file=_ac.teacher_workspace_file,
        teacher_daily_memory_path=_ac.teacher_daily_memory_path,
        teacher_read_text=lambda path, max_chars=8000: _ac.read_text_safe(path, limit=max_chars),
        teacher_memory_search=_ac.teacher_memory_search,
        teacher_memory_propose=_ac.teacher_memory_propose,
        teacher_memory_apply=_ac.teacher_memory_apply,
        teacher_llm_routing_get=_ac.teacher_llm_routing_get,
        teacher_llm_routing_simulate=_ac.teacher_llm_routing_simulate,
        teacher_llm_routing_propose=_ac.teacher_llm_routing_propose,
        teacher_llm_routing_apply=_ac.teacher_llm_routing_apply,
        teacher_llm_routing_rollback=_ac.teacher_llm_routing_rollback,
    )


def _upload_llm_deps():
    _ac = _app_core()
    return UploadLlmDeps(
        app_root=_ac.APP_ROOT,
        call_llm=_ac.call_llm,
        diag_log=_ac.diag_log,
        parse_list_value=_ac.parse_list_value,
        compute_requirements_missing=_ac._compute_requirements_missing_impl,
        merge_requirements=lambda base, update, overwrite=False: _ac._merge_requirements_impl(
            base,
            update,
            overwrite=overwrite,
        ),
        normalize_excel_cell=_ac._normalize_excel_cell_impl,
    )


def _upload_text_deps():
    _ac = _app_core()
    from ..global_limits import GLOBAL_OCR_SEMAPHORE

    return UploadTextDeps(
        diag_log=_ac.diag_log,
        limit=_ac._limit,
        ocr_semaphore=(_ac._OCR_SEMAPHORE, GLOBAL_OCR_SEMAPHORE),
    )


def _content_catalog_deps():
    _ac = _app_core()
    from ..skills.loader import load_skills

    return ContentCatalogDeps(
        data_dir=_ac.DATA_DIR,
        app_root=_ac.APP_ROOT,
        load_profile_file=_ac.load_profile_file,
        load_skills=load_skills,
        teacher_skills_dir=_ac.TEACHER_SKILLS_DIR,
    )


def _chart_api_deps():
    _ac = _app_core()
    return ChartApiDeps(
        chart_exec=lambda args: _ac.execute_chart_exec(args, app_root=_ac.APP_ROOT, uploads_dir=_ac.UPLOADS_DIR)
    )


def _chart_agent_run_deps():
    _ac = _app_core()
    return ChartAgentRunDeps(
        safe_int_arg=_ac._safe_int_arg,
        chart_bool=_ac._chart_agent_bool_impl,
        chart_engine=_ac._chart_agent_engine_impl,
        chart_packages=_ac._chart_agent_packages_impl,
        chart_opencode_overrides=_ac._chart_agent_opencode_overrides_impl,
        resolve_opencode_status=_ac.resolve_opencode_status,
        app_root=_ac.APP_ROOT,
        uploads_dir=_ac.UPLOADS_DIR,
        generate_candidate=lambda task, input_data, last_error, previous_code, attempt, max_retries: _ac._chart_agent_generate_candidate_impl(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            max_retries,
            call_llm=_ac.call_llm,
            parse_json_from_text=_ac.parse_json_from_text,
        ),
        generate_candidate_opencode=lambda task, input_data, last_error, previous_code, attempt, max_retries, opencode_overrides: _ac._chart_agent_generate_candidate_opencode_impl(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            max_retries,
            opencode_overrides,
            app_root=_ac.APP_ROOT,
            run_opencode_codegen=_ac.run_opencode_codegen,
        ),
        execute_chart_exec=_ac.execute_chart_exec,
        default_code=_ac._chart_agent_default_code_impl,
    )


def _lesson_core_tool_deps():
    _ac = _app_core()
    return LessonCaptureDeps(
        is_safe_tool_id=_ac._is_safe_tool_id,
        resolve_app_path=_ac._resolve_app_path,
        app_root=_ac.APP_ROOT,
        run_script=_ac.run_script,
    )


def _core_example_tool_deps():
    _ac = _app_core()
    return CoreExampleToolDeps(
        data_dir=_ac.DATA_DIR,
        app_root=_ac.APP_ROOT,
        is_safe_tool_id=_ac._is_safe_tool_id,
        resolve_app_path=_ac._resolve_app_path,
        run_script=_ac.run_script,
    )


def _agent_runtime_deps():
    _ac = _app_core()
    return AgentRuntimeDeps(
        app_root=_ac.APP_ROOT,
        build_system_prompt=_ac.build_system_prompt,
        diag_log=_ac.diag_log,
        load_skill_runtime=lambda role_hint, skill_id: _ac._default_load_skill_runtime_impl(_ac.APP_ROOT, role_hint, skill_id, teacher_skills_dir=_ac.TEACHER_SKILLS_DIR),
        allowed_tools=_ac.allowed_tools,
        max_tool_rounds=_ac.CHAT_MAX_TOOL_ROUNDS,
        max_tool_calls=_ac.CHAT_MAX_TOOL_CALLS,
        extract_min_chars_requirement=_ac.extract_min_chars_requirement,
        extract_exam_id=_ac.extract_exam_id,
        is_exam_analysis_request=_ac.is_exam_analysis_request,
        build_exam_longform_context=_ac.build_exam_longform_context,
        generate_longform_reply=_ac._generate_longform_reply,
        call_llm=_ac.call_llm,
        tool_dispatch=_ac.tool_dispatch,
        teacher_tools_to_openai=_ac._default_teacher_tools_to_openai_impl,
    )
