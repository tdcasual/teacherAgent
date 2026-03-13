from __future__ import annotations

from services.api.survey_report_render_service import render_survey_report


def test_render_survey_report_outputs_markdown_and_json_shapes() -> None:
    rendered = render_survey_report(
        report={
            "report_id": "report_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
            "confidence": 0.81,
        },
        analysis_artifact={
            "executive_summary": "班级整体在实验设计题上失分较多。",
            "key_signals": [
                {"title": "实验设计理解偏弱", "detail": "Q1 中选择偏难的比例较高。", "evidence_refs": ["question:Q1"]}
            ],
            "group_differences": [{"group_name": "实验班", "summary": "偏难反馈占比更高。"}],
            "teaching_recommendations": ["下节课增加实验设计拆解练习。"],
            "confidence_and_gaps": {"confidence": 0.81, "gaps": ["student_level_raw_data"]},
        },
        bundle_meta={"parse_confidence": 0.78, "missing_fields": ["student_level_raw_data"]},
    )

    assert rendered["summary"] == "班级整体在实验设计题上失分较多。"
    assert rendered["markdown"].startswith("# 问卷分析报告")
    assert "实验设计理解偏弱" in rendered["markdown"]
    assert "教学建议" in rendered["markdown"]
    assert rendered["json"]["analysis_artifact"]["executive_summary"] == "班级整体在实验设计题上失分较多。"
    assert rendered["json"]["bundle_meta"]["parse_confidence"] == 0.78
