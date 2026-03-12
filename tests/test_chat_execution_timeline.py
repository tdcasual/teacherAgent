from __future__ import annotations

from services.api.chat_execution_timeline_service import append_chat_execution_timeline


def _event(event_type: str, payload: dict, ts: str) -> dict:
    return {
        'type': event_type,
        'payload': payload,
        'ts': ts,
    }


def test_append_chat_execution_timeline_normalizes_key_events() -> None:
    timeline = []
    timeline = append_chat_execution_timeline(timeline, _event('job.queued', {'lane_queue_position': 2}, '2026-03-12T09:00:00Z'))
    timeline = append_chat_execution_timeline(timeline, _event('job.processing', {}, '2026-03-12T09:00:01Z'))
    timeline = append_chat_execution_timeline(timeline, _event('workflow.resolved', {'effective_skill_id': 'physics-homework-generator'}, '2026-03-12T09:00:02Z'))
    timeline = append_chat_execution_timeline(timeline, _event('tool.start', {'tool_name': 'exam.get'}, '2026-03-12T09:00:03Z'))
    timeline = append_chat_execution_timeline(timeline, _event('tool.finish', {'tool_name': 'exam.get', 'ok': True}, '2026-03-12T09:00:04Z'))
    timeline = append_chat_execution_timeline(timeline, _event('assistant.done', {'text': '完成'}, '2026-03-12T09:00:05Z'))
    timeline = append_chat_execution_timeline(timeline, _event('job.done', {'reply': '完成'}, '2026-03-12T09:00:06Z'))

    assert [item['type'] for item in timeline] == [
        'job.queued',
        'job.processing',
        'workflow.resolved',
        'tool.start',
        'tool.finish',
        'assistant.done',
        'job.done',
    ]
    assert timeline[0]['summary'] == '排队中（前方 2）'
    assert timeline[2]['summary'] == '工作流已解析：physics-homework-generator'
    assert timeline[4]['summary'] == '工具完成：exam.get'
    assert timeline[-1]['summary'] == '任务完成'


def test_append_chat_execution_timeline_ignores_non_timeline_events_and_trims() -> None:
    timeline = []
    timeline = append_chat_execution_timeline(timeline, _event('assistant.delta', {'delta': 'a'}, '2026-03-12T09:00:00Z'))
    assert timeline == []

    for idx in range(20):
        timeline = append_chat_execution_timeline(
            timeline,
            _event('tool.start', {'tool_name': f'tool-{idx}'}, f'2026-03-12T09:00:{idx:02d}Z'),
        )
    assert len(timeline) == 12
    assert timeline[0]['meta']['tool_name'] == 'tool-8'
    assert timeline[-1]['meta']['tool_name'] == 'tool-19'
