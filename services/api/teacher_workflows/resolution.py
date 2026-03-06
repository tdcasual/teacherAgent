from __future__ import annotations

from typing import Any, Dict

from .exam_analysis import build_exam_analysis_workflow
from .homework_generation import build_homework_generation_workflow
from .lesson_capture import build_lesson_capture_workflow
from .student_focus import build_student_focus_workflow


def _looks_like_exam_analysis(text: str) -> bool:
    content = str(text or "").strip()
    return any(token in content for token in ("考试分析", "讲评", "成绩", "试卷", "班级分析", "exam"))


def resolve_teacher_workflow(
    req: Any,
    *,
    effective_skill_id: str,
    last_user_text: str,
    attachment_context: str,
) -> Dict[str, Any]:
    skill_id = str(effective_skill_id or "").strip()
    if skill_id == "physics-homework-generator":
        return build_homework_generation_workflow(
            req,
            last_user_text=last_user_text,
            attachment_context=attachment_context,
        )
    if skill_id == "physics-student-focus":
        return build_student_focus_workflow(
            req,
            last_user_text=last_user_text,
            attachment_context=attachment_context,
        )
    if skill_id == "physics-lesson-capture":
        return build_lesson_capture_workflow(
            req,
            last_user_text=last_user_text,
            attachment_context=attachment_context,
        )
    if skill_id == "physics-teacher-ops" and _looks_like_exam_analysis(last_user_text):
        return build_exam_analysis_workflow(
            req,
            last_user_text=last_user_text,
            attachment_context=attachment_context,
        )
    return {}
