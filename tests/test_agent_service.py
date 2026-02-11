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

    def test_run_agent_runtime_total_mode_matching_single_subject_is_guarded(self):
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

        reply = str(result.get("reply") or "")
        self.assertIn("单科成绩说明", reply)
        self.assertIn("score_mode: \"total\"", reply)
        self.assertIn("不能把总分当作物理单科成绩", reply)
        self.assertEqual(len(llm_calls), 0)
        self.assertTrue(any(event == "teacher.subject_total_guard" for event, _ in logs))
        self.assertFalse(any(event == "teacher.subject_total_allow_single_subject" for event, _ in logs))


    def test_run_agent_runtime_subject_request_with_auto_extracted_subject_allows_agent(self):
        llm_calls = []
        logs = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            llm_calls.append({"messages": messages, "kwargs": kwargs})
            return {"choices": [{"message": {"content": "subject_score_reply"}}]}

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
                    "score_mode": "subject",
                    "score_mode_source": "subject_from_scores_file",
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

        self.assertEqual(result.get("reply"), "subject_score_reply")
        self.assertEqual(len(llm_calls), 1)
        self.assertTrue(any(event == "teacher.subject_total_auto_extract_subject" for event, _ in logs))
        self.assertFalse(any(event == "teacher.subject_total_guard" for event, _ in logs))


    # ------------------------------------------------------------------
    # Tool-calling loop tests
    # ------------------------------------------------------------------

    def _make_deps(self, *, call_llm, tool_dispatch=None, allowed=None, logs=None):
        """Helper to build AgentRuntimeDeps with sensible defaults."""
        _logs = logs if logs is not None else []
        return AgentRuntimeDeps(
            app_root=Path("."),
            build_system_prompt=lambda role: f"system-{role or 'unknown'}",
            diag_log=lambda event, payload=None: _logs.append((event, payload or {})),
            load_skill_runtime=lambda role, skill_id: (None, None),
            allowed_tools=lambda role: allowed or {"exam.get"},
            max_tool_rounds=3,
            max_tool_calls=5,
            extract_min_chars_requirement=lambda text: None,
            extract_exam_id=lambda text: None,
            is_exam_analysis_request=lambda text: False,
            build_exam_longform_context=lambda exam_id: {},
            generate_longform_reply=lambda *args, **kwargs: "",
            call_llm=call_llm,
            tool_dispatch=tool_dispatch or (lambda name, args, role: {"ok": True}),
            teacher_tools_to_openai=lambda allowed: [
                {"type": "function", "function": {"name": n, "parameters": {}}}
                for n in sorted(allowed)
            ],
        )

    def test_tool_dispatch_exception_structured_path(self):
        """tool_dispatch raising in structured tool_calls path should not crash."""
        call_count = [0]

        def fake_call_llm(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"choices": [{"message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {"name": "exam.get", "arguments": '{"exam_id":"EX001"}'},
                    }],
                }}]}
            return {"choices": [{"message": {"content": "final reply"}}]}

        def bad_dispatch(name, args, role):
            raise RuntimeError("db connection lost")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=bad_dispatch)
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertIn("reply", result)
        self.assertGreaterEqual(call_count[0], 2)

    def test_tool_dispatch_exception_json_fallback_path(self):
        """tool_dispatch raising in JSON-in-content path should not crash."""
        call_count = [0]

        def fake_call_llm(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"choices": [{"message": {
                    "content": '{"tool":"exam.get","arguments":{"exam_id":"EX001"}}',
                }}]}
            return {"choices": [{"message": {"content": "recovered reply"}}]}

        def bad_dispatch(name, args, role):
            raise ValueError("invalid exam_id")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=bad_dispatch)
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertEqual(result.get("reply"), "recovered reply")

    def test_tool_permission_denied(self):
        """Tool not in allowed set should return permission denied, not crash."""
        call_count = [0]

        def fake_call_llm(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"choices": [{"message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {"name": "dangerous.tool", "arguments": "{}"},
                    }],
                }}]}
            return {"choices": [{"message": {"content": "ok without tool"}}]}

        deps = self._make_deps(
            call_llm=fake_call_llm,
            allowed={"exam.get"},
        )
        result = run_agent_runtime(
            [{"role": "user", "content": "do something"}], "teacher", deps=deps,
        )
        self.assertIn("reply", result)

    def test_tool_budget_exhaustion(self):
        """After max_tool_calls, agent should stop calling tools."""
        call_count = [0]

        def fake_call_llm(messages, **kwargs):
            call_count[0] += 1
            if kwargs.get("tools") is not None:
                return {"choices": [{"message": {
                    "content": "",
                    "tool_calls": [{
                        "id": f"call_{call_count[0]}",
                        "function": {"name": "exam.get", "arguments": "{}"},
                    }],
                }}]}
            return {"choices": [{"message": {"content": "budget exhausted reply"}}]}

        deps = self._make_deps(call_llm=fake_call_llm)
        # Override max_tool_calls to 2 for quick test
        deps = AgentRuntimeDeps(**{**deps.__dict__, "max_tool_calls": 2})
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        reply = result.get("reply", "")
        self.assertTrue(len(reply) > 0)


if __name__ == "__main__":
    unittest.main()
