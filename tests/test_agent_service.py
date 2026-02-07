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
        self.assertEqual(llm_calls[0]["kwargs"].get("kind"), "chat.agent")


if __name__ == "__main__":
    unittest.main()
