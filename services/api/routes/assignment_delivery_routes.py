from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter


def register_assignment_delivery_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any, core: Any
) -> None:
    @router.get("/assignment/{assignment_id}/download")
    async def assignment_download(assignment_id: str, file: str) -> Any:
        return await assignment_app.download_assignment_file(
            assignment_id,
            file,
            deps=app_deps,
        )

    @router.get("/assignment/today")
    async def assignment_today(
        student_id: str,
        date: Optional[str] = None,
        auto_generate: bool = False,
        generate: bool = True,
        per_kp: int = 5,
    ) -> Any:
        return await assignment_app.get_assignment_today(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=app_deps,
        )

    @router.get("/assignment/{assignment_id}")
    async def assignment_detail(assignment_id: str) -> Any:
        # Keep compatibility with tests and legacy monkeypatch surface on app_core.
        return core._get_assignment_detail_api_impl(
            assignment_id,
            deps=core._assignment_api_deps(),
        )
