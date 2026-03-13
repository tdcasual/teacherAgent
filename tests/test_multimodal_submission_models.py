from __future__ import annotations

from services.api.media_segment_models import (
    MediaExtractionFailure,
    MediaFrameEvidence,
    MediaTextSegment,
)
from services.api.multimodal_submission_models import (
    MultimodalMediaFile,
    MultimodalScope,
    MultimodalSourceMeta,
    MultimodalSubmissionBundle,
)


def test_multimodal_submission_bundle_exports_uniform_artifact_envelope() -> None:
    bundle = MultimodalSubmissionBundle(
        source_meta=MultimodalSourceMeta(
            source_type='video_homework_upload',
            title='化学实验演示',
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
                storage_path='uploads/multimodal/video_1.mp4',
                mime_type='video/mp4',
                bytes=1024,
                duration_sec=42.5,
                original_name='demo.mp4',
            )
        ],
        transcript_segments=[
            MediaTextSegment(
                segment_id='seg_1',
                kind='asr',
                start_sec=0.0,
                end_sec=4.2,
                text='今天我来演示实验步骤。',
                confidence=0.91,
            )
        ],
        subtitle_segments=[
            MediaTextSegment(
                segment_id='sub_1',
                kind='subtitle',
                start_sec=0.0,
                end_sec=4.2,
                text='今天我来演示实验步骤。',
            )
        ],
        keyframe_evidence=[
            MediaFrameEvidence(
                frame_id='frame_1',
                timestamp_sec=1.5,
                image_path='derived/frame_1.jpg',
                ocr_text='酒精灯',
                confidence=0.82,
            )
        ],
        extraction_status='partial',
        extraction_failures=[
            MediaExtractionFailure(stage='ocr', code='sdk_unavailable', message='OCR unavailable', retryable=True)
        ],
        parse_confidence=0.74,
        missing_fields=['ocr_text_more_frames'],
        provenance={'source': 'upload', 'extractor_version': 'v1'},
    )

    artifact = bundle.to_artifact_envelope()

    assert artifact.artifact_type == 'multimodal_submission_bundle'
    assert artifact.subject_scope['teacher_id'] == 'teacher_1'
    assert artifact.subject_scope['student_id'] == 'student_1'
    assert artifact.payload['transcript_segments'][0]['text'] == '今天我来演示实验步骤。'
    assert artifact.evidence_refs[0].ref_id == 'video_1'
    assert artifact.evidence_refs[1].ref_id == 'frame_1'
    assert artifact.missing_fields == ['ocr_text_more_frames']
