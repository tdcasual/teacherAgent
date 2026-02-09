import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from services.api.assignment_generate_service import AssignmentGenerateError
from services.api.handlers import assignment_io_handlers


def _deps(tmp_path, **overrides):
    def resolve_assignment_dir(assignment_id: str) -> Path:
        return Path(tmp_path) / assignment_id

    def sanitize_filename(name: str) -> str:
        return name

    def run_script(args):
        return "ok"

    async def assignment_questions_ocr(**_kwargs):
        return {"ok": True}

    def generate_assignment(**_kwargs):
        return {"ok": True}

    deps = assignment_io_handlers.AssignmentIoHandlerDeps(
        resolve_assignment_dir=resolve_assignment_dir,
        sanitize_filename=sanitize_filename,
        run_script=run_script,
        assignment_questions_ocr=assignment_questions_ocr,
        generate_assignment=generate_assignment,
        app_root=Path(tmp_path),
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_assignment_download_invalid_assignment(tmp_path):
    def resolve_assignment_dir(_assignment_id: str) -> Path:
        raise ValueError("bad id")

    deps = _deps(tmp_path, resolve_assignment_dir=resolve_assignment_dir)

    with pytest.raises(HTTPException) as exc:
        await assignment_io_handlers.assignment_download("bad", "file.txt", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_download_missing_source(tmp_path):
    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_io_handlers.assignment_download("a1", "file.txt", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_download_invalid_file(tmp_path):
    def sanitize_filename(_name: str) -> str:
        return ""

    assignment_dir = Path(tmp_path) / "a1"
    (assignment_dir / "source").mkdir(parents=True)

    deps = _deps(tmp_path, sanitize_filename=sanitize_filename)

    with pytest.raises(HTTPException) as exc:
        await assignment_io_handlers.assignment_download("a1", "bad", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_download_file_not_found(tmp_path):
    assignment_dir = Path(tmp_path) / "a1"
    (assignment_dir / "source").mkdir(parents=True)

    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_io_handlers.assignment_download("a1", "missing.txt", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_download_success(tmp_path):
    assignment_dir = Path(tmp_path) / "a1"
    source_dir = assignment_dir / "source"
    source_dir.mkdir(parents=True)
    file_path = source_dir / "ok.txt"
    file_path.write_text("data", encoding="utf-8")

    deps = _deps(tmp_path)

    result = await assignment_io_handlers.assignment_download("a1", "ok.txt", deps=deps)

    assert isinstance(result, FileResponse)


@pytest.mark.anyio
async def test_render_assignment_runs_script(tmp_path):
    calls = {}

    def run_script(args):
        calls["args"] = args
        return "done"

    deps = _deps(tmp_path, run_script=run_script)

    result = await assignment_io_handlers.render_assignment("a1", deps=deps)

    assert result == {"ok": True, "output": "done"}
    assert "render_assignment_pdf.py" in calls["args"][1]


@pytest.mark.anyio
async def test_assignment_questions_ocr_returns_result(tmp_path):
    async def assignment_questions_ocr(**_kwargs):
        return {"ok": True, "count": 1}

    deps = _deps(tmp_path, assignment_questions_ocr=assignment_questions_ocr)

    result = await assignment_io_handlers.assignment_questions_ocr(
        assignment_id="a1",
        files=[],
        kp_id="kp",
        difficulty="basic",
        tags="ocr",
        ocr_mode="FREE_OCR",
        language="zh",
        deps=deps,
    )

    assert result == {"ok": True, "count": 1}


@pytest.mark.anyio
async def test_generate_assignment_maps_error(tmp_path):
    def generate_assignment(**_kwargs):
        raise AssignmentGenerateError(400, "bad")

    deps = _deps(tmp_path, generate_assignment=generate_assignment)

    with pytest.raises(HTTPException) as exc:
        await assignment_io_handlers.generate_assignment(
            assignment_id="a1",
            kp="",
            question_ids="",
            per_kp=5,
            core_examples="",
            generate=False,
            mode="",
            date="",
            due_at="",
            class_name="",
            student_ids="",
            source="",
            requirements_json="",
            deps=deps,
        )

    assert exc.value.status_code == 400
