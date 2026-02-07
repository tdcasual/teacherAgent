from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class StudentSubmitDeps:
    uploads_dir: Path
    app_root: Path
    student_submissions_dir: Path
    run_script: Callable[[list[str]], str]


async def submit(
    *,
    student_id: str,
    files: List[Any],
    assignment_id: Optional[str],
    auto_assignment: bool,
    deps: StudentSubmitDeps,
) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)

    file_paths: List[str] = []
    for upload_file in files:
        dest = deps.uploads_dir / upload_file.filename
        dest.write_bytes(await upload_file.read())
        file_paths.append(str(dest))

    script = deps.app_root / "scripts" / "grade_submission.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        student_id,
        "--out-dir",
        str(deps.student_submissions_dir),
        "--files",
        *file_paths,
    ]
    if assignment_id:
        args += ["--assignment-id", assignment_id]
    if auto_assignment or not assignment_id:
        args += ["--auto-assignment"]

    out = deps.run_script(args)
    return {"ok": True, "output": out}
