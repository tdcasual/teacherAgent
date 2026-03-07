from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..class_signal_bundle_models import ClassSignalBundle
from ..config import APP_ROOT
from ..upload_llm_service import parse_llm_json
from .contracts import ArtifactRef, HandoffContract, SpecialistAgentResult

_PROMPT_PATH = APP_ROOT / 'prompts' / 'v1' / 'teacher' / 'agents' / 'class_signal_analyst.md'


@dataclass(frozen=True)
class ClassSignalAnalystDeps:
    call_llm: Callable[..., Dict[str, Any]]
    prompt_loader: Callable[[], str]
    diag_log: Callable[..., None]



def load_class_signal_analyst_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding='utf-8')
    except Exception:
        return '你是 Class Signal Analyst，只输出 analysis_artifact 的严格 JSON。'



def _to_bundle(value: ClassSignalBundle | Dict[str, Any]) -> ClassSignalBundle:
    if isinstance(value, ClassSignalBundle):
        return value
    return ClassSignalBundle.model_validate(value)



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



def _fallback_artifact(bundle: ClassSignalBundle) -> Dict[str, Any]:
    key_signals: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    for signal in bundle.theme_like_signals[:2]:
        key_signals.append(
            {
                'title': signal.theme,
                'detail': signal.summary or f'出现 {int(signal.evidence_count or 0)} 次相关反馈。',
                'evidence_refs': list(signal.evidence_refs or []),
            }
        )
        recommendations.append(f'围绕“{signal.theme}”做一次板书拆解或分步复盘。')

    for risk in bundle.risk_like_signals[:2]:
        key_signals.append(
            {
                'title': risk.risk,
                'detail': risk.summary or '需要尽快复核并做纠偏。',
                'evidence_refs': list(risk.evidence_refs or []),
            }
        )
        recommendations.append(f'针对“{risk.risk}”补充概念辨析与即时检测。')

    for question in bundle.question_like_signals[:1]:
        key_signals.append(
            {
                'title': question.title,
                'detail': question.summary or question.title,
                'evidence_refs': list(question.evidence_refs or []),
            }
        )
        recommendations.append(f'围绕“{question.title}”安排分层练习并观察迁移效果。')

    if not recommendations:
        recommendations.append('先基于当前班级信号做一次针对性复盘，再补一轮验证性练习。')

    summary_parts = [item for item in bundle.narrative_blocks[:2] if str(item or '').strip()]
    if bundle.class_scope.class_name:
        summary_parts.insert(0, f'{bundle.class_scope.class_name} 已完成班级信号归纳')
    executive_summary = '；'.join(summary_parts) or '已生成班级信号归纳与教学建议。'

    return {
        'executive_summary': executive_summary,
        'key_signals': key_signals,
        'teaching_recommendations': _dedupe_strings(recommendations),
        'confidence_and_gaps': {
            'confidence': float(bundle.parse_confidence),
            'gaps': list(bundle.missing_fields or []),
        },
    }



def _normalize_key_signals(value: Any, fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items: List[Dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, str):
            items.append({'title': raw, 'detail': raw, 'evidence_refs': []})
            continue
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                'title': str(raw.get('title') or raw.get('signal') or '').strip(),
                'detail': str(raw.get('detail') or raw.get('summary') or raw.get('title') or '').strip(),
                'evidence_refs': [str(item).strip() for item in (raw.get('evidence_refs') or []) if str(item).strip()],
            }
        )
    return [item for item in items if item['title'] or item['detail']] or fallback



def _normalize_recommendations(value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item or '').strip() for item in value if str(item or '').strip()]
    return items or fallback



def _normalize_artifact(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    confidence_and_gaps = parsed.get('confidence_and_gaps') if isinstance(parsed.get('confidence_and_gaps'), dict) else {}
    confidence = _safe_float(confidence_and_gaps.get('confidence'))
    if confidence is None:
        confidence = _safe_float((fallback.get('confidence_and_gaps') or {}).get('confidence'))
    gaps = _dedupe_strings(
        [str(item) for item in (confidence_and_gaps.get('gaps') or []) if str(item or '').strip()]
        + [str(item) for item in ((fallback.get('confidence_and_gaps') or {}).get('gaps') or []) if str(item or '').strip()]
    )
    return {
        'executive_summary': str(parsed.get('executive_summary') or fallback.get('executive_summary') or '').strip()
        or str(fallback.get('executive_summary') or '').strip(),
        'key_signals': _normalize_key_signals(parsed.get('key_signals'), list(fallback.get('key_signals') or [])),
        'teaching_recommendations': _normalize_recommendations(
            parsed.get('teaching_recommendations'),
            list(fallback.get('teaching_recommendations') or []),
        ),
        'confidence_and_gaps': {
            'confidence': float(confidence or 0.0),
            'gaps': gaps,
        },
    }



def run_class_signal_analyst(
    *,
    handoff: HandoffContract,
    class_signal_bundle: ClassSignalBundle | Dict[str, Any],
    teacher_context: Dict[str, Any],
    task_goal: str,
    deps: ClassSignalAnalystDeps,
) -> SpecialistAgentResult:
    request = HandoffContract.model_validate(handoff)
    bundle = _to_bundle(class_signal_bundle)
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
                            'class_signal_bundle': bundle.model_dump(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            role_hint='teacher',
            kind='class_report.analysis',
            max_tokens=int(request.budget.max_tokens or 1600),
        )
        content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
        parsed = parse_llm_json(content)
        if isinstance(parsed, dict):
            artifact = _normalize_artifact(parsed, fallback_artifact)
        else:
            deps.diag_log('class_signal_analyst.fallback', {'reason': 'parse_failed'})
    except Exception as exc:
        deps.diag_log('class_signal_analyst.error', {'error': str(exc)[:200]})

    confidence = _safe_float((artifact.get('confidence_and_gaps') or {}).get('confidence')) or float(bundle.parse_confidence)
    return SpecialistAgentResult(
        handoff_id=request.handoff_id,
        agent_id=request.to_agent,
        status='completed',
        output=artifact,
        confidence=confidence,
        artifacts=[ArtifactRef(artifact_id=f'{request.handoff_id}:analysis', artifact_type='analysis_artifact')],
    )
