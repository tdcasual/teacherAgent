import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useAssignmentUploadStatusPolling.ts"
EXAM = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useExamUploadStatusPolling.ts"
POLLER = ROOT / "frontend" / "apps" / "shared" / "visibilityBackoffPolling.ts"
STUDENT_CHAT = ROOT / "frontend" / "apps" / "student" / "src" / "hooks" / "useChatPolling.ts"
TEACHER_CHAT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "chat" / "useTeacherChatApi.ts"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hooks_use_shared_poller_and_no_manual_timers():
    assignment = _read(ASSIGNMENT)
    exam = _read(EXAM)

    assert "startVisibilityAwareBackoffPolling" in assignment
    assert "startVisibilityAwareBackoffPolling" in exam

    for text in (assignment, exam):
        assert "setTimeout" not in text
        assert "visibilitychange" not in text
        assert "document.visibilityState" not in text


def test_exam_hook_preserves_hidden_min_delay():
    exam = _read(EXAM)
    assert "hiddenMinDelayMs" in exam


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
    teacher = _read(TEACHER_CHAT)
    for text in (student, teacher):
        assert "signal" in text
        assert "pollTimeoutMs" in text
