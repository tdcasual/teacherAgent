# mypy: disable-error-code=no-untyped-def
"""Miscellaneous deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "tool_dispatch_deps",
    "upload_llm_deps",
    "upload_text_deps",
    "content_catalog_deps",
    "chart_agent_run_deps",
    "lesson_core_tool_deps",
    "core_example_tool_deps",
    "agent_runtime_deps",
    "_tool_dispatch_deps",
    "_upload_llm_deps",
    "_upload_text_deps",
    "_content_catalog_deps",
    "_chart_agent_run_deps",
    "_lesson_core_tool_deps",
    "_core_example_tool_deps",
    "_agent_runtime_deps",
]

from typing import Any

from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

from ..agent_service import (
    AgentRuntimeDeps,
)
from ..agent_service import (
    default_load_skill_runtime as _default_load_skill_runtime_impl,
)
from ..agent_service import (
    default_teacher_tools_to_openai as _default_teacher_tools_to_openai_impl,
)
from ..assignment_requirements_service import (
    compute_requirements_missing as _compute_requirements_missing_impl,
)
from ..assignment_requirements_service import (
    merge_requirements as _merge_requirements_impl,
)
from ..chart_agent_run_service import (
    ChartAgentRunDeps,
)
from ..chart_agent_run_service import (
    chart_agent_bool as _chart_agent_bool_impl,
)
from ..chart_agent_run_service import (
    chart_agent_default_code as _chart_agent_default_code_impl,
)
from ..chart_agent_run_service import (
    chart_agent_engine as _chart_agent_engine_impl,
)
from ..chart_agent_run_service import (
    chart_agent_generate_candidate as _chart_agent_generate_candidate_impl,
)
from ..chart_agent_run_service import (
    chart_agent_generate_candidate_opencode as _chart_agent_generate_candidate_opencode_impl,
)
from ..chart_agent_run_service import (
    chart_agent_opencode_overrides as _chart_agent_opencode_overrides_impl,
)
from ..chart_agent_run_service import (
    chart_agent_packages as _chart_agent_packages_impl,
)
from ..content_catalog_service import ContentCatalogDeps
from ..core_example_tool_service import CoreExampleToolDeps
from ..core_utils import _is_safe_tool_id, _resolve_app_path, _safe_int_arg, normalize_excel_cell
from ..lesson_core_tool_service import LessonCaptureDeps
from ..skills.affiliates import extra_skill_ids_for_role as _extra_skill_ids_for_role
from ..tool_dispatch_service import ToolDispatchDeps
from ..upload_llm_service import UploadLlmDeps
from ..upload_text_service import UploadTextDeps
from . import get_app_core as _app_core


def _tool_dispatch_deps(core: Any | None = None):
    _ac = _app_core(core)

    def _assignment_publish(assignment_id: str) -> dict[str, Any]:
        from ..assignment_archive_service import AssignmentArchiveError, publish_assignment
        from ..auth_service import get_current_principal

        try:
            return publish_assignment(assignment_id, principal=get_current_principal())
        except AssignmentArchiveError as exc:
            return {"error": exc.detail, "status_code": exc.status_code}

    def _assignment_archive(assignment_id: str) -> dict[str, Any]:
        from ..assignment_archive_service import AssignmentArchiveError, archive_assignment
        from ..auth_service import get_current_principal

        try:
            return archive_assignment(assignment_id, principal=get_current_principal())
        except AssignmentArchiveError as exc:
            return {"error": exc.detail, "status_code": exc.status_code}

    def _assignment_unarchive(assignment_id: str) -> dict[str, Any]:
        from ..assignment_archive_service import AssignmentArchiveError, unarchive_assignment
        from ..auth_service import get_current_principal

        try:
            return unarchive_assignment(assignment_id, principal=get_current_principal())
        except AssignmentArchiveError as exc:
            return {"error": exc.detail, "status_code": exc.status_code}

    def _assignment_recompute_roster(assignment_id: str) -> dict[str, Any]:
        from ..assignment_recompute_roster_service import (
            AssignmentRecomputeRosterError,
            recompute_assignment_roster,
        )
        from ..auth_service import get_current_principal

        try:
            return recompute_assignment_roster(assignment_id, principal=get_current_principal())
        except AssignmentRecomputeRosterError as exc:
            return {"error": exc.detail, "status_code": exc.status_code}

    def _assignment_my_today(student_id: str, date: str | None = None) -> dict[str, Any]:
        from ..assignment_today_service import AssignmentTodayError, assignment_today
        from .assignment_wiring import assignment_today_deps

        try:
            return assignment_today(
                student_id=student_id,
                date=date,
                auto_generate=False,
                generate=False,
                per_kp=5,
                deps=assignment_today_deps(_ac),
            )
        except AssignmentTodayError as exc:
            return {"error": exc.detail, "status_code": exc.status_code}

    def _assignment_owner_id(assignment_id: str) -> str | None:
        aid = str(assignment_id or "").strip()
        if not aid:
            return None
        folder = _ac.DATA_DIR / "assignments" / aid
        if not folder.exists():
            return None
        from ..assignment.visibility import assignment_owner_id
        from ..assignment_data_service import load_assignment_meta

        try:
            meta = load_assignment_meta(folder)
        except Exception:  # policy: allowed-broad-except
            return None
        return str(assignment_owner_id(meta) if isinstance(meta, dict) else "").strip()

    def _assignment_my_result(assignment_id: str, student_id: str) -> dict[str, Any]:
        from ..assignment.visibility import snapshot_student_ids, student_can_read_assignment

        sid = str(student_id or "").strip()
        aid = str(assignment_id or "").strip()
        if not sid:
            return {"error": "student_id_required"}
        if not aid:
            return {"error": "assignment_id is required"}
        folder = _ac.DATA_DIR / "assignments" / aid
        if not folder.exists():
            return {"error": "assignment_not_found", "assignment_id": aid}
        from ..assignment_data_service import load_assignment_meta

        try:
            meta = load_assignment_meta(folder)
        except Exception:  # policy: allowed-broad-except
            return {"error": "assignment_not_found", "assignment_id": aid}
        if not isinstance(meta, dict):
            meta = {}
        if not student_can_read_assignment(meta) or sid not in snapshot_student_ids(meta):
            return {"error": "forbidden_assignment_scope", "assignment_id": aid}
        attempts = _ac.list_submission_attempts(aid, sid)
        best = _ac.best_submission_attempt(attempts)
        official = None
        if isinstance(best, dict):
            official = best.get("score_earned")
        return {
            "ok": True,
            "assignment_id": aid,
            "student_id": sid,
            "submitted": bool(best),
            "official_score": official,
            "best": best,
        }

    return ToolDispatchDeps(
        tool_registry=DEFAULT_TOOL_REGISTRY,
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
        resolve_teacher_id=_ac.require_teacher_id,
        ensure_teacher_workspace=_ac.ensure_teacher_workspace,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        teacher_workspace_file=_ac.teacher_workspace_file,
        teacher_daily_memory_path=_ac.teacher_daily_memory_path,
        teacher_read_text=lambda path, max_chars=8000: _ac.read_text_safe(path, limit=max_chars),
        teacher_memory_search=_ac.teacher_memory_search,
        teacher_memory_propose=_ac.teacher_memory_propose,
        teacher_memory_apply=_ac.teacher_memory_apply,
        load_skill_runtime=lambda role_hint, skill_id: _default_load_skill_runtime_impl(
            _ac.APP_ROOT,
            role_hint,
            skill_id,
            extra_skill_ids=_extra_skill_ids_for_role(_ac, role_hint),
        ),
        allowed_tools=_ac.allowed_tools,
        assignment_progress=lambda assignment_id: _ac.compute_assignment_progress(
            assignment_id, include_students=True
        ),
        assignment_publish=_assignment_publish,
        assignment_archive=_assignment_archive,
        assignment_unarchive=_assignment_unarchive,
        assignment_recompute_roster=_assignment_recompute_roster,
        assignment_my_today=_assignment_my_today,
        assignment_my_result=_assignment_my_result,
        assignment_owner_id=_assignment_owner_id,
    )


def _upload_llm_deps(core: Any | None = None):
    _ac = _app_core(core)
    return UploadLlmDeps(
        app_root=_ac.APP_ROOT,
        call_llm=_ac.call_llm,
        diag_log=_ac.diag_log,
        parse_list_value=_ac.parse_list_value,
        compute_requirements_missing=_compute_requirements_missing_impl,
        merge_requirements=_merge_requirements_impl,
        normalize_excel_cell=normalize_excel_cell,
    )


def _upload_text_deps(core: Any | None = None):
    _ac = _app_core(core)
    from ..global_limits import GLOBAL_OCR_SEMAPHORE

    return UploadTextDeps(
        diag_log=_ac.diag_log,
        limit=_ac._limit,
        ocr_semaphore=(_ac._OCR_SEMAPHORE, GLOBAL_OCR_SEMAPHORE),
    )


def _content_catalog_deps(core: Any | None = None):
    _ac = _app_core(core)
    from ..skills.loader import load_skills

    return ContentCatalogDeps(
        data_dir=_ac.DATA_DIR,
        app_root=_ac.APP_ROOT,
        load_profile_file=_ac.load_profile_file,
        load_skills=load_skills,
    )


def _chart_agent_run_deps(core: Any | None = None):
    _ac = _app_core(core)
    return ChartAgentRunDeps(
        safe_int_arg=_safe_int_arg,
        chart_bool=_chart_agent_bool_impl,
        chart_engine=_chart_agent_engine_impl,
        chart_packages=_chart_agent_packages_impl,
        chart_opencode_overrides=_chart_agent_opencode_overrides_impl,
        resolve_opencode_status=_ac.resolve_opencode_status,
        app_root=_ac.APP_ROOT,
        uploads_dir=_ac.UPLOADS_DIR,
        generate_candidate=lambda task, input_data, last_error, previous_code, attempt, max_retries: _chart_agent_generate_candidate_impl(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            max_retries,
            call_llm=_ac.call_llm,
            parse_json_from_text=_ac.parse_json_from_text,
        ),
        generate_candidate_opencode=lambda task, input_data, last_error, previous_code, attempt, max_retries, opencode_overrides: _chart_agent_generate_candidate_opencode_impl(
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
        default_code=_chart_agent_default_code_impl,
    )


def _lesson_core_tool_deps(core: Any | None = None):
    _ac = _app_core(core)
    return LessonCaptureDeps(
        is_safe_tool_id=_is_safe_tool_id,
        resolve_app_path=_resolve_app_path,
        app_root=_ac.APP_ROOT,
        run_script=_ac.run_script,
    )


def _core_example_tool_deps(core: Any | None = None):
    _ac = _app_core(core)
    return CoreExampleToolDeps(
        data_dir=_ac.DATA_DIR,
        app_root=_ac.APP_ROOT,
        is_safe_tool_id=_is_safe_tool_id,
        resolve_app_path=_resolve_app_path,
        run_script=_ac.run_script,
    )


def _agent_runtime_deps(core: Any | None = None):
    _ac = _app_core(core)
    return AgentRuntimeDeps(
        app_root=_ac.APP_ROOT,
        build_system_prompt=_ac.build_system_prompt,
        diag_log=_ac.diag_log,
        load_skill_runtime=lambda role_hint, skill_id: _default_load_skill_runtime_impl(
            _ac.APP_ROOT,
            role_hint,
            skill_id,
            extra_skill_ids=_extra_skill_ids_for_role(_ac, role_hint),
        ),
        allowed_tools=_ac.allowed_tools,
        max_tool_rounds=_ac.CHAT_MAX_TOOL_ROUNDS,
        max_tool_calls=_ac.CHAT_MAX_TOOL_CALLS,
        extract_min_chars_requirement=_ac.extract_min_chars_requirement,
        generate_longform_reply=lambda *args, **kwargs: "",
        call_llm=_ac.call_llm,
        tool_dispatch=_ac.tool_dispatch,
        teacher_tools_to_openai=_default_teacher_tools_to_openai_impl,
    )


def tool_dispatch_deps(core: Any):
    return _tool_dispatch_deps(core)


def upload_llm_deps(core: Any):
    return _upload_llm_deps(core)


def upload_text_deps(core: Any):
    return _upload_text_deps(core)


def content_catalog_deps(core: Any):
    return _content_catalog_deps(core)


def chart_agent_run_deps(core: Any):
    return _chart_agent_run_deps(core)


def lesson_core_tool_deps(core: Any):
    return _lesson_core_tool_deps(core)


def core_example_tool_deps(core: Any):
    return _core_example_tool_deps(core)


def agent_runtime_deps(core: Any):
    return _agent_runtime_deps(core)
