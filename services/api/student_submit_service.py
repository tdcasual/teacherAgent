from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .student_ops_service import (
    STUDENT_ALLOWED_SUFFIXES,
    UploadLimitError,
    raise_upload_limit_http,
    save_capped_uploads,
)


class StudentSubmitError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "student_submit_error")


def _default_sanitize_filename(name: str) -> str:
    return Path(str(name or "").strip()).name


_SAFE_ID_RE = re.compile(r"^[\w-]+$")


def _require_safe_id(value: str, field: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise StudentSubmitError(400, f"{field} is required")
    if not _SAFE_ID_RE.fullmatch(token):
        raise StudentSubmitError(400, f"invalid_{field}")
    return token


@dataclass(frozen=True)
class StudentSubmitDeps:
    uploads_dir: Path
    app_root: Path
    student_submissions_dir: Path
    run_script: Callable[[list[str]], str]
    compute_assignment_progress: Callable[[str, bool], Dict[str, Any]]
    student_memory_auto_propose_from_assignment_evidence: Callable[..., Dict[str, Any]]
    load_assignment_teacher_id: Callable[[str], Optional[str]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename
    trigger_process_archive: Optional[Callable[..., Dict[str, Any]]] = None
    authorize_student_submit: Optional[Callable[[str, str], None]] = None


def authorize_student_submit_assignment(
    assignment_id: str,
    student_id: str,
    *,
    load_meta: Callable[[str], Optional[Dict[str, Any]]],
    student_enrolled: Callable[..., bool],
    is_sql_published: Optional[Callable[[str], bool]] = None,
) -> None:
    from .assignment.visibility import (
        assignment_owner_id,
        effective_visibility_status,
        snapshot_student_ids,
    )

    meta = load_meta(assignment_id)
    if not isinstance(meta, dict) or not meta:
        raise StudentSubmitError(404, "assignment not found")
    published = (
        bool(is_sql_published(assignment_id))
        if is_sql_published is not None
        else effective_visibility_status(meta) == "published"
    )
    if not published:
        raise StudentSubmitError(403, "forbidden_assignment_scope")
    if student_id not in snapshot_student_ids(meta):
        raise StudentSubmitError(403, "forbidden_assignment_scope")
    teacher_id = assignment_owner_id(meta)
    subject_id = str(meta.get("subject_id") or "").strip()
    if not teacher_id or not subject_id:
        raise StudentSubmitError(403, "forbidden_assignment_scope")
    scope = str(meta.get("scope") or "").strip().lower()
    class_name = str(meta.get("class_name") or "").strip() if scope == "class" else ""
    if not student_enrolled(student_id, teacher_id, subject_id, class_name):
        raise StudentSubmitError(403, "forbidden_assignment_scope")


def _require_assignment_id(assignment_id: Optional[str], auto_assignment: bool) -> str:
    if bool(auto_assignment):
        raise StudentSubmitError(400, "auto_assignment_disabled")
    token = str(assignment_id or "").strip()
    if not token:
        raise StudentSubmitError(400, "assignment_id_required")
    return _require_safe_id(token, "assignment_id")


def _find_student_evidence(
    *,
    progress: Dict[str, Any],
    student_id: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(progress, dict) or not bool(progress.get("ok")):
        return None
    students = progress.get("students")
    if not isinstance(students, list):
        return None
    for item in students:
        if not isinstance(item, dict):
            continue
        if str(item.get("student_id") or "").strip() != student_id:
            continue
        evidence = item.get("evidence")
        if isinstance(evidence, dict):
            return evidence
        return None
    return None


def _progress_signals(progress: Dict[str, Any], student_id: str) -> Dict[str, Any]:
    evidence = _find_student_evidence(progress=progress, student_id=student_id)
    if not isinstance(evidence, dict):
        return {}
    signals = evidence.get("signals")
    return signals if isinstance(signals, dict) else {}


def _official_score(signals: Dict[str, Any]) -> Optional[float]:
    for key in ("official_score", "best_score_earned"):
        raw = signals.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _submit_reason(progress: Dict[str, Any], student_id: str, signals: Dict[str, Any]) -> str:
    if bool(signals.get("submitted")):
        return ""
    if _find_student_evidence(progress=progress, student_id=student_id) is None:
        return "progress_unavailable"
    return "min_graded_total"


def _submit_payload(
    *,
    assignment_id: str,
    output: str,
    progress: Dict[str, Any],
    student_id: str,
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    submitted = bool(signals.get("submitted"))
    payload: Dict[str, Any] = {
        "ok": True,
        "submitted": submitted,
        "assignment_id": assignment_id,
        "attempt_id": str(signals.get("best_attempt_id") or ""),
        "official_score": _official_score(signals) if submitted else None,
        "output": output,
        "process_archive_id": "",
        "process_archive_status": "none",
    }
    if not submitted:
        payload["reason"] = _submit_reason(progress, student_id, signals)
    return payload


def _maybe_propose_memory(
    *,
    deps: StudentSubmitDeps,
    student_id: str,
    assignment_id: str,
    progress: Dict[str, Any],
) -> None:
    evidence = _find_student_evidence(progress=progress, student_id=student_id)
    if not evidence:
        return
    teacher_id = str(deps.load_assignment_teacher_id(assignment_id) or "").strip()
    if not teacher_id:
        return
    try:
        auto = deps.student_memory_auto_propose_from_assignment_evidence(
            teacher_id=teacher_id,
            student_id=student_id,
            assignment_id=assignment_id,
            evidence=evidence,
            request_id=None,
        )
    except Exception as exc:  # policy: allowed-broad-except
        deps.diag_log(
            "student.memory.assignment_evidence.failed",
            {"student_id": student_id, "assignment_id": assignment_id, "error": str(exc)[:200]},
        )
        return
    if not bool(auto.get("created")):
        return
    deps.diag_log(
        "student.memory.assignment_evidence.proposed",
        {
            "teacher_id": str(auto.get("teacher_id") or teacher_id),
            "student_id": student_id,
            "assignment_id": assignment_id,
            "proposal_id": str(auto.get("proposal_id") or ""),
            "memory_type": str(auto.get("memory_type") or ""),
        },
    )


def _attach_process_archive(
    payload: Dict[str, Any],
    *,
    deps: StudentSubmitDeps,
    assignment_id: str,
    student_id: str,
) -> None:
    trigger = deps.trigger_process_archive
    if trigger is None:
        return
    try:
        archive = trigger(assignment_id=assignment_id, student_id=student_id, reason="submit")
    except Exception as exc:  # policy: allowed-broad-except
        deps.diag_log(
            "process_archive.trigger.failed",
            {"assignment_id": assignment_id, "student_id": student_id, "error": str(exc)[:200]},
        )
        payload["process_archive_status"] = "pending"
        payload["process_archive_id"] = ""
        return
    if not isinstance(archive, dict):
        payload["process_archive_status"] = "pending"
        return
    payload["process_archive_id"] = str(archive.get("job_id") or archive.get("process_archive_id") or "")
    payload["process_archive_status"] = str(archive.get("status") or "pending")


def _read_progress(deps: StudentSubmitDeps, assignment_id: str, student_id: str) -> Dict[str, Any]:
    try:
        progress = deps.compute_assignment_progress(assignment_id, True)
    except Exception as exc:  # policy: allowed-broad-except
        deps.diag_log(
            "student.submit.progress.failed",
            {"student_id": student_id, "assignment_id": assignment_id, "error": str(exc)[:200]},
        )
        return {}
    return progress if isinstance(progress, dict) else {}


def _is_grade_script_http_failure(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    try:
        return int(status) >= 500
    except (TypeError, ValueError):
        return False


def _grade_script_error_text(exc: Exception) -> str:
    if isinstance(exc, TimeoutExpired):
        return "grade_script_timeout"
    detail = getattr(exc, "detail", None)
    if detail:
        return str(detail)[:500]
    return str(exc)[:500]


def _copy_saved_uploads(attempt_dir: Path, file_paths: list[str]) -> list[str]:
    files_dir = attempt_dir / "files"
    linked: list[str] = []
    for index, raw in enumerate(file_paths):
        src = Path(str(raw or ""))
        if not src.is_file():
            if str(raw or "").strip():
                linked.append(str(src))
            continue
        files_dir.mkdir(parents=True, exist_ok=True)
        dest = files_dir / (src.name or f"upload_{index}")
        if dest.exists():
            dest = files_dir / f"{src.stem}_{index}{src.suffix}"
        try:
            dest.write_bytes(src.read_bytes())
        except OSError:
            linked.append(str(src))
            continue
        linked.append(str(dest))
    return linked


def _write_ungraded_grading_report(
    *,
    deps: StudentSubmitDeps,
    assignment_id: str,
    student_id: str,
    error: str,
    file_paths: list[str],
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    attempt_dir = deps.student_submissions_dir / assignment_id / student_id / f"submission_{timestamp}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    linked = _copy_saved_uploads(attempt_dir, file_paths)
    report = {
        "student_id": student_id,
        "assignment_id": assignment_id,
        "graded_total": 0,
        "ungraded": 1,
        "correct": 0,
        "error": error,
        "files": linked,
        "items": [
            {
                "status": "ungraded",
                "confidence": 0.0,
                "score": 0.0,
                "reason": "auto_grade_failed",
            }
        ],
    }
    (attempt_dir / "grading_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return f"ungraded: {error}"


def _record_ungraded_grade(
    deps: StudentSubmitDeps,
    assignment_id: str,
    student_id: str,
    exc: Exception,
    file_paths: list[str],
) -> str:
    error = _grade_script_error_text(exc)
    deps.diag_log(
        "student.submit.grade_script.failed",
        {"student_id": student_id, "assignment_id": assignment_id, "error": error[:200]},
    )
    return _write_ungraded_grading_report(
        deps=deps,
        assignment_id=assignment_id,
        student_id=student_id,
        error=error,
        file_paths=file_paths,
    )


def _run_grade_script(
    deps: StudentSubmitDeps,
    args: list[str],
    *,
    assignment_id: str,
    student_id: str,
    file_paths: list[str],
) -> str:
    try:
        return deps.run_script(args)
    except TimeoutExpired as exc:
        return _record_ungraded_grade(deps, assignment_id, student_id, exc, file_paths)
    except Exception as exc:  # policy: allowed-broad-except
        if not _is_grade_script_http_failure(exc):
            raise
        return _record_ungraded_grade(deps, assignment_id, student_id, exc, file_paths)


async def submit(
    *,
    student_id: str,
    files: List[Any],
    assignment_id: Optional[str],
    auto_assignment: bool,
    deps: StudentSubmitDeps,
) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_student_id = _require_safe_id(student_id, "student_id")
    safe_assignment_id = _require_assignment_id(assignment_id, auto_assignment)
    if deps.authorize_student_submit is not None:
        deps.authorize_student_submit(safe_assignment_id, safe_student_id)

    try:
        saved = await save_capped_uploads(
            files,
            target_dir=deps.uploads_dir,
            sanitize_filename=deps.sanitize_filename,
            save_upload_file=deps.save_upload_file,
            allowed_suffixes=STUDENT_ALLOWED_SUFFIXES,
        )
    except UploadLimitError as exc:
        raise_upload_limit_http(exc)
    file_paths = [str(path) for path in saved]

    script = deps.app_root / "scripts" / "grade_submission.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        safe_student_id,
        "--out-dir",
        str(deps.student_submissions_dir),
        "--files",
        *file_paths,
        "--assignment-id",
        safe_assignment_id,
    ]
    out = _run_grade_script(
        deps,
        args,
        assignment_id=safe_assignment_id,
        student_id=safe_student_id,
        file_paths=file_paths,
    )
    progress = _read_progress(deps, safe_assignment_id, safe_student_id)
    signals = _progress_signals(progress, safe_student_id)
    payload = _submit_payload(
        assignment_id=safe_assignment_id,
        output=out,
        progress=progress,
        student_id=safe_student_id,
        signals=signals,
    )
    if bool(signals.get("submitted")):
        _maybe_propose_memory(
            deps=deps,
            student_id=safe_student_id,
            assignment_id=safe_assignment_id,
            progress=progress,
        )
        _attach_process_archive(
            payload,
            deps=deps,
            assignment_id=safe_assignment_id,
            student_id=safe_student_id,
        )
    return payload
