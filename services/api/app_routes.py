from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .routes.analysis_report_routes import build_router as build_analysis_report_router
from .routes.assignment_routes import build_router as build_assignment_router
from .routes.chat_routes import build_router as build_chat_router
from .routes.class_report_routes import build_router as build_class_report_router
from .routes.exam_routes import build_router as build_exam_router
from .routes.misc_routes import build_router as build_misc_router
from .routes.multimodal_routes import build_router as build_multimodal_router
from .routes.skill_routes import build_router as build_skill_router
from .routes.survey_routes import build_router as build_survey_router
from .routes.student_routes import build_router as build_student_router
from .routes.teacher_routes import build_router as build_teacher_router


def register_routes(app: FastAPI, core: Any) -> None:
    if core is None:
        raise ValueError("core must not be None")

    app.include_router(build_misc_router(core))
    app.include_router(build_chat_router(core))
    app.include_router(build_student_router(core))
    app.include_router(build_teacher_router(core))
    app.include_router(build_analysis_report_router(core))
    app.include_router(build_class_report_router(core))
    app.include_router(build_multimodal_router(core))
    app.include_router(build_survey_router(core))
    app.include_router(build_skill_router(core))
    app.include_router(build_exam_router(core))
    app.include_router(build_assignment_router(core))
