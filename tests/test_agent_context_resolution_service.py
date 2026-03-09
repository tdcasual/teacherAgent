from services.api.agent_context_resolution_service import (
    build_longform_context_prompt,
    extract_exam_id_from_messages,
    find_exam_id_for_longform,
    find_last_user_text,
)


def test_extract_exam_id_from_messages_falls_back_to_regex():
    exam_id = extract_exam_id_from_messages(
        '请分析 EX20260209_9b92e1 的成绩',
        [{'role': 'assistant', 'content': '好的'}],
        extract_exam_id=lambda text: None,
    )

    assert exam_id == 'EX20260209_9b92e1'


def test_find_exam_id_for_longform_reads_history():
    exam_id = find_exam_id_for_longform(
        '请写成报告',
        [
            {'role': 'user', 'content': '先分析 EX20260209_9b92e1'},
            {'role': 'assistant', 'content': '收到'},
        ],
        extract_exam_id=lambda text: 'EX20260209_9b92e1' if 'EX20260209_9b92e1' in (text or '') else None,
    )

    assert exam_id == 'EX20260209_9b92e1'


def test_find_last_user_text_returns_latest_user_message():
    assert find_last_user_text([
        {'role': 'user', 'content': '第一次'},
        {'role': 'assistant', 'content': '回复'},
        {'role': 'user', 'content': '第二次'},
    ]) == '第二次'


def test_build_longform_context_prompt_embeds_payload():
    prompt = build_longform_context_prompt(1200, {'exam_analysis': {'ok': True}})

    assert '不少于 1200 字' in prompt
    assert 'BEGIN EXAM CONTEXT' in prompt
    assert 'exam_analysis' in prompt
