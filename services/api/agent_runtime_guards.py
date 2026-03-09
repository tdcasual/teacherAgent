from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .agent_context_resolution_service import extract_exam_id_from_messages
from .subject_score_guard_service import (
    looks_like_subject_score_request,
    should_guard_total_mode_subject_request,
    subject_display,
)

_log = logging.getLogger(__name__)


def _fmt_total_score(value: Any) -> str:
    try:
        return f'{float(value):.1f}'
    except Exception:
        _log.debug('numeric conversion failed', exc_info=True)
        return '-'



def build_subject_total_mode_reply(
    exam_id: str,
    overview: Dict[str, Any],
    *,
    requested_subject: Optional[str],
    inferred_subject: Optional[str],
) -> str:
    totals = overview.get('totals_summary') if isinstance(overview.get('totals_summary'), dict) else {}
    avg_total = _fmt_total_score((totals or {}).get('avg_total'))
    median_total = _fmt_total_score((totals or {}).get('median_total'))
    max_total = _fmt_total_score((totals or {}).get('max_total_observed'))
    min_total = _fmt_total_score((totals or {}).get('min_total_observed'))

    requested_label = subject_display(requested_subject)
    inferred_label = subject_display(inferred_subject)

    unsupported_subject_line = (
        f'未提供可验证的{requested_label}单科分数字段。'
        if requested_subject
        else '未提供可验证的单科分数字段。'
    )
    cannot_treat_line = (
        f'因此我不能把总分当作{requested_label}单科成绩。'
        if requested_subject
        else '因此我不能把总分直接当作某一门单科成绩。'
    )

    inferred_hint = ''
    if inferred_subject and inferred_subject != requested_subject:
        inferred_hint = f'从试卷/答案文件名推断，该考试更可能是「{inferred_label}」单科总分。\n\n'

    return (
        f'## 考试 {exam_id} 单科成绩说明\n\n'
        '当前数据为**总分模式**（`score_mode: "total"`），系统仅有 `TOTAL` 总分字段，'
        f'{unsupported_subject_line}\n\n'
        f'{cannot_treat_line}\n\n'
        f'{inferred_hint}'
        '可提供的总分统计（供参考）：\n'
        f'- 平均分：{avg_total}\n'
        f'- 中位数：{median_total}\n'
        f'- 最高分：{max_total}\n'
        f'- 最低分：{min_total}\n\n'
        '如需更精准单科分析，请上传包含该学科列或每题得分的成绩表（xlsx）。'
    )



def maybe_guard_teacher_subject_total(
    deps: Any,
    *,
    messages: List[Dict[str, Any]],
    last_user_text: str,
) -> Optional[Dict[str, Any]]:
    if not looks_like_subject_score_request(last_user_text):
        return None
    exam_id = extract_exam_id_from_messages(
        last_user_text,
        messages,
        extract_exam_id=deps.extract_exam_id,
    )
    if not exam_id:
        return None
    try:
        context = deps.build_exam_longform_context(exam_id)
    except Exception as exc:
        _log.debug('operation failed', exc_info=True)
        deps.diag_log(
            'teacher.subject_total_guard_failed',
            {
                'exam_id': exam_id,
                'error': str(exc)[:200],
            },
        )
        context = {}
    overview = context.get('exam_overview') if isinstance(context, dict) else {}
    if not isinstance(overview, dict):
        return None
    should_guard, requested_subject, inferred_subject = should_guard_total_mode_subject_request(
        last_user_text,
        overview,
    )
    if should_guard:
        deps.diag_log(
            'teacher.subject_total_guard',
            {
                'exam_id': exam_id,
                'score_mode': 'total',
                'requested_subject': requested_subject or '',
                'inferred_subject': inferred_subject or '',
                'last_user': last_user_text[:200],
            },
        )
        return {
            'reply': build_subject_total_mode_reply(
                exam_id,
                overview,
                requested_subject=requested_subject,
                inferred_subject=inferred_subject,
            )
        }
    score_mode = str(overview.get('score_mode') or '').strip().lower()
    score_mode_source = str(overview.get('score_mode_source') or '').strip().lower()
    if score_mode_source == 'subject_from_scores_file':
        deps.diag_log(
            'teacher.subject_total_auto_extract_subject',
            {
                'exam_id': exam_id,
                'score_mode': score_mode,
                'score_mode_source': score_mode_source,
                'requested_subject': requested_subject or '',
                'inferred_subject': inferred_subject or '',
                'last_user': last_user_text[:200],
            },
        )
    elif score_mode == 'total':
        deps.diag_log(
            'teacher.subject_total_allow_single_subject',
            {
                'exam_id': exam_id,
                'score_mode': 'total',
                'requested_subject': requested_subject or '',
                'inferred_subject': inferred_subject or '',
                'last_user': last_user_text[:200],
            },
        )
    return None
