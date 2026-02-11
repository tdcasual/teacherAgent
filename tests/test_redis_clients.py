"""Tests for services.api.redis_clients."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import services.api.redis_clients as mod


@pytest.fixture(autouse=True)
def _clear_cache():
    mod._REDIS_CLIENTS.clear()
    yield
    mod._REDIS_CLIENTS.clear()


@patch("redis.Redis.from_url", return_value=MagicMock())
class TestGetRedisClient:
    """All tests patch redis.Redis.from_url to avoid real connections."""

    def test_default_url(self, mock_from_url: MagicMock, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        mod.get_redis_client()
        mock_from_url.assert_called_once_with("redis://localhost:6379/0", decode_responses=True)

    def test_custom_url(self, mock_from_url: MagicMock):
        mod.get_redis_client(url="redis://custom:1234/1")
        mock_from_url.assert_called_once_with("redis://custom:1234/1", decode_responses=True)

    def test_env_var(self, mock_from_url: MagicMock, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REDIS_URL", "redis://from-env:6379/2")
        mod.get_redis_client()
        mock_from_url.assert_called_once_with("redis://from-env:6379/2", decode_responses=True)

    def test_caching_returns_same_client(self, mock_from_url: MagicMock):
        c1 = mod.get_redis_client(url="redis://x:1/0")
        c2 = mod.get_redis_client(url="redis://x:1/0")
        assert c1 is c2
        assert mock_from_url.call_count == 1

    def test_different_decode_responses_returns_different_clients(self, mock_from_url: MagicMock):
        mock_from_url.side_effect = [MagicMock(), MagicMock()]
        c1 = mod.get_redis_client(url="redis://x:1/0", decode_responses=True)
        c2 = mod.get_redis_client(url="redis://x:1/0", decode_responses=False)
        assert c1 is not c2
        assert mock_from_url.call_count == 2

    def test_decode_responses_default_is_true(self, mock_from_url: MagicMock):
        mod.get_redis_client(url="redis://x:1/0")
        _, kwargs = mock_from_url.call_args
        assert kwargs["decode_responses"] is True
