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

    def test_resolve_target_disallows_none_timeout_env(self):
        previous = os.environ.get("LLM_TIMEOUT_SEC")
        os.environ["LLM_TIMEOUT_SEC"] = "none"
        os.environ["LLM_API_KEY"] = os.environ.get("LLM_API_KEY", "test-key")
        try:
            gateway = LLMGateway(self.registry_path)
            target = gateway.resolve_target()
            self.assertIsNotNone(target.timeout_sec)
            self.assertNotEqual(target.timeout_sec, None)
        finally:
            if previous is None:
                os.environ.pop("LLM_TIMEOUT_SEC", None)
            else:
                os.environ["LLM_TIMEOUT_SEC"] = previous

    def test_target_override_uses_finite_connect_and_read_timeout(self):
        gateway = LLMGateway(self.registry_path)
        target = gateway._target_from_override(
            {
                "provider": "custom",
                "mode": "openai-chat",
                "model": "test-model",
                "base_url": "https://example.invalid",
                "endpoint": "/v1/chat/completions",
                "timeout_sec": "none",
                "headers": {"Authorization": "Bearer token"},
            },
            provider=None,
            mode=None,
            model=None,
        )
        self.assertIsNotNone(target.timeout_sec)
        self.assertNotEqual(target.timeout_sec, None)
        self.assertIsInstance(target.timeout_sec, tuple)
        self.assertEqual(len(target.timeout_sec), 2)


if __name__ == "__main__":
    unittest.main()
