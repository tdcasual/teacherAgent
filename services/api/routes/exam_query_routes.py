from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..auth_service import AuthError, require_principal
from .exam_route_helpers import ensure_exam_ok


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_exam_query_routes(router: APIRouter, *, app_deps: Any, exam_app: Any) -> None:
    @router.get("/exams")
    async def exams(limit: int = 50, cursor: int = 0) -> Any:
        _require_teacher_or_admin()
        return exam_app.list_exams(limit=limit, cursor=cursor, deps=app_deps)

    @router.get("/exam/{exam_id}")
    async def exam_detail(exam_id: str) -> Any:
        _require_teacher_or_admin()
        result = exam_app.get_exam_detail(exam_id, deps=app_deps)
        ensure_exam_ok(result)
        return result

    @router.get("/exam/{exam_id}/analysis")
    async def exam_analysis(exam_id: str) -> Any:
        _require_teacher_or_admin()
        result = exam_app.get_exam_analysis(exam_id, deps=app_deps)
        ensure_exam_ok(result)
        return result

    @router.get("/exam/{exam_id}/students")
    async def exam_students(exam_id: str, limit: int = 50) -> Any:
        _require_teacher_or_admin()
        result = exam_app.list_exam_students(exam_id, limit=limit, deps=app_deps)
        ensure_exam_ok(result)
        return result

    @router.get("/exam/{exam_id}/student/{student_id}")
    async def exam_student(exam_id: str, student_id: str) -> Any:
        _require_teacher_or_admin()
        result = exam_app.get_exam_student_detail(exam_id, student_id=student_id, deps=app_deps)
        ensure_exam_ok(result)
        return result

    @router.get("/exam/{exam_id}/question/{question_id}")
    async def exam_question(exam_id: str, question_id: str) -> Any:
        _require_teacher_or_admin()
        result = exam_app.get_exam_question_detail(exam_id, question_id=question_id, deps=app_deps)
        ensure_exam_ok(result)
        return result
