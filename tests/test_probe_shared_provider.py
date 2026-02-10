"""Tests for shared provider probe-models support."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from services.api.teacher_provider_registry_service import (
    TeacherProviderRegistryDeps,
    resolve_shared_provider_target,
    teacher_provider_registry_probe_models,
)


def _make_registry() -> Dict[str, Any]:
    return {
        "providers": {
            "siliconflow": {
                "base_url": "https://api.siliconflow.cn/v1",
                "auth": {"type": "bearer"},
                "api_key_envs": ["SILICONFLOW_API_KEY"],
                "modes": {
                    "openai-chat": {
                        "endpoint": "/chat/completions",
                        "default_model": "deepseek-ai/DeepSeek-V3",
                    }
                },
            },
            "gemini": {
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "auth": {"type": "x-goog-api-key"},
                "api_key_envs": ["GEMINI_API_KEY"],
                "modes": {
                    "openai-chat": {
                        "endpoint": "/chat/completions",
                        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                        "default_model": "gemini-2.5-flash",
                    }
                },
            },
        },
        "defaults": {"provider": "siliconflow", "mode": "openai-chat"},
    }


def _make_deps(registry: Dict[str, Any], env_map: Optional[Dict[str, str]] = None) -> TeacherProviderRegistryDeps:
    env = env_map or {}
    return TeacherProviderRegistryDeps(
        model_registry=registry,
        resolve_teacher_id=lambda tid: tid or "teacher_default",
        teacher_workspace_dir=lambda actor: Path("/tmp/test_probe_shared") / actor,
        atomic_write_json=MagicMock(),
        now_iso=lambda: "2026-02-10T00:00:00Z",
        getenv=lambda key, default=None: env.get(key, default),
    )


class TestResolveSharedProviderTarget:
    def test_siliconflow(self):
        deps = _make_deps(_make_registry(), {"SILICONFLOW_API_KEY": "sk-test-123"})
        result = resolve_shared_provider_target(provider_id="siliconflow", deps=deps)
        assert result is not None
        assert result["provider"] == "siliconflow"
        assert result["base_url"] == "https://api.siliconflow.cn/v1"
        assert result["headers"]["Authorization"] == "Bearer sk-test-123"
        assert result["endpoint"] == "/chat/completions"

    def test_gemini_x_goog_api_key(self):
        deps = _make_deps(_make_registry(), {"GEMINI_API_KEY": "AIza-test"})
        result = resolve_shared_provider_target(provider_id="gemini", deps=deps)
        assert result is not None
        assert result["provider"] == "gemini"
        assert "x-goog-api-key" in result["headers"]
        assert result["headers"]["x-goog-api-key"] == "AIza-test"
        # mode-level base_url should take precedence
        assert "openai" in result["base_url"]

    def test_missing_api_key_returns_none(self):
        deps = _make_deps(_make_registry(), {})
        result = resolve_shared_provider_target(provider_id="siliconflow", deps=deps)
        assert result is None

    def test_unknown_provider_returns_none(self):
        deps = _make_deps(_make_registry(), {"SILICONFLOW_API_KEY": "sk-test"})
        result = resolve_shared_provider_target(provider_id="nonexistent", deps=deps)
        assert result is None

    def test_llm_api_key_takes_priority(self):
        deps = _make_deps(_make_registry(), {"LLM_API_KEY": "global-key"})
        result = resolve_shared_provider_target(provider_id="siliconflow", deps=deps)
        assert result is not None
        assert result["headers"]["Authorization"] == "Bearer global-key"


class TestProbeModelsSharedFallback:
    @patch("services.api.teacher_provider_registry_service.requests.get")
    def test_probe_models_shared_fallback(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({
            "data": [
                {"id": "deepseek-ai/DeepSeek-V3"},
                {"id": "Qwen/Qwen3-8B"},
            ]
        })
        mock_resp.json.return_value = {
            "data": [
                {"id": "deepseek-ai/DeepSeek-V3"},
                {"id": "Qwen/Qwen3-8B"},
            ]
        }
        mock_get.return_value = mock_resp

        deps = _make_deps(_make_registry(), {"SILICONFLOW_API_KEY": "sk-test"})
        result = teacher_provider_registry_probe_models(
            {"provider_id": "siliconflow"}, deps=deps,
        )
        assert result["ok"] is True
        assert "deepseek-ai/DeepSeek-V3" in result["models"]
        assert "Qwen/Qwen3-8B" in result["models"]
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert "siliconflow" in call_url or "api.siliconflow.cn" in call_url

    def test_probe_models_unknown_provider(self):
        deps = _make_deps(_make_registry(), {"SILICONFLOW_API_KEY": "sk-test"})
        result = teacher_provider_registry_probe_models(
            {"provider_id": "nonexistent"}, deps=deps,
        )
        assert result["ok"] is False
        assert result["error"] == "provider_not_found"
