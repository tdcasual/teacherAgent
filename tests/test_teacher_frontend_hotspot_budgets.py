from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'App.tsx'
_CHAT_API_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'chat' / 'useTeacherChatApi.ts'
_ASSIGNMENT_WORKFLOW_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'workbench' / 'hooks' / 'useAssignmentWorkflow.ts'
_SESSION_STATE_HOOK_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'state' / 'useTeacherSessionState.ts'
_WORKBENCH_STATE_HOOK_PATH = _ROOT / 'frontend' / 'apps' / 'teacher' / 'src' / 'features' / 'state' / 'useTeacherWorkbenchState.ts'


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding='utf-8').splitlines())


def test_teacher_hotspot_files_remain_within_budget() -> None:
    assert _line_count(_APP_PATH) < 930
    assert _line_count(_CHAT_API_PATH) < 1150
    assert _line_count(_ASSIGNMENT_WORKFLOW_PATH) < 860


def test_teacher_app_uses_extracted_state_hooks() -> None:
    source = _APP_PATH.read_text(encoding='utf-8')
    assert 'useTeacherSessionState' in source
    assert 'useTeacherWorkbenchState' in source
    assert _SESSION_STATE_HOOK_PATH.exists()
    assert _WORKBENCH_STATE_HOOK_PATH.exists()
