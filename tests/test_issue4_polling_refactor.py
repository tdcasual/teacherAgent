import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useAssignmentUploadStatusPolling.ts"
EXAM = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useExamUploadStatusPolling.ts"
POLLER = ROOT / "frontend" / "apps" / "shared" / "visibilityBackoffPolling.ts"


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
