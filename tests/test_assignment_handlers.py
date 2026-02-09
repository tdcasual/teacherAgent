import pytest
from fastapi import HTTPException
from pathlib import Path

from services.api.api_models import AssignmentRequirementsRequest
from services.api.handlers import assignment_handlers


def _deps(tmp_path, **overrides):
    def list_assignments():
        return {"assignments": []}

    def compute_assignment_progress(assignment_id: str, include_students: bool = True):
        return {"ok": True, "assignment_id": assignment_id, "updated_at": "2024-01-01T00:00:00"}

    def parse_date_str(value):
        return str(value or "")

    def save_assignment_requirements(assignment_id, requirements, date_str, created_by):
        return {"ok": True, "assignment_id": assignment_id}

    def resolve_assignment_dir(assignment_id: str) -> Path:
        return Path(tmp_path) / assignment_id

    def load_assignment_requirements(folder: Path):
        return {"difficulty": "medium"}

    def assignment_today(**_kwargs):
        return {"ok": True}

    def get_assignment_detail_api(_assignment_id: str):
        return {"ok": True}

    deps = assignment_handlers.AssignmentHandlerDeps(
        list_assignments=list_assignments,
        compute_assignment_progress=compute_assignment_progress,
        parse_date_str=parse_date_str,
        save_assignment_requirements=save_assignment_requirements,
        resolve_assignment_dir=resolve_assignment_dir,
        load_assignment_requirements=load_assignment_requirements,
        assignment_today=assignment_today,
        get_assignment_detail_api=get_assignment_detail_api,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_assignment_requirements_maps_error(tmp_path):
    def save_assignment_requirements(*_args, **_kwargs):
        return {"error": "bad"}

    deps = _deps(tmp_path, save_assignment_requirements=save_assignment_requirements)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements(
            AssignmentRequirementsRequest(assignment_id="a1", requirements={}),
            deps=deps,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_requirements_get_invalid_id(tmp_path):
    def resolve_assignment_dir(_assignment_id: str):
        raise ValueError("invalid assignment_id")

    deps = _deps(tmp_path, resolve_assignment_dir=resolve_assignment_dir)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements_get("bad", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_requirements_get_missing(tmp_path):
    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements_get("missing", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_detail_maps_not_found(tmp_path):
    def get_assignment_detail_api(_assignment_id: str):
        return {"error": "assignment_not_found"}

    deps = _deps(tmp_path, get_assignment_detail_api=get_assignment_detail_api)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_detail("a1", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_teacher_assignment_progress_requires_id(tmp_path):
    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.teacher_assignment_progress("", include_students=True, deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_teacher_assignment_progress_maps_not_found(tmp_path):
    def compute_assignment_progress(_assignment_id: str, include_students: bool = True):
        return {"ok": False, "error": "assignment_not_found"}

    deps = _deps(tmp_path, compute_assignment_progress=compute_assignment_progress)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.teacher_assignment_progress("a1", include_students=True, deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_teacher_assignments_progress_filters_and_sorts(tmp_path):
    def parse_date_str(_value):
        return "2024-01-02"

    def list_assignments():
        return {
            "assignments": [
                {"assignment_id": "a1", "date": "2024-01-02"},
                {"assignment_id": "a2", "date": "2024-01-02"},
                {"assignment_id": "a3", "date": "2024-01-01"},
            ]
        }

    def compute_assignment_progress(assignment_id: str, include_students: bool = False):
        updated = "2024-01-02T09:00:00" if assignment_id == "a1" else "2024-01-02T10:00:00"
        return {"ok": True, "assignment_id": assignment_id, "updated_at": updated}

    deps = _deps(
        tmp_path,
        parse_date_str=parse_date_str,
        list_assignments=list_assignments,
        compute_assignment_progress=compute_assignment_progress,
    )

    result = await assignment_handlers.teacher_assignments_progress(date="ignored", deps=deps)

    assert [item["assignment_id"] for item in result["assignments"]] == ["a2", "a1"]


@pytest.mark.anyio
async def test_assignment_today_returns_result(tmp_path):
    def assignment_today(**kwargs):
        return {"ok": True, "student_id": kwargs["student_id"]}

    deps = _deps(tmp_path, assignment_today=assignment_today)

    result = await assignment_handlers.assignment_today(
        student_id="s1",
        date=None,
        auto_generate=False,
        generate=True,
        per_kp=5,
        deps=deps,
    )

    assert result == {"ok": True, "student_id": "s1"}
