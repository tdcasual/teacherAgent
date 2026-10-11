from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..assignment.store import assignment_is_sql_published
from ..assignment_data_service import load_assignment_meta
from ..assignment_student_list_service import student_currently_enrolled
from ..auth_service import get_current_principal
from ..student_practice_service import (
    StudentPracticeDeps,
    StudentPracticeError,
    list_practices,
    recommend_practice,
    require_practice_actor,
    submit_practice,
)
from ..student_submit_service import StudentSubmitError, authorize_student_submit_assignment


def _default_sanitize(name: str) -> str:
    return Path(str(name or "").strip()).name


def _actor_id() -> str:
    try:
        return require_practice_actor(get_current_principal())
    except StudentPracticeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _practice_deps(core: Any) -> StudentPracticeDeps:
    data_dir = Path(getattr(core, "DATA_DIR"))
    submissions = Path(getattr(core, "STUDENT_SUBMISSIONS_DIR", data_dir / "student_submissions"))

    def _load_meta(assignment_id: str) -> Optional[dict]:
        resolve = getattr(core, "resolve_assignment_dir", None)
        if callable(resolve):
            folder = resolve(assignment_id)
        else:
            folder = data_dir / "assignments" / assignment_id
        if folder is None or not Path(folder).exists():
            return None
        loader = getattr(core, "load_assignment_meta", load_assignment_meta)
        meta = loader(Path(folder))
        return meta if isinstance(meta, dict) else None

    def _authorize(assignment_id: str, student_id: str) -> None:
        authorize_student_submit_assignment(
            assignment_id,
            student_id,
            load_meta=_load_meta,
            student_enrolled=lambda sid, tid, sub, class_name="": student_currently_enrolled(
                sid, tid, sub, data_dir=data_dir, class_name=class_name
            ),
            is_sql_published=lambda aid: assignment_is_sql_published(data_dir, aid),
        )

    async def _save_upload(upload: Any, dest: Path) -> int:
        saver = getattr(core, "save_upload_file", None)
        if callable(saver):
            return await saver(upload, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = await upload.read()
        dest.write_bytes(payload)
        return len(payload)

    return StudentPracticeDeps(
        data_dir=data_dir,
        app_root=Path(getattr(core, "APP_ROOT", data_dir)),
        student_submissions_dir=submissions,
        uploads_dir=Path(getattr(core, "UPLOADS_DIR", data_dir / "uploads")),
        run_script=getattr(core, "run_script"),
        diag_log=getattr(core, "diag_log", lambda _event, _payload: None),
        save_upload_file=_save_upload,
        sanitize_filename=getattr(core, "sanitize_filename", _default_sanitize),
        authorize_student_submit=_authorize,
        grade_count_conf_threshold=float(getattr(core, "GRADE_COUNT_CONF_THRESHOLD", 0.6) or 0.6),
    )


def _raise_practice(exc: Exception) -> None:
    if isinstance(exc, (StudentPracticeError, StudentSubmitError)):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


def register_student_practice_routes(router: APIRouter, core: Any) -> None:
    @router.post("/student/assignment/{assignment_id}/practice")
    def student_practice_recommend(assignment_id: str) -> Any:
        actor = _actor_id()
        try:
            return recommend_practice(assignment_id, student_id=actor, deps=_practice_deps(core))
        except (StudentPracticeError, StudentSubmitError) as exc:
            _raise_practice(exc)

    @router.get("/student/assignment/{assignment_id}/practice")
    def student_practice_list(assignment_id: str) -> Any:
        actor = _actor_id()
        try:
            return list_practices(assignment_id, student_id=actor, deps=_practice_deps(core))
        except (StudentPracticeError, StudentSubmitError) as exc:
            _raise_practice(exc)

    @router.post("/student/assignment/{assignment_id}/practice/{practice_id}/submit")
    async def student_practice_submit(
        assignment_id: str,
        practice_id: str,
        files: list[UploadFile] = File(...),
    ) -> Any:
        actor = _actor_id()
        try:
            return await submit_practice(
                assignment_id,
                practice_id,
                student_id=actor,
                files=files,
                deps=_practice_deps(core),
            )
        except (StudentPracticeError, StudentSubmitError) as exc:
            _raise_practice(exc)
