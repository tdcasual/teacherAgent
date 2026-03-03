from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agent_service import (
    parse_tool_json as _parse_tool_json_impl,
)
from .agent_service import (
    run_agent_runtime as _run_agent_runtime_impl,
)
from .api_models import ChatRequest, ChatStartRequest
from .chart_agent_run_service import chart_agent_run as _chart_agent_run_impl
from .chat_job_processing_service import (
    compute_chat_reply_sync as _compute_chat_reply_sync_impl,
)
from .chat_job_processing_service import (
    process_chat_job as _process_chat_job_impl,
)
from .chat_runtime_service import call_llm_runtime as _call_llm_runtime_impl
from .chat_session_utils import resolve_student_session_id as _resolve_student_session_id_impl
from .chat_support_service import (
    allowed_tools as _allowed_tools_impl,
)
from .chat_support_service import (
    build_interaction_note as _build_interaction_note_impl,
)
from .chat_support_service import (
    build_system_prompt as _build_system_prompt_impl,
)
from .chat_support_service import (
    build_verified_student_context as _build_verified_student_context_impl,
)
from .chat_support_service import (
    detect_latex_tokens as _detect_latex_tokens_impl,
)
from .chat_support_service import (
    detect_math_delimiters as _detect_math_delimiters_impl,
)
from .chat_support_service import (
    detect_student_study_trigger as _detect_student_study_trigger_impl,
)
from .chat_support_service import (
    extract_exam_id as _extract_exam_id_impl,
)
from .chat_support_service import (
    extract_min_chars_requirement as _extract_min_chars_requirement_impl,
)
from .chat_support_service import (
    is_exam_analysis_request as _is_exam_analysis_request_impl,
)
from .chat_support_service import (
    normalize_math_delimiters as _normalize_math_delimiters_impl,
)
from .content_catalog_service import (
    list_lessons as _list_lessons_impl,
)
from .content_catalog_service import (
    list_skills as _list_skills_impl,
)
from .core_example_tool_service import (
    core_example_register as _core_example_register_impl,
)
from .core_example_tool_service import (
    core_example_render as _core_example_render_impl,
)
from .core_example_tool_service import (
    core_example_search as _core_example_search_impl,
)
from .exam_longform_service import (
    build_exam_longform_context as _build_exam_longform_context_impl,
)
from .exam_longform_service import (
    summarize_exam_students as _summarize_exam_students_impl,
)
from .handlers import chat_handlers as _chat_handlers_module
from .lesson_core_tool_service import lesson_capture as _lesson_capture_impl
from .paths import DATA_DIR, parse_date_str
from .student_import_service import (
    import_students_from_responses as _import_students_from_responses_impl,
)
from .student_import_service import (
    resolve_responses_file as _resolve_responses_file_impl,
)
from .student_import_service import (
    student_import as _student_import_impl,
)
from .teacher_model_config_service import (
    teacher_model_config_get as _teacher_model_config_get_impl,
)
from .teacher_model_config_service import (
    teacher_model_config_update as _teacher_model_config_update_impl,
)
from .teacher_provider_registry_service import (
    teacher_provider_registry_create as _teacher_provider_registry_create_impl,
)
from .teacher_provider_registry_service import (
    teacher_provider_registry_delete as _teacher_provider_registry_delete_impl,
)
from .teacher_provider_registry_service import (
    teacher_provider_registry_get as _teacher_provider_registry_get_impl,
)
from .teacher_provider_registry_service import (
    teacher_provider_registry_probe_models as _teacher_provider_registry_probe_models_impl,
)
from .teacher_provider_registry_service import (
    teacher_provider_registry_update as _teacher_provider_registry_update_impl,
)
from .tool_dispatch_service import tool_dispatch as _tool_dispatch_impl
from .wiring.assignment_wiring import _assignment_generate_tool_deps
from .wiring.chat_wiring import (
    _chat_event_stream_deps,
    _chat_handlers_deps,
    _chat_job_process_deps,
    _chat_runtime_deps,
    _chat_support_deps,
    _compute_chat_reply_deps,
)
from .wiring.exam_wiring import _exam_longform_deps
from .wiring.misc_wiring import (
    _agent_runtime_deps,
    _chart_agent_run_deps,
    _content_catalog_deps,
    _core_example_tool_deps,
    _lesson_core_tool_deps,
    _tool_dispatch_deps,
)
from .wiring.student_wiring import _student_import_deps
from .wiring.teacher_wiring import _teacher_model_config_deps, _teacher_provider_registry_deps


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


async def chat(req: ChatRequest) -> Any:
    return await _chat_handlers_module.chat(req, deps=_chat_handlers_deps())


async def chat_start(req: ChatStartRequest) -> Any:
    return await _chat_handlers_module.chat_start(req, deps=_chat_handlers_deps())


async def chat_status(job_id: str) -> Any:
    return await _chat_handlers_module.chat_status(job_id, deps=_chat_handlers_deps())


def chat_event_stream_deps() -> Any:
    return _chat_event_stream_deps()


def teacher_model_config_get(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_model_config_get_impl(args, deps=_teacher_model_config_deps())


def teacher_model_config_update(args: Dict[str, Any]) -> Dict[str, Any]:
    return _teacher_model_config_update_impl(args, deps=_teacher_model_config_deps())


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
    from .assignment_generate_tool_service import (
        assignment_generate as _assignment_generate_tool_impl,
    )

    return _assignment_generate_tool_impl(args, deps=_assignment_generate_tool_deps())


def assignment_render(args: Dict[str, Any]) -> Dict[str, Any]:
    from .assignment_generate_tool_service import assignment_render as _assignment_render_impl

    return _assignment_render_impl(args, deps=_assignment_generate_tool_deps())


def chart_exec(args: Dict[str, Any]) -> Dict[str, Any]:
    from .wiring import get_app_core as _app_core

    _ac = _app_core()
    return _ac.execute_chart_exec(
        args,
        app_root=_ac.APP_ROOT,
        uploads_dir=_ac.UPLOADS_DIR,
    )


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


def tool_dispatch(
    name: str,
    args: Dict[str, Any],
    role: Optional[str] = None,
    *,
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
) -> Dict[str, Any]:
    return _tool_dispatch_impl(
        name,
        args,
        role,
        deps=_tool_dispatch_deps(),
        skill_id=skill_id,
        teacher_id=teacher_id,
    )


def call_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    role_hint: Optional[str] = None,
    max_tokens: Optional[int] = None,
    skill_id: Optional[str] = None,
    kind: Optional[str] = None,
    teacher_id: Optional[str] = None,
    skill_runtime: Optional[Any] = None,
    stream: bool = False,
    token_sink: Optional[Callable[[str], None]] = None,
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
        stream=stream,
        token_sink=token_sink,
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


def run_agent(
    messages: List[Dict[str, Any]],
    role_hint: Optional[str],
    extra_system: Optional[str] = None,
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    return _run_agent_runtime_impl(
        messages,
        role_hint,
        deps=_agent_runtime_deps(),
        extra_system=extra_system,
        skill_id=skill_id,
        teacher_id=teacher_id,
        event_sink=event_sink,
    )


def compute_chat_reply_sync(
    req: ChatRequest,
    session_id: str = "main",
    teacher_id_override: Optional[str] = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Tuple[str, Optional[str], str]:
    return _compute_chat_reply_sync_impl(
        req,
        deps=_compute_chat_reply_deps(),
        session_id=session_id,
        teacher_id_override=teacher_id_override,
        event_sink=event_sink,
    )


def resolve_student_session_id(
    student_id: str,
    assignment_id: Optional[str],
    assignment_date: Optional[str],
) -> str:
    return _resolve_student_session_id_impl(
        student_id,
        assignment_id,
        assignment_date,
        parse_date_str=parse_date_str,
    )


def process_chat_job(job_id: str) -> None:
    _process_chat_job_impl(job_id, deps=_chat_job_process_deps())
