from __future__ import annotations

from typing import Any, Dict, List, Optional

_TIMELINE_LIMIT = 12
_ALLOWED_EVENT_TYPES = {
    'job.queued',
    'job.processing',
    'workflow.resolved',
    'tool.start',
    'tool.finish',
    'assistant.done',
    'job.done',
    'job.failed',
    'job.cancelled',
}


def _summary_for_event(event_type: str, payload: Dict[str, Any]) -> str:
    if event_type == 'job.queued':
        lane_pos = int(payload.get('lane_queue_position', 0) or 0)
        return f'排队中（前方 {lane_pos}）' if lane_pos > 0 else '排队中'
    if event_type == 'job.processing':
        return '处理中'
    if event_type == 'workflow.resolved':
        skill_id = str(payload.get('effective_skill_id') or payload.get('skill_id_effective') or '').strip()
        return f'工作流已解析：{skill_id}' if skill_id else '工作流已解析'
    if event_type == 'tool.start':
        tool_name = str(payload.get('tool_name') or '').strip() or 'tool'
        return f'调用工具：{tool_name}'
    if event_type == 'tool.finish':
        tool_name = str(payload.get('tool_name') or '').strip() or 'tool'
        ok = bool(payload.get('ok'))
        return f'工具完成：{tool_name}' if ok else f'工具失败：{tool_name}'
    if event_type == 'assistant.done':
        return '已生成回复'
    if event_type == 'job.done':
        return '任务完成'
    if event_type == 'job.failed':
        return '任务失败'
    if event_type == 'job.cancelled':
        return '任务已取消'
    return event_type


def build_chat_execution_timeline_entry(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(event, dict):
        return None
    event_type = str(event.get('type') or '').strip()
    if event_type not in _ALLOWED_EVENT_TYPES:
        return None
    payload = event.get('payload') if isinstance(event.get('payload'), dict) else {}
    entry: Dict[str, Any] = {
        'type': event_type,
        'ts': str(event.get('ts') or '').strip(),
        'summary': _summary_for_event(event_type, payload),
        'meta': payload,
    }
    return entry


def append_chat_execution_timeline(
    timeline: Any,
    event: Dict[str, Any],
    *,
    limit: int = _TIMELINE_LIMIT,
) -> List[Dict[str, Any]]:
    items = [item for item in (timeline or []) if isinstance(item, dict)]
    entry = build_chat_execution_timeline_entry(event)
    if entry is None:
        return items[-max(1, int(limit)) :]
    items.append(entry)
    return items[-max(1, int(limit)) :]
