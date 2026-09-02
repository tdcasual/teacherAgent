from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set, Tuple

from .paths import TeacherIdentityError
from .tool_confirm_service import maybe_confirmation_required, tool_is_mutating


def _default_load_skill_runtime(_role: Optional[str], _skill_id: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
    return None, None


def _default_allowed_tools(_role: Optional[str]) -> Set[str]:
    return set()


def _default_assignment_progress(_assignment_id: str) -> Dict[str, Any]:
    return {"error": "assignment_progress_not_available"}


def _default_assignment_mutate(_assignment_id: str) -> Dict[str, Any]:
    return {"error": "assignment_mutate_not_available"}


def _default_assignment_my_today(_student_id: str, _date: Optional[str] = None) -> Dict[str, Any]:
    return {"error": "assignment_today_not_available"}


def _default_assignment_my_result(_assignment_id: str, _student_id: str) -> Dict[str, Any]:
    return {"error": "assignment_result_not_available"}


def _default_assignment_owner_id(_assignment_id: str) -> Optional[str]:
    return None


@dataclass(frozen=True)
class ToolDispatchDeps:
    tool_registry: Any
    list_assignments: Callable[..., Dict[str, Any]]
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
    load_skill_runtime: Callable[[Optional[str], Optional[str]], Tuple[Optional[Any], Optional[str]]] = _default_load_skill_runtime
    allowed_tools: Callable[[Optional[str]], Set[str]] = _default_allowed_tools
    assignment_progress: Callable[[str], Dict[str, Any]] = _default_assignment_progress
    assignment_publish: Callable[[str], Dict[str, Any]] = _default_assignment_mutate
    assignment_archive: Callable[[str], Dict[str, Any]] = _default_assignment_mutate
    assignment_unarchive: Callable[[str], Dict[str, Any]] = _default_assignment_mutate
    assignment_recompute_roster: Callable[[str], Dict[str, Any]] = _default_assignment_mutate
    assignment_my_today: Callable[[str, Optional[str]], Dict[str, Any]] = _default_assignment_my_today
    assignment_my_result: Callable[[str, str], Dict[str, Any]] = _default_assignment_my_result
    assignment_owner_id: Callable[[str], Optional[str]] = _default_assignment_owner_id



def _require_teacher(role: Optional[str], detail: str) -> Optional[Dict[str, Any]]:
    if role == "teacher":
        return None
    return {"error": "permission denied", "detail": detail}


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


def _assignment_list_for_actor(
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    role_norm = str(role or "").strip().lower()
    if role_norm in {"admin", "service"}:
        return deps.list_assignments(owner_teacher_id=None)
    owner = str(teacher_id or "").strip()
    if not owner:
        return {"error": "teacher_id_required"}
    return deps.list_assignments(owner_teacher_id=owner)


def _require_student_actor(*, role: Optional[str], actor_id: Optional[str]) -> str | Dict[str, Any]:
    if str(role or "").strip().lower() != "student":
        return {"error": "permission denied", "detail": "student tools require student role"}
    student_id = str(actor_id or "").strip()
    if not student_id:
        return {"error": "student_id_required"}
    return student_id


def _require_assignment_owner(
    assignment_id: str,
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
    allow_missing: bool = False,
) -> Optional[Dict[str, Any]]:
    role_norm = str(role or "").strip().lower()
    if role_norm in {"admin", "service"}:
        return None
    aid = str(assignment_id or "").strip()
    if not aid:
        if allow_missing:
            return None
        return {"error": "assignment_id is required"}
    owner = str(teacher_id or "").strip()
    if not owner:
        return {"error": "teacher_id_required"}
    meta_owner = deps.assignment_owner_id(aid)
    if meta_owner is None:
        if allow_missing:
            return None
        return {"error": "assignment_not_found", "assignment_id": aid}
    if str(meta_owner).strip() != owner:
        return {"error": "forbidden_assignment_owner"}
    return None


def _owned_assignment_generate(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    denied = _require_assignment_owner(
        str(args.get("assignment_id") or ""),
        deps=deps,
        role=role,
        teacher_id=teacher_id,
        allow_missing=True,
    )
    if denied:
        return denied
    return deps.assignment_generate(args)


def _owned_assignment_render(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    denied = _require_assignment_owner(
        str(args.get("assignment_id") or ""),
        deps=deps,
        role=role,
        teacher_id=teacher_id,
    )
    if denied:
        return denied
    return deps.assignment_render(args)


def _owned_assignment_requirements_save(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    denied = _require_assignment_owner(
        str(args.get("assignment_id") or ""),
        deps=deps,
        role=role,
        teacher_id=teacher_id,
        allow_missing=True,
    )
    if denied:
        return denied
    return deps.save_assignment_requirements(
        str(args.get("assignment_id", "")),
        args.get("requirements") or {},
        deps.parse_date_str(args.get("date")),
        created_by="teacher",
    )


def _owned_assignment_progress(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    assignment_id = str(args.get("assignment_id") or "")
    denied = _require_assignment_owner(
        assignment_id, deps=deps, role=role, teacher_id=teacher_id
    )
    if denied:
        return denied
    return deps.assignment_progress(assignment_id)


def _filter_progress_students(progress: Dict[str, Any], *, predicate) -> Dict[str, Any]:
    if not isinstance(progress, dict) or progress.get("error"):
        return progress
    students = [item for item in (progress.get("students") or []) if isinstance(item, dict) and predicate(item)]
    out = dict(progress)
    out["students"] = students
    out["count"] = len(students)
    return out


def _is_unsubmitted(student: Dict[str, Any]) -> bool:
    submission = student.get("submission") if isinstance(student.get("submission"), dict) else {}
    return not bool(submission.get("best"))


def _assignment_missing(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    return _filter_progress_students(
        _owned_assignment_progress(args, deps=deps, role=role, teacher_id=teacher_id),
        predicate=_is_unsubmitted,
    )


def _assignment_overdue(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    return _filter_progress_students(
        _owned_assignment_progress(args, deps=deps, role=role, teacher_id=teacher_id),
        predicate=lambda student: bool(student.get("overdue")) and _is_unsubmitted(student),
    )


def _assignment_attempt_get(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    teacher_id: Optional[str],
) -> Dict[str, Any]:
    assignment_id = str(args.get("assignment_id") or "")
    student_id = str(args.get("student_id") or "")
    progress = _owned_assignment_progress(args, deps=deps, role=role, teacher_id=teacher_id)
    if not isinstance(progress, dict) or progress.get("error"):
        return progress
    for student in progress.get("students") or []:
        if isinstance(student, dict) and str(student.get("student_id") or "") == student_id:
            return {"ok": True, "assignment_id": assignment_id, "student": student}
    return {"error": "attempt_not_found", "assignment_id": assignment_id, "student_id": student_id}


def _assignment_my_today(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    actor_id: Optional[str],
) -> Dict[str, Any]:
    student_id = _require_student_actor(role=role, actor_id=actor_id)
    if isinstance(student_id, dict):
        return student_id
    return deps.assignment_my_today(student_id, str(args.get("date") or "").strip() or None)


def _assignment_my_result(
    args: Dict[str, Any],
    *,
    deps: ToolDispatchDeps,
    role: Optional[str],
    actor_id: Optional[str],
) -> Dict[str, Any]:
    student_id = _require_student_actor(role=role, actor_id=actor_id)
    if isinstance(student_id, dict):
        return student_id
    return deps.assignment_my_result(str(args.get("assignment_id") or ""), student_id)


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
    actor_id: Optional[str] = None,
) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    return {
        "assignment.list": lambda _args: _assignment_list_for_actor(
            deps=deps, role=role, teacher_id=teacher_id
        ),
        "assignment.progress": _teacher_only_handler(
            role=role,
            detail="assignment.progress requires teacher role",
            fn=lambda args: _owned_assignment_progress(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.missing": _teacher_only_handler(
            role=role,
            detail="assignment.missing requires teacher role",
            fn=lambda args: _assignment_missing(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.overdue": _teacher_only_handler(
            role=role,
            detail="assignment.overdue requires teacher role",
            fn=lambda args: _assignment_overdue(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.attempt.get": _teacher_only_handler(
            role=role,
            detail="assignment.attempt.get requires teacher role",
            fn=lambda args: _assignment_attempt_get(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.publish": _teacher_only_handler(
            role=role,
            detail="assignment.publish requires teacher role",
            fn=lambda args: deps.assignment_publish(str(args.get("assignment_id") or "")),
        ),
        "assignment.archive": _teacher_only_handler(
            role=role,
            detail="assignment.archive requires teacher role",
            fn=lambda args: deps.assignment_archive(str(args.get("assignment_id") or "")),
        ),
        "assignment.unarchive": _teacher_only_handler(
            role=role,
            detail="assignment.unarchive requires teacher role",
            fn=lambda args: deps.assignment_unarchive(str(args.get("assignment_id") or "")),
        ),
        "assignment.recompute_roster": _teacher_only_handler(
            role=role,
            detail="assignment.recompute_roster requires teacher role",
            fn=lambda args: deps.assignment_recompute_roster(str(args.get("assignment_id") or "")),
        ),
        "assignment.my_today": lambda args: _assignment_my_today(
            args, deps=deps, role=role, actor_id=actor_id
        ),
        "assignment.my_result": lambda args: _assignment_my_result(
            args, deps=deps, role=role, actor_id=actor_id
        ),
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
        "assignment.generate": _teacher_only_handler(
            role=role,
            detail="assignment.generate requires teacher role",
            fn=lambda args: _owned_assignment_generate(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.render": _teacher_only_handler(
            role=role,
            detail="assignment.render requires teacher role",
            fn=lambda args: _owned_assignment_render(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
        ),
        "assignment.requirements.save": _teacher_only_handler(
            role=role,
            detail="assignment.requirements.save requires teacher role",
            fn=lambda args: _owned_assignment_requirements_save(
                args, deps=deps, role=role, teacher_id=teacher_id
            ),
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
        "teacher.workspace.init": lambda args: _teacher_workspace_init_handler(
            {**args, "teacher_id": args.get("teacher_id") or teacher_id}, deps=deps
        ),
        "teacher.memory.get": lambda args: _teacher_memory_get(
            {**args, "teacher_id": args.get("teacher_id") or teacher_id}, deps
        ),
        "teacher.memory.search": lambda args: _teacher_memory_search_handler(
            {**args, "teacher_id": args.get("teacher_id") or teacher_id}, deps=deps
        ),
        "teacher.memory.propose": lambda args: _teacher_memory_propose_handler(
            {**args, "teacher_id": args.get("teacher_id") or teacher_id}, deps=deps
        ),
        "teacher.memory.apply": lambda args: _teacher_memory_apply_handler(
            {**args, "teacher_id": args.get("teacher_id") or teacher_id}, deps=deps
        ),
    }



def _deny_mutating_for_non_teacher(
    *,
    static_tool: Any,
    name: str,
    args: Dict[str, Any],
    role: Optional[str],
    confirmed: bool,
    actor_id: Optional[str],
    job_id: Optional[str],
    lane_id: Optional[str],
    tool_call_id: Optional[str],
    skill_id: Optional[str],
    teacher_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not tool_is_mutating(static_tool, name):
        return None
    role_norm = str(role or "").strip().lower()
    if role_norm not in {"teacher", "admin"}:
        return {"error": "permission denied", "detail": f"{name} requires teacher role"}
    return maybe_confirmation_required(
        tool=static_tool,
        name=name,
        args=args,
        confirmed=bool(confirmed),
        actor_id=str(actor_id or teacher_id or ""),
        job_id=str(job_id or ""),
        lane_id=str(lane_id or ""),
        tool_call_id=str(tool_call_id or ""),
        role=str(role or ""),
        skill_id=str(skill_id or ""),
        teacher_id=str(teacher_id or ""),
    )


def tool_dispatch(
    name: str,
    args: Dict[str, Any],
    role: Optional[str],
    deps: ToolDispatchDeps,
    *,
    skill_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    confirmed: bool = False,
    actor_id: Optional[str] = None,
    job_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
) -> Dict[str, Any]:
    static_tool = deps.tool_registry.get(name)
    if static_tool is None:
        return {"error": f"unknown tool: {name}"}

    issues = deps.tool_registry.validate_arguments(name, args)
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

    handlers = _build_handlers(role=role, deps=deps, teacher_id=teacher_id, actor_id=actor_id)
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    mutating_denied = _deny_mutating_for_non_teacher(
        static_tool=static_tool,
        name=name,
        args=args,
        role=role,
        confirmed=confirmed,
        actor_id=actor_id,
        job_id=job_id,
        lane_id=lane_id,
        tool_call_id=tool_call_id,
        skill_id=skill_id,
        teacher_id=teacher_id,
    )
    if mutating_denied is not None:
        return mutating_denied
    try:
        return handler(args)
    except TeacherIdentityError as exc:
        return {"error": str(exc.detail or "teacher_id_required"), "status_code": int(exc.status_code)}
