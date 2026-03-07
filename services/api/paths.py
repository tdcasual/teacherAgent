from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from . import settings as _settings
from .config import (
    APP_ROOT,
    DATA_DIR,
    EXAM_UPLOAD_JOB_DIR,
    STUDENT_SESSIONS_DIR,
    TEACHER_SESSIONS_DIR,
    TEACHER_WORKSPACES_DIR,
    UPLOAD_JOB_DIR,
    UPLOADS_DIR,
)

_log = logging.getLogger(__name__)


def _path_from_core(core: Any | None, attr: str, fallback: Path) -> Path:
    if core is None:
        return fallback
    try:
        value = getattr(core, attr, None)
    except Exception:
        _log.debug("failed to read path attr from core: %s", attr, exc_info=True)
        return fallback
    if value is None:
        return fallback
    try:
        return Path(value)
    except Exception:
        _log.debug("invalid path attr on core: %s=%r", attr, value, exc_info=True)
        return fallback


# ---------------------------------------------------------------------------
# Tiny date helpers (needed by teacher_daily_memory_path)
# ---------------------------------------------------------------------------

def today_iso() -> str:
    return datetime.now().date().isoformat()


def parse_date_str(date_str: Optional[str]) -> str:
    if not date_str:
        return today_iso()
    try:
        return datetime.fromisoformat(date_str).date().isoformat()
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return today_iso()


# ---------------------------------------------------------------------------
# Generic filesystem-safe id helpers
# ---------------------------------------------------------------------------

def safe_fs_id(value: str, prefix: str = "id") -> str:
    raw = str(value or "").strip()
    slug = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if len(slug) < 6:
        digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10] if raw else uuid.uuid4().hex[:10]
        slug = f"{prefix}_{digest}"
    return slug


# ---------------------------------------------------------------------------
# Upload / exam job paths
# ---------------------------------------------------------------------------

def upload_job_path(job_id: str, core: Any | None = None) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    upload_job_dir = _path_from_core(core, "UPLOAD_JOB_DIR", UPLOAD_JOB_DIR)
    return upload_job_dir / safe


def exam_job_path(job_id: str, core: Any | None = None) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    exam_upload_job_dir = _path_from_core(core, "EXAM_UPLOAD_JOB_DIR", EXAM_UPLOAD_JOB_DIR)
    return exam_upload_job_dir / safe


# ---------------------------------------------------------------------------
# Survey job / report paths
# ---------------------------------------------------------------------------

def survey_job_path(job_id: str, core: Any | None = None) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    uploads_dir = _path_from_core(core, "UPLOADS_DIR", UPLOADS_DIR)
    return uploads_dir / "survey_jobs" / safe


def survey_raw_payload_dir(job_id: str, core: Any | None = None) -> Path:
    return survey_job_path(job_id, core=core) / "raw_payloads"


def survey_bundle_path(job_id: str, core: Any | None = None) -> Path:
    return survey_job_path(job_id, core=core) / "bundle.json"


def survey_report_path(report_id: str, core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    safe = safe_fs_id(report_id, prefix="report")
    return data_dir / "survey_reports" / f"{safe}.json"


def survey_review_queue_path(core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    return data_dir / "survey_review_queue.jsonl"



# ---------------------------------------------------------------------------
# Multimodal submission paths
# ---------------------------------------------------------------------------

def multimodal_submission_path(submission_id: str, core: Any | None = None) -> Path:
    uploads_dir = _path_from_core(core, "UPLOADS_DIR", UPLOADS_DIR)
    safe = safe_fs_id(submission_id, prefix="submission")
    return uploads_dir / "multimodal_submissions" / safe


def multimodal_submission_meta_path(submission_id: str, core: Any | None = None) -> Path:
    return multimodal_submission_path(submission_id, core=core) / "submission.json"


def multimodal_submission_media_dir(submission_id: str, core: Any | None = None) -> Path:
    return multimodal_submission_path(submission_id, core=core) / "media"


def multimodal_submission_derived_dir(submission_id: str, core: Any | None = None) -> Path:
    return multimodal_submission_path(submission_id, core=core) / "derived"


def multimodal_extraction_path(submission_id: str, core: Any | None = None) -> Path:
    return multimodal_submission_derived_dir(submission_id, core=core) / "extraction.json"


# ---------------------------------------------------------------------------
# Student session paths
# ---------------------------------------------------------------------------

def student_sessions_base_dir(student_id: str, core: Any | None = None) -> Path:
    sessions_dir = _path_from_core(core, "STUDENT_SESSIONS_DIR", STUDENT_SESSIONS_DIR)
    return sessions_dir / safe_fs_id(student_id, prefix="student")


def student_sessions_index_path(student_id: str, core: Any | None = None) -> Path:
    return student_sessions_base_dir(student_id, core=core) / "index.json"


def student_session_view_state_path(student_id: str, core: Any | None = None) -> Path:
    return student_sessions_base_dir(student_id, core=core) / "view_state.json"


def student_session_file(student_id: str, session_id: str, core: Any | None = None) -> Path:
    return student_sessions_base_dir(student_id, core=core) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"


# ---------------------------------------------------------------------------
# Teacher identity / workspace paths
# ---------------------------------------------------------------------------

def resolve_teacher_id(teacher_id: Optional[str] = None) -> str:
    raw = (teacher_id or _settings.default_teacher_id() or "teacher").strip()
    # Use a stable filesystem-safe id; keep original value in USER.md if needed.
    return safe_fs_id(raw, prefix="teacher")


def teacher_workspace_dir(teacher_id: str, core: Any | None = None) -> Path:
    workspaces_dir = _path_from_core(core, "TEACHER_WORKSPACES_DIR", TEACHER_WORKSPACES_DIR)
    return workspaces_dir / safe_fs_id(teacher_id, prefix="teacher")


def teacher_workspace_file(teacher_id: str, name: str, core: Any | None = None) -> Path:
    allowed = {"AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}
    if name not in allowed:
        raise ValueError(f"invalid teacher workspace file: {name}")
    return teacher_workspace_dir(teacher_id, core=core) / name


def teacher_provider_registry_path(
    teacher_id: Optional[str] = None, core: Any | None = None
) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final, core=core) / "provider_registry.json"


def teacher_provider_registry_audit_path(
    teacher_id: Optional[str] = None, core: Any | None = None
) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final, core=core) / "provider_registry_audit.jsonl"


# ---------------------------------------------------------------------------
# Teacher memory paths
# ---------------------------------------------------------------------------

def teacher_daily_memory_dir(teacher_id: str, core: Any | None = None) -> Path:
    return teacher_workspace_dir(teacher_id, core=core) / "memory"


def teacher_daily_memory_path(
    teacher_id: str, date_str: Optional[str] = None, core: Any | None = None
) -> Path:
    date_final = parse_date_str(date_str)
    return teacher_daily_memory_dir(teacher_id, core=core) / f"{date_final}.md"


# ---------------------------------------------------------------------------
# Teacher session paths
# ---------------------------------------------------------------------------

def teacher_sessions_base_dir(teacher_id: str, core: Any | None = None) -> Path:
    sessions_dir = _path_from_core(core, "TEACHER_SESSIONS_DIR", TEACHER_SESSIONS_DIR)
    return sessions_dir / safe_fs_id(teacher_id, prefix="teacher")


def teacher_sessions_index_path(teacher_id: str, core: Any | None = None) -> Path:
    return teacher_sessions_base_dir(teacher_id, core=core) / "index.json"


def teacher_session_view_state_path(teacher_id: str, core: Any | None = None) -> Path:
    return teacher_sessions_base_dir(teacher_id, core=core) / "view_state.json"


def teacher_session_file(teacher_id: str, session_id: str, core: Any | None = None) -> Path:
    return teacher_sessions_base_dir(teacher_id, core=core) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"


# ---------------------------------------------------------------------------
# Assignment / exam / analysis / student-profile directory paths
# ---------------------------------------------------------------------------

def resolve_assignment_dir(assignment_id: str, core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    assignments_root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise ValueError("assignment_id is required")
    folder = (assignments_root / aid).resolve()
    if folder != assignments_root and assignments_root not in folder.parents:
        raise ValueError("invalid assignment_id")
    return folder


def resolve_exam_dir(exam_id: str, core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    exams_root = (data_dir / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (exams_root / eid).resolve()
    if folder != exams_root and exams_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder


def resolve_analysis_dir(exam_id: str, core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    analysis_root = (data_dir / "analysis").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (analysis_root / eid).resolve()
    if folder != analysis_root and analysis_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder


def resolve_student_profile_path(student_id: str, core: Any | None = None) -> Path:
    data_dir = _path_from_core(core, "DATA_DIR", DATA_DIR)
    profiles_root = (data_dir / "student_profiles").resolve()
    sid = str(student_id or "").strip()
    if not sid:
        raise ValueError("student_id is required")
    path = (profiles_root / f"{sid}.json").resolve()
    if path != profiles_root and profiles_root not in path.parents:
        raise ValueError("invalid student_id")
    return path


# ---------------------------------------------------------------------------
# Manifest / exam file path helpers (pure path computation only)
# ---------------------------------------------------------------------------

def resolve_manifest_path(path_value: Any, core: Any | None = None) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        app_root = _path_from_core(core, "APP_ROOT", APP_ROOT)
        path = (app_root / path).resolve()
    return path
