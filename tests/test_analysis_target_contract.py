from __future__ import annotations

from services.api.api_models import ChatRequest


_BASE_MESSAGES = [{"role": "user", "content": "请继续分析这个对象"}]


def test_chat_request_accepts_explicit_report_analysis_target() -> None:
    req = ChatRequest.model_validate(
        {
            "messages": _BASE_MESSAGES,
            "analysis_target": {
                "target_type": "report",
                "target_id": "report_7",
                "source_domain": "survey",
                "artifact_type": "survey_evidence_bundle",
                "strategy_id": "survey.teacher.report",
            },
        }
    )

    assert req.analysis_target is not None
    assert req.analysis_target.target_type == "report"
    assert req.analysis_target.target_id == "report_7"
    assert req.analysis_target.report_id == "report_7"
    assert req.analysis_target.source_domain == "survey"


def test_chat_request_accepts_submission_analysis_target() -> None:
    req = ChatRequest.model_validate(
        {
            "messages": _BASE_MESSAGES,
            "analysis_target": {
                "target_type": "submission",
                "target_id": "submission_42",
                "source_domain": "video_homework",
                "artifact_type": "video_submission_bundle",
                "strategy_id": "video_homework.teacher.submission_review",
            },
        }
    )

    assert req.analysis_target is not None
    assert req.analysis_target.target_type == "submission"
    assert req.analysis_target.target_id == "submission_42"
    assert req.analysis_target.report_id is None
    assert req.analysis_target.source_domain == "video_homework"


def test_chat_request_accepts_class_analysis_target() -> None:
    req = ChatRequest.model_validate(
        {
            "messages": _BASE_MESSAGES,
            "analysis_target": {
                "target_type": "class",
                "target_id": "class_2403",
                "source_domain": "class_report",
                "artifact_type": "class_report_bundle",
                "strategy_id": "class_report.teacher.class_summary",
            },
        }
    )

    assert req.analysis_target is not None
    assert req.analysis_target.target_type == "class"
    assert req.analysis_target.target_id == "class_2403"
    assert req.analysis_target.source_domain == "class_report"
