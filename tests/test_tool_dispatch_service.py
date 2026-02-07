import unittest
from pathlib import Path

from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch


class _FakeRegistry:
    def __init__(self):
        self._tools = {"exam.get", "teacher.llm_routing.get", "teacher.memory.get", "teacher.memory.propose"}

    def get(self, name):
        return name if name in self._tools else None

    def validate_arguments(self, name, args):
        if name == "exam.get":
            if "exam_id" not in args:
                return ["'exam_id' is required"]
            if "unexpected" in args:
                return ["unexpected is not allowed"]
        return []


class ToolDispatchServiceTest(unittest.TestCase):
    def _deps(self):
        return ToolDispatchDeps(
            tool_registry=_FakeRegistry(),
            list_exams=lambda: {"ok": True},
            exam_get=lambda exam_id: {"ok": True, "exam_id": exam_id},
            exam_analysis_get=lambda exam_id: {"ok": True, "exam_id": exam_id},
            exam_analysis_charts_generate=lambda args: {"ok": True, "args": args},
            exam_students_list=lambda exam_id, limit: {"ok": True, "exam_id": exam_id, "limit": limit},
            exam_student_detail=lambda exam_id, student_id=None, student_name=None, class_name=None: {"ok": True, "exam_id": exam_id},
            exam_question_detail=lambda exam_id, question_id=None, question_no=None, top_n=5: {"ok": True, "exam_id": exam_id},
            exam_range_top_students=lambda exam_id, start_question_no=None, end_question_no=None, top_n=10: {"ok": True},
            exam_range_summary_batch=lambda exam_id, ranges=None, top_n=5: {"ok": True},
            exam_question_batch_detail=lambda exam_id, question_nos=None, top_n=5: {"ok": True},
            list_assignments=lambda: {"ok": True},
            list_lessons=lambda: {"ok": True},
            lesson_capture=lambda args: {"ok": True, "args": args},
            student_search=lambda query, limit: {"ok": True, "query": query, "limit": limit},
            student_profile_get=lambda student_id: {"ok": True, "student_id": student_id},
            student_profile_update=lambda args: {"ok": True, "args": args},
            student_import=lambda args: {"ok": True, "args": args},
            assignment_generate=lambda args: {"ok": True, "args": args},
            assignment_render=lambda args: {"ok": True, "args": args},
            save_assignment_requirements=lambda assignment_id, requirements, date_str, created_by="teacher": {"ok": True},
            parse_date_str=lambda raw: str(raw or ""),
            core_example_search=lambda args: {"ok": True, "args": args},
            core_example_register=lambda args: {"ok": True, "args": args},
            core_example_render=lambda args: {"ok": True, "args": args},
            chart_agent_run=lambda args: {"ok": True, "args": args},
            chart_exec=lambda args: {"ok": True, "args": args},
            resolve_teacher_id=lambda raw: str(raw or "teacher"),
            ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / teacher_id,
            teacher_workspace_dir=lambda teacher_id: Path("/tmp") / teacher_id,
            teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / teacher_id / name,
            teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / teacher_id / f"{date_str or 'daily'}.md",
            teacher_read_text=lambda path, max_chars=8000: f"text:{path}:{max_chars}",
            teacher_memory_search=lambda teacher_id, query, limit=5: {"mode": "keyword", "matches": []},
            teacher_memory_propose=lambda teacher_id, target, title, content: {"ok": True, "proposal_id": "p1", "target": target},
            teacher_memory_apply=lambda teacher_id, proposal_id, approve=True: {"ok": True, "proposal_id": proposal_id, "status": "applied"},
            teacher_llm_routing_get=lambda args: {"ok": True, "routing": {}},
            teacher_llm_routing_simulate=lambda args: {"ok": True, "result": {}},
            teacher_llm_routing_propose=lambda args: {"ok": True, "proposal_id": "r1"},
            teacher_llm_routing_apply=lambda args: {"ok": True},
            teacher_llm_routing_rollback=lambda args: {"ok": True},
        )

    def test_unknown_tool_returns_error(self):
        out = tool_dispatch("missing.tool", {}, role="teacher", deps=self._deps())
        self.assertEqual(out.get("error"), "unknown tool: missing.tool")

    def test_invalid_arguments_short_circuit(self):
        out = tool_dispatch("exam.get", {"unexpected": 1}, role="teacher", deps=self._deps())
        self.assertEqual(out.get("error"), "invalid_arguments")
        self.assertEqual(out.get("tool"), "exam.get")

    def test_teacher_only_tool_requires_teacher_role(self):
        out = tool_dispatch("teacher.llm_routing.get", {}, role="student", deps=self._deps())
        self.assertEqual(out.get("error"), "permission denied")

    def test_teacher_memory_get_uses_safe_default_file(self):
        out = tool_dispatch(
            "teacher.memory.get",
            {"teacher_id": "t1", "file": "../bad.md", "max_chars": 120},
            role="teacher",
            deps=self._deps(),
        )
        self.assertTrue(out.get("ok"))
        self.assertTrue(str(out.get("file") or "").endswith("/MEMORY.md"))


if __name__ == "__main__":
    unittest.main()
