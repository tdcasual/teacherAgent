import os
import unittest
from pathlib import Path

from llm_gateway import LLMGateway, _messages_to_response_input


class TestLLMGateway(unittest.TestCase):
    def setUp(self):
        self.registry_path = Path(__file__).resolve().parents[1] / "config" / "model_registry.yaml"

    def test_registry_loads(self):
        gateway = LLMGateway(self.registry_path)
        self.assertIn("providers", gateway.registry)
        self.assertIn("defaults", gateway.registry)

    def test_resolve_alias(self):
        gateway = LLMGateway(self.registry_path)
        provider, mode = gateway.resolve_alias("openai-response")
        self.assertEqual(provider, "openai")
        self.assertEqual(mode, "openai-response")

    def test_messages_to_response_input(self):
        instructions, items = _messages_to_response_input(
            [
                {"role": "system", "content": "system note"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ]
        )
        self.assertEqual(instructions, "system note")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["role"], "user")
        self.assertEqual(items[1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
