from __future__ import annotations

from services.api.assignment.visibility import public_student_assignment_detail


def test_public_student_assignment_detail_allowlists_question_fields() -> None:
    payload = {
        "assignment_id": "HW_1",
        "meta": {
            "teacher_id": "t_zhang",
            "visibility_status": "published",
            "expected_students": ["S001"],
            "student_ids": ["S001"],
            "answer_files": ["answers/q1.md"],
            "assignment_kind": "problem_set",
        },
        "questions": [
            {
                "question_id": "Q1",
                "kp_id": "力学",
                "difficulty": "basic",
                "type": "open",
                "stem_ref": "data/assignments/HW_1/stems/q1.md",
                "stem_text": "求加速度",
                "answer_ref": "data/assignments/HW_1/answers/q1.md",
                "secret_answer": "42",
                "source": "upload",
                "tags": "力学",
                "max_score": "10",
            }
        ],
    }

    out = public_student_assignment_detail(payload)

    assert out["meta"]["assignment_kind"] == "problem_set"
    assert "expected_students" not in out["meta"]
    assert "student_ids" not in out["meta"]
    assert "answer_files" not in out["meta"]
    question = out["questions"][0]
    assert question == {
        "question_id": "Q1",
        "kp_id": "力学",
        "difficulty": "basic",
        "type": "open",
        "stem_text": "求加速度",
        "source": "upload",
        "tags": "力学",
        "max_score": "10",
    }
    assert public_student_assignment_detail(payload) is not payload
    assert payload["questions"][0]["answer_ref"] == "data/assignments/HW_1/answers/q1.md"
