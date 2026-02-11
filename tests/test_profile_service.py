"""Tests for services.api.profile_service."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from services.api.profile_service import (
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
