"""Tests for services.api.assignment_data_service."""
from __future__ import annotations

import json
import os
import sys
import time
import types
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


def test_build_assignment_detail_cached_with_ttl_disabled_bypasses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from services.api import assignment_data_service as mod

    mod.reset_assignment_cache()
    monkeypatch.setattr(mod, "ASSIGNMENT_DETAIL_CACHE_TTL_SEC", 0)

    calls = {"count": 0}
    fake_app_core = types.ModuleType("services.api.app_core")

    def _fake_build_assignment_detail(folder: Path, *, include_text: bool = True):
        calls["count"] += 1
        return {"call_count": calls["count"], "folder": str(folder), "include_text": include_text}

    fake_app_core.build_assignment_detail = _fake_build_assignment_detail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "services.api.app_core", fake_app_core)

    first = mod.build_assignment_detail_cached(tmp_path, include_text=False)
    second = mod.build_assignment_detail_cached(tmp_path, include_text=False)
    assert first["call_count"] == 1
    assert second["call_count"] == 2
    assert calls["count"] == 2


def test_build_assignment_detail_cached_reuses_cache_then_invalidates_on_fingerprint_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from services.api import assignment_data_service as mod

    mod.reset_assignment_cache()
    monkeypatch.setattr(mod, "ASSIGNMENT_DETAIL_CACHE_TTL_SEC", 60)

    meta_path = tmp_path / "meta.json"
    _write_json(meta_path, {"version": 1})
    _write_json(tmp_path / "requirements.json", {"course": "physics"})
    (tmp_path / "questions.csv").write_text("q,a\n1,2\n", encoding="utf-8")

    calls = {"count": 0}
    fake_app_core = types.ModuleType("services.api.app_core")

    def _fake_build_assignment_detail(folder: Path, *, include_text: bool = True):
        calls["count"] += 1
        return {"call_count": calls["count"], "folder": str(folder), "include_text": include_text}

    fake_app_core.build_assignment_detail = _fake_build_assignment_detail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "services.api.app_core", fake_app_core)

    first = mod.build_assignment_detail_cached(tmp_path, include_text=True)
    second = mod.build_assignment_detail_cached(tmp_path, include_text=True)
    assert first["call_count"] == 1
    assert second["call_count"] == 1
    assert calls["count"] == 1

    _write_json(meta_path, {"version": 2})
    future_ts = time.time() + 5
    os.utime(meta_path, (future_ts, future_ts))
    third = mod.build_assignment_detail_cached(tmp_path, include_text=True)
    assert third["call_count"] == 2
    assert calls["count"] == 2


def test_assignment_detail_fingerprint_handles_stat_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from services.api import assignment_data_service as mod

    _write_json(tmp_path / "meta.json", {"a": 1})
    _write_json(tmp_path / "requirements.json", {"b": 2})
    (tmp_path / "questions.csv").write_text("q,a\n1,2\n", encoding="utf-8")

    orig_stat = Path.stat

    def _patched_stat(path_obj: Path):
        if path_obj.name == "requirements.json":
            raise OSError("simulated stat failure")
        return orig_stat(path_obj)

    monkeypatch.setattr(Path, "stat", _patched_stat)
    fp = mod._assignment_detail_fingerprint(tmp_path)
    assert fp[0] > 0.0
    assert fp[1] == 0.0
    assert fp[2] > 0.0
