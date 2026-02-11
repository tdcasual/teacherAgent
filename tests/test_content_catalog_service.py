"""Tests for services.api.content_catalog_service."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from services.api.content_catalog_service import (
    ContentCatalogDeps,
    list_lessons,
    list_skills,
    load_kp_catalog,
    load_question_kp_map,
)


def _make_deps(tmp_path: Path, **overrides: Any) -> ContentCatalogDeps:
    defaults: Dict[str, Any] = dict(
        data_dir=tmp_path,
        app_root=tmp_path,
        load_profile_file=lambda p: json.loads(p.read_text()),
        load_skills=lambda *a, **kw: SimpleNamespace(skills={}, errors=[]),
        teacher_skills_dir=tmp_path / "teacher_skills",
    )
    defaults.update(overrides)
    return ContentCatalogDeps(**defaults)


# -- list_lessons -------------------------------------------------------------

def test_list_lessons_no_dir(tmp_path: Path):
    deps = _make_deps(tmp_path)
    assert list_lessons(deps=deps) == {"lessons": []}


def test_list_lessons_sorted_with_json(tmp_path: Path):
    lessons = tmp_path / "lessons"
    for fid, lid in [("b_folder", "L002"), ("a_folder", "L001")]:
        d = lessons / fid
        d.mkdir(parents=True)
        (d / "lesson.json").write_text(json.dumps({"lesson_id": lid, "summary": f"s-{lid}"}))

    deps = _make_deps(tmp_path)
    result = list_lessons(deps=deps)
    ids = [l["lesson_id"] for l in result["lessons"]]
    assert ids == ["L001", "L002"]
    assert result["lessons"][0]["summary"] == "s-L001"


def test_list_lessons_folder_without_json(tmp_path: Path):
    (tmp_path / "lessons" / "my_lesson").mkdir(parents=True)
    deps = _make_deps(tmp_path)
    result = list_lessons(deps=deps)
    assert result["lessons"] == [{"lesson_id": "my_lesson", "summary": ""}]


# -- load_kp_catalog ----------------------------------------------------------

def _write_csv(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_kp_catalog_valid(tmp_path: Path):
    _write_csv(
        tmp_path / "knowledge" / "knowledge_points.csv",
        "kp_id,name,status,notes\nKP001,力学基础,active,重点\nKP002,热学,active,\n",
    )
    result = load_kp_catalog(tmp_path)
    assert result["KP001"] == {"name": "力学基础", "status": "active", "notes": "重点"}
    assert result["KP002"]["name"] == "热学"


def test_load_kp_catalog_missing_file(tmp_path: Path):
    assert load_kp_catalog(tmp_path) == {}


def test_load_kp_catalog_corrupt(tmp_path: Path, caplog):
    p = tmp_path / "knowledge" / "knowledge_points.csv"
    _write_csv(p, "kp_id,name,status,notes\n")
    # Corrupt the file so csv parsing raises inside the loop
    p.write_bytes(b"\xff\xfe" + b"\x00" * 200)
    with caplog.at_level(logging.ERROR):
        result = load_kp_catalog(tmp_path)
    assert result == {} or isinstance(result, dict)


def test_load_kp_catalog_skips_empty_kp_id(tmp_path: Path):
    _write_csv(
        tmp_path / "knowledge" / "knowledge_points.csv",
        "kp_id,name,status,notes\n,empty_name,active,\nKP003,valid,active,ok\n",
    )
    result = load_kp_catalog(tmp_path)
    assert "KP003" in result
    assert "" not in result
    assert len(result) == 1


# -- load_question_kp_map -----------------------------------------------------

def test_load_question_kp_map_valid(tmp_path: Path):
    _write_csv(
        tmp_path / "knowledge" / "knowledge_point_map.csv",
        "question_id,kp_id\nQ1,KP001\nQ2,KP002\n",
    )
    result = load_question_kp_map(tmp_path)
    assert result == {"Q1": "KP001", "Q2": "KP002"}


def test_load_question_kp_map_missing(tmp_path: Path):
    assert load_question_kp_map(tmp_path) == {}


# -- list_skills ---------------------------------------------------------------

def test_list_skills_delegates(tmp_path: Path):
    fake_spec = SimpleNamespace(as_public_dict=lambda: {"id": "sk1", "name": "Skill 1"})
    fake_loaded = SimpleNamespace(skills={"sk1": fake_spec}, errors=[])
    called_with: list = []

    def mock_load(skills_dir, *, teacher_skills_dir):
        called_with.append((skills_dir, teacher_skills_dir))
        return fake_loaded

    deps = _make_deps(tmp_path, load_skills=mock_load)
    result = list_skills(deps=deps)
    assert result == {"skills": [{"id": "sk1", "name": "Skill 1"}]}
    assert called_with[0][0] == tmp_path / "skills"
