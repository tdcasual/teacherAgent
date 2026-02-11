"""Tests for exam_score_processing_service — edge cases and error paths."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest


def test_parse_score_value_normal():
    from services.api.exam_score_processing_service import parse_score_value
    assert parse_score_value("85.5") == 85.5
    assert parse_score_value(100) == 100.0
    assert parse_score_value("  42  ") == 42.0


def test_parse_score_value_none_and_empty():
    from services.api.exam_score_processing_service import parse_score_value
    assert parse_score_value(None) is None
    assert parse_score_value("") is None
    assert parse_score_value("  ") is None


def test_parse_score_value_nan_and_inf():
    from services.api.exam_score_processing_service import parse_score_value
    result = parse_score_value("nan")
    assert result is not None and math.isnan(result)
    assert parse_score_value("inf") == float("inf")


def test_parse_score_value_garbage():
    from services.api.exam_score_processing_service import parse_score_value
    assert parse_score_value("abc") is None
    assert parse_score_value("--") is None


def test_score_objective_answer_normal():
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("A", "A", 5.0)
    assert score == 5.0 and correct == 1


def test_score_objective_answer_wrong():
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("B", "A", 5.0)
    assert score == 0.0 and correct == 0


def test_score_objective_answer_partial_multi():
    from services.api.exam_score_processing_service import score_objective_answer
    # Subset of correct answers gets half credit
    score, correct = score_objective_answer("A", "AB", 10.0)
    assert score == 5.0 and correct == 0


def test_score_objective_answer_nan_max_score():
    """NaN max_score should return 0 instead of propagating NaN."""
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("A", "A", float("nan"))
    assert score == 0.0 and correct == 0


def test_score_objective_answer_zero_max_score():
    """Zero max_score should return 0."""
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("A", "A", 0.0)
    assert score == 0.0 and correct == 0


def test_score_objective_answer_negative_max_score():
    """Negative max_score should return 0."""
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("A", "A", -5.0)
    assert score == 0.0 and correct == 0


def test_score_objective_answer_inf_max_score():
    """Infinity max_score should return 0."""
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("A", "A", float("inf"))
    assert score == 0.0 and correct == 0


def test_score_objective_answer_empty_answer():
    from services.api.exam_score_processing_service import score_objective_answer
    score, correct = score_objective_answer("", "A", 5.0)
    assert score == 0.0 and correct == 0


def test_normalize_student_id_basic():
    from services.api.exam_score_processing_service import normalize_student_id_for_exam
    result = normalize_student_id_for_exam("三班", "张三")
    assert result == "三班_张三"


def test_normalize_student_id_empty():
    from services.api.exam_score_processing_service import normalize_student_id_for_exam
    assert normalize_student_id_for_exam("", "") == "unknown"
    assert normalize_student_id_for_exam(None, None) == "unknown"


def test_ensure_questions_max_score_on_missing_csv(tmp_path):
    """Non-existent CSV should return [] without crashing."""
    from services.api.exam_score_processing_service import ensure_questions_max_score
    result = ensure_questions_max_score(
        tmp_path / "nonexistent.csv", {"Q1"}, 5.0,
    )
    assert result == []


def test_ensure_questions_max_score_fills_missing(tmp_path):
    from services.api.exam_score_processing_service import ensure_questions_max_score
    csv_path = tmp_path / "questions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
        w.writeheader()
        w.writerow({"question_id": "Q1", "question_no": "1", "sub_no": "", "order": "1", "max_score": "", "stem_ref": ""})
        w.writerow({"question_id": "Q2", "question_no": "2", "sub_no": "", "order": "2", "max_score": "10", "stem_ref": ""})
    result = ensure_questions_max_score(csv_path, {"Q1", "Q2"}, 5.0)
    assert "Q1" in result
    assert "Q2" not in result  # Q2 already has max_score
