from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes.multimodal_routes import build_router


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'
        self.diag_log = lambda *_args, **_kwargs: None
        self.media_transcribe = lambda submission: [
            {
                'segment_id': 'asr_1',
                'kind': 'asr',
                'start_sec': 0.0,
                'end_sec': 3.5,
                'text': '首先介绍实验器材。',
                'confidence': 0.93,
            }
        ]
        self.media_extract_keyframes = lambda submission: [
            {
                'frame_id': 'frame_1',
                'timestamp_sec': 1.2,
                'image_path': 'derived/frame_1.jpg',
                'confidence': 0.8,
            }
        ]
        self.media_ocr_frame = lambda frame, submission: '酒精灯与铁架台'



def _payload(bytes_value: int = 2048, duration_sec: float = 58.0) -> dict:
    return {
        'source_meta': {
            'source_type': 'video_homework_upload',
            'title': '物理实验讲解',
            'submission_id': 'submission_1',
            'uploaded_at': '2026-03-07T10:00:00',
        },
        'scope': {
            'teacher_id': 'teacher_1',
            'student_id': 'student_1',
            'class_name': '高二2403班',
            'assignment_id': 'assignment_1',
            'submission_kind': 'video_homework',
        },
        'media_files': [
            {
                'file_id': 'video_1',
                'kind': 'video',
                'storage_path': '/tmp/video_1.mp4',
                'mime_type': 'video/mp4',
                'bytes': bytes_value,
                'duration_sec': duration_sec,
                'original_name': 'demo.mp4',
            }
        ],
        'subtitle_segments': [
            {
                'segment_id': 'subtitle_1',
                'kind': 'subtitle',
                'start_sec': 0.0,
                'end_sec': 3.5,
                'text': '首先介绍实验器材。',
            }
        ],
        'parse_confidence': 0.62,
        'provenance': {'source': 'upload'},
    }



def test_multimodal_routes_create_fetch_and_extract_submission(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        create_res = client.post('/teacher/multimodal/submissions', json=_payload())
        fetch_res = client.get('/teacher/multimodal/submissions/submission_1')
        extract_res = client.post('/teacher/multimodal/submissions/submission_1/extract')

    assert create_res.status_code == 200
    assert create_res.json()['submission_id'] == 'submission_1'
    assert fetch_res.status_code == 200
    assert fetch_res.json()['submission']['source_meta']['submission_id'] == 'submission_1'
    assert extract_res.status_code == 200
    assert extract_res.json()['submission']['extraction_status'] == 'completed'
    assert extract_res.json()['submission']['keyframe_evidence'][0]['ocr_text'] == '酒精灯与铁架台'



def test_multimodal_routes_reject_submission_exceeding_limits(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        res = client.post('/teacher/multimodal/submissions', json=_payload(bytes_value=300 * 1024 * 1024, duration_sec=1200.0))

    assert res.status_code == 413
    assert res.json()['detail'] == 'multimodal_submission_too_large'
