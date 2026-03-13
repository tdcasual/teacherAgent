from __future__ import annotations

import json

from services.api.media_segment_models import MediaFrameEvidence, MediaTextSegment
from services.api.multimodal_submission_models import (
    MultimodalMediaFile,
    MultimodalScope,
    MultimodalSourceMeta,
    MultimodalSubmissionBundle,
)
from services.api.specialist_agents.contracts import ArtifactRef, HandoffContract
from services.api.specialist_agents.video_homework_analyst import (
    VideoHomeworkAnalystDeps,
    run_video_homework_analyst,
)


def _bundle() -> MultimodalSubmissionBundle:
    return MultimodalSubmissionBundle(
        source_meta=MultimodalSourceMeta(
            source_type='video_homework_upload',
            title='物理实验讲解',
            submission_id='submission_1',
            uploaded_at='2026-03-07T10:00:00',
        ),
        scope=MultimodalScope(
            teacher_id='teacher_1',
            student_id='student_1',
            class_name='高二2403班',
            assignment_id='assignment_1',
            submission_kind='video_homework',
        ),
        media_files=[
            MultimodalMediaFile(
                file_id='video_1',
                kind='video',
                storage_path='/tmp/video_1.mp4',
                mime_type='video/mp4',
                bytes=2048,
                duration_sec=58.0,
            )
        ],
        transcript_segments=[
            MediaTextSegment(
                segment_id='asr_1',
                kind='asr',
                start_sec=0.0,
                end_sec=4.0,
                text='首先介绍实验器材与步骤。',
                confidence=0.92,
                evidence_refs=['segment:asr_1'],
            )
        ],
        keyframe_evidence=[
            MediaFrameEvidence(
                frame_id='frame_1',
                timestamp_sec=1.2,
                image_path='derived/frame_1.jpg',
                ocr_text='酒精灯与铁架台',
                confidence=0.81,
            )
        ],
        extraction_status='completed',
        parse_confidence=0.84,
        missing_fields=['teacher_rubric'],
        provenance={'source': 'upload'},
    )



def test_video_homework_analyst_sanitizes_llm_output_and_keeps_evidence_clips() -> None:
    handoff = HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='video_homework_analyst',
        task_kind='video_homework.analysis',
        artifact_refs=[ArtifactRef(artifact_id='submission_1', artifact_type='multimodal_submission_bundle')],
        goal='输出老师可读的视频作业反馈',
        constraints={},
        budget={'max_tokens': 1600},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )
    content = json.dumps(
        {
            'executive_summary': '学生能完整展示实验步骤，但口头表达仍偏简略。',
            'completion_overview': {
                'status': 'completed',
                'summary': '已完成主要实验流程展示。',
                'duration_sec': 58.0,
            },
            'expression_signals': [
                {
                    'title': '步骤表达较完整',
                    'detail': '能够按顺序介绍器材与步骤。',
                    'evidence_refs': ['segment:asr_1', 'frame:frame_1'],
                }
            ],
            'evidence_clips': [
                {
                    'label': '器材介绍',
                    'start_sec': 0.0,
                    'end_sec': 4.0,
                    'evidence_ref': 'segment:asr_1',
                    'excerpt': '首先介绍实验器材与步骤。',
                }
            ],
            'teaching_recommendations': ['增加术语表达模板练习。'],
            'confidence_and_gaps': {'confidence': 0.88, 'gaps': ['teacher_rubric']},
            'auto_score': 95,
        },
        ensure_ascii=False,
    )
    deps = VideoHomeworkAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': content}}]},
        prompt_loader=lambda: 'video homework analyst prompt',
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_video_homework_analyst(
        handoff=handoff,
        multimodal_submission_bundle=_bundle(),
        teacher_context={'subject': 'physics'},
        task_goal='输出老师可读的视频作业反馈',
        deps=deps,
    )

    assert result.agent_id == 'video_homework_analyst'
    assert result.output['executive_summary'].startswith('学生能完整展示')
    assert result.output['expression_signals'][0]['evidence_refs'] == ['segment:asr_1', 'frame:frame_1']
    assert result.output['evidence_clips'][0]['evidence_ref'] == 'segment:asr_1'
    assert result.output['teaching_recommendations'] == ['增加术语表达模板练习。']
    assert result.output['confidence_and_gaps']['confidence'] == 0.88
    assert 'auto_score' not in result.output



def test_video_homework_analyst_falls_back_to_bundle_heuristics_on_invalid_llm_output() -> None:
    handoff = HandoffContract(
        handoff_id='handoff_2',
        from_agent='coordinator',
        to_agent='video_homework_analyst',
        task_kind='video_homework.analysis',
        artifact_refs=[ArtifactRef(artifact_id='submission_1', artifact_type='multimodal_submission_bundle')],
        goal='输出老师可读的视频作业反馈',
        constraints={},
        budget={'max_tokens': 1600},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )
    deps = VideoHomeworkAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': 'not-json'}}]},
        prompt_loader=lambda: 'video homework analyst prompt',
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_video_homework_analyst(
        handoff=handoff,
        multimodal_submission_bundle=_bundle(),
        teacher_context={'subject': 'physics'},
        task_goal='输出老师可读的视频作业反馈',
        deps=deps,
    )

    assert result.output['executive_summary']
    assert result.output['completion_overview']['status'] == 'completed'
    assert result.output['expression_signals']
    assert result.output['evidence_clips']
    assert result.output['confidence_and_gaps']['confidence'] == 0.84
