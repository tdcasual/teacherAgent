from __future__ import annotations

import unittest
from pathlib import Path

from services.api.agent_service import (
    AgentRuntimeDeps,
    _resolve_runtime_tool_limits,
    parse_tool_json,
    run_agent_runtime,
)


class AgentServiceTest(unittest.TestCase):
    def test_parse_tool_json_accepts_fenced_json(self):
        content = '```json\n{"tool":"exam.get","arguments":{"exam_id":"EX001"}}\n```'
        parsed = parse_tool_json(content)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("tool"), "exam.get")
        self.assertEqual((parsed.get("arguments") or {}).get("exam_id"), "EX001")

    def test_parse_tool_json_accepts_crlf_fenced_json(self):
        content = '```json\r\n{"tool":"exam.get","arguments":{"exam_id":"EX001"}}\r\n```'
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
            tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
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
            tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
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
            tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
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
            tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
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
            tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
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
            tool_dispatch=tool_dispatch or (lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True}),
            teacher_tools_to_openai=lambda allowed, skill_runtime=None: [
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

        def bad_dispatch(name, args, role, skill_id=None, teacher_id=None):
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

        def bad_dispatch(name, args, role, skill_id=None, teacher_id=None):
            raise ValueError("invalid exam_id")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=bad_dispatch)
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertEqual(result.get("reply"), "recovered reply")

    def test_tool_dispatch_internal_type_error_does_not_retry_compat_fallback(self):
        """Internal TypeError should not trigger legacy-signature retry calls."""
        call_count = [0]
        dispatch_calls = [0]

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
            return {"choices": [{"message": {"content": "recovered reply"}}]}

        def bad_dispatch(name, args, role, **kwargs):
            dispatch_calls[0] += 1
            raise TypeError("internal_tool_dispatch_type_error")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=bad_dispatch)
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertEqual(result.get("reply"), "recovered reply")
        self.assertEqual(dispatch_calls[0], 1)

    def test_tool_dispatch_signature_like_internal_type_error_does_not_retry_compat_fallback(self):
        """Signature-like internal TypeError should not trigger legacy-signature retry calls."""
        call_count = [0]
        dispatch_calls = [0]

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
            return {"choices": [{"message": {"content": "recovered reply"}}]}

        def bad_dispatch(name, args, role, **kwargs):
            dispatch_calls[0] += 1
            raise TypeError("helper() missing 1 required positional argument: 'ctx'")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=bad_dispatch)
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertEqual(result.get("reply"), "recovered reply")
        self.assertEqual(dispatch_calls[0], 1)

    def test_teacher_tools_internal_type_error_does_not_retry_compat_fallback(self):
        """Internal TypeError in teacher_tools_to_openai should not be retried."""
        tool_calls = [0]

        def fake_call_llm(messages, **kwargs):
            return {"choices": [{"message": {"content": "ignored"}}]}

        def bad_teacher_tools(*args, **kwargs):
            tool_calls[0] += 1
            raise TypeError("internal_teacher_tools_type_error")

        deps = self._make_deps(call_llm=fake_call_llm)
        deps = AgentRuntimeDeps(**{**deps.__dict__, "teacher_tools_to_openai": bad_teacher_tools})

        with self.assertRaises(TypeError):
            run_agent_runtime(
                [{"role": "user", "content": "你好"}], "teacher", deps=deps,
            )
        self.assertEqual(tool_calls[0], 1)

    def test_teacher_tools_signature_like_internal_type_error_does_not_retry_compat_fallback(self):
        """Signature-like internal TypeError in teacher_tools_to_openai should not be retried."""
        tool_calls = [0]

        def fake_call_llm(messages, **kwargs):
            return {"choices": [{"message": {"content": "ignored"}}]}

        def bad_teacher_tools(*args, **kwargs):
            tool_calls[0] += 1
            raise TypeError("helper() missing 1 required positional argument: 'ctx'")

        deps = self._make_deps(call_llm=fake_call_llm)
        deps = AgentRuntimeDeps(**{**deps.__dict__, "teacher_tools_to_openai": bad_teacher_tools})

        with self.assertRaises(TypeError):
            run_agent_runtime(
                [{"role": "user", "content": "你好"}], "teacher", deps=deps,
            )
        self.assertEqual(tool_calls[0], 1)

    def test_tool_dispatch_uninspectable_signature_like_internal_type_error_does_not_retry(self):
        call_count = [0]
        dispatch_calls = [0]

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
            return {"choices": [{"message": {"content": "recovered reply"}}]}

        class _BadDispatch:
            @property
            def __signature__(self):
                raise ValueError("signature unavailable")

            def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                dispatch_calls[0] += 1
                raise TypeError("helper() missing 1 required positional argument: 'ctx'")

        deps = self._make_deps(call_llm=fake_call_llm, tool_dispatch=_BadDispatch())
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}], "teacher", deps=deps,
        )
        self.assertEqual(result.get("reply"), "recovered reply")
        self.assertEqual(dispatch_calls[0], 1)

    def test_teacher_tools_uninspectable_signature_like_internal_type_error_does_not_retry(self):
        tool_calls = [0]

        def fake_call_llm(messages, **kwargs):
            return {"choices": [{"message": {"content": "ignored"}}]}

        class _BadTeacherTools:
            @property
            def __signature__(self):
                raise ValueError("signature unavailable")

            def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                tool_calls[0] += 1
                raise TypeError("helper() missing 1 required positional argument: 'ctx'")

        deps = self._make_deps(call_llm=fake_call_llm)
        deps = AgentRuntimeDeps(**{**deps.__dict__, "teacher_tools_to_openai": _BadTeacherTools()})

        with self.assertRaises(TypeError):
            run_agent_runtime(
                [{"role": "user", "content": "你好"}], "teacher", deps=deps,
            )
        self.assertEqual(tool_calls[0], 1)

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

    def test_skill_runtime_budget_cannot_relax_global_caps(self):
        deps = self._make_deps(call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "ok"}}]})

        class _Runtime:
            max_tool_rounds = 999
            max_tool_calls = 999
            dynamic_tools = {}

            @staticmethod
            def apply_tool_policy(allowed):
                return set(allowed)

        _, max_rounds, max_calls = _resolve_runtime_tool_limits(deps, "teacher", _Runtime())
        self.assertEqual(max_rounds, deps.max_tool_rounds)
        self.assertEqual(max_calls, deps.max_tool_calls)

    def test_skill_runtime_budget_can_tighten_global_caps(self):
        deps = self._make_deps(call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "ok"}}]})

        class _Runtime:
            max_tool_rounds = 1
            max_tool_calls = 2
            dynamic_tools = {}

            @staticmethod
            def apply_tool_policy(allowed):
                return set(allowed)

        _, max_rounds, max_calls = _resolve_runtime_tool_limits(deps, "teacher", _Runtime())
        self.assertEqual(max_rounds, 1)
        self.assertEqual(max_calls, 2)

    def test_run_agent_runtime_event_sink_uses_native_token_stream_chunks(self):
        event_records = []

        def event_sink(event_type, payload):
            event_records.append((str(event_type), dict(payload or {})))

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            sink = kwargs.get("token_sink")
            if callable(sink):
                sink("第一段")
                self.assertTrue(
                    any(et == "assistant.delta" for et, _ in event_records),
                    "assistant.delta should be emitted during token callback",
                )
                sink("第二段")
            return {"choices": [{"message": {"content": "第一段第二段"}}]}

        deps = self._make_deps(call_llm=fake_call_llm, allowed=set())
        result = run_agent_runtime(
            [{"role": "user", "content": "hello"}],
            "student",
            deps=deps,
            event_sink=event_sink,
        )

        self.assertEqual(result.get("reply"), "第一段第二段")
        delta_payloads = [payload.get("delta") for et, payload in event_records if et == "assistant.delta"]
        done_payloads = [payload.get("text") for et, payload in event_records if et == "assistant.done"]
        self.assertEqual(delta_payloads, ["第一段", "第二段"])
        self.assertEqual(done_payloads, ["第一段第二段"])

    def test_run_agent_runtime_late_sink_from_previous_round_does_not_pollute_current_round_chunks(self):
        event_records = []

        def event_sink(event_type, payload):
            event_records.append((str(event_type), dict(payload or {})))

        state = {"calls": 0, "previous_sink": None}

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            state["calls"] += 1
            sink = kwargs.get("token_sink")
            if state["calls"] == 1:
                state["previous_sink"] = sink
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "function": {"name": "exam.get", "arguments": '{"exam_id":"EX001"}'},
                                    }
                                ],
                            }
                        }
                    ]
                }

            if callable(state.get("previous_sink")):
                state["previous_sink"]("跨轮延迟片段")
            if callable(sink):
                sink("当前轮片段")
            return {"choices": [{"message": {"content": ""}}]}

        deps = self._make_deps(
            call_llm=fake_call_llm,
            allowed={"exam.get"},
            tool_dispatch=lambda _name, _args, _role, skill_id=None, teacher_id=None: {"ok": True, "exam_id": "EX001"},
        )
        result = run_agent_runtime(
            [{"role": "user", "content": "查看考试"}],
            "teacher",
            deps=deps,
            event_sink=event_sink,
        )

        self.assertEqual(result.get("reply"), "当前轮片段")
        self.assertEqual(state["calls"], 2)

        done_payloads = [payload.get("text") for et, payload in event_records if et == "assistant.done"]
        self.assertEqual(done_payloads, ["当前轮片段"])


if __name__ == "__main__":
    unittest.main()
