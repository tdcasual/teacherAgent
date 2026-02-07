import unittest
from dataclasses import dataclass

from services.api.assignment_llm_gate_service import (
    AssignmentLlmGateDeps,
    llm_assignment_gate,
    parse_json_from_text,
)


@dataclass
class _Msg:
    role: str
    content: str


@dataclass
class _Req:
    messages: list
    assignment_id: str = ""
    assignment_date: str = ""
    skill_id: str = ""
    teacher_id: str = ""


class AssignmentLlmGateServiceTest(unittest.TestCase):
    def test_parse_json_from_text_accepts_fenced_json(self):
        payload = parse_json_from_text("```json\n{\"intent\":\"assignment\"}\n```")
        self.assertEqual(payload.get("intent"), "assignment")

    def test_llm_assignment_gate_returns_parsed_json(self):
        logs = []

        def _call_llm(_messages, **_kwargs):
            return {"choices": [{"message": {"content": '{"intent":"assignment","ready_to_generate":false}'}}]}

        deps = AssignmentLlmGateDeps(
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
            call_llm=_call_llm,
        )
        req = _Req(messages=[_Msg(role="user", content="请布置作业")], assignment_id="HW_1", assignment_date="2026-02-08")

        result = llm_assignment_gate(req, deps=deps)

        self.assertEqual(result.get("intent"), "assignment")
        self.assertEqual(logs[0][0], "llm_gate.request")
        self.assertEqual(logs[-1][0], "llm_gate.response")


if __name__ == "__main__":
    unittest.main()
