from pathlib import Path

import pytest
from fastapi import HTTPException

from services.api.api_models import UploadConfirmRequest, UploadDraftSaveRequest
from services.api.assignment_upload_start_service import AssignmentUploadStartError
from services.api.handlers import assignment_upload_handlers


def _assignment_deps(tmp_path, **overrides):
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

    def finalize_published_from_folder(*_args, **_kwargs):
        return {"ok": True, "via": "folder"}

    def save_assignment_folder_draft(*_args, **_kwargs):
        return {"ok": True, "via": "folder_save"}

    def get_assignment_folder_draft(*_args, **_kwargs):
        return {"ok": True, "draft": {}}

    deps = assignment_upload_handlers.AssignmentUploadHandlerDeps(
        start_assignment_upload=start_assignment_upload,
        assignment_upload_status=assignment_upload_status,
        assignment_upload_draft=assignment_upload_draft,
        assignment_upload_draft_save=assignment_upload_draft_save,
        load_upload_job=load_upload_job,
        ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready,
        confirm_assignment_upload=confirm_assignment_upload,
        upload_job_path=upload_job_path,
        finalize_published_from_folder=finalize_published_from_folder,
        save_assignment_folder_draft=save_assignment_folder_draft,
        get_assignment_folder_draft=get_assignment_folder_draft,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps



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
            subject_id="physics",
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

    deps = _assignment_deps(
        tmp_path, ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready
    )

    result = await assignment_upload_handlers.assignment_upload_confirm(
        UploadConfirmRequest(job_id="job-1"),
        deps=deps,
    )

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_confirm_without_job_id_calls_folder_finalize(tmp_path):
    called = {}

    def finalize_published_from_folder(assignment_id, **kwargs):
        called["assignment_id"] = assignment_id
        called["kwargs"] = kwargs
        return {"ok": True, "assignment_id": assignment_id}

    def load_upload_job(_job_id):
        raise AssertionError("should not load job")

    deps = _assignment_deps(
        tmp_path,
        finalize_published_from_folder=finalize_published_from_folder,
        load_upload_job=load_upload_job,
    )
    result = await assignment_upload_handlers.assignment_upload_confirm(
        UploadConfirmRequest(assignment_id="A1"),
        deps=deps,
    )
    assert result["ok"] is True
    assert called["assignment_id"] == "A1"


@pytest.mark.anyio
async def test_draft_save_without_job_id_writes_folder(tmp_path):
    called = {}

    def save_assignment_folder_draft(assignment_id, requirements, questions):
        called["assignment_id"] = assignment_id
        called["requirements"] = requirements
        called["questions"] = questions
        return {"ok": True, "assignment_id": assignment_id}

    def assignment_upload_draft_save(*_args, **_kwargs):
        raise AssertionError("should not save job draft")

    deps = _assignment_deps(
        tmp_path,
        save_assignment_folder_draft=save_assignment_folder_draft,
        assignment_upload_draft_save=assignment_upload_draft_save,
    )
    result = await assignment_upload_handlers.assignment_upload_draft_save(
        UploadDraftSaveRequest(assignment_id="A1", requirements={"brief": "x"}, questions=[]),
        deps=deps,
    )
    assert result["ok"] is True
    assert called["assignment_id"] == "A1"
