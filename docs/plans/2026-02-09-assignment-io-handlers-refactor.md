# Assignment IO Handlers Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract assignment IO/script endpoints (download/render/ocr/generate) into a dedicated handler module so `app_core.py` only wires deps and delegates.

**Architecture:** Introduce `handlers/assignment_io_handlers.py` with a deps dataclass that wraps filesystem helpers, script runner, OCR service, and generator service. `app_core.py` builds deps (binding existing service deps) and delegates. Error mapping stays in handlers for testability.

**Tech Stack:** Python 3.11, FastAPI, pytest (anyio)

---

### Task 1: Add assignment IO handlers + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_io_handlers.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_assignment_io_handlers.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_assignment_io_handlers.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assignment_io_handlers.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_io_handlers.py`:

```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..assignment_generate_service import AssignmentGenerateError


@dataclass
class AssignmentIoHandlerDeps:
    resolve_assignment_dir: Callable[[str], Path]
    sanitize_filename: Callable[[str], str]
    run_script: Callable[[list[str]], str]
    assignment_questions_ocr: Callable[..., Any]
    generate_assignment: Callable[..., Any]
    app_root: Path


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignment_download(assignment_id: str, file: str, *, deps: AssignmentIoHandlerDeps):
    try:
        assignment_dir = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    folder = (assignment_dir / "source").resolve()
    if assignment_dir not in folder.parents:
        raise HTTPException(status_code=400, detail="invalid assignment_id path")
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment source not found")
    safe_name = deps.sanitize_filename(file)
    if not safe_name:
        raise HTTPException(status_code=400, detail="invalid file")
    path = (folder / safe_name).resolve()
    if path != folder and folder not in path.parents:
        raise HTTPException(status_code=400, detail="invalid file path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


async def render_assignment(assignment_id: str, *, deps: AssignmentIoHandlerDeps):
    script = deps.app_root / "scripts" / "render_assignment_pdf.py"
    out = deps.run_script(["python3", str(script), "--assignment-id", assignment_id])
    return {"ok": True, "output": out}


async def assignment_questions_ocr(
    *,
    assignment_id: str,
    files,
    kp_id: Optional[str],
    difficulty: Optional[str],
    tags: Optional[str],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentIoHandlerDeps,
):
    return await _maybe_await(
        deps.assignment_questions_ocr(
            assignment_id=assignment_id,
            files=files,
            kp_id=kp_id,
            difficulty=difficulty,
            tags=tags,
            ocr_mode=ocr_mode,
            language=language,
        )
    )


async def generate_assignment(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate: bool,
    mode: Optional[str],
    date: Optional[str],
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    deps: AssignmentIoHandlerDeps,
):
    try:
        return await _maybe_await(
            deps.generate_assignment(
                assignment_id=assignment_id,
                kp=kp,
                question_ids=question_ids,
                per_kp=per_kp,
                core_examples=core_examples,
                generate=generate,
                mode=mode,
                date=date,
                due_at=due_at,
                class_name=class_name,
                student_ids=student_ids,
                source=source,
                requirements_json=requirements_json,
            )
        )
    except AssignmentGenerateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assignment_io_handlers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/handlers/assignment_io_handlers.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_assignment_io_handlers.py
git commit -m "refactor: add assignment io handlers"
```

---

### Task 2: Delegate assignment IO endpoints to handlers

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`

**Step 1: Write failing test (if needed)**

No new route tests required beyond Task 1; keep existing route tests intact.

**Step 2: Update app_core to use handlers**

In `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

- Import handler module:

```python
from .handlers import assignment_io_handlers
```

- Add deps builder near other handlers deps:

```python
def _assignment_io_handlers_deps() -> assignment_io_handlers.AssignmentIoHandlerDeps:
    return assignment_io_handlers.AssignmentIoHandlerDeps(
        resolve_assignment_dir=resolve_assignment_dir,
        sanitize_filename=sanitize_filename,
        run_script=run_script,
        assignment_questions_ocr=lambda **kwargs: _assignment_questions_ocr_impl(
            deps=_assignment_questions_ocr_deps(),
            **kwargs,
        ),
        generate_assignment=lambda **kwargs: _generate_assignment_impl(
            deps=_assignment_generate_deps(),
            **kwargs,
        ),
        app_root=APP_ROOT,
    )
```

- Replace endpoint bodies to delegate:

```python
async def assignment_download(assignment_id: str, file: str):
    return await assignment_io_handlers.assignment_download(
        assignment_id,
        file,
        deps=_assignment_io_handlers_deps(),
    )

async def render_assignment(assignment_id: str = Form(...)):
    return await assignment_io_handlers.render_assignment(assignment_id, deps=_assignment_io_handlers_deps())

async def assignment_questions_ocr(
    assignment_id: str = Form(...),
    files: list[UploadFile] = File(...),
    kp_id: Optional[str] = Form("uncategorized"),
    difficulty: Optional[str] = Form("basic"),
    tags: Optional[str] = Form("ocr"),
    ocr_mode: Optional[str] = Form("FREE_OCR"),
    language: Optional[str] = Form("zh"),
):
    return await assignment_io_handlers.assignment_questions_ocr(
        assignment_id=assignment_id,
        files=files,
        kp_id=kp_id,
        difficulty=difficulty,
        tags=tags,
        ocr_mode=ocr_mode,
        language=language,
        deps=_assignment_io_handlers_deps(),
    )

async def generate_assignment(
    assignment_id: str = Form(...),
    kp: str = Form(""),
    question_ids: Optional[str] = Form(""),
    per_kp: int = Form(5),
    core_examples: Optional[str] = Form(""),
    generate: bool = Form(False),
    mode: Optional[str] = Form(""),
    date: Optional[str] = Form(""),
    due_at: Optional[str] = Form(""),
    class_name: Optional[str] = Form(""),
    student_ids: Optional[str] = Form(""),
    source: Optional[str] = Form(""),
    requirements_json: Optional[str] = Form(""),
):
    return await assignment_io_handlers.generate_assignment(
        assignment_id=assignment_id,
        kp=kp,
        question_ids=question_ids,
        per_kp=per_kp,
        core_examples=core_examples,
        generate=generate,
        mode=mode,
        date=date,
        due_at=due_at,
        class_name=class_name,
        student_ids=student_ids,
        source=source,
        requirements_json=requirements_json,
        deps=_assignment_io_handlers_deps(),
    )
```

**Step 3: Run targeted tests**

Run:
- `python3 -m pytest tests/test_assignment_io_handlers.py -v`
- `python3 -m pytest tests/test_app_queue_backend_mode.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py
git commit -m "refactor: delegate assignment io endpoints"
```

---

### Task 3: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_assignment_io_handlers.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```
