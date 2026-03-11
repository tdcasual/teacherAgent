from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from .contracts import HandoffContract, SpecialistAgentResult


@dataclass(frozen=True)
class ReviewerAnalystDeps:
    diag_log: Callable[..., None] = lambda *_args, **_kwargs: None


_REQUIRED_SECTION_RULES = {
    'executive_summary': {
        'reason_code': 'missing_executive_summary',
        'severity': 'high',
        'detail': '缺少老师可读的执行摘要。',
        'recommended_fix': '补齐面向老师的执行摘要并明确核心判断。',
    },
    'completion_overview': {
        'reason_code': 'missing_completion_overview',
        'severity': 'high',
        'detail': '缺少完成度概览，老师无法快速判断是否完成任务。',
        'recommended_fix': '补齐 completion_overview，包含 status 与 summary。',
    },
    'evidence_clips': {
        'reason_code': 'missing_evidence_clips',
        'severity': 'high',
        'detail': '缺少可追溯的证据片段。',
        'recommended_fix': '至少补充一个包含 evidence_ref 的证据片段。',
    },
    'teaching_recommendations': {
        'reason_code': 'missing_teaching_recommendations',
        'severity': 'medium',
        'detail': '缺少可执行的教学建议。',
        'recommended_fix': '补齐至少一条具体教学建议。',
    },
}



def run_reviewer_analyst(
    *,
    handoff: HandoffContract,
    multimodal_submission_bundle: Dict[str, Any] | Any,
    teacher_context: Dict[str, Any],
    task_goal: str,
    deps: ReviewerAnalystDeps | Any,
) -> SpecialistAgentResult:
    del multimodal_submission_bundle, teacher_context, task_goal
    request = HandoffContract.model_validate(handoff)
    constraints = dict(request.constraints or {})
    previous_raw = constraints.get('job_graph_previous_result')
    checked_sections: list[str] = []
    issue_list: list[Dict[str, Any]] = []

    if not isinstance(previous_raw, dict):
        previous_result = None
        artifact: Dict[str, Any] = {}
        issue_list.append(
            {
                'severity': 'high',
                'section': 'job_graph_previous_result',
                'detail': 'verify 节点未收到上游分析结果。',
                'recommended_fix': '确保 verify 节点注入上游 primary analysis artifact。',
                'reason_code': 'missing_upstream_analysis',
            }
        )
    else:
        previous_result = SpecialistAgentResult.model_validate(previous_raw)
        artifact = dict(previous_result.output or {})

    for section, rule in _REQUIRED_SECTION_RULES.items():
        if _section_present(section, artifact):
            checked_sections.append(section)
        else:
            issue_list.append(
                {
                    'severity': rule['severity'],
                    'section': section,
                    'detail': rule['detail'],
                    'recommended_fix': rule['recommended_fix'],
                    'reason_code': rule['reason_code'],
                }
            )

    unsupported_signals = _find_unsupported_signals(artifact)
    if unsupported_signals:
        checked_sections.append('signal_evidence_consistency')
        issue_list.append(
            {
                'severity': 'medium',
                'section': 'signal_evidence_consistency',
                'detail': '存在缺少证据引用的关键信号。',
                'recommended_fix': '为每条关键/表达信号补齐 evidence_refs，或删除无法追溯的信号。',
                'reason_code': 'signal_missing_evidence_refs',
            }
        )
    else:
        checked_sections.append('signal_evidence_consistency')

    reason_codes = _dedupe_reason_codes(issue_list)
    quality_score = _quality_score(issue_list)
    approved = not any(item['severity'] == 'high' for item in issue_list) and float(quality_score) >= 0.8
    critique_summary = '结构完整，可直接交付。' if approved else '发现需要人工复核的问题：' + '、'.join(reason_codes)
    review_output = {
        'approved': approved,
        'critique_summary': critique_summary,
        'reason_codes': reason_codes,
        'recommended_action': 'deliver' if approved else 'enqueue_review',
        'checked_sections': checked_sections,
        'quality_score': quality_score,
        'issue_list': issue_list,
    }
    if hasattr(deps, 'diag_log'):
        deps.diag_log(
            'reviewer_analyst.completed',
            {
                'handoff_id': request.handoff_id,
                'strategy_id': request.strategy_id,
                'approved': approved,
                'quality_score': quality_score,
                'reason_codes': list(reason_codes),
            },
        )
    return SpecialistAgentResult(
        handoff_id=request.handoff_id,
        agent_id=request.to_agent,
        status='completed',
        output=review_output,
        confidence=previous_result.confidence if previous_result is not None else None,
    )



def _section_present(section: str, artifact: Dict[str, Any]) -> bool:
    value = artifact.get(section)
    if section == 'executive_summary':
        return bool(str(value or '').strip())
    if section == 'completion_overview':
        return isinstance(value, dict) and bool(str(value.get('summary') or '').strip()) and bool(str(value.get('status') or '').strip())
    if section == 'evidence_clips':
        if not isinstance(value, list) or not value:
            return False
        for item in value:
            if isinstance(item, dict) and str(item.get('evidence_ref') or '').strip():
                return True
        return False
    if section == 'teaching_recommendations':
        return isinstance(value, list) and any(str(item or '').strip() for item in value)
    return bool(value)



def _find_unsupported_signals(artifact: Dict[str, Any]) -> bool:
    signals = list(artifact.get('key_signals') or []) + list(artifact.get('expression_signals') or [])
    for item in signals:
        if not isinstance(item, dict):
            continue
        evidence_refs = item.get('evidence_refs')
        if not isinstance(evidence_refs, list) or not [ref for ref in evidence_refs if str(ref or '').strip()]:
            return True
    return False



def _quality_score(issue_list: list[Dict[str, Any]]) -> float:
    penalties = {'high': 0.3, 'medium': 0.15, 'low': 0.05}
    score = 1.0
    for item in issue_list:
        score -= penalties.get(str(item.get('severity') or '').strip(), 0.0)
    return round(max(score, 0.0), 4)



def _dedupe_reason_codes(issue_list: list[Dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    reason_codes: list[str] = []
    for item in issue_list:
        reason_code = str(item.get('reason_code') or '').strip()
        if not reason_code or reason_code in seen:
            continue
        seen.add(reason_code)
        reason_codes.append(reason_code)
    return reason_codes
