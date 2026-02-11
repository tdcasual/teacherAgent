"""Tests for pure / env-based helpers in services.api.mem0_adapter."""

from __future__ import annotations

import pytest

from services.api.mem0_adapter import (
    _env_bool,
    _env_float,
    _env_int,
    _teacher_user_id,
    teacher_mem0_chunk_chars,
    teacher_mem0_chunk_overlap_chars,
    teacher_mem0_enabled,
    teacher_mem0_topk_default,
    teacher_mem0_write_enabled,
)

# ── _env_bool ────────────────────────────────────────────────────────

@pytest.mark.parametrize("val", ["1", "true", "True", "YES", "on", " On "])
def test_env_bool_true_values(monkeypatch, val):
    monkeypatch.setenv("_TEST_BOOL", val)
    assert _env_bool("_TEST_BOOL") is True


@pytest.mark.parametrize("val", ["0", "false", "no", "off", "random"])
def test_env_bool_false_values(monkeypatch, val):
    monkeypatch.setenv("_TEST_BOOL", val)
    assert _env_bool("_TEST_BOOL") is False


def test_env_bool_missing_returns_default(monkeypatch):
    monkeypatch.delenv("_TEST_BOOL", raising=False)
    assert _env_bool("_TEST_BOOL") is False
    assert _env_bool("_TEST_BOOL", True) is True


# ── _env_int ─────────────────────────────────────────────────────────

def test_env_int_valid(monkeypatch):
    monkeypatch.setenv("_TEST_INT", " 42 ")
    assert _env_int("_TEST_INT", 0) == 42


def test_env_int_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("_TEST_INT", "abc")
    assert _env_int("_TEST_INT", 7) == 7


def test_env_int_missing(monkeypatch):
    monkeypatch.delenv("_TEST_INT", raising=False)
    assert _env_int("_TEST_INT", 99) == 99


# ── _env_float ───────────────────────────────────────────────────────

def test_env_float_valid(monkeypatch):
    monkeypatch.setenv("_TEST_FLOAT", " 0.75 ")
    assert _env_float("_TEST_FLOAT", 0.0) == pytest.approx(0.75)


def test_env_float_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("_TEST_FLOAT", "nope")
    assert _env_float("_TEST_FLOAT", 1.5) == pytest.approx(1.5)


def test_env_float_missing(monkeypatch):
    monkeypatch.delenv("_TEST_FLOAT", raising=False)
    assert _env_float("_TEST_FLOAT", 3.14) == pytest.approx(3.14)


# ── teacher_mem0_enabled ─────────────────────────────────────────────

def test_mem0_enabled_on(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_ENABLED", "1")
    assert teacher_mem0_enabled() is True


def test_mem0_enabled_off(monkeypatch):
    monkeypatch.delenv("TEACHER_MEM0_ENABLED", raising=False)
    assert teacher_mem0_enabled() is False


# ── teacher_mem0_write_enabled ───────────────────────────────────────

def test_write_disabled_when_mem0_disabled(monkeypatch):
    monkeypatch.delenv("TEACHER_MEM0_ENABLED", raising=False)
    monkeypatch.setenv("TEACHER_MEM0_WRITE_ENABLED", "1")
    assert teacher_mem0_write_enabled() is False


def test_write_enabled_when_both_on(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_ENABLED", "true")
    monkeypatch.setenv("TEACHER_MEM0_WRITE_ENABLED", "yes")
    assert teacher_mem0_write_enabled() is True


def test_write_defaults_true_when_mem0_on(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_ENABLED", "1")
    monkeypatch.delenv("TEACHER_MEM0_WRITE_ENABLED", raising=False)
    assert teacher_mem0_write_enabled() is True


# ── teacher_mem0_topk_default ────────────────────────────────────────

def test_topk_default(monkeypatch):
    monkeypatch.delenv("TEACHER_MEM0_TOPK", raising=False)
    assert teacher_mem0_topk_default() == 5


def test_topk_custom(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_TOPK", "20")
    assert teacher_mem0_topk_default() == 20


def test_topk_clamped_to_one(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_TOPK", "0")
    assert teacher_mem0_topk_default() == 1


# ── teacher_mem0_chunk_chars ─────────────────────────────────────────

def test_chunk_chars_default(monkeypatch):
    monkeypatch.delenv("TEACHER_MEM0_CHUNK_CHARS", raising=False)
    assert teacher_mem0_chunk_chars() == 900


def test_chunk_chars_clamped_to_200(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_CHUNK_CHARS", "50")
    assert teacher_mem0_chunk_chars() == 200


# ── teacher_mem0_chunk_overlap_chars ─────────────────────────────────

def test_chunk_overlap_default(monkeypatch):
    monkeypatch.delenv("TEACHER_MEM0_CHUNK_OVERLAP_CHARS", raising=False)
    assert teacher_mem0_chunk_overlap_chars() == 100


def test_chunk_overlap_clamped_to_zero(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_CHUNK_OVERLAP_CHARS", "-10")
    assert teacher_mem0_chunk_overlap_chars() == 0


# ── _teacher_user_id ─────────────────────────────────────────────────

def test_teacher_user_id():
    assert _teacher_user_id("abc123") == "teacher:abc123"
    assert _teacher_user_id("") == "teacher:"
