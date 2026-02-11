"""Tests for services.api.global_limits."""

from __future__ import annotations

import threading

import pytest

from services.api.global_limits import _env_int


# -- _env_int -----------------------------------------------------------------

class TestEnvInt:
    """Unit tests for the _env_int helper."""

    def test_valid_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "16")
        assert _env_int("TEST_LIMIT", 4) == 16

    def test_invalid_env_var_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "not_a_number")
        assert _env_int("TEST_LIMIT", 5) == 5

    def test_value_below_one_clamped(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "0")
        assert _env_int("TEST_LIMIT", 4) == 1

    def test_negative_value_clamped(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "-10")
        assert _env_int("TEST_LIMIT", 4) == 1

    def test_missing_env_var_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_LIMIT", raising=False)
        assert _env_int("TEST_LIMIT", 7) == 7

    def test_empty_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "")
        assert _env_int("TEST_LIMIT", 3) == 3

    def test_whitespace_around_value(self, monkeypatch):
        monkeypatch.setenv("TEST_LIMIT", "  12  ")
        assert _env_int("TEST_LIMIT", 4) == 12


# -- Module-level semaphores ---------------------------------------------------

class TestModuleSemaphores:
    """Verify that module-level semaphores are BoundedSemaphore instances."""

    @pytest.mark.parametrize("name", [
        "GLOBAL_OCR_SEMAPHORE",
        "GLOBAL_LLM_SEMAPHORE",
        "GLOBAL_LLM_SEMAPHORE_STUDENT",
        "GLOBAL_LLM_SEMAPHORE_TEACHER",
    ])
    def test_semaphore_is_bounded(self, name):
        import services.api.global_limits as gl
        sem = getattr(gl, name)
        assert isinstance(sem, threading.BoundedSemaphore)
