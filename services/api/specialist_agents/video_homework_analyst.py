from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..config import APP_ROOT
from ..multimodal_submission_models import MultimodalSubmissionBundle
from ..upload_llm_service import parse_llm_json
from .contracts import ArtifactRef, HandoffContract, SpecialistAgentResult

_PROMPT_PATH = APP_ROOT / 'prompts' / 'v1' / 'teacher' / 'agents' / 'video_homework_analyst.md'
_DISALLOWED_OUTPUT_KEYS = {'auto_score', 'score', 'score_breakdown', 'rubric_writeback'}


@dataclass(frozen=True)
class VideoHomeworkAnalystDeps:
    call_llm: Callable[..., Dict[str, Any]]
    prompt_loader: Callable[[], str]
    diag_log: Callable[..., None]



def load_video_homework_analyst_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding='utf-8')
    except Exception:
        return '你是 Video Homework Analyst，只输出 analysis_artifact 的严格 JSON。'



def _to_bundle(value: MultimodalSubmissionBundle | Dict[str, Any]) -> MultimodalSubmissionBundle:
    if isinstance(value, MultimodalSubmissionBundle):
        return value
    return MultimodalSubmissionBundle.model_validate(value)



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def _dedupe_strings(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result



def _fallback_artifact(bundle: MultimodalSubmissionBundle) -> Dict[str, Any]:
    duration_sec = next((item.duration_sec for item in bundle.media_files if item.duration_sec is not None), None)
    segments = list(bundle.transcript_segments or bundle.subtitle_segments or [])
    expression_signals: List[Dict[str, Any]] = []
    evidence_clips: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    for segment in segments[:2]:
        evidence_ref = next(iter(segment.evidence_refs or []), f'segment:{segment.segment_id}')
        expression_signals.append(
            {
                'title': f'片段 {segment.segment_id}',
                'detail': segment.text,
                'evidence_refs': [evidence_ref],
            }
        )
        evidence_clips.append(
            {
                'label': f'片段 {segment.segment_id}',
                'start_sec': float(segment.start_sec),
                'end_sec': float(segment.end_sec),
                'evidence_ref': evidence_ref,
                'excerpt': segment.text,
            }
        )

    for frame in bundle.keyframe_evidence[:1]:
        text = str(frame.ocr_text or frame.caption or '关键画面').strip()
        expression_signals.append(
            {
                'title': '关键画面',
                'detail': text,
                'evidence_refs': [f'frame:{frame.frame_id}'],
            }
        )

    if segments:
        recommendations.append('保留当前展示顺序，同时补充更完整的术语表达。')
    else:
        recommendations.append('先补齐口述说明，再结合关键画面做完整展示。')
    if bundle.missing_fields:
        recommendations.append('下一轮补充评分标准或老师 rubric，便于更稳定复核。')

    summary_bits = [str(bundle.source_meta.title or '').strip(), str(bundle.scope.student_id or '').strip()]
    summary_bits = [item for item in summary_bits if item]
    if segments:
        summary_bits.append('已识别到可用讲解片段')
    if bundle.keyframe_evidence:
        summary_bits.append('已抽取关键画面证据')
    executive_summary = '，'.join(summary_bits) or '已生成视频作业完成度与表达信号摘要。'

    return {
        'executive_summary': executive_summary,
        'completion_overview': {
            'status': 'completed' if bundle.extraction_status == 'completed' else bundle.extraction_status,
            'summary': f'视频时长 {duration_sec or 0} 秒，已抽取 {len(segments)} 段讲解证据与 {len(bundle.keyframe_evidence)} 个关键画面。',
            'duration_sec': duration_sec,
        },
        'key_signals': expression_signals,
        'expression_signals': expression_signals,
        'evidence_clips': evidence_clips,
        'teaching_recommendations': _dedupe_strings(recommendations),
        'confidence_and_gaps': {
            'confidence': float(bundle.parse_confidence),
            'gaps': list(bundle.missing_fields or []),
        },
    }



def _normalize_signal_list(value: Any, fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items: List[Dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, str):
            items.append({'title': raw, 'detail': raw, 'evidence_refs': []})
            continue
        if not isinstance(raw, dict):
            continue
        evidence_refs = [str(item).strip() for item in (raw.get('evidence_refs') or []) if str(item).strip()]
        items.append(
            {
                'title': str(raw.get('title') or raw.get('signal') or '').strip(),
                'detail': str(raw.get('detail') or raw.get('summary') or raw.get('title') or '').strip(),
                'evidence_refs': evidence_refs,
            }
        )
    return [item for item in items if item['title'] or item['detail']] or fallback



def _normalize_evidence_clips(value: Any, fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items: List[Dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                'label': str(raw.get('label') or raw.get('title') or '').strip(),
                'start_sec': _safe_float(raw.get('start_sec')),
                'end_sec': _safe_float(raw.get('end_sec')),
                'evidence_ref': str(raw.get('evidence_ref') or '').strip(),
                'excerpt': str(raw.get('excerpt') or raw.get('text') or '').strip(),
            }
        )
    return [item for item in items if item['label'] or item['evidence_ref'] or item['excerpt']] or fallback



def _normalize_recommendations(value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item or '').strip() for item in value if str(item or '').strip()]
    return items or fallback



def _normalize_artifact(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {key: value for key, value in parsed.items() if key not in _DISALLOWED_OUTPUT_KEYS}
    raw_confidence_and_gaps = sanitized.get('confidence_and_gaps')
    confidence_and_gaps: Dict[str, Any] = raw_confidence_and_gaps if isinstance(raw_confidence_and_gaps, dict) else {}
    confidence = _safe_float(confidence_and_gaps.get('confidence'))
    if confidence is None:
        confidence = _safe_float((fallback.get('confidence_and_gaps') or {}).get('confidence'))
    gaps = _dedupe_strings(
        [str(item) for item in (confidence_and_gaps.get('gaps') or []) if str(item or '').strip()]
        + [str(item) for item in ((fallback.get('confidence_and_gaps') or {}).get('gaps') or []) if str(item or '').strip()]
    )
    fallback_signals = list(fallback.get('expression_signals') or [])
    return {
        'executive_summary': str(sanitized.get('executive_summary') or fallback.get('executive_summary') or '').strip()
        or str(fallback.get('executive_summary') or '').strip(),
        'completion_overview': dict(sanitized.get('completion_overview') or fallback.get('completion_overview') or {}),
        'key_signals': _normalize_signal_list(sanitized.get('key_signals') or sanitized.get('expression_signals'), fallback_signals),
        'expression_signals': _normalize_signal_list(sanitized.get('expression_signals') or sanitized.get('key_signals'), fallback_signals),
        'evidence_clips': _normalize_evidence_clips(sanitized.get('evidence_clips'), list(fallback.get('evidence_clips') or [])),
        'teaching_recommendations': _normalize_recommendations(
            sanitized.get('teaching_recommendations'),
            list(fallback.get('teaching_recommendations') or []),
        ),
        'confidence_and_gaps': {
            'confidence': float(confidence or 0.0),
            'gaps': gaps,
        },
    }



def run_video_homework_analyst(
    *,
    handoff: HandoffContract,
    multimodal_submission_bundle: MultimodalSubmissionBundle | Dict[str, Any],
    teacher_context: Dict[str, Any],
    task_goal: str,
    deps: VideoHomeworkAnalystDeps,
) -> SpecialistAgentResult:
    request = HandoffContract.model_validate(handoff)
    bundle = _to_bundle(multimodal_submission_bundle)
    fallback_artifact = _fallback_artifact(bundle)
    artifact = dict(fallback_artifact)

    try:
        prompt = deps.prompt_loader()
        resp = deps.call_llm(
            [
                {'role': 'system', 'content': prompt},
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'task_goal': str(task_goal or request.goal),
                            'teacher_context': teacher_context,
                            'multimodal_submission_bundle': bundle.model_dump(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            role_hint='teacher',
            kind='video_homework.analysis',
            max_tokens=int(request.budget.max_tokens or 1600),
        )
        content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
        parsed = parse_llm_json(content)
        if isinstance(parsed, dict):
            artifact = _normalize_artifact(parsed, fallback_artifact)
        else:
            deps.diag_log('video_homework_analyst.fallback', {'reason': 'parse_failed'})
    except Exception as exc:
        deps.diag_log('video_homework_analyst.error', {'error': str(exc)[:200]})

    confidence = _safe_float((artifact.get('confidence_and_gaps') or {}).get('confidence')) or float(bundle.parse_confidence)
    return SpecialistAgentResult(
        handoff_id=request.handoff_id,
        agent_id=request.to_agent,
        status='completed',
        output=artifact,
        confidence=confidence,
        artifacts=[ArtifactRef(artifact_id=f'{request.handoff_id}:analysis', artifact_type='analysis_artifact')],
    )
