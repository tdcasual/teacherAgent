from __future__ import annotations

from pathlib import Path
import unittest

from services.api.agent_service import AgentRuntimeDeps, parse_tool_json, run_agent_runtime


class AgentServiceTest(unittest.TestCase):
    def test_parse_tool_json_accepts_fenced_json(self):
        content = '```json\n{"tool":"exam.get","arguments":{"exam_id":"EX001"}}\n```'
        parsed = parse_tool_json(content)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("tool"), "exam.get")
        self.assertEqual((parsed.get("arguments") or {}).get("exam_id"), "EX001")

    def test_run_agent_runtime_returns_reply_without_tool_calls(self):
        llm_calls = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            llm_calls.append({"messages": messages, "kwargs": kwargs})
            return {"choices": [{"message": {"content": "stub reply"}}]}

        deps = AgentRuntimeDeps(
            app_root=Path("."),
            build_system_prompt=lambda role: f"system-{role or 'unknown'}",
            diag_log=lambda *_args, **_kwargs: None,
            load_skill_runtime=lambda role, skill_id: (None, None),
            allowed_tools=lambda role: set(),
            max_tool_rounds=3,
            max_tool_calls=5,
            extract_min_chars_requirement=lambda text: None,
            extract_exam_id=lambda text: None,
            is_exam_analysis_request=lambda text: False,
            build_exam_longform_context=lambda exam_id: {},
            generate_longform_reply=lambda *args, **kwargs: "",
            call_llm=fake_call_llm,
            tool_dispatch=lambda name, args, role: {"ok": True},
            teacher_tools_to_openai=lambda allowed: [],
        )

        result = run_agent_runtime(
            [{"role": "user", "content": "hello"}],
            "student",
            deps=deps,
            skill_id="skill_student",
        )

        self.assertEqual(result.get("reply"), "stub reply")
        self.assertEqual(len(llm_calls), 1)
        self.assertEqual(llm_calls[0]["kwargs"].get("kind"), "chat.skill")

    def test_run_agent_runtime_guards_subject_request_on_total_mode(self):
        llm_calls = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            llm_calls.append({"messages": messages, "kwargs": kwargs})
            return {"choices": [{"message": {"content": "should_not_be_used"}}]}

        logs = []

        deps = AgentRuntimeDeps(
            app_root=Path("."),
            build_system_prompt=lambda role: f"system-{role or 'unknown'}",
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
            load_skill_runtime=lambda role, skill_id: (None, None),
            allowed_tools=lambda role: {"exam.get", "exam.analysis.get", "exam.students.list"},
            max_tool_rounds=3,
            max_tool_calls=5,
            extract_min_chars_requirement=lambda text: None,
            extract_exam_id=lambda text: "EX20260209_9b92e1" if "EX20260209_9b92e1" in (text or "") else None,
            is_exam_analysis_request=lambda text: False,
            build_exam_longform_context=lambda exam_id: {
                "exam_overview": {
                    "ok": True,
                    "exam_id": exam_id,
                    "score_mode": "total",
                    "totals_summary": {
                        "avg_total": 371.714,
                        "median_total": 366.5,
                        "max_total_observed": 511.5,
                        "min_total_observed": 289.5,
                    },
                }
            },
            generate_longform_reply=lambda *args, **kwargs: "",
            call_llm=fake_call_llm,
            tool_dispatch=lambda name, args, role: {"ok": True},
            teacher_tools_to_openai=lambda allowed: [],
        )

        result = run_agent_runtime(
            [{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
            "teacher",
            deps=deps,
            skill_id="physics-teacher-ops",
        )

        reply = str(result.get("reply") or "")
        self.assertIn("单科成绩说明", reply)
        self.assertIn("score_mode: \"total\"", reply)
        self.assertIn("不能把总分当作物理单科成绩", reply)
        self.assertEqual(len(llm_calls), 0)
        self.assertTrue(any(event == "teacher.subject_total_guard" for event, _ in logs))

    def test_run_agent_runtime_subject_request_non_total_continues(self):
        llm_calls = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            llm_calls.append({"messages": messages, "kwargs": kwargs})
            return {"choices": [{"message": {"content": "normal_teacher_reply"}}]}

        deps = AgentRuntimeDeps(
            app_root=Path("."),
            build_system_prompt=lambda role: f"system-{role or 'unknown'}",
            diag_log=lambda *_args, **_kwargs: None,
            load_skill_runtime=lambda role, skill_id: (None, None),
            allowed_tools=lambda role: set(),
            max_tool_rounds=3,
            max_tool_calls=5,
            extract_min_chars_requirement=lambda text: None,
            extract_exam_id=lambda text: "EX20260209_9b92e1" if "EX20260209_9b92e1" in (text or "") else None,
            is_exam_analysis_request=lambda text: False,
            build_exam_longform_context=lambda exam_id: {
                "exam_overview": {
                    "ok": True,
                    "exam_id": exam_id,
                    "score_mode": "subject",
                }
            },
            generate_longform_reply=lambda *args, **kwargs: "",
            call_llm=fake_call_llm,
            tool_dispatch=lambda name, args, role: {"ok": True},
            teacher_tools_to_openai=lambda allowed: [],
        )

        result = run_agent_runtime(
            [{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
            "teacher",
            deps=deps,
            skill_id="physics-teacher-ops",
        )

        self.assertEqual(result.get("reply"), "normal_teacher_reply")
        self.assertEqual(len(llm_calls), 1)

    def test_run_agent_runtime_total_mode_matching_single_subject_allows_analysis(self):
        llm_calls = []
        logs = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            llm_calls.append({"messages": messages, "kwargs": kwargs})
            return {"choices": [{"message": {"content": "physics_total_mode_reply"}}]}

        deps = AgentRuntimeDeps(
            app_root=Path("."),
            build_system_prompt=lambda role: f"system-{role or 'unknown'}",
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
            load_skill_runtime=lambda role, skill_id: (None, None),
            allowed_tools=lambda role: set(),
            max_tool_rounds=3,
            max_tool_calls=5,
            extract_min_chars_requirement=lambda text: None,
            extract_exam_id=lambda text: "EX20260209_9b92e1" if "EX20260209_9b92e1" in (text or "") else None,
            is_exam_analysis_request=lambda text: False,
            build_exam_longform_context=lambda exam_id: {
                "exam_overview": {
                    "ok": True,
                    "exam_id": exam_id,
                    "score_mode": "total",
                    "meta": {"subject": "physics"},
                }
            },
            generate_longform_reply=lambda *args, **kwargs: "",
            call_llm=fake_call_llm,
            tool_dispatch=lambda name, args, role: {"ok": True},
            teacher_tools_to_openai=lambda allowed: [],
        )

        result = run_agent_runtime(
            [{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
            "teacher",
            deps=deps,
            skill_id="physics-teacher-ops",
        )

        self.assertEqual(result.get("reply"), "physics_total_mode_reply")
        self.assertEqual(len(llm_calls), 1)
        self.assertFalse(any(event == "teacher.subject_total_guard" for event, _ in logs))
        self.assertTrue(any(event == "teacher.subject_total_allow_single_subject" for event, _ in logs))


if __name__ == "__main__":
    unittest.main()
