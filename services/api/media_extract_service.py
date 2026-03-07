from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Sequence

from . import settings
from .media_segment_models import MediaExtractionFailure, MediaFrameEvidence, MediaTextSegment
from .multimodal_submission_models import MultimodalSubmissionBundle


@dataclass(frozen=True)
class MediaExtractDeps:
    transcribe: Callable[[MultimodalSubmissionBundle], Sequence[MediaTextSegment | dict[str, Any]]]
    extract_keyframes: Callable[[MultimodalSubmissionBundle], Sequence[MediaFrameEvidence | dict[str, Any]]]
    ocr_frame: Callable[[MediaFrameEvidence, MultimodalSubmissionBundle], str | None]
    now_iso: Callable[[], str]
    timeout_sec: Callable[[], int]
    diag_log: Callable[..., None]



def build_media_extract_deps(core: Any | None = None) -> MediaExtractDeps:
    return MediaExtractDeps(
        transcribe=getattr(core, 'media_transcribe', lambda _submission: []),
        extract_keyframes=getattr(core, 'media_extract_keyframes', lambda _submission: []),
        ocr_frame=getattr(core, 'media_ocr_frame', lambda _frame, _submission: None),
        now_iso=lambda: datetime.now().isoformat(timespec='seconds'),
        timeout_sec=settings.multimodal_extract_timeout_sec,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )



def extract_multimodal_submission(
    submission: MultimodalSubmissionBundle | dict[str, Any],
    *,
    deps: MediaExtractDeps,
) -> MultimodalSubmissionBundle:
    bundle = MultimodalSubmissionBundle.model_validate(submission)
    failures: list[MediaExtractionFailure] = []

    transcript_segments: list[MediaTextSegment] = []
    try:
        transcript_segments = _normalize_text_segments(deps.transcribe(bundle), default_kind='asr')
    except Exception as exc:
        failures.append(
            MediaExtractionFailure(stage='transcribe', code='extract_failed', message=str(exc)[:200], retryable=True)
        )
        deps.diag_log('multimodal.extract.transcribe_failed', {'error': str(exc)[:200]})

    keyframe_evidence: list[MediaFrameEvidence] = []
    try:
        keyframe_evidence = _normalize_frame_evidence(deps.extract_keyframes(bundle))
    except Exception as exc:
        failures.append(
            MediaExtractionFailure(stage='keyframes', code='extract_failed', message=str(exc)[:200], retryable=True)
        )
        deps.diag_log('multimodal.extract.keyframes_failed', {'error': str(exc)[:200]})

    enriched_frames: list[MediaFrameEvidence] = []
    for frame in keyframe_evidence:
        enriched = frame
        if not str(frame.ocr_text or '').strip():
            try:
                ocr_text = deps.ocr_frame(frame, bundle)
                text_final = str(ocr_text or '').strip()
                if text_final:
                    enriched = frame.model_copy(update={'ocr_text': text_final})
            except Exception as exc:
                failures.append(
                    MediaExtractionFailure(stage='frame_ocr', code='extract_failed', message=str(exc)[:200], retryable=True)
                )
                deps.diag_log('multimodal.extract.frame_ocr_failed', {'frame_id': frame.frame_id, 'error': str(exc)[:200]})
        enriched_frames.append(enriched)

    missing_fields = _dedupe_strings(list(bundle.missing_fields or []))
    if not transcript_segments:
        missing_fields = _dedupe_strings(missing_fields + ['transcript_segments'])
    if not enriched_frames:
        missing_fields = _dedupe_strings(missing_fields + ['keyframe_evidence'])
    if enriched_frames and any(not str(frame.ocr_text or '').strip() for frame in enriched_frames):
        missing_fields = _dedupe_strings(missing_fields + ['ocr_text_more_frames'])

    status = 'completed'
    if failures:
        status = 'partial' if (transcript_segments or bundle.subtitle_segments or enriched_frames) else 'failed'

    provenance = dict(bundle.provenance or {})
    provenance.update(
        {
            'extracted_at': deps.now_iso(),
            'extract_timeout_sec': int(deps.timeout_sec()),
            'extract_pipeline': 'media_extract_service_v1',
        }
    )

    parse_confidence = _compute_parse_confidence(
        base=bundle.parse_confidence,
        transcript_segments=transcript_segments,
        subtitle_segments=bundle.subtitle_segments,
        keyframe_evidence=enriched_frames,
        partial=bool(failures),
    )

    payload = {
        **bundle.model_dump(),
        'transcript_segments': [item.model_dump() for item in transcript_segments],
        'keyframe_evidence': [item.model_dump() for item in enriched_frames],
        'extraction_status': status,
        'extraction_failures': [item.model_dump() for item in failures],
        'parse_confidence': parse_confidence,
        'missing_fields': missing_fields,
        'provenance': provenance,
    }
    return MultimodalSubmissionBundle.model_validate(payload)



def _normalize_text_segments(values: Sequence[MediaTextSegment | dict[str, Any]], *, default_kind: str) -> list[MediaTextSegment]:
    items: list[MediaTextSegment] = []
    for raw in values or []:
        item = MediaTextSegment.model_validate(raw)
        if not str(item.kind or '').strip():
            item = item.model_copy(update={'kind': default_kind})
        items.append(item)
    return items



def _normalize_frame_evidence(values: Sequence[MediaFrameEvidence | dict[str, Any]]) -> list[MediaFrameEvidence]:
    return [MediaFrameEvidence.model_validate(raw) for raw in values or []]



def _compute_parse_confidence(
    *,
    base: float,
    transcript_segments: list[MediaTextSegment],
    subtitle_segments: list[MediaTextSegment],
    keyframe_evidence: list[MediaFrameEvidence],
    partial: bool,
) -> float:
    scores: list[float] = []
    if base is not None:
        scores.append(float(base))
    transcript_scores = [float(item.confidence) for item in transcript_segments if item.confidence is not None]
    if transcript_scores:
        scores.append(sum(transcript_scores) / len(transcript_scores))
    frame_scores = [float(item.confidence) for item in keyframe_evidence if item.confidence is not None]
    if frame_scores:
        scores.append(sum(frame_scores) / len(frame_scores))
    if subtitle_segments and not transcript_scores:
        scores.append(0.7)
    confidence = max(scores) if scores else 0.0
    if partial:
        confidence = max(0.0, confidence - 0.05)
    return round(min(1.0, confidence), 4)



def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items
