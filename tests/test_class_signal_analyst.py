from __future__ import annotations

import json

from services.api.class_signal_bundle_models import (
    ClassSignalBundle,
    ClassSignalQuestionLike,
    ClassSignalRiskLike,
    ClassSignalScope,
    ClassSignalSourceMeta,
    ClassSignalThemeLike,
)
from services.api.specialist_agents.class_signal_analyst import (
    ClassSignalAnalystDeps,
    run_class_signal_analyst,
)
from services.api.specialist_agents.contracts import ArtifactRef, HandoffContract


def _bundle() -> ClassSignalBundle:
    return ClassSignalBundle(
        source_meta=ClassSignalSourceMeta(
            title='课堂反馈周报',
            provider='self_hosted_form',
            source_type='self_hosted_form_json',
            report_id='class_report_1',
        ),
        class_scope=ClassSignalScope(
            teacher_id='teacher_1',
            class_name='高二2403班',
            sample_size=36,
            grade_level='高二',
        ),
        question_like_signals=[
            ClassSignalQuestionLike(
                signal_id='Q1',
                title='课堂难点',
                summary='实验设计题仍是主要难点。',
                stats={'实验设计': 15, '计算': 8},
                evidence_refs=['question:Q1'],
            )
        ],
        theme_like_signals=[
            ClassSignalThemeLike(
                theme='实验设计',
                summary='变量控制仍是高频问题。',
                evidence_count=6,
                excerpts=['变量控制不清'],
                evidence_refs=['theme:实验设计'],
            )
        ],
        risk_like_signals=[
            ClassSignalRiskLike(
                risk='受力分析概念混淆',
                severity='medium',
                summary='平衡态与受力图判断混淆。',
                evidence_refs=['risk:受力分析概念混淆'],
            )
        ],
        narrative_blocks=['班级整体在实验设计题上失分较多。'],
        attachments=[{'name': 'report.pdf', 'kind': 'pdf', 'uri': 'file:///tmp/report.pdf'}],
        parse_confidence=0.76,
        missing_fields=['attachment_original_pdf'],
        provenance={'source': 'self_hosted_form'},
    )



def test_class_signal_analyst_sanitizes_llm_output_and_keeps_evidence_refs() -> None:
    handoff = HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='class_signal_analyst',
        task_kind='class_report.analysis',
        artifact_refs=[ArtifactRef(artifact_id='bundle_1', artifact_type='class_signal_bundle')],
        goal='输出班级信号归纳与教学建议',
        constraints={},
        budget={'max_tokens': 1600},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )
    content = json.dumps(
        {
            'executive_summary': '班级整体在实验设计与受力分析两类问题上暴露出明显缺口。',
            'key_signals': [
                {
                    'title': '实验设计理解偏弱',
                    'detail': '变量控制与实验目的判断错误较集中。',
                    'evidence_refs': ['question:Q1', 'theme:实验设计'],
                }
            ],
            'teaching_recommendations': ['先复盘变量控制，再做分层即时检测。'],
            'confidence_and_gaps': {'confidence': 0.84, 'gaps': ['attachment_original_pdf']},
            'student_profiles': ['张三'],
            'action_plan': ['自动布置练习'],
        },
        ensure_ascii=False,
    )
    deps = ClassSignalAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': content}}]},
        prompt_loader=lambda: 'class signal analyst prompt',
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_class_signal_analyst(
        handoff=handoff,
        class_signal_bundle=_bundle(),
        teacher_context={'subject': 'physics'},
        task_goal='输出班级信号归纳与教学建议',
        deps=deps,
    )

    assert result.agent_id == 'class_signal_analyst'
    assert result.output['executive_summary'].startswith('班级整体')
    assert result.output['key_signals'][0]['evidence_refs'] == ['question:Q1', 'theme:实验设计']
    assert result.output['teaching_recommendations'] == ['先复盘变量控制，再做分层即时检测。']
    assert result.output['confidence_and_gaps']['confidence'] == 0.84
    assert 'student_profiles' not in result.output
    assert 'action_plan' not in result.output



def test_class_signal_analyst_falls_back_to_bundle_heuristics_on_invalid_llm_output() -> None:
    handoff = HandoffContract(
        handoff_id='handoff_2',
        from_agent='coordinator',
        to_agent='class_signal_analyst',
        task_kind='class_report.analysis',
        artifact_refs=[ArtifactRef(artifact_id='bundle_1', artifact_type='class_signal_bundle')],
        goal='输出班级信号归纳与教学建议',
        constraints={},
        budget={'max_tokens': 1600},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )
    deps = ClassSignalAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': 'not-json'}}]},
        prompt_loader=lambda: 'class signal analyst prompt',
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_class_signal_analyst(
        handoff=handoff,
        class_signal_bundle=_bundle(),
        teacher_context={'subject': 'physics'},
        task_goal='输出班级信号归纳与教学建议',
        deps=deps,
    )

    assert result.output['executive_summary']
    assert result.output['key_signals']
    assert result.output['teaching_recommendations']
    assert result.output['confidence_and_gaps']['confidence'] == 0.76
