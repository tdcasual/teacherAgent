from pathlib import Path

from services.api.agent_service import AgentRuntimeDeps


def test_build_subject_total_mode_reply_includes_total_stats():
    from services.api.agent_runtime_guards import build_subject_total_mode_reply

    reply = build_subject_total_mode_reply(
        'EX20260209_9b92e1',
        {
            'totals_summary': {
                'avg_total': 371.714,
                'median_total': 366.5,
                'max_total_observed': 511.5,
                'min_total_observed': 289.5,
            }
        },
        requested_subject='physics',
        inferred_subject='physics',
    )

    assert '单科成绩说明' in reply
    assert '不能把总分当作物理单科成绩' in reply
    assert '371.7' in reply
    assert '511.5' in reply


def test_maybe_guard_teacher_subject_total_returns_reply_for_total_mode():
    from services.api.agent_runtime_guards import maybe_guard_teacher_subject_total

    logs = []
    deps = AgentRuntimeDeps(
        app_root=Path('.'),
        build_system_prompt=lambda role: f'system-{role or "unknown"}',
        diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        load_skill_runtime=lambda role, skill_id: (None, None),
        allowed_tools=lambda role: set(),
        max_tool_rounds=3,
        max_tool_calls=5,
        extract_min_chars_requirement=lambda text: None,
        extract_exam_id=lambda text: 'EX20260209_9b92e1' if 'EX20260209_9b92e1' in (text or '') else None,
        is_exam_analysis_request=lambda text: False,
        build_exam_longform_context=lambda exam_id: {
            'exam_overview': {
                'ok': True,
                'exam_id': exam_id,
                'score_mode': 'total',
                'meta': {'subject': 'physics'},
                'totals_summary': {'avg_total': 371.714},
            }
        },
        generate_longform_reply=lambda *args, **kwargs: '',
        call_llm=lambda *args, **kwargs: {'choices': [{'message': {'content': ''}}]},
        tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {'ok': True},
        teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
    )

    result = maybe_guard_teacher_subject_total(
        deps,
        messages=[{'role': 'user', 'content': '分析EX20260209_9b92e1的物理成绩'}],
        last_user_text='分析EX20260209_9b92e1的物理成绩',
    )

    assert '不能把总分当作物理单科成绩' in str((result or {}).get('reply') or '')
    assert any(event == 'teacher.subject_total_guard' for event, _ in logs)
