from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set, Tuple


def _default_survey_report_list(_teacher_id: str, _status: Optional[str] = None) -> Dict[str, Any]:
    return {"items": []}



def _default_survey_report_get(_report_id: str, _teacher_id: str) -> Dict[str, Any]:
    return {"error": "survey_not_available"}



def _default_survey_report_rerun(
    _report_id: str,
    _teacher_id: str,
    _reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {"error": "survey_not_available"}



def _default_analysis_report_list(
    _teacher_id: str,
    _domain: Optional[str] = None,
    _status: Optional[str] = None,
    _strategy_id: Optional[str] = None,
    _target_type: Optional[str] = None,
) -> Dict[str, Any]:
    return {"items": []}



def _default_analysis_report_get(
    _report_id: str,
    _teacher_id: str,
    _domain: Optional[str] = None,
) -> Dict[str, Any]:
    return {"error": "analysis_report_not_available"}



def _default_analysis_report_rerun(
    _report_id: str,
    _teacher_id: str,
    _domain: Optional[str] = None,
    _reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {"error": "analysis_report_not_available"}



def _default_analysis_review_list(
    _teacher_id: str,
    _domain: Optional[str] = None,
    _status: Optional[str] = None,
) -> Dict[str, Any]:
    return {"items": []}


def _default_load_skill_runtime(_role: Optional[str], _skill_id: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
    return None, None


def _default_allowed_tools(_role: Optional[str]) -> Set[str]:
    return set()


@dataclass(frozen=True)
class ToolDispatchDeps:
    tool_registry: Any
    list_exams: Callable[[], Dict[str, Any]]
    exam_get: Callable[[str], Dict[str, Any]]
    exam_analysis_get: Callable[[str], Dict[str, Any]]
    exam_analysis_charts_generate: Callable[[Dict[str, Any]], Dict[str, Any]]
    exam_students_list: Callable[[str, int], Dict[str, Any]]
    exam_student_detail: Callable[..., Dict[str, Any]]
    exam_question_detail: Callable[..., Dict[str, Any]]
    exam_range_top_students: Callable[..., Dict[str, Any]]
    exam_range_summary_batch: Callable[..., Dict[str, Any]]
    exam_question_batch_detail: Callable[..., Dict[str, Any]]
    list_assignments: Callable[[], Dict[str, Any]]
    list_lessons: Callable[[], Dict[str, Any]]
    lesson_capture: Callable[[Dict[str, Any]], Dict[str, Any]]
    student_search: Callable[[str, int], Dict[str, Any]]
    student_profile_get: Callable[[str], Dict[str, Any]]
    student_profile_update: Callable[[Dict[str, Any]], Dict[str, Any]]
    student_import: Callable[[Dict[str, Any]], Dict[str, Any]]
    assignment_generate: Callable[[Dict[str, Any]], Dict[str, Any]]
    assignment_render: Callable[[Dict[str, Any]], Dict[str, Any]]
    save_assignment_requirements: Callable[..., Dict[str, Any]]
    parse_date_str: Callable[[Any], Optional[str]]
    core_example_search: Callable[[Dict[str, Any]], Dict[str, Any]]
    core_example_register: Callable[[Dict[str, Any]], Dict[str, Any]]
    core_example_render: Callable[[Dict[str, Any]], Dict[str, Any]]
    chart_agent_run: Callable[[Dict[str, Any]], Dict[str, Any]]
    chart_exec: Callable[[Dict[str, Any]], Dict[str, Any]]
    resolve_teacher_id: Callable[[Any], str]
    ensure_teacher_workspace: Callable[[str], Any]
    teacher_workspace_dir: Callable[[str], Any]
    teacher_workspace_file: Callable[[str, str], Any]
    teacher_daily_memory_path: Callable[[str, Optional[str]], Any]
    teacher_read_text: Callable[..., str]
    teacher_memory_search: Callable[[str, str, int], Dict[str, Any]]
    teacher_memory_propose: Callable[..., Dict[str, Any]]
    teacher_memory_apply: Callable[..., Dict[str, Any]]
    survey_report_list: Callable[[str, Optional[str]], Dict[str, Any]] = _default_survey_report_list
    survey_report_get: Callable[[str, str], Dict[str, Any]] = _default_survey_report_get
    survey_report_rerun: Callable[[str, str, Optional[str]], Dict[str, Any]] = _default_survey_report_rerun
    analysis_report_list: Callable[[str, Optional[str], Optional[str], Optional[str], Optional[str]], Dict[str, Any]] = _default_analysis_report_list
    analysis_report_get: Callable[[str, str, Optional[str]], Dict[str, Any]] = _default_analysis_report_get
    analysis_report_rerun: Callable[[str, str, Optional[str], Optional[str]], Dict[str, Any]] = _default_analysis_report_rerun
    analysis_review_list: Callable[[str, Optional[str], Optional[str]], Dict[str, Any]] = _default_analysis_review_list
    load_skill_runtime: Callable[[Optional[str], Optional[str]], Tuple[Optional[Any], Optional[str]]] = _default_load_skill_runtime
    allowed_tools: Callable[[Optional[str]], Set[str]] = _default_allowed_tools



def _require_teacher(role: Optional[str], detail: str) -> Optional[Dict[str, Any]]:
    if role == "teacher":
        return None
    return {"error": "permission denied", "detail": detail}


def _resolve_survey_report_id(args: Dict[str, Any]) -> str:
    return str(args.get("report_id") or args.get("target_id") or "").strip()


def _resolve_analysis_report_id(args: Dict[str, Any]) -> str:
    return str(args.get("report_id") or args.get("target_id") or "").strip()


def _resolve_skill_allowed_tools(
    *,
    role: Optional[str],
    skill_id: Optional[str],
    deps: ToolDispatchDeps,
) -> Optional[Set[str]]:
    role_final = str(role or "").strip().lower()
    skill_id_final = str(skill_id or "").strip()
    if role_final != "teacher" or not skill_id_final:
        return None
    role_allowed = set(deps.allowed_tools(role_final))
    if not role_allowed:
        return None
    try:
        runtime, _warning = deps.load_skill_runtime(role_final, skill_id_final)
    except Exception:
        return role_allowed
    if runtime is None:
        return role_allowed
    apply_tool_policy = getattr(runtime, "apply_tool_policy", None)
    if not callable(apply_tool_policy):
        return role_allowed
    try:
        return set(apply_tool_policy(role_allowed))
    except Exception:
        return role_allowed


def _teacher_memory_get(args: Dict[str, Any], deps: ToolDispatchDeps) -> Dict[str, Any]:
    teacher_id = deps.resolve_teacher_id(args.get("teacher_id"))
    target = str(args.get("file") or "MEMORY.md").strip()
    date_str = str(args.get("date") or "").strip() or None
    max_chars = int(args.get("max_chars", 8000) or 8000)
    if target.upper() == "DAILY":
        path = deps.teacher_daily_memory_path(teacher_id, date_str)
    else:
        if target in {"AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}:
            path = deps.teacher_workspace_dir(teacher_id) / target
        else:
            path = deps.teacher_workspace_file(teacher_id, "MEMORY.md")
    return {
        "ok": True,
        "teacher_id": teacher_id,
        "file": str(path),
        "content": deps.teacher_read_text(path, max_chars=max_chars),
    }


def _teacher_only_handler(
    *,
    role: Optional[str],
    detail: str,
    fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _wrapped(args: Dict[str, Any]) -> Dict[str, Any]:
        denied = _require_teacher(role, detail)
        if denied:
            return denied
        return fn(args)

    return _wrapped


def _resolve_tool_teacher_id(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    teacher_id: Optional[str],
) -> str:
    raw_teacher_id = args.get("teacher_id") or teacher_id or ""
    return deps.resolve_teacher_id(raw_teacher_id)


def _chart_exec_handler(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    chart_exec_args = dict(args or {})
    chart_exec_args["_audit_source"] = "tool_dispatch.chart.exec"
    chart_exec_args["_audit_role"] = str(role or "").strip().lower()
    if teacher_id:
        chart_exec_args["_audit_actor"] = str(teacher_id).strip()
    return deps.chart_exec(chart_exec_args)


def _teacher_workspace_init_handler(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
) -> Dict[str, Any]:
    teacher_id_resolved = deps.resolve_teacher_id(args.get("teacher_id"))
    base = deps.ensure_teacher_workspace(teacher_id_resolved)
    return {"ok": True, "teacher_id": teacher_id_resolved, "workspace": str(base)}


def _teacher_memory_search_handler(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
) -> Dict[str, Any]:
    teacher_id_resolved = deps.resolve_teacher_id(args.get("teacher_id"))
    query = str(args.get("query") or "")
    limit = int(args.get("limit", 5) or 5)
    result = deps.teacher_memory_search(teacher_id_resolved, query, limit)
    result.update({"ok": True, "teacher_id": teacher_id_resolved, "query": query})
    return result


def _teacher_memory_propose_handler(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
) -> Dict[str, Any]:
    teacher_id_resolved = deps.resolve_teacher_id(args.get("teacher_id"))
    target = str(args.get("target") or "MEMORY")
    title = str(args.get("title") or "")
    content = str(args.get("content") or "")
    return deps.teacher_memory_propose(
        teacher_id_resolved,
        target=target,
        title=title,
        content=content,
    )


def _teacher_memory_apply_handler(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
) -> Dict[str, Any]:
    teacher_id_resolved = deps.resolve_teacher_id(args.get("teacher_id"))
    proposal_id = str(args.get("proposal_id") or "")
    approve = bool(args.get("approve", True))
    return deps.teacher_memory_apply(teacher_id_resolved, proposal_id=proposal_id, approve=approve)



def _build_handlers(
    *,
    role: Optional[str],
    deps: ToolDispatchDeps,
    teacher_id: Optional[str],
) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    return {
        "exam.list": lambda _args: deps.list_exams(),
        "exam.get": lambda args: deps.exam_get(args.get("exam_id", "")),
        "exam.analysis.get": lambda args: deps.exam_analysis_get(args.get("exam_id", "")),
        "exam.analysis.charts.generate": _teacher_only_handler(
            role=role,
            detail="exam.analysis.charts.generate requires teacher role",
            fn=lambda args: deps.exam_analysis_charts_generate(args),
        ),
        "exam.students.list": lambda args: deps.exam_students_list(
            args.get("exam_id", ""),
            int(args.get("limit", 50) or 50),
        ),
        "exam.student.get": lambda args: deps.exam_student_detail(
            args.get("exam_id", ""),
            student_id=args.get("student_id"),
            student_name=args.get("student_name"),
            class_name=args.get("class_name"),
        ),
        "exam.question.get": lambda args: deps.exam_question_detail(
            args.get("exam_id", ""),
            question_id=args.get("question_id"),
            question_no=args.get("question_no"),
            top_n=args.get("top_n", 5),
        ),
        "exam.range.top_students": lambda args: deps.exam_range_top_students(
            args.get("exam_id", ""),
            start_question_no=args.get("start_question_no"),
            end_question_no=args.get("end_question_no"),
            top_n=args.get("top_n", 10),
        ),
        "exam.range.summary.batch": lambda args: deps.exam_range_summary_batch(
            args.get("exam_id", ""),
            ranges=args.get("ranges"),
            top_n=args.get("top_n", 5),
        ),
        "exam.question.batch.get": lambda args: deps.exam_question_batch_detail(
            args.get("exam_id", ""),
            question_nos=args.get("question_nos"),
            top_n=args.get("top_n", 5),
        ),
        "analysis.report.list": _teacher_only_handler(
            role=role,
            detail="analysis.report.list requires teacher role",
            fn=lambda args: deps.analysis_report_list(
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("domain") or "").strip() or None,
                str(args.get("status") or "").strip() or None,
                str(args.get("strategy_id") or "").strip() or None,
                str(args.get("target_type") or "").strip() or None,
            ),
        ),
        "analysis.report.get": _teacher_only_handler(
            role=role,
            detail="analysis.report.get requires teacher role",
            fn=lambda args: deps.analysis_report_get(
                _resolve_analysis_report_id(args),
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("domain") or "").strip() or None,
            ),
        ),
        "analysis.report.rerun": _teacher_only_handler(
            role=role,
            detail="analysis.report.rerun requires teacher role",
            fn=lambda args: deps.analysis_report_rerun(
                _resolve_analysis_report_id(args),
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("domain") or "").strip() or None,
                str(args.get("reason") or "").strip() or None,
            ),
        ),
        "analysis.review.list": _teacher_only_handler(
            role=role,
            detail="analysis.review.list requires teacher role",
            fn=lambda args: deps.analysis_review_list(
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("domain") or "").strip() or None,
                str(args.get("status") or "").strip() or None,
            ),
        ),
        "survey.report.list": _teacher_only_handler(
            role=role,
            detail="survey.report.list requires teacher role",
            fn=lambda args: deps.survey_report_list(
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("status") or "").strip() or None,
            ),
        ),
        "survey.report.get": _teacher_only_handler(
            role=role,
            detail="survey.report.get requires teacher role",
            fn=lambda args: deps.survey_report_get(
                _resolve_survey_report_id(args),
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
            ),
        ),
        "survey.report.rerun": _teacher_only_handler(
            role=role,
            detail="survey.report.rerun requires teacher role",
            fn=lambda args: deps.survey_report_rerun(
                _resolve_survey_report_id(args),
                _resolve_tool_teacher_id(args, deps=deps, teacher_id=teacher_id),
                str(args.get("reason") or "").strip() or None,
            ),
        ),
        "assignment.list": lambda _args: deps.list_assignments(),
        "lesson.list": lambda _args: deps.list_lessons(),
        "lesson.capture": lambda args: deps.lesson_capture(args),
        "student.search": lambda args: deps.student_search(
            args.get("query", ""),
            int(args.get("limit", 5) or 5),
        ),
        "student.profile.get": lambda args: deps.student_profile_get(args.get("student_id", "")),
        "student.profile.update": lambda args: deps.student_profile_update(args),
        "student.import": _teacher_only_handler(
            role=role,
            detail="student.import requires teacher role",
            fn=lambda args: deps.student_import(args),
        ),
        "assignment.generate": lambda args: deps.assignment_generate(args),
        "assignment.render": lambda args: deps.assignment_render(args),
        "assignment.requirements.save": lambda args: deps.save_assignment_requirements(
            str(args.get("assignment_id", "")),
            args.get("requirements") or {},
            deps.parse_date_str(args.get("date")),
            created_by="teacher",
        ),
        "core_example.search": lambda args: deps.core_example_search(args),
        "core_example.register": lambda args: deps.core_example_register(args),
        "core_example.render": lambda args: deps.core_example_render(args),
        "chart.agent.run": _teacher_only_handler(
            role=role,
            detail="chart.agent.run requires teacher role",
            fn=lambda args: deps.chart_agent_run(args),
        ),
        "chart.exec": _teacher_only_handler(
            role=role,
            detail="chart.exec requires teacher role",
            fn=lambda args: _chart_exec_handler(args, deps=deps, role=role, teacher_id=teacher_id),
        ),
        "teacher.workspace.init": lambda args: _teacher_workspace_init_handler(args, deps=deps),
        "teacher.memory.get": lambda args: _teacher_memory_get(args, deps),
        "teacher.memory.search": lambda args: _teacher_memory_search_handler(args, deps=deps),
        "teacher.memory.propose": lambda args: _teacher_memory_propose_handler(args, deps=deps),
        "teacher.memory.apply": lambda args: _teacher_memory_apply_handler(args, deps=deps),
    }



def tool_dispatch(
    name: str,
    args: Dict[str, Any],
    role: Optional[str],
    deps: ToolDispatchDeps,
    *,
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
) -> Dict[str, Any]:
    static_tool = deps.tool_registry.get(name)
    if static_tool is None:
        return {"error": f"unknown tool: {name}"}

    issues = deps.tool_registry.validate_arguments(name, args)
    if name in {"survey.report.get", "survey.report.rerun"} and not _resolve_survey_report_id(args):
        issues = [*issues, "arguments.report_id: required (or provide target_id)"]
    if name in {"analysis.report.get", "analysis.report.rerun"} and not _resolve_analysis_report_id(args):
        issues = [*issues, "arguments.report_id: required (or provide target_id)"]
    if issues:
        return {"error": "invalid_arguments", "tool": name, "issues": issues[:20]}

    allowed_tools = _resolve_skill_allowed_tools(role=role, skill_id=skill_id, deps=deps)
    if allowed_tools is not None and name not in allowed_tools:
        return {
            "error": "tool_not_allowed",
            "tool": name,
            "role": str(role or ""),
            "skill_id": str(skill_id or ""),
        }

    handlers = _build_handlers(role=role, deps=deps, teacher_id=teacher_id)
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    return handler(args)
