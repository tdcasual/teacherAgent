from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'App.tsx'
_CHAT_API_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'chat' / 'useTeacherChatApi.ts'
_CHAT_SEND_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'chat' / 'useTeacherChatSend.ts'
_CHAT_STREAM_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'chat' / 'useTeacherChatStream.ts'
_CHAT_STATUS_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'chat' / 'useTeacherChatStatus.ts'
_ASSIGNMENT_WORKFLOW_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'workbench' / 'hooks' / 'useAssignmentWorkflow.ts'
_SESSION_STATE_HOOK_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'state' / 'useTeacherSessionState.ts'
_WORKBENCH_STATE_HOOK_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'state' / 'useTeacherWorkbenchState.ts'


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding='utf-8').splitlines())


def test_teacher_hotspot_files_remain_within_budget() -> None:
    assert _line_count(_APP_PATH) < 930
    assert _line_count(_CHAT_API_PATH) < 750
    assert _line_count(_ASSIGNMENT_WORKFLOW_PATH) < 860


def test_teacher_chat_api_send_stream_status_modules_exist() -> None:
    assert _CHAT_SEND_PATH.exists()
    assert _CHAT_STREAM_PATH.exists()
    assert _CHAT_STATUS_PATH.exists()
    source = _CHAT_API_PATH.read_text(encoding='utf-8')
    assert 'useTeacherChatSend' in source
    assert 'useTeacherChatStream' in source
    send = _CHAT_SEND_PATH.read_text(encoding='utf-8')
    stream = _CHAT_STREAM_PATH.read_text(encoding='utf-8')
    status = _CHAT_STATUS_PATH.read_text(encoding='utf-8')
    assert 'submitMessage' in send
    assert '/chat/stream' in stream
    assert 'pollTimeoutMs' in status
    assert 'startVisibilityAwareBackoffPolling' in status


def test_teacher_app_uses_extracted_state_hooks() -> None:
    source = _APP_PATH.read_text(encoding='utf-8')
    assert 'useTeacherSessionState' in source
    assert 'useTeacherWorkbenchState' in source
    assert _SESSION_STATE_HOOK_PATH.exists()
    assert _WORKBENCH_STATE_HOOK_PATH.exists()
