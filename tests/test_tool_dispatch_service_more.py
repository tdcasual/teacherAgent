from __future__ import annotations

from pathlib import Path

from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch


class _Registry:
    def __init__(self, tools: set[str]):
        self._tools = tools

    def get(self, name: str):
        return name if name in self._tools else None

    def validate_arguments(self, _name: str, _args: dict):
        return []


def _deps(tools: set[str]):
    calls: dict[str, object] = {}

    def _remember(name: str, payload: object) -> dict:
        calls[name] = payload
        return {"tool": name, "payload": payload}

    deps = ToolDispatchDeps(
        tool_registry=_Registry(tools),
        list_exams=lambda: {"tool": "exam.list"},
        exam_get=lambda exam_id: _remember("exam.get", exam_id),
        exam_analysis_get=lambda exam_id: _remember("exam.analysis.get", exam_id),
        exam_analysis_charts_generate=lambda args: _remember("exam.analysis.charts.generate", args),
        exam_students_list=lambda exam_id, limit: _remember("exam.students.list", (exam_id, limit)),
        exam_student_detail=lambda exam_id, student_id=None, student_name=None, class_name=None: _remember(
            "exam.student.get", (exam_id, student_id, student_name, class_name)
        ),
        exam_question_detail=lambda exam_id, question_id=None, question_no=None, top_n=5: _remember(
            "exam.question.get", (exam_id, question_id, question_no, top_n)
        ),
        exam_range_top_students=lambda exam_id, start_question_no=None, end_question_no=None, top_n=10: _remember(
            "exam.range.top_students", (exam_id, start_question_no, end_question_no, top_n)
        ),
        exam_range_summary_batch=lambda exam_id, ranges=None, top_n=5: _remember(
            "exam.range.summary.batch", (exam_id, ranges, top_n)
        ),
        exam_question_batch_detail=lambda exam_id, question_nos=None, top_n=5: _remember(
            "exam.question.batch.get", (exam_id, question_nos, top_n)
        ),
        list_assignments=lambda: {"tool": "assignment.list"},
        list_lessons=lambda: {"tool": "lesson.list"},
        lesson_capture=lambda args: _remember("lesson.capture", args),
        student_search=lambda query, limit: _remember("student.search", (query, limit)),
        student_profile_get=lambda student_id: _remember("student.profile.get", student_id),
        student_profile_update=lambda args: _remember("student.profile.update", args),
        student_import=lambda args: _remember("student.import", args),
        assignment_generate=lambda args: _remember("assignment.generate", args),
        assignment_render=lambda args: _remember("assignment.render", args),
        save_assignment_requirements=lambda assignment_id, requirements, date_str, created_by="teacher": _remember(
            "assignment.requirements.save", (assignment_id, requirements, date_str, created_by)
        ),
        parse_date_str=lambda raw: f"parsed:{raw}" if raw else None,
        core_example_search=lambda args: _remember("core_example.search", args),
        core_example_register=lambda args: _remember("core_example.register", args),
        core_example_render=lambda args: _remember("core_example.render", args),
        chart_agent_run=lambda args: _remember("chart.agent.run", args),
        chart_exec=lambda args: _remember("chart.exec", args),
        resolve_teacher_id=lambda raw: str(raw or "teacher") + "-resolved",
        ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / teacher_id,
        teacher_workspace_dir=lambda teacher_id: Path("/tmp") / teacher_id,
        teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / teacher_id / name,
        teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / teacher_id / f"{date_str or 'daily'}.md",
        teacher_read_text=lambda path, max_chars=8000: f"read:{path}:{max_chars}",
        teacher_memory_search=lambda teacher_id, query, limit=5: {"mode": "keyword", "matches": [(teacher_id, query, limit)]},
        teacher_memory_propose=lambda teacher_id, target, title, content: _remember(
            "teacher.memory.propose", (teacher_id, target, title, content)
        ),
        teacher_memory_apply=lambda teacher_id, proposal_id, approve=True: _remember(
            "teacher.memory.apply", (teacher_id, proposal_id, approve)
        ),
        teacher_llm_routing_get=lambda args: _remember("teacher.llm_routing.get", args),
        teacher_llm_routing_simulate=lambda args: _remember("teacher.llm_routing.simulate", args),
        teacher_llm_routing_propose=lambda args: _remember("teacher.llm_routing.propose", args),
        teacher_llm_routing_apply=lambda args: _remember("teacher.llm_routing.apply", args),
        teacher_llm_routing_rollback=lambda args: _remember("teacher.llm_routing.rollback", args),
    )
    return deps, calls


def test_tool_dispatch_covers_core_exam_assignment_and_student_paths():
    names = {
        "exam.list",
        "exam.get",
        "exam.analysis.get",
        "exam.students.list",
        "exam.student.get",
        "exam.question.get",
        "assignment.list",
        "lesson.list",
        "student.search",
        "student.profile.get",
        "student.profile.update",
        "assignment.generate",
        "assignment.render",
        "core_example.search",
    }
    deps, calls = _deps(names)

    assert tool_dispatch("exam.list", {}, role="teacher", deps=deps)["tool"] == "exam.list"
    assert tool_dispatch("exam.get", {"exam_id": "e1"}, role="teacher", deps=deps)["tool"] == "exam.get"
    assert tool_dispatch("exam.analysis.get", {"exam_id": "e2"}, role="teacher", deps=deps)["tool"] == "exam.analysis.get"
    assert tool_dispatch("exam.students.list", {"exam_id": "e3", "limit": 7}, role="teacher", deps=deps)["tool"] == "exam.students.list"
    assert tool_dispatch(
        "exam.student.get",
        {"exam_id": "e4", "student_id": "s1", "student_name": "N", "class_name": "C"},
        role="teacher",
        deps=deps,
    )["tool"] == "exam.student.get"
    assert tool_dispatch(
        "exam.question.get",
        {"exam_id": "e5", "question_id": "q1", "question_no": 2, "top_n": 6},
        role="teacher",
        deps=deps,
    )["tool"] == "exam.question.get"
    assert tool_dispatch("assignment.list", {}, role="teacher", deps=deps)["tool"] == "assignment.list"
    assert tool_dispatch("lesson.list", {}, role="teacher", deps=deps)["tool"] == "lesson.list"
    assert tool_dispatch("student.search", {"query": "abc", "limit": 3}, role="teacher", deps=deps)["tool"] == "student.search"
    assert tool_dispatch("student.profile.get", {"student_id": "stu1"}, role="teacher", deps=deps)["tool"] == "student.profile.get"
    assert tool_dispatch("student.profile.update", {"student_id": "stu1"}, role="teacher", deps=deps)["tool"] == "student.profile.update"
    assert tool_dispatch("assignment.generate", {"topic": "t"}, role="teacher", deps=deps)["tool"] == "assignment.generate"
    assert tool_dispatch("assignment.render", {"assignment_id": "a1"}, role="teacher", deps=deps)["tool"] == "assignment.render"
    assert tool_dispatch("core_example.search", {"query": "x"}, role="teacher", deps=deps)["tool"] == "core_example.search"

    assert calls["exam.students.list"] == ("e3", 7)
    assert calls["student.search"] == ("abc", 3)


def test_tool_dispatch_student_import_role_guard_and_success():
    deps, _ = _deps({"student.import"})

    denied = tool_dispatch("student.import", {"rows": []}, role="student", deps=deps)
    allowed = tool_dispatch("student.import", {"rows": [1]}, role="teacher", deps=deps)

    assert denied["error"] == "permission denied"
    assert allowed["tool"] == "student.import"


def test_tool_dispatch_assignment_requirements_save_uses_parser():
    deps, calls = _deps({"assignment.requirements.save"})

    out = tool_dispatch(
        "assignment.requirements.save",
        {"assignment_id": "a1", "requirements": {"x": 1}, "date": "2026-02-12"},
        role="teacher",
        deps=deps,
    )

    assert out["tool"] == "assignment.requirements.save"
    assert calls["assignment.requirements.save"] == ("a1", {"x": 1}, "parsed:2026-02-12", "teacher")


def test_tool_dispatch_teacher_workspace_and_memory_get_variants():
    deps, _ = _deps({"teacher.workspace.init", "teacher.memory.get"})

    init_out = tool_dispatch("teacher.workspace.init", {"teacher_id": "t1"}, role="teacher", deps=deps)
    assert init_out == {
        "ok": True,
        "teacher_id": "t1-resolved",
        "workspace": "/tmp/t1-resolved",
    }

    daily = tool_dispatch(
        "teacher.memory.get",
        {"teacher_id": "t1", "file": "DAILY", "date": "2026-02-12", "max_chars": 20},
        role="teacher",
        deps=deps,
    )
    agents = tool_dispatch(
        "teacher.memory.get",
        {"teacher_id": "t1", "file": "AGENTS.md", "max_chars": 30},
        role="teacher",
        deps=deps,
    )

    assert daily["ok"] is True
    assert daily["file"].endswith("/2026-02-12.md")
    assert agents["ok"] is True
    assert agents["file"].endswith("/AGENTS.md")


def test_tool_dispatch_teacher_memory_search_propose_and_apply():
    deps, _ = _deps({"teacher.memory.search", "teacher.memory.propose", "teacher.memory.apply"})

    searched = tool_dispatch(
        "teacher.memory.search",
        {"teacher_id": "t1", "query": "q", "limit": 4},
        role="teacher",
        deps=deps,
    )
    proposed = tool_dispatch(
        "teacher.memory.propose",
        {"teacher_id": "t1", "target": "MEMORY", "title": "ttl", "content": "body"},
        role="teacher",
        deps=deps,
    )
    applied = tool_dispatch(
        "teacher.memory.apply",
        {"teacher_id": "t1", "proposal_id": "p1", "approve": False},
        role="teacher",
        deps=deps,
    )

    assert searched["ok"] is True
    assert searched["teacher_id"] == "t1-resolved"
    assert searched["query"] == "q"
    assert proposed["tool"] == "teacher.memory.propose"
    assert applied["tool"] == "teacher.memory.apply"


def test_tool_dispatch_teacher_llm_routing_variants_enforce_role_and_allow_teacher():
    names = {
        "teacher.llm_routing.simulate",
        "teacher.llm_routing.propose",
        "teacher.llm_routing.apply",
        "teacher.llm_routing.rollback",
    }
    deps, _ = _deps(names)

    for name in sorted(names):
        denied = tool_dispatch(name, {"a": 1}, role="student", deps=deps)
        allowed = tool_dispatch(name, {"a": 1}, role="teacher", deps=deps)
        assert denied["error"] == "permission denied"
        assert allowed["tool"] == name


def test_tool_dispatch_covers_remaining_exam_lesson_and_core_example_branches():
    names = {
        "exam.analysis.charts.generate",
        "exam.range.top_students",
        "exam.range.summary.batch",
        "exam.question.batch.get",
        "lesson.capture",
        "core_example.register",
        "core_example.render",
    }
    deps, calls = _deps(names)

    denied = tool_dispatch("exam.analysis.charts.generate", {"exam_id": "e1"}, role="student", deps=deps)
    allowed = tool_dispatch("exam.analysis.charts.generate", {"exam_id": "e1"}, role="teacher", deps=deps)
    top_students = tool_dispatch(
        "exam.range.top_students",
        {"exam_id": "e2", "start_question_no": 1, "end_question_no": 3, "top_n": 6},
        role="teacher",
        deps=deps,
    )
    summary_batch = tool_dispatch(
        "exam.range.summary.batch",
        {"exam_id": "e3", "ranges": [[1, 3]], "top_n": 2},
        role="teacher",
        deps=deps,
    )
    question_batch = tool_dispatch(
        "exam.question.batch.get",
        {"exam_id": "e4", "question_nos": [1, 2], "top_n": 9},
        role="teacher",
        deps=deps,
    )
    captured = tool_dispatch("lesson.capture", {"topic": "x"}, role="teacher", deps=deps)
    registered = tool_dispatch("core_example.register", {"id": "c1"}, role="teacher", deps=deps)
    rendered = tool_dispatch("core_example.render", {"id": "c1"}, role="teacher", deps=deps)

    assert denied["error"] == "permission denied"
    assert allowed["tool"] == "exam.analysis.charts.generate"
    assert top_students["tool"] == "exam.range.top_students"
    assert summary_batch["tool"] == "exam.range.summary.batch"
    assert question_batch["tool"] == "exam.question.batch.get"
    assert captured["tool"] == "lesson.capture"
    assert registered["tool"] == "core_example.register"
    assert rendered["tool"] == "core_example.render"
    assert calls["exam.range.top_students"] == ("e2", 1, 3, 6)
    assert calls["exam.range.summary.batch"] == ("e3", [[1, 3]], 2)
    assert calls["exam.question.batch.get"] == ("e4", [1, 2], 9)


def test_tool_dispatch_chart_tools_and_llm_get_require_teacher_role():
    deps, _ = _deps({"chart.agent.run", "chart.exec", "teacher.llm_routing.get"})

    denied_agent = tool_dispatch("chart.agent.run", {"x": 1}, role="student", deps=deps)
    allowed_agent = tool_dispatch("chart.agent.run", {"x": 1}, role="teacher", deps=deps)
    denied_exec = tool_dispatch("chart.exec", {"x": 1}, role="student", deps=deps)
    allowed_exec = tool_dispatch("chart.exec", {"x": 1}, role="teacher", deps=deps)
    allowed_get = tool_dispatch("teacher.llm_routing.get", {"x": 1}, role="teacher", deps=deps)

    assert denied_agent["error"] == "permission denied"
    assert allowed_agent["tool"] == "chart.agent.run"
    assert denied_exec["error"] == "permission denied"
    assert allowed_exec["tool"] == "chart.exec"
    assert allowed_get["tool"] == "teacher.llm_routing.get"


def test_tool_dispatch_chart_exec_attaches_audit_context():
    deps, calls = _deps({"chart.exec"})

    out = tool_dispatch(
        "chart.exec",
        {"python_code": "print(1)"},
        role="teacher",
        deps=deps,
        teacher_id="teacher_a",
    )

    assert out["tool"] == "chart.exec"
    payload = calls["chart.exec"]
    assert isinstance(payload, dict)
    assert payload.get("_audit_source") == "tool_dispatch.chart.exec"
    assert payload.get("_audit_role") == "teacher"
    assert payload.get("_audit_actor") == "teacher_a"


def test_tool_dispatch_falls_back_to_unknown_when_registry_accepts_unhandled_name():
    deps, _ = _deps({"custom.unhandled"})
    out = tool_dispatch("custom.unhandled", {"x": 1}, role="teacher", deps=deps)
    assert out == {"error": "unknown tool: custom.unhandled"}
