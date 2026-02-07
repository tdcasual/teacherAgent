import unittest

from services.api.llm_agent_tooling_service import parse_tool_json_safe


class LlmAgentToolingServiceTest(unittest.TestCase):
    def test_parse_tool_json_safe_handles_invalid_json(self):
        self.assertIsNone(parse_tool_json_safe("{bad"))


if __name__ == "__main__":
    unittest.main()
