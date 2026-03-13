from __future__ import annotations

from services.api.survey_normalize_structured_service import normalize_structured_survey_payload


def test_normalize_structured_survey_payload_maps_core_fields() -> None:
    payload = {
        "submission_id": "sub-1",
        "title": "课堂反馈问卷",
        "teacher_id": "teacher_1",
        "class_name": "高二2403班",
        "sample_size": 35,
        "questions": [
            {
                "id": "Q1",
                "prompt": "本节课难度如何？",
                "response_type": "single_choice",
                "stats": {"偏难": 12, "适中": 20, "偏易": 3},
            }
        ],
        "groups": [
            {"group_name": "实验班", "sample_size": 20, "stats": {"Q1:偏难": 10}}
        ],
        "text_signals": [
            {"theme": "公式推导", "evidence_count": 5, "excerpts": ["推导太快了"]}
        ],
    }

    bundle = normalize_structured_survey_payload(provider="provider", payload=payload)

    assert bundle.survey_meta.title == "课堂反馈问卷"
    assert bundle.survey_meta.provider == "provider"
    assert bundle.audience_scope.teacher_id == "teacher_1"
    assert bundle.audience_scope.class_name == "高二2403班"
    assert bundle.audience_scope.sample_size == 35
    assert bundle.question_summaries[0].question_id == "Q1"
    assert bundle.group_breakdowns[0].group_name == "实验班"
    assert bundle.free_text_signals[0].theme == "公式推导"
    assert bundle.parse_confidence == 1.0
    assert bundle.missing_fields == []



def test_normalize_structured_survey_payload_tracks_missing_fields() -> None:
    payload = {
        "submission_id": "sub-2",
        "questions": [],
    }

    bundle = normalize_structured_survey_payload(provider="provider", payload=payload)

    assert "title" in bundle.missing_fields
    assert "teacher_id" in bundle.missing_fields
    assert "class_name" in bundle.missing_fields
    assert bundle.parse_confidence < 1.0
