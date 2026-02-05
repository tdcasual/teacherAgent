import os
import tempfile
import unittest
from pathlib import Path

import requests

from llm_gateway import LLMGateway, UnifiedLLMRequest


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self  # type: ignore[attr-defined]
            raise err

    def json(self):
        return self._payload


class TestLLMGatewayRetry(unittest.TestCase):
    def _write_registry(self, path: Path):
        path.write_text(
            """
defaults:
  provider: openai
  mode: openai-chat
  timeout_sec: 5
  retry: 2
providers:
  openai:
    api_key_envs: [LLM_API_KEY]
    auth:
      type: bearer
    modes:
      openai-chat:
        endpoint: /v1/chat/completions
        base_url: http://example.invalid
        default_model: test
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def test_retries_on_429_then_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            registry = Path(d) / "registry.yaml"
            self._write_registry(registry)
            os.environ["MODEL_REGISTRY_PATH"] = str(registry)
            os.environ["LLM_API_KEY"] = "x"

            gw = LLMGateway()
            calls = {"n": 0}

            def fake_post(*args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    return _FakeResponse(429, {"error": "rate_limited"})
                return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}], "usage": {}})

            gw._session.post = fake_post  # type: ignore[assignment]

            req = UnifiedLLMRequest(messages=[{"role": "user", "content": "ping"}], temperature=0)
            resp = gw.generate(req, allow_fallback=False)
            self.assertEqual(resp.text, "ok")
            self.assertGreaterEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()

