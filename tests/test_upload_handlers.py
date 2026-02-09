import pytest
from fastapi import HTTPException
from pathlib import Path

from services.api.api_models import UploadConfirmRequest
from services.api.handlers import assignment_upload_handlers, exam_upload_handlers
from services.api.exam_upload_api_service import ExamUploadApiError
from services.api.assignment_upload_start_service import AssignmentUploadStartError


def _exam_deps(**overrides):
    def start_exam_upload(*_args, **_kwargs):
        return {"ok": True}

    def exam_upload_status(_job_id):
        return {"ok": True}

    def exam_upload_draft(_job_id):
        return {"ok": True}

    def exam_upload_draft_save(**_kwargs):
        return {"ok": True}

    def exam_upload_confirm(_job_id):
        return {"ok": True}

    deps = exam_upload_handlers.ExamUploadHandlerDeps(
        start_exam_upload=start_exam_upload,
        exam_upload_status=exam_upload_status,
        exam_upload_draft=exam_upload_draft,
        exam_upload_draft_save=exam_upload_draft_save,
        exam_upload_confirm=exam_upload_confirm,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


def _assignment_deps(tmp_path, **overrides):
    def assignment_upload_legacy(**_kwargs):
        return {"ok": True}

    async def start_assignment_upload(**_kwargs):
        return {"ok": True}

    def assignment_upload_status(_job_id):
        return {"ok": True}

    def assignment_upload_draft(_job_id):
        return {"ok": True}

    def assignment_upload_draft_save(*_args, **_kwargs):
        return {"ok": True}

    def load_upload_job(_job_id):
        return {"job_id": _job_id, "status": "done"}

    def ensure_assignment_upload_confirm_ready(_job):
        return None

    def confirm_assignment_upload(*_args, **_kwargs):
        return {"ok": True}

    def upload_job_path(_job_id):
        return Path(tmp_path)

    deps = assignment_upload_handlers.AssignmentUploadHandlerDeps(
        assignment_upload_legacy=assignment_upload_legacy,
        start_assignment_upload=start_assignment_upload,
        assignment_upload_status=assignment_upload_status,
        assignment_upload_draft=assignment_upload_draft,
        assignment_upload_draft_save=assignment_upload_draft_save,
        load_upload_job=load_upload_job,
        ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready,
        confirm_assignment_upload=confirm_assignment_upload,
        upload_job_path=upload_job_path,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_exam_upload_status_maps_error():
    def exam_upload_status(_job_id):
        raise ExamUploadApiError(400, "bad")

    deps = _exam_deps(exam_upload_status=exam_upload_status)

    with pytest.raises(HTTPException) as exc:
        await exam_upload_handlers.exam_upload_status("job-1", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_upload_start_maps_error(tmp_path):
    async def start_assignment_upload(**_kwargs):
        raise AssignmentUploadStartError(400, "bad")

    deps = _assignment_deps(tmp_path, start_assignment_upload=start_assignment_upload)

    with pytest.raises(HTTPException) as exc:
        await assignment_upload_handlers.assignment_upload_start(
            assignment_id="a1",
            date="",
            due_at="",
            scope="",
            class_name="",
            student_ids="",
            files=[],
            answer_files=None,
            ocr_mode="FREE_OCR",
            language="zh",
            deps=deps,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_upload_confirm_not_found(tmp_path):
    def load_upload_job(_job_id):
        raise FileNotFoundError("missing")

    deps = _assignment_deps(tmp_path, load_upload_job=load_upload_job)

    with pytest.raises(HTTPException) as exc:
        await assignment_upload_handlers.assignment_upload_confirm(
            UploadConfirmRequest(job_id="job-1"),
            deps=deps,
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_upload_confirm_returns_ready(tmp_path):
    def ensure_assignment_upload_confirm_ready(_job):
        return {"ok": True}

    deps = _assignment_deps(tmp_path, ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready)

    result = await assignment_upload_handlers.assignment_upload_confirm(
        UploadConfirmRequest(job_id="job-1"),
        deps=deps,
    )

    assert result == {"ok": True}
