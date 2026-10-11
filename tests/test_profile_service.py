"""Tests for services.api.profile_service."""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from services.api.paths import resolve_student_profile_path
from services.api.profile_service import (
    apply_derived_profile,
    derive_kp_from_profile,
    detect_role,
    load_profile_file,
    reset_profile_cache,
    safe_assignment_id,
)

# ---------------------------------------------------------------------------
# detect_role
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("我是老师", "teacher"),
    ("学生小明", "student"),
    ("hello", None),
    ("", None),
])
def test_detect_role(text, expected):
    assert detect_role(text) == expected


# ---------------------------------------------------------------------------
# load_profile_file
# ---------------------------------------------------------------------------

@patch("services.api.profile_service.PROFILE_CACHE_TTL_SEC", 60)
def test_load_profile_file_valid(tmp_path):
    reset_profile_cache()
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
    assert load_profile_file(p) == {"name": "Alice"}


@patch("services.api.profile_service.PROFILE_CACHE_TTL_SEC", 60)
def test_load_profile_file_missing(tmp_path):
    reset_profile_cache()
    assert load_profile_file(tmp_path / "no_such.json") == {}


@patch("services.api.profile_service.PROFILE_CACHE_TTL_SEC", 60)
def test_load_profile_file_corrupt(tmp_path, caplog):
    reset_profile_cache()
    p = tmp_path / "bad.json"
    p.write_text("{invalid json", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="services.api.profile_service"):
        result = load_profile_file(p)
    assert result == {}
    assert "failed to load profile" in caplog.text


@patch("services.api.profile_service.PROFILE_CACHE_TTL_SEC", 60)
def test_load_profile_file_cache_hit(tmp_path):
    reset_profile_cache()
    p = tmp_path / "cached.json"
    p.write_text(json.dumps({"v": 1}), encoding="utf-8")

    first = load_profile_file(p)
    assert first == {"v": 1}

    # Save original mtime, overwrite content, then restore mtime
    import os
    orig = os.stat(p)
    p.write_text(json.dumps({"v": 2}), encoding="utf-8")
    os.utime(p, (orig.st_atime, orig.st_mtime))

    second = load_profile_file(p)
    assert second == {"v": 1}


# ---------------------------------------------------------------------------
# derive_kp_from_profile
# ---------------------------------------------------------------------------

def test_derive_kp_combined_deduped():
    profile = {
        "next_focus": "力学",
        "recent_weak_kp": ["力学", "热学"],
        "recent_medium_kp": ["光学"],
    }
    result = derive_kp_from_profile(profile)
    assert result == ["力学", "热学", "光学"]


def test_derive_kp_empty_profile():
    assert derive_kp_from_profile({}) == []


def test_apply_derived_profile_uses_resolve_student_profile_path(tmp_path, monkeypatch):
    monkeypatch.setattr("services.api.paths.DATA_DIR", tmp_path)
    core = type("Core", (), {"DATA_DIR": tmp_path})()
    expected = resolve_student_profile_path("S1", core=core)
    seeded = {
        "recent_weak_kp": ["旧弱点"],
        "recent_medium_kp": ["旧中等"],
        "next_focus": "旧弱点",
        "mastery_by_kp": {"旧弱点": {"accuracy": 0.1}},
    }
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.write_text(json.dumps(seeded), encoding="utf-8")
    ok = apply_derived_profile(
        "S1",
        {
            "recent_weak_kp": [],
            "recent_medium_kp": [],
            "recent_strong_kp": ["力学"],
            "next_focus": "",
            "source": "graded",
            "assignment_id": "HW_1",
            "question_ids": ["Q1"],
            "mastery_by_kp": {"力学": {"accuracy": 1.0, "attempts": 1}},
        },
        core=core,
    )
    assert ok is True
    assert expected.exists()
    profile = json.loads(expected.read_text(encoding="utf-8"))
    assert profile["recent_weak_kp"] == []
    assert profile["recent_strong_kp"] == ["力学"]
    assert profile["next_focus"] == ""
    assert profile["mastery_by_kp"]["力学"]["accuracy"] == 1.0
    assert profile["mastery_by_kp"]["旧弱点"]["accuracy"] == 0.1
    assert profile["practice_history"][0]["assignment_id"] == "HW_1"


# ---------------------------------------------------------------------------
# safe_assignment_id
# ---------------------------------------------------------------------------

def test_safe_assignment_id_normal():
    assert safe_assignment_id("student1", "2026-01-15") == "AUTO_student1_2026-01-15"


def test_safe_assignment_id_empty():
    assert safe_assignment_id("", "2026-01-15") == "AUTO_student_2026-01-15"


# ---------------------------------------------------------------------------
# reset_profile_cache
# ---------------------------------------------------------------------------

@patch("services.api.profile_service.PROFILE_CACHE_TTL_SEC", 60)
def test_reset_profile_cache_clears(tmp_path):
    reset_profile_cache()
    p = tmp_path / "reset.json"
    p.write_text(json.dumps({"k": 1}), encoding="utf-8")

    load_profile_file(p)
    # Mutate file content (keep same mtime impossible after reset, so just reset)
    reset_profile_cache()

    p.write_text(json.dumps({"k": 2}), encoding="utf-8")
    assert load_profile_file(p) == {"k": 2}
