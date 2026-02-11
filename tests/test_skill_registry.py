"""Tests for services.api.skill_registry."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from services.api.skill_registry import (
    SkillEntry,
    _as_str_list,
    _load_yaml,
    list_skill_entries,
    load_skill_entry,
)

# -- _as_str_list --

@pytest.mark.parametrize("inp,expected", [
    (None, []),
    ("hello", ["hello"]),
    ("", []),
    ("  ", []),
    (["a", None, "b"], ["a", "b"]),
    (["", None, "  "], []),
    (0, []),
])
def test_as_str_list(inp, expected):
    assert _as_str_list(inp) == expected

# -- SkillEntry.as_dict --

def test_as_dict():
    e = SkillEntry(id="s1", title="T", desc="D", prompts=["p"], examples=["e"], allowed_roles=["student"])
    d = e.as_dict()
    assert d == {"id": "s1", "title": "T", "desc": "D", "prompts": ["p"], "examples": ["e"], "allowed_roles": ["student"]}

# -- _load_yaml --

def test_load_yaml_corrupt(tmp_path, caplog):
    bad = tmp_path / "bad.yaml"
    bad.write_text(": :\n  - :\n: [", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        result = _load_yaml(bad)
    assert result == {}
    assert "failed to parse skill YAML" in caplog.text

# -- load_skill_entry --

def _write_skill(skill_dir: Path, content: str):
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.yaml").write_text(content, encoding="utf-8")

def test_load_valid(tmp_path):
    _write_skill(tmp_path / "physics", (
        "title: Physics\n"
        "desc: Mechanics basics\n"
        "allowed_roles:\n  - student\n  - teacher\n"
    ))
    e = load_skill_entry(tmp_path / "physics")
    assert e is not None
    assert e.id == "physics"
    assert e.title == "Physics"
    assert e.desc == "Mechanics basics"
    assert e.allowed_roles == ["student", "teacher"]

def test_load_missing_yaml(tmp_path):
    (tmp_path / "empty_skill").mkdir()
    assert load_skill_entry(tmp_path / "empty_skill") is None

def test_load_not_a_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi")
    assert load_skill_entry(f) is None

def test_load_minimal_no_title(tmp_path):
    _write_skill(tmp_path / "bare", "desc: just a desc\n")
    e = load_skill_entry(tmp_path / "bare")
    assert e is not None
    assert e.title == "未命名技能"
    assert e.desc == "just a desc"

def test_load_with_ui_prompts_examples(tmp_path):
    _write_skill(tmp_path / "rich", (
        "title: Rich\n"
        "ui:\n"
        "  prompts:\n    - Ask about gravity\n"
        "  examples:\n    - What is F=ma?\n"
    ))
    e = load_skill_entry(tmp_path / "rich")
    assert e is not None
    assert e.prompts == ["Ask about gravity"]
    assert e.examples == ["What is F=ma?"]

# -- list_skill_entries --

def test_list_sorted(tmp_path):
    _write_skill(tmp_path / "beta", "title: Beta\n")
    _write_skill(tmp_path / "alpha", "title: Alpha\n")
    entries = list_skill_entries(tmp_path)
    assert len(entries) == 2
    assert entries[0].id == "alpha"
    assert entries[1].id == "beta"

def test_list_nonexistent(tmp_path):
    assert list_skill_entries(tmp_path / "nope") == []
