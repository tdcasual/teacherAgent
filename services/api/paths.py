from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from . import settings as _settings
from .config import (
    APP_ROOT,
    DATA_DIR,
    EXAM_UPLOAD_JOB_DIR,
    LLM_ROUTING_PATH,
    STUDENT_SESSIONS_DIR,
    TEACHER_SESSIONS_DIR,
    TEACHER_SKILLS_DIR,
    TEACHER_WORKSPACES_DIR,
    UPLOAD_JOB_DIR,
)

_log = logging.getLogger(__name__)


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


def teacher_skill_dir(skill_id: str) -> Path:
    safe_id = safe_fs_id(skill_id, prefix="skill")
    return TEACHER_SKILLS_DIR / safe_id


# ---------------------------------------------------------------------------
# Upload / exam job paths
# ---------------------------------------------------------------------------

def upload_job_path(job_id: str) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    return UPLOAD_JOB_DIR / safe


def exam_job_path(job_id: str) -> Path:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if not safe:
        safe = f"job_{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    return EXAM_UPLOAD_JOB_DIR / safe


# ---------------------------------------------------------------------------
# Student session paths
# ---------------------------------------------------------------------------

def student_sessions_base_dir(student_id: str) -> Path:
    return STUDENT_SESSIONS_DIR / safe_fs_id(student_id, prefix="student")


def student_sessions_index_path(student_id: str) -> Path:
    return student_sessions_base_dir(student_id) / "index.json"


def student_session_view_state_path(student_id: str) -> Path:
    return student_sessions_base_dir(student_id) / "view_state.json"


def student_session_file(student_id: str, session_id: str) -> Path:
    return student_sessions_base_dir(student_id) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"


# ---------------------------------------------------------------------------
# Teacher identity / workspace paths
# ---------------------------------------------------------------------------

def resolve_teacher_id(teacher_id: Optional[str] = None) -> str:
    raw = (teacher_id or _settings.default_teacher_id() or "teacher").strip()
    # Use a stable filesystem-safe id; keep original value in USER.md if needed.
    return safe_fs_id(raw, prefix="teacher")


def teacher_workspace_dir(teacher_id: str) -> Path:
    return TEACHER_WORKSPACES_DIR / safe_fs_id(teacher_id, prefix="teacher")


def teacher_workspace_file(teacher_id: str, name: str) -> Path:
    allowed = {"AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}
    if name not in allowed:
        raise ValueError(f"invalid teacher workspace file: {name}")
    return teacher_workspace_dir(teacher_id) / name


def teacher_llm_routing_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "llm_routing.json"


def teacher_provider_registry_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "provider_registry.json"


def teacher_provider_registry_audit_path(teacher_id: Optional[str] = None) -> Path:
    teacher_id_final = resolve_teacher_id(teacher_id)
    return teacher_workspace_dir(teacher_id_final) / "provider_registry_audit.jsonl"


def routing_config_path_for_role(role_hint: Optional[str], teacher_id: Optional[str] = None) -> Path:
    if role_hint == "teacher":
        return teacher_llm_routing_path(teacher_id)
    return LLM_ROUTING_PATH


# ---------------------------------------------------------------------------
# Teacher memory paths
# ---------------------------------------------------------------------------

def teacher_daily_memory_dir(teacher_id: str) -> Path:
    return teacher_workspace_dir(teacher_id) / "memory"


def teacher_daily_memory_path(teacher_id: str, date_str: Optional[str] = None) -> Path:
    date_final = parse_date_str(date_str)
    return teacher_daily_memory_dir(teacher_id) / f"{date_final}.md"


# ---------------------------------------------------------------------------
# Teacher session paths
# ---------------------------------------------------------------------------

def teacher_sessions_base_dir(teacher_id: str) -> Path:
    return TEACHER_SESSIONS_DIR / safe_fs_id(teacher_id, prefix="teacher")


def teacher_sessions_index_path(teacher_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / "index.json"


def teacher_session_view_state_path(teacher_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / "view_state.json"


def teacher_session_file(teacher_id: str, session_id: str) -> Path:
    return teacher_sessions_base_dir(teacher_id) / f"{safe_fs_id(session_id, prefix='session')}.jsonl"


# ---------------------------------------------------------------------------
# Assignment / exam / analysis / student-profile directory paths
# ---------------------------------------------------------------------------

def resolve_assignment_dir(assignment_id: str) -> Path:
    assignments_root = (DATA_DIR / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise ValueError("assignment_id is required")
    folder = (assignments_root / aid).resolve()
    if folder != assignments_root and assignments_root not in folder.parents:
        raise ValueError("invalid assignment_id")
    return folder


def resolve_exam_dir(exam_id: str) -> Path:
    exams_root = (DATA_DIR / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (exams_root / eid).resolve()
    if folder != exams_root and exams_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder


def resolve_analysis_dir(exam_id: str) -> Path:
    analysis_root = (DATA_DIR / "analysis").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ValueError("exam_id is required")
    folder = (analysis_root / eid).resolve()
    if folder != analysis_root and analysis_root not in folder.parents:
        raise ValueError("invalid exam_id")
    return folder


def resolve_student_profile_path(student_id: str) -> Path:
    profiles_root = (DATA_DIR / "student_profiles").resolve()
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

def resolve_manifest_path(path_value: Any) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (APP_ROOT / path).resolve()
    return path


def exam_file_path(manifest: Dict[str, Any], key: str) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    return resolve_manifest_path(files.get(key))
