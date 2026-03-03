from __future__ import annotations

from pathlib import Path


def test_http_api_doc_has_no_removed_teacher_routing_endpoints() -> None:
    text = Path("docs/http_api.md").read_text(encoding="utf-8")
    assert "/teacher/llm-routing" not in text


def test_http_api_doc_no_missing_service_paths() -> None:
    text = Path("docs/http_api.md").read_text(encoding="utf-8")
    stale = [
        "services/api/exam_api_service.py",
        "services/api/assignment_api_service.py",
        "services/api/student_profile_api_service.py",
        "services/api/teacher_routing_api_service.py",
        "services/api/chat_api_service.py",
        "services/api/chart_api_service.py",
        "services/api/teacher_memory_api_service.py",
    ]
    for path in stale:
        assert path not in text
