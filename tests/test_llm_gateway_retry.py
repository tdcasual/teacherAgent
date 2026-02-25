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


class _FakeStreamResponse:
    def __init__(self, lines):
        self.status_code = 200
        self._lines = list(lines)

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self  # type: ignore[attr-defined]
            raise err

    def iter_lines(self, decode_unicode=False):
        for line in self._lines:
            yield line if decode_unicode else line.encode("utf-8")


class _FakeLatin1DecodedStreamResponse(_FakeStreamResponse):
    def iter_lines(self, decode_unicode=False):
        for line in self._lines:
            raw = line.encode("utf-8")
            if decode_unicode:
                # Simulate requests defaulting to latin-1 when charset is absent.
                yield raw.decode("latin-1")
            else:
                yield raw


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

    def test_generate_stream_openai_chat_parses_sse_and_tool_calls(self):
        with tempfile.TemporaryDirectory() as d:
            registry = Path(d) / "registry.yaml"
            self._write_registry(registry)
            os.environ["MODEL_REGISTRY_PATH"] = str(registry)
            os.environ["LLM_API_KEY"] = "x"

            gw = LLMGateway()

            sse_lines = [
                'data: {"choices":[{"delta":{"content":"hello "}}]}',
                "",
                'data: {"choices":[{"delta":{"content":"world"}}]}',
                "",
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"exam.get","arguments":"{\\"exam_id\\":\\""}}]}}]}',
                "",
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"EX001\\"}"}}]},"finish_reason":"tool_calls"}]}',
                "",
                "data: [DONE]",
                "",
            ]

            def fake_post(*args, **kwargs):
                if kwargs.get("stream"):
                    return _FakeStreamResponse(sse_lines)
                return _FakeResponse(200, {"choices": [{"message": {"content": "fallback"}}], "usage": {}})

            gw._session.post = fake_post  # type: ignore[assignment]

            chunks = []
            req = UnifiedLLMRequest(messages=[{"role": "user", "content": "ping"}], temperature=0, stream=True)
            resp = gw.generate(req, allow_fallback=False, token_sink=lambda delta: chunks.append(str(delta)))

            self.assertEqual(resp.text, "hello world")
            self.assertEqual(chunks, ["hello ", "world"])
            self.assertEqual(len(resp.tool_calls), 1)
            self.assertEqual(resp.tool_calls[0].get("id"), "call_1")
            func = resp.tool_calls[0].get("function") or {}
            self.assertEqual(func.get("name"), "exam.get")
            self.assertEqual(func.get("arguments"), '{"exam_id":"EX001"}')

    def test_generate_stream_openai_chat_decodes_utf8_without_mojibake(self):
        with tempfile.TemporaryDirectory() as d:
            registry = Path(d) / "registry.yaml"
            self._write_registry(registry)
            os.environ["MODEL_REGISTRY_PATH"] = str(registry)
            os.environ["LLM_API_KEY"] = "x"

            gw = LLMGateway()

            sse_lines = [
                'data: {"choices":[{"delta":{"content":"你好"}}]}',
                "",
                "data: [DONE]",
                "",
            ]

            def fake_post(*args, **kwargs):
                if kwargs.get("stream"):
                    return _FakeLatin1DecodedStreamResponse(sse_lines)
                return _FakeResponse(200, {"choices": [{"message": {"content": "fallback"}}], "usage": {}})

            gw._session.post = fake_post  # type: ignore[assignment]

            chunks = []
            req = UnifiedLLMRequest(messages=[{"role": "user", "content": "ping"}], temperature=0, stream=True)
            resp = gw.generate(req, allow_fallback=False, token_sink=lambda delta: chunks.append(str(delta)))

            self.assertEqual(resp.text, "你好")
            self.assertEqual(chunks, ["你好"])


if __name__ == "__main__":
    unittest.main()
