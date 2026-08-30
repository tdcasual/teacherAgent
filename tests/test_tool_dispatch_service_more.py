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
        list_assignments=lambda owner_teacher_id=None: {
            "tool": "assignment.list",
            "owner": owner_teacher_id,
        },
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
    )
    return deps, calls


def test_tool_dispatch_covers_core_assignment_and_student_paths():
    names = {
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

    listed = tool_dispatch("assignment.list", {}, role="teacher", teacher_id="t_zhang", deps=deps)
    assert listed["tool"] == "assignment.list"
    assert listed["owner"] == "t_zhang"
    missing = tool_dispatch("assignment.list", {}, role="teacher", deps=deps)
    assert missing.get("error") == "teacher_id_required"
    assert tool_dispatch("lesson.list", {}, role="teacher", deps=deps)["tool"] == "lesson.list"
    assert tool_dispatch("student.search", {"query": "abc", "limit": 3}, role="teacher", deps=deps)["tool"] == "student.search"
    assert tool_dispatch("student.profile.get", {"student_id": "stu1"}, role="teacher", deps=deps)["tool"] == "student.profile.get"
    assert tool_dispatch("student.profile.update", {"student_id": "stu1"}, role="teacher", deps=deps, confirmed=True)["tool"] == "student.profile.update"
    assert tool_dispatch("assignment.generate", {"topic": "t"}, role="teacher", deps=deps, confirmed=True)["tool"] == "assignment.generate"
    generate_denied = tool_dispatch("assignment.generate", {"topic": "t"}, role="student", deps=deps, confirmed=True)
    assert generate_denied.get("error") == "permission denied"
    assert tool_dispatch("assignment.render", {"assignment_id": "a1"}, role="teacher", deps=deps, confirmed=True)["tool"] == "assignment.render"
    assert tool_dispatch("core_example.search", {"query": "x"}, role="teacher", deps=deps)["tool"] == "core_example.search"

    assert calls["student.search"] == ("abc", 3)


def test_tool_dispatch_student_import_role_guard_and_success():
    deps, _ = _deps({"student.import"})

    denied = tool_dispatch("student.import", {"rows": []}, role="student", deps=deps)
    allowed = tool_dispatch("student.import", {"rows": [1]}, role="teacher", deps=deps, confirmed=True)

    assert denied["error"] == "permission denied"
    assert allowed["tool"] == "student.import"


def test_tool_dispatch_assignment_requirements_save_uses_parser():
    deps, calls = _deps({"assignment.requirements.save"})

    out = tool_dispatch(
        "assignment.requirements.save",
        {"assignment_id": "a1", "requirements": {"x": 1}, "date": "2026-02-12"},
        role="teacher",
        deps=deps,
        confirmed=True,
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
        confirmed=True,
    )

    assert searched["ok"] is True
    assert searched["teacher_id"] == "t1-resolved"
    assert searched["query"] == "q"
    assert proposed["tool"] == "teacher.memory.propose"
    assert applied["tool"] == "teacher.memory.apply"


def test_tool_dispatch_covers_remaining_lesson_and_core_example_branches():
    names = {
        "lesson.capture",
        "core_example.register",
        "core_example.render",
    }
    deps, _calls = _deps(names)

    captured = tool_dispatch("lesson.capture", {"topic": "x"}, role="teacher", deps=deps, confirmed=True)
    registered = tool_dispatch("core_example.register", {"id": "c1"}, role="teacher", deps=deps, confirmed=True)
    rendered = tool_dispatch("core_example.render", {"id": "c1"}, role="teacher", deps=deps)

    assert captured["tool"] == "lesson.capture"
    assert registered["tool"] == "core_example.register"
    assert rendered["tool"] == "core_example.render"


def test_tool_dispatch_chart_tools_require_teacher_role():
    deps, _ = _deps({"chart.agent.run", "chart.exec"})

    denied_agent = tool_dispatch("chart.agent.run", {"x": 1}, role="student", deps=deps)
    allowed_agent = tool_dispatch("chart.agent.run", {"x": 1}, role="teacher", deps=deps, confirmed=True)
    denied_exec = tool_dispatch("chart.exec", {"x": 1}, role="student", deps=deps)
    allowed_exec = tool_dispatch("chart.exec", {"x": 1}, role="teacher", deps=deps, confirmed=True)
    assert denied_agent["error"] == "permission denied"
    assert allowed_agent["tool"] == "chart.agent.run"
    assert denied_exec["error"] == "permission denied"
    assert allowed_exec["tool"] == "chart.exec"


def test_tool_dispatch_chart_exec_attaches_audit_context():
    deps, calls = _deps({"chart.exec"})

    out = tool_dispatch(
        "chart.exec",
        {"python_code": "print(1)"},
        role="teacher",
        deps=deps,
        teacher_id="teacher_a",
        confirmed=True,
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


def test_tool_dispatch_survey_report_tools_accept_target_id_alias():
    deps, calls = _deps({"survey.report.get", "survey.report.rerun"})
    deps = ToolDispatchDeps(
        **{**deps.__dict__,
           "survey_report_get": lambda report_id, teacher_id: {"tool": "survey.report.get", "payload": (report_id, teacher_id)},
           "survey_report_rerun": lambda report_id, teacher_id, reason=None: {
               "tool": "survey.report.rerun",
               "payload": (report_id, teacher_id, reason),
           }}
    )

    got = tool_dispatch(
        "survey.report.get",
        {"target_id": "report_9", "teacher_id": "t1"},
        role="teacher",
        deps=deps,
    )
    rerun = tool_dispatch(
        "survey.report.rerun",
        {"target_id": "report_9", "teacher_id": "t1", "reason": "need-refresh"},
        role="teacher",
        deps=deps,
        confirmed=True,
    )

    assert got["payload"] == ("report_9", "t1-resolved")
    assert rerun["payload"] == ("report_9", "t1-resolved", "need-refresh")



def test_tool_dispatch_survey_report_tools_require_report_id_or_target_id():
    deps, _ = _deps({"survey.report.get", "survey.report.rerun"})

    got = tool_dispatch("survey.report.get", {"teacher_id": "t1"}, role="teacher", deps=deps)
    rerun = tool_dispatch("survey.report.rerun", {"teacher_id": "t1"}, role="teacher", deps=deps)

    assert got["error"] == "invalid_arguments"
    assert any("target_id" in issue for issue in got["issues"])
    assert rerun["error"] == "invalid_arguments"
    assert any("target_id" in issue for issue in rerun["issues"])


def test_tool_dispatch_analysis_report_tools_cover_unified_report_plane():
    deps, _ = _deps({"analysis.report.list", "analysis.report.get", "analysis.report.rerun", "analysis.review.list"})
    deps = ToolDispatchDeps(
        **{
            **deps.__dict__,
            'analysis_report_list': lambda teacher_id, domain=None, status=None, strategy_id=None, target_type=None: {
                'tool': 'analysis.report.list',
                'payload': (teacher_id, domain, status, strategy_id, target_type),
            },
            'analysis_report_get': lambda report_id, teacher_id, domain=None: {
                'tool': 'analysis.report.get',
                'payload': (report_id, teacher_id, domain),
            },
            'analysis_report_rerun': lambda report_id, teacher_id, domain=None, reason=None: {
                'tool': 'analysis.report.rerun',
                'payload': (report_id, teacher_id, domain, reason),
            },
            'analysis_review_list': lambda teacher_id, domain=None, status=None: {
                'tool': 'analysis.review.list',
                'payload': (teacher_id, domain, status),
            },
        }
    )

    listed = tool_dispatch(
        'analysis.report.list',
        {'teacher_id': 't1', 'domain': 'survey', 'status': 'analysis_ready', 'strategy_id': 'survey.teacher.report', 'target_type': 'report'},
        role='teacher',
        deps=deps,
    )
    got = tool_dispatch(
        'analysis.report.get',
        {'teacher_id': 't1', 'domain': 'survey', 'report_id': 'report_1'},
        role='teacher',
        deps=deps,
    )
    rerun = tool_dispatch(
        'analysis.report.rerun',
        {'teacher_id': 't1', 'domain': 'survey', 'target_id': 'report_1', 'reason': 'refresh'},
        role='teacher',
        deps=deps,
        confirmed=True,
    )
    review = tool_dispatch(
        'analysis.review.list',
        {'teacher_id': 't1', 'domain': 'survey', 'status': 'queued'},
        role='teacher',
        deps=deps,
    )

    assert listed['payload'] == ('t1-resolved', 'survey', 'analysis_ready', 'survey.teacher.report', 'report')
    assert got['payload'] == ('report_1', 't1-resolved', 'survey')
    assert rerun['payload'] == ('report_1', 't1-resolved', 'survey', 'refresh')
    assert review['payload'] == ('t1-resolved', 'survey', 'queued')


def test_assignment_progress_tools_require_owner():
    owners = {"HW_MINE": "t_zhang", "HW_OTHER": "t_li"}
    calls: list[str] = []
    base, _ = _deps({"assignment.progress", "assignment.missing", "assignment.overdue", "assignment.attempt.get"})
    deps = ToolDispatchDeps(
        **{
            **base.__dict__,
            "assignment_owner_id": lambda assignment_id: owners.get(str(assignment_id or "").strip()),
            "assignment_progress": lambda assignment_id: calls.append(assignment_id) or {
                "ok": True,
                "assignment_id": assignment_id,
                "students": [
                    {"student_id": "S1", "overdue": True, "submission": {"best": None}},
                    {"student_id": "S2", "overdue": True, "submission": {"best": {"score_earned": 8}}},
                ],
            },
        }
    )
    mine = tool_dispatch(
        "assignment.progress",
        {"assignment_id": "HW_MINE"},
        role="teacher",
        teacher_id="t_zhang",
        deps=deps,
    )
    assert mine.get("ok") is True
    forbidden = tool_dispatch(
        "assignment.missing",
        {"assignment_id": "HW_OTHER"},
        role="teacher",
        teacher_id="t_zhang",
        deps=deps,
    )
    assert forbidden.get("error") == "forbidden_assignment_owner"
    missing = tool_dispatch(
        "assignment.progress",
        {"assignment_id": "HW_MINE"},
        role="teacher",
        deps=deps,
    )
    assert missing.get("error") == "teacher_id_required"
    overdue = tool_dispatch(
        "assignment.overdue",
        {"assignment_id": "HW_MINE"},
        role="teacher",
        teacher_id="t_zhang",
        deps=deps,
    )
    assert overdue.get("count") == 1
    assert overdue["students"][0]["student_id"] == "S1"
    assert "HW_OTHER" not in calls


def test_assignment_student_tools_require_student_actor_id():
    base, _ = _deps({"assignment.my_today", "assignment.my_result"})
    deps = ToolDispatchDeps(
        **{
            **base.__dict__,
            "assignment_my_today": lambda student_id, date=None: {
                "ok": True,
                "student_id": student_id,
                "date": date,
            },
            "assignment_my_result": lambda assignment_id, student_id: {
                "ok": True,
                "assignment_id": assignment_id,
                "student_id": student_id,
            },
        }
    )
    denied = tool_dispatch("assignment.my_today", {}, role="teacher", teacher_id="t_zhang", deps=deps)
    assert denied.get("error") == "permission denied"
    missing = tool_dispatch("assignment.my_today", {}, role="student", deps=deps)
    assert missing.get("error") == "student_id_required"
    today = tool_dispatch(
        "assignment.my_today",
        {},
        role="student",
        actor_id="S_WU",
        deps=deps,
    )
    assert today == {"ok": True, "student_id": "S_WU", "date": None}
    result = tool_dispatch(
        "assignment.my_result",
        {"assignment_id": "HW_1"},
        role="student",
        actor_id="S_WU",
        deps=deps,
    )
    assert result == {"ok": True, "assignment_id": "HW_1", "student_id": "S_WU"}
