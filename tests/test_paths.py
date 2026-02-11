"""Tests for services.api.paths — path construction and traversal guards."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from services.api import paths
from services.api import config as _cfg


# ── safe_fs_id ──────────────────────────────────────────────────────────

class TestSafeFsId:
    def test_normal_string(self):
        result = paths.safe_fs_id("hello-world_123")
        assert result == "hello-world_123"

    def test_special_chars_sanitized(self):
        result = paths.safe_fs_id("a/b@c d!e")
        assert re.fullmatch(r"[\w_-]+", result), f"unexpected chars in {result}"

    def test_short_string_gets_hash(self):
        result = paths.safe_fs_id("ab", prefix="id")
        assert result.startswith("id_")
        assert len(result) >= 13  # "id_" + 10 hex chars

    def test_empty_string_gets_hash(self):
        result = paths.safe_fs_id("", prefix="x")
        assert result.startswith("x_")


# ── parse_date_str ──────────────────────────────────────────────────────

class TestParseDateStr:
    def test_valid_iso(self):
        assert paths.parse_date_str("2025-03-15") == "2025-03-15"

    def test_none_returns_today(self):
        assert paths.parse_date_str(None) == date.today().isoformat()

    def test_garbage_returns_today(self):
        assert paths.parse_date_str("not-a-date") == date.today().isoformat()


# ── resolve_assignment_dir ──────────────────────────────────────────────

class TestResolveAssignmentDir:
    def test_valid_id(self):
        result = paths.resolve_assignment_dir("hw1")
        assert result == (paths.DATA_DIR / "assignments" / "hw1").resolve()

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="required"):
            paths.resolve_assignment_dir("")

    def test_traversal_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            paths.resolve_assignment_dir("../etc")


# ── resolve_exam_dir ────────────────────────────────────────────────────

class TestResolveExamDir:
    def test_valid_id(self):
        result = paths.resolve_exam_dir("midterm")
        assert result == (paths.DATA_DIR / "exams" / "midterm").resolve()

    def test_traversal_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            paths.resolve_exam_dir("../../passwd")


# ── resolve_analysis_dir ────────────────────────────────────────────────

class TestResolveAnalysisDir:
    def test_valid_id(self):
        result = paths.resolve_analysis_dir("final")
        assert result == (paths.DATA_DIR / "analysis" / "final").resolve()

    def test_traversal_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            paths.resolve_analysis_dir("../secrets")


# ── resolve_student_profile_path ────────────────────────────────────────

class TestResolveStudentProfilePath:
    def test_valid_id(self):
        result = paths.resolve_student_profile_path("stu001")
        assert result == (paths.DATA_DIR / "student_profiles" / "stu001.json").resolve()

    def test_traversal_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            paths.resolve_student_profile_path("../../etc/shadow")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="required"):
            paths.resolve_student_profile_path("")


# ── resolve_manifest_path ──────────────────────────────────────────────

class TestResolveManifestPath:
    def test_none_returns_none(self):
        assert paths.resolve_manifest_path(None) is None

    def test_empty_returns_none(self):
        assert paths.resolve_manifest_path("") is None

    def test_relative_resolved_against_app_root(self):
        result = paths.resolve_manifest_path("data/manifest.json")
        assert result == (_cfg.APP_ROOT / "data" / "manifest.json").resolve()

    def test_absolute_returned_as_is(self):
        result = paths.resolve_manifest_path("/tmp/manifest.json")
        assert result == Path("/tmp/manifest.json")


# ── teacher_workspace_file ──────────────────────────────────────────────

class TestTeacherWorkspaceFile:
    def test_allowed_name(self):
        result = paths.teacher_workspace_file("teacher1", "SOUL.md")
        assert result.name == "SOUL.md"

    def test_disallowed_name_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            paths.teacher_workspace_file("teacher1", "evil.txt")


# ── routing_config_path_for_role ────────────────────────────────────────

class TestRoutingConfigPathForRole:
    def test_teacher_role(self):
        result = paths.routing_config_path_for_role("teacher", "t1")
        assert "llm_routing.json" in str(result)
        assert "teacher" in str(result).lower()

    def test_student_role_returns_global(self):
        result = paths.routing_config_path_for_role("student")
        assert result == _cfg.LLM_ROUTING_PATH
