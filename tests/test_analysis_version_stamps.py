from __future__ import annotations

from pathlib import Path

from services.api.analysis_report_service import build_analysis_report_deps, get_analysis_report, list_analysis_reports
from services.api.survey_repository import write_survey_report


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'



def test_analysis_report_includes_strategy_prompt_adapter_and_runtime_versions(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        'report_1',
        {
            'report_id': 'report_1',
            'teacher_id': 'teacher_1',
            'analysis_type': 'survey',
            'target_type': 'report',
            'target_id': 'report_1',
            'strategy_id': 'survey.teacher.report',
            'status': 'analysis_ready',
            'confidence': 0.73,
            'summary': '已生成报告。',
            'analysis_artifact': {'executive_summary': '已生成报告。'},
            'bundle_meta': {'parse_confidence': 0.73},
            'created_at': '2026-03-08T10:00:00',
            'updated_at': '2026-03-08T10:05:00',
        },
        core=core,
    )

    deps = build_analysis_report_deps(core)
    list_payload = list_analysis_reports(
        teacher_id='teacher_1',
        domain='survey',
        status='analysis_ready',
        strategy_id='survey.teacher.report',
        target_type='report',
        deps=deps,
    )
    detail = get_analysis_report(report_id='report_1', teacher_id='teacher_1', domain='survey', deps=deps)

    assert list_payload['items'][0]['strategy_version'] == 'v1'
    assert list_payload['items'][0]['prompt_version'] == 'v1'
    assert list_payload['items'][0]['adapter_version'] == 'v1'
    assert list_payload['items'][0]['runtime_version'] == 'v1'
    assert detail['report']['strategy_version'] == 'v1'
    assert detail['report']['prompt_version'] == 'v1'
    assert detail['report']['adapter_version'] == 'v1'
    assert detail['report']['runtime_version'] == 'v1'



def test_handoff_plan_uses_manifest_prompt_runtime_and_adapter_versions() -> None:
    from services.api.strategies.planner import build_handoff_plan, build_lineage_metadata
    from services.api.strategies.selector import build_default_strategy_selector
    from services.api.survey_bundle_models import SurveyEvidenceBundle

    artifact = SurveyEvidenceBundle.model_validate(
        {
            'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider', 'submission_id': 'sub-1'},
            'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
            'question_summaries': [],
            'group_breakdowns': [],
            'free_text_signals': [],
            'attachments': [],
            'parse_confidence': 0.83,
            'missing_fields': [],
            'provenance': {'source': 'structured'},
        }
    ).to_artifact_envelope()
    decision = build_default_strategy_selector().select(
        role='teacher',
        artifact=artifact,
        task_kind='survey.chat_followup',
        target_scope='class',
    )

    plan = build_handoff_plan(
        strategy=decision,
        artifact=artifact,
        artifact_id='job_1',
        handoff_id='handoff_1',
        from_agent='coordinator',
        goal='输出班级问卷洞察和教学建议',
        extra_constraints={'teacher_context': {'teacher_id': 'teacher_1'}},
        fallback_policy='ask_user_to_clarify',
    )
    lineage = build_lineage_metadata(strategy=decision, artifact=artifact)

    assert plan.prompt_version == 'survey.chat_followup.prompt.v1'
    assert plan.runtime_version == 'survey.runtime.v1'
    assert plan.adapter_version == 'survey.bundle.adapter.v1'
    assert plan.handoff.prompt_version == 'survey.chat_followup.prompt.v1'
    assert plan.handoff.runtime_version == 'survey.runtime.v1'
    assert lineage['prompt_version'] == 'survey.chat_followup.prompt.v1'
    assert lineage['runtime_version'] == 'survey.runtime.v1'
    assert lineage['adapter_version'] == 'survey.bundle.adapter.v1'
