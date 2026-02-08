from __future__ import annotations

import inspect
from typing import Any, Iterable, Tuple

from fastapi import FastAPI

RouteDef = Tuple[str, str, str]

ROUTES: Iterable[RouteDef] = (
    ("get", "/health", "health"),
    ("post", "/chat", "chat"),
    ("post", "/chat/start", "chat_start"),
    ("get", "/chat/status", "chat_status"),
    ("get", "/student/history/sessions", "student_history_sessions"),
    ("get", "/student/session/view-state", "student_session_view_state"),
    ("put", "/student/session/view-state", "update_student_session_view_state"),
    ("get", "/student/history/session", "student_history_session"),
    ("get", "/teacher/history/sessions", "teacher_history_sessions"),
    ("get", "/teacher/session/view-state", "teacher_session_view_state"),
    ("put", "/teacher/session/view-state", "update_teacher_session_view_state"),
    ("get", "/teacher/history/session", "teacher_history_session"),
    ("get", "/teacher/memory/proposals", "teacher_memory_proposals"),
    ("get", "/teacher/memory/insights", "teacher_memory_insights_api"),
    ("post", "/teacher/memory/proposals/{proposal_id}/review", "teacher_memory_proposal_review"),
    ("post", "/upload", "upload"),
    ("get", "/student/profile/{student_id}", "get_profile"),
    ("post", "/student/profile/update", "update_profile"),
    ("post", "/student/import", "import_students"),
    ("post", "/student/verify", "verify_student"),
    ("get", "/exams", "exams"),
    ("get", "/exam/{exam_id}", "exam_detail"),
    ("get", "/exam/{exam_id}/analysis", "exam_analysis"),
    ("get", "/exam/{exam_id}/students", "exam_students"),
    ("get", "/exam/{exam_id}/student/{student_id}", "exam_student"),
    ("get", "/exam/{exam_id}/question/{question_id}", "exam_question"),
    ("get", "/assignments", "assignments"),
    ("get", "/teacher/assignment/progress", "teacher_assignment_progress"),
    ("get", "/teacher/assignments/progress", "teacher_assignments_progress"),
    ("post", "/assignment/requirements", "assignment_requirements"),
    ("get", "/assignment/{assignment_id}/requirements", "assignment_requirements_get"),
    ("post", "/assignment/upload", "assignment_upload"),
    ("post", "/exam/upload/start", "exam_upload_start"),
    ("get", "/exam/upload/status", "exam_upload_status"),
    ("get", "/exam/upload/draft", "exam_upload_draft"),
    ("post", "/exam/upload/draft/save", "exam_upload_draft_save"),
    ("post", "/exam/upload/confirm", "exam_upload_confirm"),
    ("post", "/assignment/upload/start", "assignment_upload_start"),
    ("get", "/assignment/upload/status", "assignment_upload_status"),
    ("get", "/assignment/upload/draft", "assignment_upload_draft"),
    ("post", "/assignment/upload/draft/save", "assignment_upload_draft_save"),
    ("post", "/assignment/upload/confirm", "assignment_upload_confirm"),
    ("get", "/assignment/{assignment_id}/download", "assignment_download"),
    ("get", "/assignment/today", "assignment_today"),
    ("get", "/assignment/{assignment_id}", "assignment_detail"),
    ("get", "/lessons", "lessons"),
    ("get", "/skills", "skills"),
    ("get", "/charts/{run_id}/{file_name}", "chart_image_file"),
    ("get", "/chart-runs/{run_id}/meta", "chart_run_meta"),
    ("get", "/teacher/llm-routing", "teacher_llm_routing"),
    ("post", "/teacher/llm-routing/simulate", "teacher_llm_routing_simulate_api"),
    ("post", "/teacher/llm-routing/proposals", "teacher_llm_routing_proposals_api"),
    ("get", "/teacher/llm-routing/proposals/{proposal_id}", "teacher_llm_routing_proposal_api"),
    ("post", "/teacher/llm-routing/proposals/{proposal_id}/review", "teacher_llm_routing_proposal_review_api"),
    ("post", "/teacher/llm-routing/rollback", "teacher_llm_routing_rollback_api"),
    ("get", "/teacher/provider-registry", "teacher_provider_registry_api"),
    ("post", "/teacher/provider-registry/providers", "teacher_provider_registry_create_api"),
    ("patch", "/teacher/provider-registry/providers/{provider_id}", "teacher_provider_registry_update_api"),
    ("delete", "/teacher/provider-registry/providers/{provider_id}", "teacher_provider_registry_delete_api"),
    ("post", "/teacher/provider-registry/providers/{provider_id}/probe-models", "teacher_provider_registry_probe_models_api"),
    ("post", "/assignment/generate", "generate_assignment"),
    ("post", "/assignment/render", "render_assignment"),
    ("post", "/assignment/questions/ocr", "assignment_questions_ocr"),
    ("post", "/student/submit", "submit"),
)


def _wrap(mod: Any, func_name: str):
    func = getattr(mod, func_name)
    signature = inspect.signature(func)

    async def handler(*args, **kwargs):
        target = getattr(mod, func_name)
        result = target(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    handler.__name__ = f"{func_name}_route"
    handler.__signature__ = signature
    return handler


def _register(app: FastAPI, method: str, path: str, mod: Any, func_name: str) -> None:
    decorator = getattr(app, method)
    decorator(path)(_wrap(mod, func_name))


def register_routes(app: FastAPI, mod: Any) -> None:
    if mod is None:
        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return

    for method, path, func_name in ROUTES:
        _register(app, method, path, mod, func_name)
