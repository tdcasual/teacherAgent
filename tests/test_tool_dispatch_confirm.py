from __future__ import annotations

from pathlib import Path

import pytest

from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY


def _deps(*, executed: list):
    return ToolDispatchDeps(
        tool_registry=DEFAULT_TOOL_REGISTRY,
        list_exams=lambda: {"ok": True},
        exam_get=lambda exam_id: {"ok": True, "exam_id": exam_id},
        exam_analysis_get=lambda exam_id: {"ok": True},
        exam_analysis_charts_generate=lambda args: {"ok": True},
        exam_students_list=lambda exam_id, limit: {"ok": True},
        exam_student_detail=lambda exam_id, student_id=None, student_name=None, class_name=None: {"ok": True},
        exam_question_detail=lambda exam_id, question_id=None, question_no=None, top_n=5: {"ok": True},
        exam_range_top_students=lambda exam_id, start_question_no=None, end_question_no=None, top_n=10: {"ok": True},
        exam_range_summary_batch=lambda exam_id, ranges=None, top_n=5: {"ok": True},
        exam_question_batch_detail=lambda exam_id, question_nos=None, top_n=5: {"ok": True},
        list_assignments=lambda: {"ok": True},
        list_lessons=lambda: {"ok": True},
        lesson_capture=lambda args: executed.append("lesson.capture") or {"ok": True},
        student_search=lambda query, limit: {"ok": True},
        student_profile_get=lambda student_id: {"ok": True},
        student_profile_update=lambda args: executed.append("student.profile.update") or {"ok": True, "args": args},
        student_import=lambda args: executed.append("student.import") or {"ok": True},
        assignment_generate=lambda args: executed.append("assignment.generate") or {"ok": True},
        assignment_render=lambda args: executed.append("assignment.render") or {"ok": True},
        save_assignment_requirements=lambda assignment_id, requirements, date_str, created_by="teacher": {"ok": True},
        parse_date_str=lambda raw: str(raw or ""),
        core_example_search=lambda args: {"ok": True},
        core_example_register=lambda args: executed.append("core_example.register") or {"ok": True},
        core_example_render=lambda args: {"ok": True},
        chart_agent_run=lambda args: executed.append("chart.agent.run") or {"ok": True},
        chart_exec=lambda args: executed.append("chart.exec") or {"ok": True},
        resolve_teacher_id=lambda raw: str(raw or "teacher"),
        ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / teacher_id,
        teacher_workspace_dir=lambda teacher_id: Path("/tmp") / teacher_id,
        teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / teacher_id / name,
        teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / teacher_id / "daily.md",
        teacher_read_text=lambda path, max_chars=8000: "",
        teacher_memory_search=lambda teacher_id, query, limit=5: {"matches": []},
        teacher_memory_propose=lambda teacher_id, target, title, content: {"ok": True},
        teacher_memory_apply=lambda teacher_id, proposal_id, approve=True: executed.append("teacher.memory.apply") or {"ok": True},
    )


def test_mutating_tool_without_confirm_does_not_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "unit-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from services.api import config as config_mod

    config_mod.reset_default_config()
    executed: list[str] = []
    out = tool_dispatch(
        "student.profile.update",
        {"student_id": "S1"},
        role="teacher",
        deps=_deps(executed=executed),
        job_id="job-1",
        actor_id="teacher-1",
    )
    assert out.get("error") == "confirmation_required"
    assert out.get("confirm_id")
    assert executed == []
    confirmed = tool_dispatch(
        "student.profile.update",
        {"student_id": "S1"},
        role="teacher",
        deps=_deps(executed=executed),
        confirmed=True,
    )
    assert confirmed.get("ok") is True
    assert executed == ["student.profile.update"]
