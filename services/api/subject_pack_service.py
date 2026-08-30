from __future__ import annotations

import importlib.util
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

import yaml

_log = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = Path(os.getenv("SUBJECT_PACKS_DIR", APP_ROOT / "packs" / "subjects"))
GENERIC_PACK_ID = "generic"
_SAFE_SUBJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_GRADER_ADAPTER = "python_adapter"
SUBJECT_ID_ALIASES = {
    "物理": "physics",
    "数学": "math",
    "通用": "generic",
}
_PACK_LOAD_ERRORS = (OSError, UnicodeDecodeError, ValueError, TypeError, yaml.YAMLError)

_fallback_logger: Optional[Callable[[str, Dict[str, Any]], None]] = None


def bind_fallback_logger(logger: Optional[Callable[[str, Dict[str, Any]], None]]) -> None:
    global _fallback_logger
    _fallback_logger = logger


class SubjectPackError(RuntimeError):
    """Raised when the required generic pack cannot be loaded."""


class GradeAdapter(Protocol):
    def score_item(self, *, question: dict, student_text: str) -> dict:
        """Return {score, confidence, status, reason} compatible with grading_report items."""


@dataclass(frozen=True)
class PackManifest:
    subject_id: str
    display_name: str
    schema_version: int
    grader: str
    prompts: Dict[str, str]
    pack_dir: Path
    fallback: bool = False
    requested_subject_id: str = ""
    skill_affiliates: Tuple[str, ...] = ()


def clear_pack_cache() -> None:
    _load_pack_cached.cache_clear()
    _load_adapter_cached.cache_clear()


def load_pack(subject_id: Optional[str] = None) -> PackManifest:
    original = str(subject_id or "").strip()
    safe_id = _normalize_subject_id(subject_id)
    return _load_pack_cached(safe_id, original, str(PACKS_DIR))


def pack_id_from_meta(meta: Optional[Dict[str, Any]]) -> str:
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("pack_id") or meta.get("subject_id") or "").strip()


def student_prompt_overlay(subject_id: Optional[str] = None) -> str:
    pack = load_pack(subject_id)
    rel = pack.prompts.get("student_overlay") or "prompts/student_overlay.md"
    return _read_pack_text(pack.pack_dir, rel)


def teacher_prompt_overlay(subject_id: Optional[str] = None) -> str:
    pack = load_pack(subject_id)
    rel = pack.prompts.get("teacher_overlay") or "prompts/teacher_overlay.md"
    return _read_pack_text(pack.pack_dir, rel)


def overlay_for_role(subject_id: Optional[str] = None, role_hint: Optional[str] = None) -> str:
    if role_hint == "teacher":
        return teacher_prompt_overlay(subject_id)
    return student_prompt_overlay(subject_id)


def grade_adapter(subject_id: Optional[str] = None) -> Optional[GradeAdapter]:
    pack = load_pack(subject_id)
    if pack.grader != _GRADER_ADAPTER:
        return None
    adapter_path = pack.pack_dir / "grader" / "adapter.py"
    return _load_adapter_cached(str(adapter_path), str(pack.pack_dir))


def _normalize_subject_id(subject_id: Optional[str]) -> str:
    token = str(subject_id or "").strip()
    if not token:
        return GENERIC_PACK_ID
    aliased = SUBJECT_ID_ALIASES.get(token, token)
    if not _SAFE_SUBJECT_ID.fullmatch(aliased):
        return ""
    return aliased


def _emit_pack_fallback(subject_id: str) -> None:
    payload = {"subject_id": subject_id, "pack": GENERIC_PACK_ID}
    _log.warning("subject_pack_fallback subject_id=%s pack=generic", subject_id)
    if _fallback_logger is not None:
        _fallback_logger("subject_pack_fallback", payload)


def _pack_yaml_path(packs_dir: Path, pack_id: str) -> Optional[Path]:
    if not pack_id or not _SAFE_SUBJECT_ID.fullmatch(pack_id):
        return None
    root = packs_dir.resolve()
    target = (root / pack_id / "pack.yaml").resolve()
    if root not in target.parents:
        return None
    if not target.is_file():
        return None
    return target


def _read_yaml_mapping(path: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("pack manifest must be a non-empty mapping")
    return raw


def _normalize_grader(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token == _GRADER_ADAPTER:
        return _GRADER_ADAPTER
    return "none"


def _normalize_prompts(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    prompts: Dict[str, str] = {}
    for key, item in value.items():
        rel = str(item or "").strip()
        if key and rel:
            prompts[str(key)] = rel
    return prompts


def _normalize_skill_affiliates(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    affiliates: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        affiliates.append(token)
    return tuple(affiliates)


def _manifest_from_yaml(path: Path, *, fallback: bool, requested_subject_id: str) -> PackManifest:
    data = _read_yaml_mapping(path)
    pack_dir = path.parent
    subject_id = str(data.get("subject_id") or pack_dir.name).strip() or GENERIC_PACK_ID
    display_name = str(data.get("display_name") or subject_id).strip()
    try:
        schema_version = int(data.get("schema_version") or 1)
    except (TypeError, ValueError):
        schema_version = 1
    return PackManifest(
        subject_id=subject_id,
        display_name=display_name,
        schema_version=schema_version,
        grader=_normalize_grader(data.get("grader")),
        prompts=_normalize_prompts(data.get("prompts")),
        pack_dir=pack_dir,
        fallback=fallback,
        requested_subject_id=requested_subject_id,
        skill_affiliates=_normalize_skill_affiliates(data.get("skill_affiliates")),
    )


def _load_generic_pack(packs_dir: Path, *, requested_subject_id: str, fallback: bool) -> PackManifest:
    generic_path = _pack_yaml_path(packs_dir, GENERIC_PACK_ID)
    if generic_path is None:
        raise SubjectPackError("generic subject pack is required")
    try:
        return _manifest_from_yaml(
            generic_path,
            fallback=fallback,
            requested_subject_id=requested_subject_id,
        )
    except _PACK_LOAD_ERRORS as exc:
        raise SubjectPackError("generic subject pack is required") from exc


@lru_cache(maxsize=64)
def _load_pack_cached(safe_id: str, original: str, packs_dir: str) -> PackManifest:
    root = Path(packs_dir)
    requested = original or safe_id
    if safe_id and safe_id != GENERIC_PACK_ID:
        yaml_path = _pack_yaml_path(root, safe_id)
        if yaml_path is not None:
            try:
                return _manifest_from_yaml(
                    yaml_path,
                    fallback=False,
                    requested_subject_id=safe_id,
                )
            except _PACK_LOAD_ERRORS:
                _emit_pack_fallback(requested)
                return _load_generic_pack(root, requested_subject_id=requested, fallback=True)
        _emit_pack_fallback(requested)
        return _load_generic_pack(root, requested_subject_id=requested, fallback=True)
    if not safe_id:
        _emit_pack_fallback(requested)
        return _load_generic_pack(root, requested_subject_id=requested, fallback=True)
    return _load_generic_pack(root, requested_subject_id=GENERIC_PACK_ID, fallback=False)


def _read_pack_text(pack_dir: Path, relpath: str) -> str:
    rel = str(relpath or "").strip()
    if not rel:
        return ""
    root = pack_dir.resolve()
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        return ""
    if not target.is_file():
        return ""
    return target.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=32)
def _load_adapter_cached(adapter_path: str, pack_dir: str) -> Optional[GradeAdapter]:
    root = Path(pack_dir).resolve()
    resolved = Path(adapter_path).resolve()
    if root not in resolved.parents and resolved != root:
        return None
    if not resolved.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"subject_pack_adapter_{root.name}", resolved)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, ImportError, SyntaxError, TypeError):
        return None
    candidate = getattr(module, "ADAPTER", None)
    if candidate is None:
        candidate = module
    score_item = getattr(candidate, "score_item", None)
    if not callable(score_item):
        return None
    return candidate


__all__ = [
    "GENERIC_PACK_ID",
    "GradeAdapter",
    "PACKS_DIR",
    "PackManifest",
    "SubjectPackError",
    "bind_fallback_logger",
    "clear_pack_cache",
    "grade_adapter",
    "load_pack",
    "overlay_for_role",
    "pack_id_from_meta",
    "student_prompt_overlay",
    "teacher_prompt_overlay",
]
