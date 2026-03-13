from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from services.api.chat_runtime_service import ChatRuntimeDeps, call_llm_runtime


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def as_chat_completion(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, req, provider=None, mode=None, model=None, allow_fallback=True, target_override=None):
        self.calls.append(
            {
                "provider": provider,
                "mode": mode,
                "model": model,
                "allow_fallback": allow_fallback,
                "target_override": target_override,
                "messages_len": len(req.messages or []),
            }
        )
        return _FakeResponse("ok")


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def _deps(gateway: _FakeGateway) -> ChatRuntimeDeps:
    @contextmanager
    def fake_limit(_limiter):
        yield

    return ChatRuntimeDeps(
        gateway=gateway,
        limit=fake_limit,
        default_limiter=object(),
        student_limiter=object(),
        teacher_limiter=object(),
        resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher_default"),
        resolve_teacher_model_config=lambda _actor: {
            "models": {
                "conversation": {
                    "provider": "openai",
                    "mode": "openai-chat",
                    "model": "gpt-4.1-mini",
                }
            }
        },
        resolve_teacher_provider_target=lambda _teacher_id, _provider, _mode, _model: {"api_key": "secret"},
        diag_log=lambda *_args, **_kwargs: None,
    )


def test_chat_runtime_hotspot_removed() -> None:
    target = "services/api/chat_runtime_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def call_llm_runtime(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_call_llm_runtime_prefers_target_override_when_teacher_route_resolves() -> None:
    gateway = _FakeGateway()

    result = call_llm_runtime(
        [{"role": "user", "content": "hi"}],
        deps=_deps(gateway),
        role_hint="teacher",
        teacher_id="teacher_a",
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert gateway.calls[-1]["target_override"] == {"api_key": "secret"}
    assert gateway.calls[-1]["allow_fallback"] is False
