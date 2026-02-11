"""Tests for fs_atomic.py — atomic file write with fsync."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_atomic_write_json_creates_file(tmp_path):
    from services.api.fs_atomic import atomic_write_json
    target = tmp_path / "data.json"
    payload = {"key": "value", "num": 42}
    atomic_write_json(target, payload)
    assert target.exists()
    assert json.loads(target.read_text("utf-8")) == payload


def test_atomic_write_json_overwrites(tmp_path):
    from services.api.fs_atomic import atomic_write_json
    target = tmp_path / "data.json"
    atomic_write_json(target, {"v": 1})
    atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text("utf-8"))["v"] == 2


def test_atomic_write_json_creates_parent_dirs(tmp_path):
    from services.api.fs_atomic import atomic_write_json
    target = tmp_path / "a" / "b" / "data.json"
    atomic_write_json(target, {"nested": True})
    assert target.exists()


def test_atomic_write_json_no_temp_file_left(tmp_path):
    from services.api.fs_atomic import atomic_write_json
    target = tmp_path / "clean.json"
    atomic_write_json(target, {"ok": True})
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].name == "clean.json"


def test_atomic_write_jsonl(tmp_path):
    from services.api.fs_atomic import atomic_write_jsonl
    target = tmp_path / "records.jsonl"
    records = [{"id": 1}, {"id": 2}, {"id": 3}]
    atomic_write_jsonl(target, records)
    lines = target.read_text("utf-8").strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0]) == {"id": 1}
    assert json.loads(lines[2]) == {"id": 3}
