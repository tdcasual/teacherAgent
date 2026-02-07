from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


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
    teacher_read_text: Callable[[Any, int], str]
    teacher_memory_search: Callable[[str, str, int], Dict[str, Any]]
    teacher_memory_propose: Callable[[str, str, str, str], Dict[str, Any]]
    teacher_memory_apply: Callable[[str, str, bool], Dict[str, Any]]
    teacher_llm_routing_get: Callable[[Dict[str, Any]], Dict[str, Any]]
    teacher_llm_routing_simulate: Callable[[Dict[str, Any]], Dict[str, Any]]
    teacher_llm_routing_propose: Callable[[Dict[str, Any]], Dict[str, Any]]
    teacher_llm_routing_apply: Callable[[Dict[str, Any]], Dict[str, Any]]
    teacher_llm_routing_rollback: Callable[[Dict[str, Any]], Dict[str, Any]]


def _require_teacher(role: Optional[str], detail: str) -> Optional[Dict[str, Any]]:
    if role == "teacher":
        return None
    return {"error": "permission denied", "detail": detail}


def tool_dispatch(name: str, args: Dict[str, Any], role: Optional[str], deps: ToolDispatchDeps) -> Dict[str, Any]:
    if deps.tool_registry.get(name) is None:
        return {"error": f"unknown tool: {name}"}
    issues = deps.tool_registry.validate_arguments(name, args)
    if issues:
        return {"error": "invalid_arguments", "tool": name, "issues": issues[:20]}

    if name == "exam.list":
        return deps.list_exams()
    if name == "exam.get":
        return deps.exam_get(args.get("exam_id", ""))
    if name == "exam.analysis.get":
        return deps.exam_analysis_get(args.get("exam_id", ""))
    if name == "exam.analysis.charts.generate":
        denied = _require_teacher(role, "exam.analysis.charts.generate requires teacher role")
        if denied:
            return denied
        return deps.exam_analysis_charts_generate(args)
    if name == "exam.students.list":
        return deps.exam_students_list(args.get("exam_id", ""), int(args.get("limit", 50) or 50))
    if name == "exam.student.get":
        return deps.exam_student_detail(
            args.get("exam_id", ""),
            student_id=args.get("student_id"),
            student_name=args.get("student_name"),
            class_name=args.get("class_name"),
        )
    if name == "exam.question.get":
        return deps.exam_question_detail(
            args.get("exam_id", ""),
            question_id=args.get("question_id"),
            question_no=args.get("question_no"),
            top_n=args.get("top_n", 5),
        )
    if name == "exam.range.top_students":
        return deps.exam_range_top_students(
            args.get("exam_id", ""),
            start_question_no=args.get("start_question_no"),
            end_question_no=args.get("end_question_no"),
            top_n=args.get("top_n", 10),
        )
    if name == "exam.range.summary.batch":
        return deps.exam_range_summary_batch(
            args.get("exam_id", ""),
            ranges=args.get("ranges"),
            top_n=args.get("top_n", 5),
        )
    if name == "exam.question.batch.get":
        return deps.exam_question_batch_detail(
            args.get("exam_id", ""),
            question_nos=args.get("question_nos"),
            top_n=args.get("top_n", 5),
        )
    if name == "assignment.list":
        return deps.list_assignments()
    if name == "lesson.list":
        return deps.list_lessons()
    if name == "lesson.capture":
        return deps.lesson_capture(args)
    if name == "student.search":
        return deps.student_search(args.get("query", ""), int(args.get("limit", 5)))
    if name == "student.profile.get":
        return deps.student_profile_get(args.get("student_id", ""))
    if name == "student.profile.update":
        return deps.student_profile_update(args)
    if name == "student.import":
        denied = _require_teacher(role, "student.import requires teacher role")
        if denied:
            return denied
        return deps.student_import(args)
    if name == "assignment.generate":
        return deps.assignment_generate(args)
    if name == "assignment.render":
        return deps.assignment_render(args)
    if name == "assignment.requirements.save":
        assignment_id = str(args.get("assignment_id", ""))
        date_str = deps.parse_date_str(args.get("date"))
        requirements = args.get("requirements") or {}
        return deps.save_assignment_requirements(assignment_id, requirements, date_str, created_by="teacher")
    if name == "core_example.search":
        return deps.core_example_search(args)
    if name == "core_example.register":
        return deps.core_example_register(args)
    if name == "core_example.render":
        return deps.core_example_render(args)
    if name == "chart.agent.run":
        denied = _require_teacher(role, "chart.agent.run requires teacher role")
        if denied:
            return denied
        return deps.chart_agent_run(args)
    if name == "chart.exec":
        denied = _require_teacher(role, "chart.exec requires teacher role")
        if denied:
            return denied
        return deps.chart_exec(args)
    if name == "teacher.workspace.init":
        teacher_id = deps.resolve_teacher_id(args.get("teacher_id"))
        base = deps.ensure_teacher_workspace(teacher_id)
        return {"ok": True, "teacher_id": teacher_id, "workspace": str(base)}
    if name == "teacher.memory.get":
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
        return {"ok": True, "teacher_id": teacher_id, "file": str(path), "content": deps.teacher_read_text(path, max_chars=max_chars)}
    if name == "teacher.memory.search":
        teacher_id = deps.resolve_teacher_id(args.get("teacher_id"))
        query = str(args.get("query") or "")
        limit = int(args.get("limit", 5) or 5)
        result = deps.teacher_memory_search(teacher_id, query, limit)
        result.update({"ok": True, "teacher_id": teacher_id, "query": query})
        return result
    if name == "teacher.memory.propose":
        teacher_id = deps.resolve_teacher_id(args.get("teacher_id"))
        target = str(args.get("target") or "MEMORY")
        title = str(args.get("title") or "")
        content = str(args.get("content") or "")
        return deps.teacher_memory_propose(teacher_id, target=target, title=title, content=content)
    if name == "teacher.memory.apply":
        teacher_id = deps.resolve_teacher_id(args.get("teacher_id"))
        proposal_id = str(args.get("proposal_id") or "")
        approve = bool(args.get("approve", True))
        return deps.teacher_memory_apply(teacher_id, proposal_id=proposal_id, approve=approve)
    if name == "teacher.llm_routing.get":
        denied = _require_teacher(role, "teacher.llm_routing.get requires teacher role")
        if denied:
            return denied
        return deps.teacher_llm_routing_get(args)
    if name == "teacher.llm_routing.simulate":
        denied = _require_teacher(role, "teacher.llm_routing.simulate requires teacher role")
        if denied:
            return denied
        return deps.teacher_llm_routing_simulate(args)
    if name == "teacher.llm_routing.propose":
        denied = _require_teacher(role, "teacher.llm_routing.propose requires teacher role")
        if denied:
            return denied
        return deps.teacher_llm_routing_propose(args)
    if name == "teacher.llm_routing.apply":
        denied = _require_teacher(role, "teacher.llm_routing.apply requires teacher role")
        if denied:
            return denied
        return deps.teacher_llm_routing_apply(args)
    if name == "teacher.llm_routing.rollback":
        denied = _require_teacher(role, "teacher.llm_routing.rollback requires teacher role")
        if denied:
            return denied
        return deps.teacher_llm_routing_rollback(args)
    return {"error": f"unknown tool: {name}"}
