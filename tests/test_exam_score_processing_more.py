from __future__ import annotations

import csv
import io
from pathlib import Path

from services.api import exam_score_processing_service as eps


def test_normalize_excel_cell_and_parse_question_label_variants() -> None:
    assert eps.normalize_excel_cell(None) == ""
    assert eps.normalize_excel_cell("12.0") == "12"

    assert eps.parse_exam_question_label("") is None
    assert eps.parse_exam_question_label("12") == (12, None, "12")
    assert eps.parse_exam_question_label("12(A)") == (12, "A", "12(A)")
    assert eps.parse_exam_question_label("12-A1") == (12, "A1", "12-A1")
    assert eps.parse_exam_question_label("12A") == (12, "A", "12A")
    assert eps.parse_exam_question_label("bad") is None


def test_build_exam_question_id_with_and_without_sub_no() -> None:
    assert eps.build_exam_question_id(3, None) == "Q3"
    assert eps.build_exam_question_id(3, "A") == "Q3A"


def test_build_exam_rows_from_parsed_scores_rejects_invalid_students() -> None:
    rows, questions, warnings = eps.build_exam_rows_from_parsed_scores(
        "EX1",
        {"mode": "total", "students": "invalid", "warnings": ["w1"]},
    )

    assert rows == []
    assert questions == []
    assert warnings == ["students_missing_or_invalid"]


def test_build_exam_rows_from_parsed_scores_total_mode_paths(monkeypatch) -> None:
    monkeypatch.setattr(eps, "parse_score_value", lambda v: None if v == "NA" else float(v))

    parsed = {
        "mode": "total",
        "students": [
            {"student_name": "", "class_name": "", "student_id": "", "total_score": 80},
            {"student_name": "Alice", "class_name": "C1", "student_id": "", "total_score": "NA"},
            {"student_name": "Bob", "class_name": "C1", "student_id": "", "total_score": 90},
        ],
    }

    rows, questions, warnings = eps.build_exam_rows_from_parsed_scores("EX2", parsed)

    assert warnings == []
    assert questions == []
    assert len(rows) == 2
    assert rows[0]["question_id"] == "TOTAL"
    assert rows[1]["score"] == 90.0


def test_build_exam_rows_from_parsed_scores_question_mode_with_mixed_inputs(monkeypatch) -> None:
    parsed = {
        "mode": "question",
        "questions": [
            "skip-me",
            {"question_no": "bad-int", "sub_no": "A"},
            {"question_no": 1, "sub_no": "A"},
            {"question_id": "Q9", "question_no": "x", "sub_no": ""},
        ],
        "students": [
            "skip",
            {
                "student_name": "Amy",
                "class_name": "Class 1",
                "scores": [
                    "bad",
                    {"raw_label": "1A", "score": "5"},
                    {"label": "2", "score": "bad"},
                ],
            },
            {
                "student_name": "Ben",
                "class_name": "Class 1",
                "scores": {
                    "": 1,
                    "Q3": 4,
                    "3-B": 6,
                },
            },
            {
                "student_name": "Cara",
                "class_name": "Class 1",
                "scores": "not-a-dict",
            },
        ],
    }

    rows, questions, warnings = eps.build_exam_rows_from_parsed_scores("EX3", parsed)

    assert warnings == []
    assert len(rows) == 3
    assert {row["question_id"] for row in rows} == {"Q1A", "Q3", "Q3B"}
    assert any(q["question_id"] == "Q9" for q in questions)


def test_write_exam_responses_csv_and_write_exam_questions_csv(tmp_path: Path) -> None:
    responses_path = tmp_path / "responses.csv"
    eps.write_exam_responses_csv(
        responses_path,
        [{"exam_id": "EX", "student_id": "s1", "question_id": "Q1", "score": 2.0}],
    )

    text = responses_path.read_text(encoding="utf-8")
    assert "score" in text
    assert "2.0" in text

    questions_path = tmp_path / "questions.csv"
    eps.write_exam_questions_csv(
        questions_path,
        [
            {"question_id": "", "question_no": "", "sub_no": ""},
            {"question_id": "Q1", "question_no": "1", "sub_no": ""},
        ],
        max_scores={"Q1": 7.0},
    )

    rows = list(csv.DictReader(questions_path.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["question_id"] == "Q1"
    assert rows[0]["max_score"] == "7.0"


def test_compute_max_scores_from_rows_handles_invalid_rows() -> None:
    out = eps.compute_max_scores_from_rows(
        [
            {"question_id": "TOTAL", "score": 99},
            {"question_id": "Q1", "score": None},
            {"question_id": "Q1", "score": "bad"},
            {"question_id": "Q1", "score": 2},
            {"question_id": "Q1", "score": 5},
        ]
    )

    assert out == {"Q1": 5.0}


def test_normalize_objective_answer_paths() -> None:
    assert eps.normalize_objective_answer(" 123 ") == "123"
    assert eps.normalize_objective_answer("a") == "A"
    assert eps.normalize_objective_answer("bca") == "ABC"


def test_parse_exam_answer_key_text_handles_empty_and_line_and_inline() -> None:
    rows, warnings = eps.parse_exam_answer_key_text("   ")
    assert rows == []
    assert warnings

    line_rows, line_warnings = eps.parse_exam_answer_key_text("1) a\n2(A): BC\nnot-match")
    assert line_warnings == []
    assert {r["question_id"] for r in line_rows} == {"Q1", "Q2A"}

    inline_rows, inline_warnings = eps.parse_exam_answer_key_text("答案：1:A, 2B:C")
    assert inline_warnings == []
    assert {r["question_id"] for r in inline_rows} == {"Q1", "Q2B"}


def test_parse_exam_answer_key_text_warning_when_no_items() -> None:
    rows, warnings = eps.parse_exam_answer_key_text("no answer key here")
    assert rows == []
    assert warnings


def test_parse_exam_answer_key_text_sort_fallback_branch(monkeypatch) -> None:
    monkeypatch.setattr(eps.re, "match", lambda _pattern, _text: None)
    rows, warnings = eps.parse_exam_answer_key_text("1:A\n2:B")
    assert warnings == []
    assert len(rows) == 2


def test_write_exam_answers_csv_skips_invalid_rows_and_normalizes(tmp_path: Path) -> None:
    out = tmp_path / "answers.csv"
    eps.write_exam_answers_csv(
        out,
        [
            "bad-row",
            {"question_id": "", "correct_answer": "A"},
            {"question_id": "Q2", "correct_answer": ""},
            {"question_id": "Q1", "question_no": "1", "sub_no": "", "raw_label": "1", "correct_answer": "bca"},
        ],
    )

    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["question_id"] == "Q1"
    assert rows[0]["correct_answer"] == "ABC"


class _OpenErrorPath:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    def exists(self) -> bool:
        return self._exists

    def open(self, *args, **kwargs):
        raise OSError("open failed")

    def __str__(self) -> str:
        return "fake.csv"


class _ReadOkWriteFailPath:
    def __init__(self, text: str) -> None:
        self._text = text

    def exists(self) -> bool:
        return True

    def open(self, mode: str = "r", *args, **kwargs):
        if "w" in mode:
            raise OSError("write failed")
        return io.StringIO(self._text)

    def __str__(self) -> str:
        return "fake_rw.csv"


def test_load_exam_answer_key_from_csv_paths(tmp_path: Path) -> None:
    missing = eps.load_exam_answer_key_from_csv(tmp_path / "missing.csv")
    assert missing == {}

    csv_path = tmp_path / "answers.csv"
    csv_path.write_text("question_id,question_no,correct_answer\n,1,A\nQ1,,b\n", encoding="utf-8")
    loaded = eps.load_exam_answer_key_from_csv(csv_path)
    assert loaded == {"1": "A", "Q1": "B"}

    err = eps.load_exam_answer_key_from_csv(_OpenErrorPath())
    assert err == {}


def test_load_exam_max_scores_from_questions_csv_paths(tmp_path: Path) -> None:
    missing = eps.load_exam_max_scores_from_questions_csv(tmp_path / "missing.csv")
    assert missing == {}

    csv_path = tmp_path / "questions.csv"
    csv_path.write_text(
        "question_id,max_score\n,5\nQ1,\nQ2,bad\nQ3,10\n",
        encoding="utf-8",
    )
    loaded = eps.load_exam_max_scores_from_questions_csv(csv_path)
    assert loaded == {"Q3": 10.0}

    err = eps.load_exam_max_scores_from_questions_csv(_OpenErrorPath())
    assert err == {}


def test_ensure_questions_max_score_exception_paths_and_empty_target() -> None:
    assert eps.ensure_questions_max_score(_OpenErrorPath(exists=False), [], 1.0) == []
    assert eps.ensure_questions_max_score(_OpenErrorPath(), ["Q1"], 1.0) == []

    read_ok_write_fail = _ReadOkWriteFailPath(
        "question_id,question_no,sub_no,order,max_score,stem_ref\nQ1,1,,1,,\n"
    )
    assert eps.ensure_questions_max_score(read_ok_write_fail, ["Q1"], 3.0) == []


def test_apply_answer_key_to_responses_csv_covers_missing_and_pre_scored_paths(tmp_path: Path) -> None:
    responses = tmp_path / "responses.csv"
    answers = tmp_path / "answers.csv"
    questions = tmp_path / "questions.csv"
    out = tmp_path / "out.csv"

    responses.write_text(
        "question_id,raw_answer,score\n"
        "Q1,A,\n"
        "Q2,B,\n"
        "Q3,C,\n"
        "Q4,,\n"
        "Q5,,2\n",
        encoding="utf-8",
    )
    answers.write_text("question_id,correct_answer\nQ1,A\nQ3,C\n", encoding="utf-8")
    questions.write_text("question_id,max_score\nQ1,5\n", encoding="utf-8")

    stats = eps.apply_answer_key_to_responses_csv(responses, answers, questions, out)

    assert stats["total_rows"] == 5
    assert stats["updated_rows"] == 1
    assert stats["scored_rows"] == 2
    assert stats["missing_answer_qids"] == ["Q2"]
    assert stats["missing_max_score_qids"] == ["Q3"]

    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert "is_correct" in rows[0]
    assert rows[0]["score"] == "5"
    assert rows[0]["is_correct"] == "1"


def test_score_objective_answer_handles_normalized_empty_raw_answer() -> None:
    score, correct = eps.score_objective_answer("123", "A", 5.0)
    assert score == 0.0
    assert correct == 0
