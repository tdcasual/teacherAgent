from __future__ import annotations

from services.api.media_extract_service import MediaExtractDeps, extract_multimodal_submission
from services.api.media_segment_models import MediaFrameEvidence, MediaTextSegment
from services.api.multimodal_submission_models import (
    MultimodalMediaFile,
    MultimodalScope,
    MultimodalSourceMeta,
    MultimodalSubmissionBundle,
)



def _submission() -> MultimodalSubmissionBundle:
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
        subtitle_segments=[
            MediaTextSegment(
                segment_id='subtitle_1',
                kind='subtitle',
                start_sec=0.0,
                end_sec=3.5,
                text='首先介绍实验器材。',
            )
        ],
        parse_confidence=0.62,
        provenance={'source': 'upload'},
    )



def test_extract_multimodal_submission_builds_transcript_and_keyframe_evidence() -> None:
    deps = MediaExtractDeps(
        transcribe=lambda submission: [
            MediaTextSegment(
                segment_id='asr_1',
                kind='asr',
                start_sec=0.0,
                end_sec=3.5,
                text='首先介绍实验器材。',
                confidence=0.93,
            )
        ],
        extract_keyframes=lambda submission: [
            MediaFrameEvidence(frame_id='frame_1', timestamp_sec=1.2, image_path='derived/frame_1.jpg', confidence=0.8)
        ],
        ocr_frame=lambda frame, submission: '酒精灯与铁架台',
        now_iso=lambda: '2026-03-07T10:05:00',
        timeout_sec=lambda: 90,
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = extract_multimodal_submission(_submission(), deps=deps)

    assert result.extraction_status == 'completed'
    assert result.transcript_segments[0].kind == 'asr'
    assert result.keyframe_evidence[0].ocr_text == '酒精灯与铁架台'
    assert result.provenance['extracted_at'] == '2026-03-07T10:05:00'
    assert result.provenance['extract_timeout_sec'] == 90
    assert result.parse_confidence > 0.8



def test_extract_multimodal_submission_keeps_subtitle_fallback_when_asr_fails() -> None:
    deps = MediaExtractDeps(
        transcribe=lambda submission: (_ for _ in ()).throw(RuntimeError('ASR unavailable')),
        extract_keyframes=lambda submission: [
            MediaFrameEvidence(frame_id='frame_1', timestamp_sec=1.2, image_path='derived/frame_1.jpg', confidence=0.72)
        ],
        ocr_frame=lambda frame, submission: None,
        now_iso=lambda: '2026-03-07T10:06:00',
        timeout_sec=lambda: 90,
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = extract_multimodal_submission(_submission(), deps=deps)

    assert result.extraction_status == 'partial'
    assert result.transcript_segments == []
    assert result.subtitle_segments[0].text == '首先介绍实验器材。'
    assert result.extraction_failures[0].stage == 'transcribe'
    assert 'transcript_segments' in result.missing_fields
    assert result.keyframe_evidence[0].frame_id == 'frame_1'
