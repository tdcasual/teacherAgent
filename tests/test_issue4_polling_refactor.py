import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useAssignmentUploadStatusPolling.ts"
POLLER = ROOT / "frontend" / "apps" / "shared" / "visibilityBackoffPolling.ts"
STUDENT_CHAT = ROOT / "frontend" / "apps" / "student" / "src" / "hooks" / "useChatPolling.ts"
TEACHER_CHAT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "chat" / "useTeacherChatApi.ts"
TEACHER_CHAT_STATUS = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "chat" / "useTeacherChatStatus.ts"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hooks_use_shared_poller_and_no_manual_timers():
    assignment = _read(ASSIGNMENT)

    assert "startVisibilityAwareBackoffPolling" in assignment
    assert "setTimeout" not in assignment
    assert "visibilitychange" not in assignment
    assert "document.visibilityState" not in assignment


def test_shared_poller_supports_hidden_min_delay():
    poller = _read(POLLER)
    assert "hiddenMinDelayMs" in poller


def test_shared_poller_supports_timeout_abort_context():
    poller = _read(POLLER)
    assert "AbortController" in poller
    assert "inFlightTimeoutMs" in poller
    assert "signal" in poller
    assert "abortInFlight" in poller


def test_chat_polling_hooks_use_shared_abort_signal():
    student = _read(STUDENT_CHAT)
    teacher = _read(TEACHER_CHAT) + _read(TEACHER_CHAT_STATUS)
    for text in (student, teacher):
        assert "signal" in text
        assert "pollTimeoutMs" in text
