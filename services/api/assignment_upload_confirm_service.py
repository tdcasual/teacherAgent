from __future__ import annotations

import csv
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment.store import connect as assignment_connect
from .assignment.store import ensure as assignment_ensure
from .assignment.store import get_assignment as assignment_get
from .assignment.store import upsert_assignment
from .assignment.visibility import effective_visibility_status
from .assignment_catalog_service import (
    _default_assignment_completion_policy,
    effective_assignment_kind,
    effective_content_source,
)
from .assignment_requirements_service import call_compute_requirements_missing
from .auth.identity_graph_service import ExpectedStudentsError
from .auth_service import get_current_principal
from .paths import APP_ROOT, InvalidAssignmentDate
from .question_bank_select_service import (
    count_question_data_rows,
    ensure_questions_csv_header,
    write_questions_csv,
)

_log = logging.getLogger(__name__)


class AssignmentUploadConfirmError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentUploadConfirmError(400, "assignment_id is required")
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        raise AssignmentUploadConfirmError(400, "invalid assignment_id")
    return target


@dataclass(frozen=True)
class AssignmentUploadConfirmDeps:
    data_dir: Path
    now_iso: Callable[[], str]
    discussion_complete_marker: str
    write_upload_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    merge_requirements: Callable[[Dict[str, Any], Dict[str, Any], bool], Dict[str, Any]]
    compute_requirements_missing: Callable[..., List[str]]
    write_uploaded_questions: Callable[[Path, str, List[Dict[str, Any]]], List[Dict[str, Any]]]
    optional_assignment_date: Callable[[Any], Optional[str]]
    save_assignment_requirements: Callable[..., Any]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    normalize_due_at: Callable[[Any], Optional[str]]
    compute_expected_students: Callable[..., List[str]]
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    copy2: Callable[[Path, Path], Any]


@dataclass(frozen=True)
class _PreparedConfirmData:
    questions: List[Dict[str, Any]]
    requirements: Dict[str, Any]
    missing: List[str]
    warnings: List[str]
    delivery_mode: str
    autofilled: bool


def _load_draft_override(job_dir: Path) -> Dict[str, Any]:
    override_path = job_dir / "draft_override.json"
    if not override_path.exists():
        return {}
    try:
        payload = json.loads(override_path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to parse draft_override.json in %s", override_path, exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _copy_if_exists(src: Path, dst: Path, copy2: Callable[[Path, Path], Any]) -> None:
    if src.exists():
        copy2(src, dst)


def _mark_confirming(job_id: str, deps: AssignmentUploadConfirmDeps) -> None:
    deps.write_upload_job(
        job_id,
        {
            "status": "confirming",
            "step": "start",
            "progress": 5,
            "confirm_started_at": deps.now_iso(),
        },
    )


def _load_parsed_or_fail(
    job_id: str, job_dir: Path, deps: AssignmentUploadConfirmDeps
) -> Dict[str, Any]:
    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        deps.write_upload_job(
            job_id,
            {"status": "failed", "error": "parsed result missing", "step": "failed"},
        )
        raise AssignmentUploadConfirmError(400, "parsed result missing")
    return json.loads(parsed_path.read_text(encoding="utf-8"))


def _prepare_confirm_data(
    *,
    job: Dict[str, Any],
    parsed: Dict[str, Any],
    override: Dict[str, Any],
    requirements_override: Optional[Dict[str, Any]],
    deps: AssignmentUploadConfirmDeps,
) -> _PreparedConfirmData:
    questions = parsed.get("questions") or []
    if isinstance(override.get("questions"), list) and override.get("questions"):
        questions = override.get("questions") or questions

    requirements = parsed.get("requirements") or {}
    if isinstance(override.get("requirements"), dict) and override.get("requirements"):
        requirements = deps.merge_requirements(
            requirements,
            override.get("requirements") or {},
            True,
        )
    if requirements_override:
        requirements = deps.merge_requirements(requirements, requirements_override, True)

    kind = effective_assignment_kind({"assignment_kind": job.get("assignment_kind")})
    missing = call_compute_requirements_missing(
        deps.compute_requirements_missing, requirements, assignment_kind=kind
    )
    warnings = parsed.get("warnings") or []
    delivery_mode = parsed.get("delivery_mode") or job.get("delivery_mode") or "image"
    autofilled = parsed.get("autofilled") or False

    return _PreparedConfirmData(
        questions=questions,
        requirements=requirements,
        missing=missing,
        warnings=warnings,
        delivery_mode=delivery_mode,
        autofilled=autofilled,
    )


def _ensure_requirements_ready(
    job_id: str,
    *,
    strict_requirements: bool,
    missing: List[str],
    deps: AssignmentUploadConfirmDeps,
) -> None:
    if not (strict_requirements and missing):
        return
    deps.write_upload_job(
        job_id,
        {
            "status": "done",
            "step": "await_requirements",
            "progress": 100,
            "requirements_missing": missing,
        },
    )
    raise AssignmentUploadConfirmError(
        400,
        {
            "error": "requirements_missing",
            "missing": missing,
            "message": "作业要求未补全，无法创建作业。",
        },
    )


def _resolve_output_target(
    job_id: str,
    job: Dict[str, Any],
    deps: AssignmentUploadConfirmDeps,
) -> tuple[str, Path, Path]:
    assignment_id = str(job.get("assignment_id") or "").strip()
    if not assignment_id:
        deps.write_upload_job(
            job_id,
            {"status": "failed", "error": "assignment_id missing", "step": "failed"},
        )
        raise AssignmentUploadConfirmError(400, "assignment_id missing")
    try:
        out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    except AssignmentUploadConfirmError as exc:
        deps.write_upload_job(
            job_id,
            {"status": "failed", "error": str(exc.detail), "step": "failed"},
        )
        raise

    meta_path = out_dir / "meta.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    return assignment_id, out_dir, meta_path


def _copy_uploaded_files(
    job_id: str,
    job: Dict[str, Any],
    job_dir: Path,
    out_dir: Path,
    deps: AssignmentUploadConfirmDeps,
) -> None:
    deps.write_upload_job(job_id, {"step": "copy_files", "progress": 20})
    source_dir = out_dir / "source"
    answer_dir = out_dir / "answer_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    answer_dir.mkdir(parents=True, exist_ok=True)
    for fname in job.get("source_files") or []:
        _copy_if_exists(job_dir / "source" / str(fname), source_dir / str(fname), deps.copy2)
    for fname in job.get("answer_files") or []:
        _copy_if_exists(job_dir / "answer_source" / str(fname), answer_dir / str(fname), deps.copy2)


def _write_questions_and_requirements(
    job_id: str,
    *,
    job: Dict[str, Any],
    out_dir: Path,
    assignment_id: str,
    questions: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    deps: AssignmentUploadConfirmDeps,
) -> tuple[List[Dict[str, Any]], str]:
    deps.write_upload_job(job_id, {"step": "write_questions", "progress": 55})
    rows = deps.write_uploaded_questions(out_dir, assignment_id, questions)
    try:
        date_str = deps.optional_assignment_date(job.get("date")) or ""
    except InvalidAssignmentDate as exc:
        raise AssignmentUploadConfirmError(400, "invalid_assignment_date") from exc
    deps.write_upload_job(job_id, {"step": "save_requirements", "progress": 70})
    deps.save_assignment_requirements(
        assignment_id,
        requirements,
        date_str,
        created_by="teacher_upload",
        validate=False,
    )
    return rows, date_str


def _resolve_students_scope(
    job: Dict[str, Any], deps: AssignmentUploadConfirmDeps
) -> tuple[List[str], str]:
    student_ids_list = deps.parse_ids_value(job.get("student_ids") or [])
    scope_val = deps.resolve_scope(
        job.get("scope") or "",
        student_ids_list,
        job.get("class_name") or "",
    )
    if scope_val == "student" and not student_ids_list:
        raise AssignmentUploadConfirmError(400, "student scope requires student_ids")
    return student_ids_list, scope_val


def _mark_confirm_failed(job_id: str, deps: AssignmentUploadConfirmDeps, error: str) -> None:
    deps.write_upload_job(job_id, {"status": "failed", "error": error, "step": "failed"})


def _compute_confirm_expected_students(
    deps: AssignmentUploadConfirmDeps,
    *,
    scope_val: str,
    class_name: str,
    student_ids: List[str],
    teacher_id: str,
    subject_id: str,
    job_id: str = "",
) -> List[str]:
    try:
        return deps.compute_expected_students(
            scope_val,
            class_name,
            student_ids,
            teacher_id=teacher_id,
            subject_id=subject_id,
        )
    except ExpectedStudentsError as exc:
        if job_id:
            _mark_confirm_failed(job_id, deps, exc.error)
        raise AssignmentUploadConfirmError(400, exc.error) from exc


def _require_meta_owner(
    job: Dict[str, Any],
    *,
    job_id: str,
    deps: AssignmentUploadConfirmDeps,
) -> tuple[str, str]:
    teacher_id = str(job.get("teacher_id") or "").strip()
    if not teacher_id:
        principal = get_current_principal()
        teacher_id = str(getattr(principal, "actor_id", "") or "").strip()
    subject_id = str(job.get("subject_id") or "").strip()
    if not teacher_id:
        _mark_confirm_failed(job_id, deps, "teacher_id_required")
        raise AssignmentUploadConfirmError(400, "teacher_id_required")
    if not subject_id:
        _mark_confirm_failed(job_id, deps, "subject_id_required")
        raise AssignmentUploadConfirmError(400, "subject_id_required")
    return teacher_id, subject_id


def _build_assignment_meta(
    job_id: str,
    *,
    job: Dict[str, Any],
    assignment_id: str,
    date_str: str,
    rows: List[Dict[str, Any]],
    prepared: _PreparedConfirmData,
    student_ids_list: List[str],
    scope_val: str,
    teacher_id: str,
    subject_id: str,
    expected_students: List[str],
    deps: AssignmentUploadConfirmDeps,
    completion_policy_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    kind = effective_assignment_kind({"assignment_kind": job.get("assignment_kind")})
    return {
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "pack_id": subject_id,
        "date": date_str or "",
        "due_at": deps.normalize_due_at(job.get("due_at")) or "",
        "visibility_status": "published",
        "archived_at": None,
        "mode": "upload",
        "content_source": "upload",
        "assignment_kind": kind,
        "target_kp": prepared.requirements.get("core_concepts") or [],
        "question_ids": [row.get("question_id") for row in rows if row.get("question_id")],
        "class_name": job.get("class_name") or "",
        "student_ids": student_ids_list,
        "scope": scope_val,
        "expected_students": list(expected_students),
        "expected_students_generated_at": deps.now_iso(),
        "completion_policy": _merge_completion_policy(
            None,
            completion_policy_override,
            assignment_kind=kind,
            discussion_marker=deps.discussion_complete_marker,
        ),
        "source": "teacher",
        "delivery_mode": prepared.delivery_mode,
        "source_files": job.get("source_files") or [],
        "answer_files": job.get("answer_files") or [],
        "requirements_missing": prepared.missing,
        "requirements_autofilled": prepared.autofilled,
        "generated_at": deps.now_iso(),
        "job_id": job_id,
    }


def _mark_confirmed(job_id: str, deps: AssignmentUploadConfirmDeps) -> None:
    deps.write_upload_job(
        job_id,
        {
            "status": "confirmed",
            "step": "confirmed",
            "progress": 100,
            "confirmed_at": deps.now_iso(),
        },
    )


def _rollback_quiet(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        _log.debug("rollback skipped; no open transaction", exc_info=True)


def _conflict_already_exists(job_id: str, deps: AssignmentUploadConfirmDeps) -> None:
    deps.write_upload_job(job_id, {"status": "confirmed", "step": "confirmed", "progress": 100})
    raise AssignmentUploadConfirmError(409, "assignment already exists")


def _ok_payload(
    assignment_id: str, question_count: int, missing: List[str], warnings: List[str]
) -> Dict[str, Any]:
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "question_count": question_count,
        "requirements_missing": missing,
        "warnings": warnings,
        "status": "confirmed",
    }


def _read_existing_meta(meta_path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log.warning("failed to parse existing assignment meta %s", meta_path, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def _open_assignment_conn(data_dir: Path) -> sqlite3.Connection:
    conn = assignment_connect(data_dir)
    assignment_ensure(conn, data_dir=data_dir)
    return conn


def _try_heal_existing_meta(
    job_id: str,
    *,
    assignment_id: str,
    teacher_id: str,
    meta_path: Path,
    deps: AssignmentUploadConfirmDeps,
) -> Optional[Dict[str, Any]]:
    if not meta_path.exists():
        return None
    existing = _read_existing_meta(meta_path)
    if existing is None or str(existing.get("teacher_id") or "").strip() != teacher_id:
        _conflict_already_exists(job_id, deps)
    assert existing is not None
    conn = _open_assignment_conn(deps.data_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if assignment_get(conn, assignment_id) is not None:
                raise AssignmentUploadConfirmError(409, "assignment already exists")
            upsert_assignment(conn, existing, now_iso=deps.now_iso())
            conn.execute("COMMIT")
        except AssignmentUploadConfirmError as exc:
            _rollback_quiet(conn)
            if exc.status_code == 409:
                _conflict_already_exists(job_id, deps)
            raise
        except Exception as exc:
            _rollback_quiet(conn)
            raise AssignmentUploadConfirmError(500, "assignment_persist_failed") from exc
    finally:
        conn.close()
    _mark_confirmed(job_id, deps)
    question_ids = existing.get("question_ids") if isinstance(existing.get("question_ids"), list) else []
    return _ok_payload(assignment_id, len(question_ids), list(existing.get("requirements_missing") or []), [])


def _persist_new_assignment(
    job_id: str,
    *,
    assignment_id: str,
    meta_path: Path,
    build_meta: Callable[[sqlite3.Connection], Dict[str, Any]],
    deps: AssignmentUploadConfirmDeps,
) -> Dict[str, Any]:
    conn = _open_assignment_conn(deps.data_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if assignment_get(conn, assignment_id) is not None:
                raise AssignmentUploadConfirmError(409, "assignment already exists")
            meta = build_meta(conn)
            upsert_assignment(conn, meta, now_iso=deps.now_iso())
            deps.atomic_write_json(meta_path, meta)
            conn.execute("COMMIT")
        except AssignmentUploadConfirmError:
            _rollback_quiet(conn)
            raise
        except Exception as exc:
            _rollback_quiet(conn)
            raise AssignmentUploadConfirmError(500, "assignment_persist_failed") from exc
    finally:
        conn.close()
    return meta


def confirm_assignment_upload(
    job_id: str,
    job: Dict[str, Any],
    job_dir: Path,
    *,
    requirements_override: Optional[Dict[str, Any]],
    strict_requirements: bool,
    deps: AssignmentUploadConfirmDeps,
    completion_policy_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _mark_confirming(job_id, deps)
    parsed = _load_parsed_or_fail(job_id, job_dir, deps)
    override = _load_draft_override(job_dir)
    prepared = _prepare_confirm_data(
        job=job,
        parsed=parsed,
        override=override,
        requirements_override=requirements_override,
        deps=deps,
    )
    _ensure_requirements_ready(
        job_id,
        strict_requirements=strict_requirements,
        missing=prepared.missing,
        deps=deps,
    )
    kind = effective_assignment_kind({"assignment_kind": job.get("assignment_kind")})
    _ensure_problem_set_has_questions(
        job_id, kind=kind, questions=prepared.questions, deps=deps
    )
    teacher_id, subject_id = _require_meta_owner(job, job_id=job_id, deps=deps)
    assignment_id, out_dir, meta_path = _resolve_output_target(job_id, job, deps)
    healed = _try_heal_existing_meta(
        job_id,
        assignment_id=assignment_id,
        teacher_id=teacher_id,
        meta_path=meta_path,
        deps=deps,
    )
    if healed is not None:
        return healed
    _copy_uploaded_files(job_id, job, job_dir, out_dir, deps)
    rows, date_str = _write_questions_and_requirements(
        job_id,
        job=job,
        out_dir=out_dir,
        assignment_id=assignment_id,
        questions=prepared.questions,
        requirements=prepared.requirements,
        deps=deps,
    )
    if kind != "problem_set" and not rows:
        ensure_questions_csv_header(out_dir / "questions.csv")
    _write_brief_markdown(out_dir, prepared.requirements)
    student_ids_list, scope_val = _resolve_students_scope(job, deps)
    # Roster lives in the same sqlite file as assignments. Snapshot students
    # before BEGIN IMMEDIATE so confirm does not open a second connection
    # against a locked auth_registry.sqlite3.
    expected_students = _compute_confirm_expected_students(
        deps,
        scope_val=scope_val,
        class_name=str(job.get("class_name") or ""),
        student_ids=student_ids_list,
        teacher_id=teacher_id,
        subject_id=subject_id,
        job_id=job_id,
    )

    def _build_meta(_conn: sqlite3.Connection) -> Dict[str, Any]:
        return _build_assignment_meta(
            job_id,
            job=job,
            assignment_id=assignment_id,
            date_str=date_str,
            rows=rows,
            prepared=prepared,
            student_ids_list=student_ids_list,
            scope_val=scope_val,
            teacher_id=teacher_id,
            subject_id=subject_id,
            expected_students=expected_students,
            deps=deps,
            completion_policy_override=completion_policy_override,
        )

    try:
        _persist_new_assignment(
            job_id,
            assignment_id=assignment_id,
            meta_path=meta_path,
            build_meta=_build_meta,
            deps=deps,
        )
    except AssignmentUploadConfirmError as exc:
        if exc.status_code == 409:
            _conflict_already_exists(job_id, deps)
        raise
    _mark_confirmed(job_id, deps)
    return _ok_payload(assignment_id, len(rows), prepared.missing, prepared.warnings)


def _merge_completion_policy(
    current: Optional[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
    *,
    assignment_kind: str,
    discussion_marker: str,
) -> Dict[str, Any]:
    policy = _default_assignment_completion_policy(
        discussion_marker, assignment_kind=assignment_kind
    )
    if isinstance(current, dict):
        for key, value in current.items():
            if value is not None:
                policy[key] = value
    if isinstance(override, dict):
        for key in (
            "requires_discussion",
            "requires_submission",
            "allow_practice",
            "min_graded_total",
            "discussion_marker",
            "best_attempt",
            "version",
        ):
            if key in override and override[key] is not None:
                policy[key] = override[key]
    return policy


def _ensure_problem_set_has_questions(
    job_id: str,
    *,
    kind: str,
    questions: List[Dict[str, Any]],
    deps: AssignmentUploadConfirmDeps,
) -> None:
    if kind != "problem_set" or questions:
        return
    deps.write_upload_job(
        job_id,
        {"status": "done", "step": "await_questions", "progress": 100},
    )
    raise AssignmentUploadConfirmError(400, "questions_missing")


def _write_brief_markdown(out_dir: Path, requirements: Dict[str, Any]) -> None:
    brief = str((requirements or {}).get("brief") or "").strip()
    if not brief:
        return
    (out_dir / "brief.md").write_text(brief + "\n", encoding="utf-8")


def _load_json_dict(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _snapshot_bank_refs(out_dir: Path, *, app_root: Path) -> None:
    csv_path = out_dir / "questions.csv"
    rows = _load_csv_rows(csv_path)
    if not rows:
        return
    stem_dir = out_dir / "bank_stems"
    answer_dir = out_dir / "bank_answers"
    stem_dir.mkdir(parents=True, exist_ok=True)
    answer_dir.mkdir(parents=True, exist_ok=True)
    app_root_resolved = Path(app_root).resolve()
    rewritten: List[Dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        qid = str(row.get("question_id") or "item").strip() or "item"
        for field, dest_dir in (("stem_ref", stem_dir), ("answer_ref", answer_dir)):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            src = Path(raw)
            if not src.is_absolute():
                src = app_root_resolved / src
            if not src.exists():
                continue
            dest = dest_dir / f"{qid}{src.suffix or '.md'}"
            dest.write_bytes(src.read_bytes())
            try:
                updated[field] = str(dest.resolve().relative_to(app_root_resolved))
            except ValueError:
                updated[field] = str(dest.resolve())
        rewritten.append(updated)
    write_questions_csv(csv_path, rewritten)


def _folder_owner_teacher_id() -> str:
    principal = get_current_principal()
    return str(getattr(principal, "actor_id", "") or "").strip()


def _persist_folder_assignment(
    *,
    assignment_id: str,
    meta_path: Path,
    meta: Dict[str, Any],
    deps: AssignmentUploadConfirmDeps,
) -> None:
    conn = _open_assignment_conn(deps.data_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            upsert_assignment(conn, meta, now_iso=deps.now_iso())
            deps.atomic_write_json(meta_path, meta)
            conn.execute("COMMIT")
        except AssignmentUploadConfirmError:
            _rollback_quiet(conn)
            raise
        except Exception as exc:
            _rollback_quiet(conn)
            raise AssignmentUploadConfirmError(500, "assignment_persist_failed") from exc
    finally:
        conn.close()


def _finalize_published_from_folder(
    assignment_id: str,
    *,
    requirements_override: Optional[Dict[str, Any]] = None,
    completion_policy_override: Optional[Dict[str, Any]] = None,
    strict_requirements: bool = True,
    deps: AssignmentUploadConfirmDeps,
) -> Dict[str, Any]:
    out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    if not out_dir.exists():
        raise AssignmentUploadConfirmError(404, "assignment not found")
    meta_path = out_dir / "meta.json"
    meta = _load_json_dict(meta_path)
    if effective_visibility_status(meta) != "draft":
        raise AssignmentUploadConfirmError(409, "invalid_visibility_status")
    actor = _folder_owner_teacher_id()
    owner = str(meta.get("teacher_id") or "").strip()
    if not actor or owner != actor:
        raise AssignmentUploadConfirmError(403, "forbidden")
    requirements = _load_json_dict(out_dir / "requirements.json")
    if requirements_override:
        requirements = deps.merge_requirements(requirements, requirements_override, True)
    kind = effective_assignment_kind(meta)
    source = effective_content_source(meta, folder=out_dir)
    missing = call_compute_requirements_missing(
        deps.compute_requirements_missing, requirements, assignment_kind=kind
    )
    if strict_requirements and missing:
        raise AssignmentUploadConfirmError(
            400,
            {
                "error": "requirements_missing",
                "missing": missing,
                "message": "作业要求未补全，无法创建作业。",
            },
        )
    if source == "bank" and kind != "problem_set":
        raise AssignmentUploadConfirmError(400, "bank_requires_problem_set")
    question_count = count_question_data_rows(out_dir / "questions.csv")
    if kind == "problem_set" and question_count <= 0:
        raise AssignmentUploadConfirmError(400, "questions_missing")
    if kind != "problem_set":
        ensure_questions_csv_header(out_dir / "questions.csv")
    meta["content_source"] = source
    meta["assignment_kind"] = kind
    meta["completion_policy"] = _merge_completion_policy(
        meta.get("completion_policy") if isinstance(meta.get("completion_policy"), dict) else None,
        completion_policy_override,
        assignment_kind=kind,
        discussion_marker=deps.discussion_complete_marker,
    )
    student_ids_list = deps.parse_ids_value(meta.get("student_ids") or [])
    scope_val = deps.resolve_scope(
        str(meta.get("scope") or ""),
        student_ids_list,
        str(meta.get("class_name") or ""),
    )
    teacher_id = owner
    subject_id = str(meta.get("subject_id") or "").strip()
    expected_students = _compute_confirm_expected_students(
        deps,
        scope_val=scope_val,
        class_name=str(meta.get("class_name") or ""),
        student_ids=student_ids_list,
        teacher_id=teacher_id,
        subject_id=subject_id,
    )
    meta["scope"] = scope_val
    meta["expected_students"] = list(expected_students)
    meta["expected_students_generated_at"] = deps.now_iso()
    if source == "bank":
        _snapshot_bank_refs(out_dir, app_root=APP_ROOT)
    meta["visibility_status"] = "published"
    meta["published_at"] = deps.now_iso()
    meta["archived_at"] = None
    if requirements:
        date_str = str(meta.get("date") or "")
        deps.save_assignment_requirements(
            assignment_id,
            requirements,
            date_str,
            created_by="teacher",
            validate=False,
        )
    _write_brief_markdown(out_dir, requirements)
    question_ids = [
        str(row.get("question_id") or "").strip()
        for row in _load_csv_rows(out_dir / "questions.csv")
        if str(row.get("question_id") or "").strip()
    ]
    meta["question_ids"] = question_ids
    _persist_folder_assignment(
        assignment_id=assignment_id,
        meta_path=meta_path,
        meta=meta,
        deps=deps,
    )
    _log.info(
        "assignment.confirm.published assignment_id=%s kind=%s source=%s allow_practice=%s",
        assignment_id,
        kind,
        source,
        meta.get("completion_policy", {}).get("allow_practice"),
    )
    return _ok_payload(assignment_id, len(question_ids), missing, [])


def build_default_folder_finalize_deps(data_dir: Path) -> AssignmentUploadConfirmDeps:
    from .assignment_requirements_service import (
        AssignmentRequirementsDeps,
        compute_requirements_missing,
        merge_requirements,
        save_assignment_requirements,
    )
    from .config import DISCUSSION_COMPLETE_MARKER
    from .core_services_application import compute_expected_students
    from .core_utils import normalize_due_at, parse_ids_value, resolve_scope
    from .fs_atomic import atomic_write_json

    def _save(assignment_id: str, requirements: Dict[str, Any], date_str: str, created_by: str = "teacher", validate: bool = False) -> Any:
        return save_assignment_requirements(
            assignment_id,
            requirements,
            date_str,
            deps=AssignmentRequirementsDeps(
                data_dir=data_dir,
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            ),
            created_by=created_by,
            validate=validate,
        )

    return AssignmentUploadConfirmDeps(
        data_dir=data_dir,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        discussion_complete_marker=DISCUSSION_COMPLETE_MARKER,
        write_upload_job=lambda *_args, **_kwargs: {},
        merge_requirements=merge_requirements,
        compute_requirements_missing=compute_requirements_missing,
        write_uploaded_questions=lambda *_args, **_kwargs: [],
        optional_assignment_date=lambda value: str(value or "").strip() or None,
        save_assignment_requirements=_save,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        normalize_due_at=normalize_due_at,
        compute_expected_students=lambda *args, **kwargs: compute_expected_students(
            *args, **kwargs, data_dir=data_dir
        ),
        atomic_write_json=atomic_write_json,
        copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
    )
