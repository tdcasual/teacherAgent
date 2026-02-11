"""Tests for services.api.assignment_data_service."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# load_assignment_meta
# ---------------------------------------------------------------------------

def test_load_assignment_meta_with_file(tmp_path: Path):
    from services.api.assignment_data_service import load_assignment_meta

    _write_json(tmp_path / "meta.json", {"title": "Kinematics", "grade": 10})
    result = load_assignment_meta(tmp_path)
    assert result == {"title": "Kinematics", "grade": 10}


def test_load_assignment_meta_missing(tmp_path: Path):
    from services.api.assignment_data_service import load_assignment_meta

    result = load_assignment_meta(tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# load_assignment_requirements
# ---------------------------------------------------------------------------

def test_load_assignment_requirements_with_file(tmp_path: Path):
    from services.api.assignment_data_service import load_assignment_requirements

    _write_json(tmp_path / "requirements.json", {"min_score": 60})
    result = load_assignment_requirements(tmp_path)
    assert result == {"min_score": 60}


def test_load_assignment_requirements_missing(tmp_path: Path):
    from services.api.assignment_data_service import load_assignment_requirements

    result = load_assignment_requirements(tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# _assignment_detail_fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint_all_files_present(tmp_path: Path):
    from services.api.assignment_data_service import _assignment_detail_fingerprint

    _write_json(tmp_path / "meta.json", {})
    _write_json(tmp_path / "requirements.json", {})
    (tmp_path / "questions.csv").write_text("q,a\n1,2\n", encoding="utf-8")

    fp = _assignment_detail_fingerprint(tmp_path)
    assert isinstance(fp, tuple) and len(fp) == 3
    assert all(v > 0.0 for v in fp)


def test_fingerprint_empty_folder(tmp_path: Path):
    from services.api.assignment_data_service import _assignment_detail_fingerprint

    assert _assignment_detail_fingerprint(tmp_path) == (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# reset_assignment_cache
# ---------------------------------------------------------------------------

def test_reset_assignment_cache():
    from services.api import assignment_data_service as mod

    # Seed the cache with a dummy entry
    mod._ASSIGNMENT_DETAIL_CACHE["dummy"] = "value"
    assert len(mod._ASSIGNMENT_DETAIL_CACHE) == 1

    mod.reset_assignment_cache()
    assert mod._ASSIGNMENT_DETAIL_CACHE == {}
