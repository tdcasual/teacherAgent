from __future__ import annotations

from types import SimpleNamespace

from services.api.specialist_agents.contracts import SpecialistAgentResult


class _Runtime:
    def __init__(self) -> None:
        self.calls = []

    def run(self, handoff):
        self.calls.append(handoff)
        return SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={
                'executive_summary': '已完成更深入的问卷复盘。',
                'key_signals': [],
                'group_differences': [],
                'teaching_recommendations': ['先做错因归类，再安排针对性讲评。'],
                'confidence_and_gaps': {'confidence': 0.83, 'gaps': []},
            },
        )


def _deps(runtime: _Runtime):
    return SimpleNamespace(
        diag_log=lambda *_args, **_kwargs: None,
        survey_list_reports=lambda teacher_id, status=None: {
            'items': [
                {'report_id': 'report_1', 'class_name': '高二2403班', 'summary': 'old-1'},
                {'report_id': 'report_2', 'class_name': '高二2403班', 'summary': 'old-2'},
            ]
        },
        survey_get_report=lambda report_id, teacher_id: {
            'report': {'report_id': report_id, 'summary': f'report:{report_id}'},
            'bundle_meta': {'job_id': f'job-{report_id}'},
        },
        load_survey_bundle=lambda job_id: {
            'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider', 'submission_id': job_id},
            'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
            'question_summaries': [],
            'group_breakdowns': [],
            'free_text_signals': [],
            'attachments': [],
            'parse_confidence': 0.83,
            'missing_fields': [],
            'provenance': {'source': 'structured'},
        },
        survey_specialist_runtime=runtime,
    )


def test_explicit_analysis_target_routes_survey_followup_without_keyword_hint() -> None:
    from services.api.analysis_followup_router import maybe_route_analysis_followup

    runtime = _Runtime()
    deps = _deps(runtime)
    events = []

    result = maybe_route_analysis_followup(
        deps,
        messages=[{'role': 'user', 'content': '请继续深入复盘'}],
        last_user_text='请继续深入复盘',
        teacher_id='teacher_1',
        analysis_target={
            'source_domain': 'survey',
            'target_type': 'report',
            'target_id': 'report_2',
            'report_id': 'report_2',
        },
        event_sink=lambda event, payload: events.append((event, payload)),
    )

    assert result is not None
    assert '更深入的问卷复盘' in str(result.get('reply') or '')
    assert len(runtime.calls) == 1
    assert runtime.calls[0].handoff_id == 'chat-survey-report_2'
    assert events[0][0] == 'analysis.followup'
    assert events[0][1]['domain'] == 'survey'


def test_message_history_analysis_target_routes_followup_with_multiple_candidates() -> None:
    from services.api.analysis_followup_router import maybe_route_analysis_followup

    runtime = _Runtime()
    deps = _deps(runtime)

    result = maybe_route_analysis_followup(
        deps,
        messages=[
            {
                'role': 'assistant',
                'content': '[analysis_target] domain=survey target_type=report target_id=report_2 strategy_id=survey.teacher.report',
            },
            {'role': 'user', 'content': '请基于问卷做更深入的教学建议复盘'},
        ],
        last_user_text='请基于问卷做更深入的教学建议复盘',
        teacher_id='teacher_1',
        analysis_target=None,
        event_sink=None,
    )

    assert result is not None
    assert len(runtime.calls) == 1
    assert runtime.calls[0].handoff_id == 'chat-survey-report_2'


def test_ambiguous_survey_followup_returns_clarification_instead_of_guessing() -> None:
    from services.api.analysis_followup_router import maybe_route_analysis_followup

    runtime = _Runtime()
    deps = _deps(runtime)

    result = maybe_route_analysis_followup(
        deps,
        messages=[{'role': 'user', 'content': '请基于问卷做更深入的教学建议复盘'}],
        last_user_text='请基于问卷做更深入的教学建议复盘',
        teacher_id='teacher_1',
        analysis_target=None,
        event_sink=None,
    )

    assert '请先告诉我 report_id' in str((result or {}).get('reply') or '')
    assert runtime.calls == []
