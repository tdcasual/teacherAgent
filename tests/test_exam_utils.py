"""Tests for services.api.exam_utils pure functions."""
from __future__ import annotations

import csv
import types
from pathlib import Path

import pytest

from services.api.exam_utils import (
    _EXAM_CHART_DEFAULT_TYPES,
    _median_float,
    _normalize_exam_chart_types,
    _normalize_question_no_list,
    _parse_question_no_int,
    _parse_xlsx_with_script,
    _safe_int_arg,
    compute_exam_totals,
    parse_score_value,
    read_questions_csv,
)


# -- parse_score_value --------------------------------------------------------

@pytest.mark.parametrize("inp,expected", [
    (None, None),
    ("", None),
    ("3.5", 3.5),
    ("abc", None),
    (0, 0.0),
    ("  7 ", 7.0),
])
def test_parse_score_value(inp, expected):
    assert parse_score_value(inp) == expected


# -- _parse_question_no_int ---------------------------------------------------

@pytest.mark.parametrize("inp,expected", [
    ("3", 3),
    ("5abc", 5),
    ("0", None),
    ("", None),
    ("-1", None),
    (None, None),
])
def test_parse_question_no_int(inp, expected):
    assert _parse_question_no_int(inp) == expected


# -- _median_float ------------------------------------------------------------

@pytest.mark.parametrize("values,expected", [
    ([], 0.0),
    ([5.0], 5.0),
    ([1.0, 3.0], 2.0),
    ([1.0, 2.0, 3.0], 2.0),
    ([10.0, 20.0, 30.0, 40.0], 25.0),
])
def test_median_float(values, expected):
    assert _median_float(values) == expected


# -- _normalize_question_no_list ----------------------------------------------

def test_normalize_question_no_list_csv_string():
    assert _normalize_question_no_list("1,2,3") == [1, 2, 3]


def test_normalize_question_no_list_dedup():
    assert _normalize_question_no_list([1, 1, 2]) == [1, 2]


def test_normalize_question_no_list_maximum():
    result = _normalize_question_no_list("1,2,3,4,5", maximum=2)
    assert result == [1, 2]


def test_normalize_question_no_list_none():
    assert _normalize_question_no_list(None) == []


# -- _safe_int_arg ------------------------------------------------------------

def test_safe_int_arg_normal():
    assert _safe_int_arg(5, default=10, minimum=1, maximum=20) == 5


def test_safe_int_arg_below_min():
    assert _safe_int_arg(-5, default=10, minimum=1, maximum=20) == 1


def test_safe_int_arg_above_max():
    assert _safe_int_arg(100, default=10, minimum=1, maximum=20) == 20


def test_safe_int_arg_non_int():
    assert _safe_int_arg("xyz", default=10, minimum=1, maximum=20) == 10


# -- _normalize_exam_chart_types ----------------------------------------------

def test_normalize_chart_types_alias():
    assert _normalize_exam_chart_types(["distribution"]) == ["score_distribution"]


def test_normalize_chart_types_empty_returns_defaults():
    assert _normalize_exam_chart_types([]) == list(_EXAM_CHART_DEFAULT_TYPES)


def test_normalize_chart_types_chinese_alias():
    assert _normalize_exam_chart_types(["成绩分布"]) == ["score_distribution"]


def test_normalize_chart_types_dedup():
    result = _normalize_exam_chart_types(["distribution", "histogram"])
    assert result == ["score_distribution"]


# -- read_questions_csv -------------------------------------------------------

def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_read_questions_csv_valid(tmp_path):
    csv_path = tmp_path / "questions.csv"
    fields = ["question_id", "question_no", "sub_no", "order", "max_score"]
    rows = [
        {"question_id": "q1", "question_no": "1", "sub_no": "", "order": "1", "max_score": "10"},
        {"question_id": "q2", "question_no": "2", "sub_no": "a", "order": "2", "max_score": "5"},
    ]
    _write_csv(csv_path, fields, rows)
    result = read_questions_csv(csv_path)
    assert len(result) == 2
    assert result["q1"]["max_score"] == 10.0
    assert result["q2"]["sub_no"] == "a"


def test_read_questions_csv_missing_file(tmp_path):
    assert read_questions_csv(tmp_path / "nope.csv") == {}


# -- compute_exam_totals ------------------------------------------------------

def test_compute_exam_totals_valid(tmp_path):
    csv_path = tmp_path / "responses.csv"
    fields = ["student_id", "student_name", "class_name", "question_id", "score"]
    rows = [
        {"student_id": "s1", "student_name": "Alice", "class_name": "A", "question_id": "q1", "score": "8"},
        {"student_id": "s1", "student_name": "Alice", "class_name": "A", "question_id": "q2", "score": "5"},
        {"student_id": "s2", "student_name": "Bob", "class_name": "B", "question_id": "q1", "score": "10"},
    ]
    _write_csv(csv_path, fields, rows)
    result = compute_exam_totals(csv_path)
    assert result["totals"]["s1"] == 13.0
    assert result["totals"]["s2"] == 10.0
    assert result["students"]["s1"]["student_name"] == "Alice"


def test_compute_exam_totals_missing_score_skipped(tmp_path):
    csv_path = tmp_path / "responses.csv"
    fields = ["student_id", "student_name", "class_name", "question_id", "score"]
    rows = [
        {"student_id": "s1", "student_name": "Alice", "class_name": "A", "question_id": "q1", "score": "8"},
        {"student_id": "s1", "student_name": "Alice", "class_name": "A", "question_id": "q2", "score": ""},
    ]
    _write_csv(csv_path, fields, rows)
    result = compute_exam_totals(csv_path)
    assert result["totals"]["s1"] == 8.0


def test_parse_xlsx_with_script_uses_default_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def _fake_run(cmd, capture_output, text, env, cwd, timeout):  # type: ignore[no-untyped-def]
        captured["timeout"] = timeout
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.delenv("EXAM_PARSE_XLSX_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr("services.api.exam_utils.subprocess.run", _fake_run)
    rows, report = _parse_xlsx_with_script(
        tmp_path / "input.xlsx",
        tmp_path / "out.csv",
        "EX1",
        "ClassA",
    )
    assert rows is None
    assert "error" in report
    assert captured["timeout"] == 300


def test_parse_xlsx_with_script_uses_env_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def _fake_run(cmd, capture_output, text, env, cwd, timeout):  # type: ignore[no-untyped-def]
        captured["timeout"] = timeout
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setenv("EXAM_PARSE_XLSX_TIMEOUT_SEC", "75")
    monkeypatch.setattr("services.api.exam_utils.subprocess.run", _fake_run)
    rows, report = _parse_xlsx_with_script(
        tmp_path / "input.xlsx",
        tmp_path / "out.csv",
        "EX1",
        "ClassA",
    )
    assert rows is None
    assert "error" in report
    assert captured["timeout"] == 75
