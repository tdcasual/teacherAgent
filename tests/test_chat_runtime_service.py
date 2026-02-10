from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import unittest

from services.api.chat_runtime_service import ChatRuntimeDeps, call_llm_runtime


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def as_chat_completion(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeGateway:
    def __init__(self):
        self.registry = object()
        self.calls = []

    def generate(self, req, provider=None, mode=None, model=None, allow_fallback=True, target_override=None):
        self.calls.append(
            {
                "provider": provider,
                "mode": mode,
                "model": model,
                "allow_fallback": allow_fallback,
                "target_override": bool(target_override),
                "messages_len": len(req.messages or []),
            }
        )
        return _FakeResponse("ok")


class ChatRuntimeServiceTest(unittest.TestCase):
    def test_call_llm_runtime_uses_role_limiter_and_returns_chat_completion(self):
        gateway = _FakeGateway()
        default_limiter = object()
        student_limiter = object()
        teacher_limiter = object()
        limiter_seen = []
        logs = []

        @contextmanager
        def fake_limit(limiter):
            limiter_seen.append(limiter)
            yield

        deps = ChatRuntimeDeps(
            gateway=gateway,
            limit=fake_limit,
            default_limiter=default_limiter,
            student_limiter=student_limiter,
            teacher_limiter=teacher_limiter,
            resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher_default"),
            resolve_teacher_model_registry=lambda _actor: {},
            resolve_teacher_provider_target=lambda _teacher_id, _provider, _mode, _model: None,
            ensure_teacher_routing_file=lambda actor: Path(f"/tmp/{actor}.json"),
            routing_config_path_for_role=lambda role_hint, teacher_id: Path("/tmp/default-routing.json"),
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        )

        result = call_llm_runtime(
            [{"role": "user", "content": "hello"}],
            deps=deps,
            role_hint="student",
            skill_id="skill_x",
            kind="chat.skill",
        )
        self.assertEqual(result.get("choices", [{}])[0].get("message", {}).get("content"), "ok")
        self.assertIs(limiter_seen[-1], student_limiter)
        self.assertTrue(gateway.calls)
        self.assertEqual(logs[-1][0], "llm.call.done")

    def test_call_llm_runtime_uses_teacher_limiter(self):
        gateway = _FakeGateway()
        default_limiter = object()
        student_limiter = object()
        teacher_limiter = object()
        limiter_seen = []

        @contextmanager
        def fake_limit(limiter):
            limiter_seen.append(limiter)
            yield

        deps = ChatRuntimeDeps(
            gateway=gateway,
            limit=fake_limit,
            default_limiter=default_limiter,
            student_limiter=student_limiter,
            teacher_limiter=teacher_limiter,
            resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher_default"),
            resolve_teacher_model_registry=lambda _actor: {},
            resolve_teacher_provider_target=lambda _teacher_id, _provider, _mode, _model: None,
            ensure_teacher_routing_file=lambda actor: Path(f"/tmp/{actor}.json"),
            routing_config_path_for_role=lambda role_hint, teacher_id: Path("/tmp/default-routing.json"),
            diag_log=lambda *_args, **_kwargs: None,
        )

        result = call_llm_runtime(
            [{"role": "user", "content": "hi"}],
            deps=deps,
            role_hint="teacher",
            teacher_id="teacher_a",
        )
        self.assertEqual(result.get("choices", [{}])[0].get("message", {}).get("content"), "ok")
        self.assertIs(limiter_seen[-1], teacher_limiter)


if __name__ == "__main__":
    unittest.main()
