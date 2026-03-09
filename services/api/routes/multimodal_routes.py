from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from .. import settings
from ..media_extract_service import build_media_extract_deps, extract_multimodal_submission
from ..multimodal_orchestrator_service import build_multimodal_orchestrator_deps, process_multimodal_submission
from ..multimodal_repository import (
    ensure_multimodal_media_dir,
    load_multimodal_submission,
    load_multimodal_submission_view,
    write_multimodal_extraction,
    write_multimodal_submission,
)
from ..multimodal_submission_models import MultimodalSubmissionBundle
from ..paths import safe_fs_id
from .teacher_route_helpers import scoped_teacher_id



def _enforce_submission_teacher_scope(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    scope = dict(data.get('scope') or {})
    scope['teacher_id'] = scoped_teacher_id(scope.get('teacher_id')) or ''
    data['scope'] = scope
    return data


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    extract_deps = build_media_extract_deps(core)
    orchestrator_deps = build_multimodal_orchestrator_deps(core)

    @router.post('/teacher/multimodal/submissions')
    async def create_multimodal_submission(payload: Dict[str, Any] = Body(default={})) -> Any:
        _ensure_enabled()
        try:
            bundle = MultimodalSubmissionBundle.model_validate(_enforce_submission_teacher_scope(dict(payload or {})))
            submission_id = str(bundle.source_meta.submission_id or '').strip() or safe_fs_id(
                f"{bundle.scope.teacher_id}_{bundle.scope.student_id}_{bundle.source_meta.title}",
                prefix='submission',
            )
            bundle = MultimodalSubmissionBundle.model_validate(
                {
                    **bundle.model_dump(),
                    'source_meta': {
                        **bundle.source_meta.model_dump(),
                        'submission_id': submission_id,
                    },
                    'extraction_status': str(bundle.extraction_status or 'pending').strip() or 'pending',
                }
            )
            _enforce_limits(bundle)
            ensure_multimodal_media_dir(submission_id, core=core)
            write_multimodal_submission(submission_id, bundle.model_dump(), core=core)
            return {
                'ok': True,
                'submission_id': submission_id,
                'status': bundle.extraction_status,
                'limits': {
                    'max_upload_bytes': settings.multimodal_max_upload_bytes(),
                    'max_duration_sec': settings.multimodal_max_duration_sec(),
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc) or 'multimodal_submission_invalid')

    @router.get('/teacher/multimodal/submissions/{submission_id}')
    async def get_multimodal_submission(submission_id: str) -> Any:
        _ensure_enabled()
        try:
            submission = load_multimodal_submission_view(submission_id, core=core)
            _enforce_submission_teacher_scope(submission)
            return {'submission': submission}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='multimodal_submission_not_found')

    @router.post('/teacher/multimodal/submissions/{submission_id}/extract')
    async def extract_submission(submission_id: str) -> Any:
        _ensure_enabled()
        try:
            payload = load_multimodal_submission(submission_id, core=core)
            payload = _enforce_submission_teacher_scope(payload)
            result = extract_multimodal_submission(payload, deps=extract_deps)
            write_multimodal_extraction(submission_id, result.model_dump(), core=core)
            return {'ok': True, 'submission': result.model_dump()}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='multimodal_submission_not_found')
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc) or 'multimodal_extract_failed')

    @router.post('/teacher/multimodal/submissions/{submission_id}/analyze')
    async def analyze_submission(submission_id: str) -> Any:
        _ensure_enabled()
        try:
            _enforce_submission_teacher_scope(load_multimodal_submission(submission_id, core=core))
            return process_multimodal_submission(submission_id, deps=orchestrator_deps)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='multimodal_submission_not_found')
        except HTTPException:
            raise
        except Exception as exc:
            detail = str(getattr(exc, 'detail', exc) or 'multimodal_analyze_failed')
            status_code = int(getattr(exc, 'status_code', 500) or 500)
            raise HTTPException(status_code=status_code, detail=detail)

    return router



def _ensure_enabled() -> None:
    if not settings.multimodal_enabled():
        raise HTTPException(status_code=404, detail='multimodal_disabled')



def _enforce_limits(bundle: MultimodalSubmissionBundle) -> None:
    max_upload_bytes = int(settings.multimodal_max_upload_bytes())
    max_duration_sec = float(settings.multimodal_max_duration_sec())
    for media_file in bundle.media_files:
        if int(media_file.bytes or 0) > max_upload_bytes:
            raise HTTPException(status_code=413, detail='multimodal_submission_too_large')
        duration_sec = media_file.duration_sec
        if duration_sec is not None and float(duration_sec) > max_duration_sec:
            raise HTTPException(status_code=413, detail='multimodal_submission_too_large')
