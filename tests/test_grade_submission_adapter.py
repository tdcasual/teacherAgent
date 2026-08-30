from __future__ import annotations

from pathlib import Path

from scripts import grade_submission as gs


class _Adapter:
    def score_item(self, *, question, student_text):
        del question
        return {
            "score": 0.8,
            "confidence": 0.7,
            "status": "matched",
            "reason": "pack_adapter",
            "student_answer": student_text[:20],
        }


def test_apply_grade_adapter_returns_normalized_item() -> None:
    item = gs.apply_grade_adapter(
        _Adapter(),
        question={"question_id": "Q1"},
        student_text="answer 42",
    )
    assert item is not None
    assert item["status"] == "matched"
    assert item["reason"] == "pack_adapter"
    assert item["score"] == 0.8
    assert item["confidence"] == 0.7
    assert item["matched"] is True


def test_apply_grade_adapter_none_falls_back() -> None:
    assert gs.apply_grade_adapter(None, question={}, student_text="x") is None


def test_evaluate_question_prefers_adapter_over_objective() -> None:
    result = gs.evaluate_question(
        question={"question_id": "Q1", "answer_text": "999"},
        block_text="not the expected answer",
        adapter=_Adapter(),
        llm_grade=False,
        llm_confidence_threshold=0.6,
    )
    assert result["reason"] == "pack_adapter"
    assert result["status"] == "matched"
    assert result["score"] == 0.8


def test_evaluate_question_without_adapter_uses_objective_match() -> None:
    result = gs.evaluate_question(
        question={"question_id": "Q1", "answer_text": "42"},
        block_text="答案：42",
        adapter=None,
        llm_grade=False,
        llm_confidence_threshold=0.6,
    )
    assert result["status"] == "matched"
    assert result["reason"] == "numeric_match"
    assert result["score"] == 1.0


def test_resolve_assignment_pack_id_from_meta(tmp_path: Path) -> None:
    folder = tmp_path / "HW1"
    folder.mkdir()
    (folder / "meta.json").write_text(
        '{"subject_id": "math", "pack_id": "math"}',
        encoding="utf-8",
    )
    assert gs.resolve_assignment_pack_id("HW1", tmp_path) == "math"


def test_resolve_assignment_pack_id_missing_meta_is_empty(tmp_path: Path) -> None:
    (tmp_path / "HW1").mkdir()
    assert gs.resolve_assignment_pack_id("HW1", tmp_path) == ""


def test_grade_submission_source_never_uses_exam_column_mapping() -> None:
    source = Path(gs.__file__).read_text(encoding="utf-8")
    assert "SUBJECT_PHYSICS" not in source
    assert "score_mode" not in source
    assert "score_schema" not in source
    assert "exam_score" not in source
