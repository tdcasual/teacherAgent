from __future__ import annotations

import json
import logging
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .assignment_catalog_service import effective_assignment_kind
from .assignment_context_service import load_practice_stems
from .assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    list_submission_attempts,
)
from .profile_service import load_profile_file
from .question_bank_select_service import (
    pick_practice_items,
    read_question_bank,
    write_questions_csv,
)
from .student_ops_service import (
    STUDENT_ALLOWED_SUFFIXES,
    UploadLimitError,
    raise_upload_limit_http,
    save_capped_uploads,
)
from .student_submit_service import (
    StudentSubmitError,
    _copy_saved_uploads,
    _write_derived_profile,
)

_log = logging.getLogger(__name__)
_SAFE_ID_RE = __import__("re").compile(r"^[\w-]+$")
PRACTICE_PREFIX = "practice_"
BANK_MISS_NAME = "bank_miss.json"
PRACTICE_SCHEMA = "practice_attempt/v1"


class StudentPracticeError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "student_practice_error")


@dataclass(frozen=True)
class StudentPracticeDeps:
    data_dir: Path
    app_root: Path
    student_submissions_dir: Path
    uploads_dir: Path
    run_script: Callable[[list[str]], str]
    diag_log: Callable[[str, Dict[str, Any]], None]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    sanitize_filename: Callable[[str], str]
    authorize_student_submit: Optional[Callable[[str, str], None]] = None
    grade_count_conf_threshold: float = 0.6
    now_iso: Callable[[], str] = lambda: datetime.now().isoformat(timespec="seconds")


def require_practice_actor(principal: Any) -> str:
    actor = str(getattr(principal, "actor_id", "") or "").strip()
    if principal is None or not actor:
        raise StudentPracticeError(400, "principal_required")
    return actor


def _require_safe_id(value: str, field: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise StudentPracticeError(400, f"{field} is required")
    if not _SAFE_ID_RE.fullmatch(token):
        raise StudentPracticeError(400, f"invalid_{field}")
    return token


def _student_root(deps: StudentPracticeDeps, assignment_id: str, student_id: str) -> Path:
    root = Path(deps.student_submissions_dir).resolve()
    target = (root / assignment_id / student_id).resolve()
    if target == root or root not in target.parents:
        raise StudentPracticeError(400, "invalid_assignment_id")
    return target


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_assignment_meta(deps: StudentPracticeDeps, assignment_id: str) -> Dict[str, Any]:
    folder = Path(deps.data_dir) / "assignments" / assignment_id
    return _load_json(folder / "meta.json")


def _allow_practice(meta: Dict[str, Any]) -> bool:
    kind = effective_assignment_kind(meta)
    if kind != "problem_set":
        return False
    policy = meta.get("completion_policy")
    if not isinstance(policy, dict) or "allow_practice" not in policy:
        return True
    return bool(policy.get("allow_practice"))


def _assert_practice_applicable(
    meta: Dict[str, Any],
    *,
    assignment_id: str = "",
    student_id: str = "",
    diag_log: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> None:
    if _allow_practice(meta):
        return
    if diag_log is not None:
        diag_log(
            "student.practice.practice_not_applicable",
            {"student_id": student_id, "assignment_id": assignment_id},
        )
    raise StudentPracticeError(409, "practice_not_applicable")


def _attempt_deps(deps: StudentPracticeDeps) -> AssignmentSubmissionAttemptDeps:
    return AssignmentSubmissionAttemptDeps(
        student_submissions_dir=Path(deps.student_submissions_dir),
        grade_count_conf_threshold=float(deps.grade_count_conf_threshold),
    )


def _homework_submitted(deps: StudentPracticeDeps, assignment_id: str, student_id: str) -> bool:
    attempts = list_submission_attempts(assignment_id, student_id, deps=_attempt_deps(deps))
    return any(isinstance(item, dict) and item.get("valid_submission") for item in attempts)


def _authorize(deps: StudentPracticeDeps, assignment_id: str, student_id: str) -> None:
    if deps.authorize_student_submit is None:
        return
    try:
        deps.authorize_student_submit(assignment_id, student_id)
    except StudentSubmitError as exc:
        raise StudentPracticeError(exc.status_code, exc.detail) from exc


def _iter_practice_dirs(root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob(f"{PRACTICE_PREFIX}*") if path.is_dir())


def _practice_meta(practice_dir: Path) -> Dict[str, Any]:
    payload = _load_json(practice_dir / "meta.json")
    if not payload:
        has_report = (practice_dir / "grading_report.json").exists()
        payload = {
            "practice_id": practice_dir.name,
            "status": "submitted" if has_report else "open",
        }
    return payload


def practice_status_counts(
    data_dir: Path,
    assignment_id: str,
    student_id: str,
) -> Dict[str, Any]:
    root = Path(data_dir) / "student_submissions" / assignment_id / student_id
    assigned = 0
    submitted = 0
    open_count = 0
    for practice_dir in _iter_practice_dirs(root):
        assigned += 1
        status = str(_practice_meta(practice_dir).get("status") or "").strip().lower()
        if status == "submitted":
            submitted += 1
        else:
            open_count += 1
    return {
        "assigned": assigned,
        "submitted": submitted,
        "open": open_count,
        "bank_miss": (root / BANK_MISS_NAME).is_file(),
    }


def history_practice_counts(
    data_dir: Path,
    assignment_id: str,
    student_id: str,
) -> Dict[str, Any]:
    summary = practice_status_counts(data_dir, assignment_id, student_id)
    return {
        "open": int(summary.get("open") or 0),
        "submitted": int(summary.get("submitted") or 0),
        "bank_miss": bool(summary.get("bank_miss")),
    }


def _find_open_practice(root: Path) -> Optional[Path]:
    for practice_dir in _iter_practice_dirs(root):
        status = str(_practice_meta(practice_dir).get("status") or "").strip().lower()
        if status != "submitted":
            return practice_dir
    return None


def _add_question_ids(excluded: Set[str], values: Any) -> None:
    if not isinstance(values, list):
        return
    for qid in values:
        token = str(qid or "").strip()
        if token:
            excluded.add(token)


def _csv_question_ids(path: Path) -> Set[str]:
    found: Set[str] = set()
    if not path.is_file():
        return found
    for row in read_question_bank(path):
        qid = str(row.get("question_id") or "").strip()
        if qid:
            found.add(qid)
    return found


def _excluded_question_ids(
    deps: StudentPracticeDeps,
    assignment_id: str,
    student_id: str,
    root: Path,
) -> Set[str]:
    excluded = _csv_question_ids(Path(deps.data_dir) / "assignments" / assignment_id / "questions.csv")
    for practice_dir in _iter_practice_dirs(root):
        _add_question_ids(excluded, _practice_meta(practice_dir).get("question_ids"))
        excluded.update(_csv_question_ids(practice_dir / "questions.csv"))
    profile_path = Path(deps.data_dir) / "student_profiles" / f"{student_id}.json"
    profile = load_profile_file(profile_path) if profile_path.exists() else {}
    for entry in profile.get("practice_history") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("assignment_id") or "").strip() != assignment_id:
            continue
        _add_question_ids(excluded, entry.get("question_ids"))
    return excluded


def _kp_list(deps: StudentPracticeDeps, assignment_id: str, student_id: str) -> list[str]:
    profile_path = Path(deps.data_dir) / "student_profiles" / f"{student_id}.json"
    profile = load_profile_file(profile_path) if profile_path.exists() else {}
    kps: list[str] = []
    for item in profile.get("recent_weak_kp") or []:
        text = str(item or "").strip()
        if text and text not in kps:
            kps.append(text)
    next_focus = str(profile.get("next_focus") or "").strip()
    if next_focus and next_focus not in kps:
        kps.append(next_focus)
    meta = _load_assignment_meta(deps, assignment_id)
    for item in meta.get("target_kp") or []:
        text = str(item or "").strip()
        if text and text not in kps:
            kps.append(text)
    req_path = Path(deps.data_dir) / "assignments" / assignment_id / "requirements.json"
    requirements = _load_json(req_path)
    for item in requirements.get("core_concepts") or []:
        text = str(item or "").strip()
        if text and text not in kps:
            kps.append(text)
    return kps


def _bank_miss_path(root: Path) -> Path:
    return root / BANK_MISS_NAME


def _write_bank_miss(root: Path, assignment_id: str, student_id: str, now_iso: str) -> None:
    _dump_json(
        _bank_miss_path(root),
        {
            "assignment_id": assignment_id,
            "student_id": student_id,
            "created_at": now_iso,
            "reason": "question_bank_insufficient",
        },
    )


def _clear_bank_miss(root: Path) -> None:
    path = _bank_miss_path(root)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        _log.debug("failed to clear bank_miss.json", exc_info=True)


def _new_practice_id() -> str:
    return PRACTICE_PREFIX + secrets.token_hex(6)


def _practice_public(deps: StudentPracticeDeps, practice_dir: Path) -> Dict[str, Any]:
    meta = _practice_meta(practice_dir)
    stems = load_practice_stems(
        practice_dir,
        data_dir=Path(deps.data_dir),
        app_root=Path(deps.app_root),
    )
    return {
        "practice_id": str(meta.get("practice_id") or practice_dir.name),
        "assignment_id": str(meta.get("assignment_id") or ""),
        "status": str(meta.get("status") or "open"),
        "question_ids": list(meta.get("question_ids") or []),
        "questions": stems,
    }


def _gate_recommend(
    deps: StudentPracticeDeps, assignment_id: str, student_id: str
) -> Dict[str, Any]:
    _authorize(deps, assignment_id, student_id)
    meta = _load_assignment_meta(deps, assignment_id)
    _assert_practice_applicable(
        meta, assignment_id=assignment_id, student_id=student_id, diag_log=deps.diag_log
    )
    if not _homework_submitted(deps, assignment_id, student_id):
        deps.diag_log(
            "student.practice.homework_not_submitted",
            {"student_id": student_id, "assignment_id": assignment_id},
        )
        raise StudentPracticeError(409, "homework_not_submitted")
    return meta


def recommend_practice(
    assignment_id: str,
    *,
    student_id: str,
    deps: StudentPracticeDeps,
) -> Dict[str, Any]:
    aid = _require_safe_id(assignment_id, "assignment_id")
    sid = _require_safe_id(student_id, "student_id")
    meta = _gate_recommend(deps, aid, sid)
    root = _student_root(deps, aid, sid)
    existing = _find_open_practice(root)
    if existing is not None:
        payload = _practice_public(deps, existing)
        payload["ok"] = True
        return payload
    pick = pick_practice_items(
        data_dir=Path(deps.data_dir),
        app_root=Path(deps.app_root),
        kp_list=_kp_list(deps, aid, sid),
        excluded_ids=_excluded_question_ids(deps, aid, sid, root),
        count=3,
    )
    if not pick.get("ok"):
        root.mkdir(parents=True, exist_ok=True)
        _write_bank_miss(root, aid, sid, deps.now_iso())
        deps.diag_log(
            "student.practice.bank_miss",
            {"student_id": sid, "assignment_id": aid},
        )
        raise StudentPracticeError(409, "question_bank_insufficient")
    items = [row for row in (pick.get("items") or []) if isinstance(row, dict)]
    practice_id = _new_practice_id()
    practice_dir = root / practice_id
    practice_dir.mkdir(parents=True, exist_ok=True)
    write_questions_csv(practice_dir / "questions.csv", items)
    question_ids = [
        str(row.get("question_id") or "").strip()
        for row in items
        if str(row.get("question_id") or "").strip()
    ]
    kp_ids = []
    for row in items:
        kp = str(row.get("kp_id") or "").strip()
        if kp and kp not in kp_ids:
            kp_ids.append(kp)
    _dump_json(
        practice_dir / "meta.json",
        {
            "schema": PRACTICE_SCHEMA,
            "practice_id": practice_id,
            "assignment_id": aid,
            "student_id": sid,
            "teacher_id": str(meta.get("teacher_id") or ""),
            "subject_id": str(meta.get("subject_id") or ""),
            "status": "open",
            "question_ids": question_ids,
            "kp_ids": kp_ids,
            "created_at": deps.now_iso(),
            "submitted_at": "",
            "bank_source": "question_bank",
        },
    )
    _clear_bank_miss(root)
    deps.diag_log(
        "student.practice.picked",
        {"student_id": sid, "assignment_id": aid, "practice_id": practice_id},
    )
    payload = _practice_public(deps, practice_dir)
    payload["ok"] = True
    return payload


def list_practices(
    assignment_id: str,
    *,
    student_id: str,
    deps: StudentPracticeDeps,
) -> Dict[str, Any]:
    aid = _require_safe_id(assignment_id, "assignment_id")
    sid = _require_safe_id(student_id, "student_id")
    _authorize(deps, aid, sid)
    meta = _load_assignment_meta(deps, aid)
    _assert_practice_applicable(meta, assignment_id=aid, student_id=sid, diag_log=deps.diag_log)
    root = _student_root(deps, aid, sid)
    practices = [_practice_public(deps, path) for path in _iter_practice_dirs(root)]
    return {
        "ok": True,
        "assignment_id": aid,
        "bank_miss": _bank_miss_path(root).is_file(),
        "practices": practices,
    }


def _resolve_practice_dir(
    deps: StudentPracticeDeps,
    assignment_id: str,
    student_id: str,
    practice_id: str,
) -> Path:
    token = _require_safe_id(practice_id, "practice_id")
    if not token.startswith(PRACTICE_PREFIX):
        raise StudentPracticeError(404, "practice not found")
    root = _student_root(deps, assignment_id, student_id)
    target = (root / token).resolve()
    if target.parent != root or not target.is_dir():
        raise StudentPracticeError(404, "practice not found")
    return target


def _submission_dirs(root: Path, student_id: str, submissions_root: Path) -> Set[Path]:
    found: Set[Path] = set()
    if root.is_dir():
        found.update(path.resolve() for path in root.glob("submission_*") if path.is_dir())
    sid_root = (Path(submissions_root) / student_id).resolve()
    if sid_root.is_dir():
        found.update(path.resolve() for path in sid_root.glob("submission_*") if path.is_dir())
    return found


def _delete_leaked(paths: Set[Path]) -> None:
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)


def _write_practice_ungraded(
    practice_dir: Path,
    *,
    assignment_id: str,
    student_id: str,
    error: str,
    file_paths: list[str],
) -> None:
    linked = _copy_saved_uploads(practice_dir, file_paths)
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
    (practice_dir / "grading_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _grade_script_error_text(exc: Exception) -> str:
    if isinstance(exc, TimeoutExpired):
        return "grade_script_timeout"
    detail = getattr(exc, "detail", None)
    if detail:
        return str(detail)[:500]
    return str(exc)[:500]


def _is_http_failure(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    try:
        return int(status) >= 500
    except (TypeError, ValueError):
        return False


def _mark_submitted(practice_dir: Path, now_iso: str) -> Dict[str, Any]:
    meta = _practice_meta(practice_dir)
    meta["status"] = "submitted"
    meta["submitted_at"] = now_iso
    _dump_json(practice_dir / "meta.json", meta)
    return meta


def _practice_submit_response(practice_id: str) -> Dict[str, Any]:
    return {
        "ok": True,
        "submitted": True,
        "official_score": None,
        "practice_id": practice_id,
    }


async def submit_practice(
    assignment_id: str,
    practice_id: str,
    *,
    student_id: str,
    files: List[Any],
    deps: StudentPracticeDeps,
) -> Dict[str, Any]:
    aid = _require_safe_id(assignment_id, "assignment_id")
    sid = _require_safe_id(student_id, "student_id")
    _authorize(deps, aid, sid)
    practice_dir = _resolve_practice_dir(deps, aid, sid, practice_id)
    meta = _practice_meta(practice_dir)
    owner = str(meta.get("student_id") or "").strip()
    if owner and owner != sid:
        raise StudentPracticeError(403, "forbidden_student_scope")
    if str(meta.get("status") or "").strip().lower() != "open":
        raise StudentPracticeError(409, "practice_not_open")

    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
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
    _copy_saved_uploads(practice_dir, file_paths)

    root = _student_root(deps, aid, sid)
    before = _submission_dirs(root, sid, Path(deps.student_submissions_dir))
    script = Path(deps.app_root) / "scripts" / "grade_submission.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        sid,
        "--out-dir",
        str(deps.student_submissions_dir),
        "--files",
        *file_paths,
        "--assignment-id",
        aid,
        "--attempt-dir",
        str(practice_dir),
        "--skip-profile-update",
        "--assignment-questions",
        str(practice_dir / "questions.csv"),
    ]
    try:
        deps.run_script(args)
    except TimeoutExpired as exc:
        _write_practice_ungraded(
            practice_dir,
            assignment_id=aid,
            student_id=sid,
            error=_grade_script_error_text(exc),
            file_paths=file_paths,
        )
    except Exception as exc:  # policy: allowed-broad-except
        if not _is_http_failure(exc):
            raise
        _write_practice_ungraded(
            practice_dir,
            assignment_id=aid,
            student_id=sid,
            error=_grade_script_error_text(exc),
            file_paths=file_paths,
        )

    leaked = _submission_dirs(root, sid, Path(deps.student_submissions_dir)) - before
    if leaked:
        _delete_leaked(leaked)
        deps.diag_log(
            "student.practice.attempt_dir_leak",
            {
                "student_id": sid,
                "assignment_id": aid,
                "practice_id": practice_dir.name,
                "leaked": [str(path) for path in sorted(leaked)][:8],
            },
        )
        raise StudentPracticeError(500, "attempt_dir_leak")

    _mark_submitted(practice_dir, deps.now_iso())
    _write_derived_profile(
        SimpleNamespace(
            data_dir=Path(deps.data_dir),
            student_submissions_dir=Path(deps.student_submissions_dir),
            diag_log=deps.diag_log,
        ),
        aid,
        sid,
        attempt_dir=practice_dir,
        practice_id=practice_dir.name,
        questions_path=practice_dir / "questions.csv",
    )
    return _practice_submit_response(practice_dir.name)
