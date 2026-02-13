"""Tests for services.api.core_utils — pure utility functions."""
from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from services.api.core_utils import (
    _is_safe_tool_id,
    _non_ws_len,
    _percentile,
    _resolve_app_path,
    _score_band_label,
    count_csv_rows,
    normalize,
    normalize_due_at,
    run_script,
    resolve_scope,
    safe_slug,
)


# --- normalize ---
@pytest.mark.parametrize("inp,expected", [
    ("Hello World", "helloworld"),
    (None, ""),
    ("", ""),
    ("  A  B  ", "ab"),
])
def test_normalize(inp, expected):
    assert normalize(inp) == expected


# --- safe_slug ---
@pytest.mark.parametrize("inp,expected", [
    ("my assignment", "my_assignment"),
    ("", "assignment"),
    ("---", "---"),
    ("@@@", "assignment"),
    ("valid-slug", "valid-slug"),
])
def test_safe_slug(inp, expected):
    assert safe_slug(inp) == expected


# --- resolve_scope ---
def test_resolve_scope_explicit():
    assert resolve_scope("public", [], "") == "public"
    assert resolve_scope("CLASS", [], "") == "class"
    assert resolve_scope("Student", [], "") == "student"

def test_resolve_scope_inferred():
    assert resolve_scope("", ["s1"], "") == "student"
    assert resolve_scope("", [], "ClassA") == "class"
    assert resolve_scope("", [], "") == "public"


# --- normalize_due_at ---
@pytest.mark.parametrize("inp,expected", [
    ("2026-01-15", "2026-01-15T23:59:59"),
    ("2026-01-15T10:00:00", "2026-01-15T10:00:00"),
    ("garbage", None),
    ("", None),
    (None, None),
])
def test_normalize_due_at(inp, expected):
    assert normalize_due_at(inp) == expected


# --- count_csv_rows ---
def test_count_csv_rows_valid(tmp_path: Path):
    csv_file = tmp_path / "data.csv"
    with csv_file.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "score"])
        w.writerow(["Alice", "90"])
        w.writerow(["Bob", "80"])
        w.writerow(["Carol", "70"])
    assert count_csv_rows(csv_file) == 3

def test_count_csv_rows_missing(tmp_path: Path):
    assert count_csv_rows(tmp_path / "nope.csv") == 0


# --- _non_ws_len ---
@pytest.mark.parametrize("inp,expected", [("a b c", 3), ("", 0), ("  ", 0)])
def test_non_ws_len(inp, expected):
    assert _non_ws_len(inp) == expected


# --- _percentile ---
def test_percentile_empty():
    assert _percentile([], 0.5) == 0.0

@pytest.mark.parametrize("p,expected", [(0.0, 10.0), (0.5, 20.0), (1.0, 30.0)])
def test_percentile_values(p, expected):
    assert _percentile([10, 20, 30], p) == expected


# --- _score_band_label ---
@pytest.mark.parametrize("pct,expected", [
    (0, "0\u20139%"),
    (50, "50\u201359%"),
    (95, "90\u2013100%"),
    (100, "90\u2013100%"),
])
def test_score_band_label(pct, expected):
    assert _score_band_label(pct) == expected


# --- _is_safe_tool_id ---
@pytest.mark.parametrize("inp,expected", [
    ("my-tool", True),
    ("", False),
    ("a/b", False),
    (None, False),
    ("a\\b", False),
])
def test_is_safe_tool_id(inp, expected):
    assert _is_safe_tool_id(inp) is expected


# --- _resolve_app_path ---
def test_resolve_app_path_inside(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    with patch("services.api.core_utils.APP_ROOT", tmp_path):
        assert _resolve_app_path("sub", must_exist=True) == sub

def test_resolve_app_path_outside(tmp_path: Path):
    with patch("services.api.core_utils.APP_ROOT", tmp_path):
        assert _resolve_app_path("/etc/passwd", must_exist=False) is None

def test_resolve_app_path_missing(tmp_path: Path):
    with patch("services.api.core_utils.APP_ROOT", tmp_path):
        assert _resolve_app_path("no_such_file", must_exist=True) is None


# --- run_script timeout guards ---
def test_run_script_uses_default_timeout(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def _fake_run(args, capture_output, text, env, cwd, timeout):  # type: ignore[no-untyped-def]
        captured["timeout"] = timeout
        return _Proc()

    monkeypatch.delenv("RUN_SCRIPT_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr("services.api.core_utils.subprocess.run", _fake_run)
    with patch("services.api.core_utils.APP_ROOT", tmp_path):
        out = run_script(["python3", "-V"])
    assert out == "ok"
    assert captured["timeout"] == 300


def test_run_script_uses_env_timeout(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def _fake_run(args, capture_output, text, env, cwd, timeout):  # type: ignore[no-untyped-def]
        captured["timeout"] = timeout
        return _Proc()

    monkeypatch.setenv("RUN_SCRIPT_TIMEOUT_SEC", "42")
    monkeypatch.setattr("services.api.core_utils.subprocess.run", _fake_run)
    with patch("services.api.core_utils.APP_ROOT", tmp_path):
        out = run_script(["python3", "-V"])
    assert out == "ok"
    assert captured["timeout"] == 42
