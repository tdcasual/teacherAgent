from __future__ import annotations

from pathlib import Path

from services.api.agent_service import AgentRuntimeDeps, run_agent_runtime
from services.api.specialist_agents.contracts import SpecialistAgentResult



def test_run_agent_runtime_uses_internal_survey_handoff_for_deeper_teacher_followup() -> None:
    events = []
    llm_calls = []

    class _Runtime:
        def run(self, handoff):
            return SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status="completed",
                output={
                    "executive_summary": "已基于最新问卷给出更深入的班级复盘。",
                    "key_signals": [],
                    "group_differences": [],
                    "teaching_recommendations": ["先做实验设计拆解，再做当堂检测。"],
                    "confidence_and_gaps": {"confidence": 0.81, "gaps": []},
                },
            )

    deps = AgentRuntimeDeps(
        app_root=Path("."),
        build_system_prompt=lambda role: f"system-{role or 'unknown'}",
        diag_log=lambda *_args, **_kwargs: None,
        load_skill_runtime=lambda role, skill_id: (None, None),
        allowed_tools=lambda role: set(),
        max_tool_rounds=3,
        max_tool_calls=5,
        extract_min_chars_requirement=lambda text: None,
        extract_exam_id=lambda text: None,
        is_exam_analysis_request=lambda text: False,
        build_exam_longform_context=lambda exam_id: {},
        generate_longform_reply=lambda *args, **kwargs: "",
        call_llm=lambda *_args, **_kwargs: llm_calls.append(1) or {"choices": [{"message": {"content": "should-not-run"}}]},
        tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
        teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
        survey_list_reports=lambda teacher_id, status=None: {"items": [{"report_id": "report_1", "class_name": "高二2403班", "summary": "old"}]},
        survey_get_report=lambda report_id, teacher_id: {"report": {"report_id": report_id, "summary": "old"}, "bundle_meta": {"job_id": "job_1"}},
        load_survey_bundle=lambda job_id: {
            "survey_meta": {"title": "课堂反馈问卷", "provider": "provider", "submission_id": "sub-1"},
            "audience_scope": {"teacher_id": "teacher_1", "class_name": "高二2403班", "sample_size": 35},
            "question_summaries": [],
            "group_breakdowns": [],
            "free_text_signals": [],
            "attachments": [],
            "parse_confidence": 0.81,
            "missing_fields": [],
            "provenance": {"source": "structured"},
        },
        survey_specialist_runtime=_Runtime(),
    )

    result = run_agent_runtime(
        [{"role": "user", "content": "请基于最新问卷做更深入的教学建议复盘"}],
        "teacher",
        deps=deps,
        teacher_id="teacher_1",
        event_sink=lambda event, payload: events.append((event, payload)),
    )

    assert "更深入的班级复盘" in str(result.get("reply") or "")
    assert "教学建议" in str(result.get("reply") or "")
    assert llm_calls == []
    assert events[0][0] == "analysis.followup"
    assert events[0][1]["domain"] == "survey"



def test_run_agent_runtime_does_not_guess_latest_report_when_multiple_candidates_exist() -> None:
    runtime_calls = []

    class _Runtime:
        def run(self, handoff):
            runtime_calls.append(handoff.handoff_id)
            return SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={'executive_summary': 'unexpected'},
            )

    deps = AgentRuntimeDeps(
        app_root=Path('.'),
        build_system_prompt=lambda role: f'system-{role or "unknown"}',
        diag_log=lambda *_args, **_kwargs: None,
        load_skill_runtime=lambda role, skill_id: (None, None),
        allowed_tools=lambda role: set(),
        max_tool_rounds=3,
        max_tool_calls=5,
        extract_min_chars_requirement=lambda text: None,
        extract_exam_id=lambda text: None,
        is_exam_analysis_request=lambda text: False,
        build_exam_longform_context=lambda exam_id: {},
        generate_longform_reply=lambda *args, **kwargs: '',
        call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': 'fallback'}}]},
        tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {'ok': True},
        teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
        survey_list_reports=lambda teacher_id, status=None: {
            'items': [
                {'report_id': 'report_1', 'class_name': '高二2403班', 'summary': 'old-1'},
                {'report_id': 'report_2', 'class_name': '高二2403班', 'summary': 'old-2'},
            ]
        },
        survey_get_report=lambda report_id, teacher_id: {'report': {'report_id': report_id, 'summary': 'old'}, 'bundle_meta': {'job_id': 'job_1'}},
        load_survey_bundle=lambda job_id: {'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider'}},
        survey_specialist_runtime=_Runtime(),
    )

    result = run_agent_runtime(
        [{'role': 'user', 'content': '请基于问卷做更深入的教学建议复盘'}],
        'teacher',
        deps=deps,
        teacher_id='teacher_1',
    )

    assert '请先告诉我 report_id' in str(result.get('reply') or '')
    assert runtime_calls == []
