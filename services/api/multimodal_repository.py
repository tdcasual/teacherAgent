from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .job_repository import _atomic_write_json
from .paths import (
    multimodal_extraction_path,
    multimodal_submission_media_dir,
    multimodal_submission_meta_path,
)


def write_multimodal_submission(submission_id: str, payload: Dict[str, Any], *, core: Any | None = None) -> Path:
    target = multimodal_submission_meta_path(submission_id, core=core)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target, dict(payload or {}))
    return target



def load_multimodal_submission(submission_id: str, *, core: Any | None = None) -> Dict[str, Any]:
    target = multimodal_submission_meta_path(submission_id, core=core)
    payload = json.loads(target.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}



def write_multimodal_extraction(submission_id: str, payload: Dict[str, Any], *, core: Any | None = None) -> Path:
    target = multimodal_extraction_path(submission_id, core=core)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target, dict(payload or {}))
    return target



def load_multimodal_extraction(submission_id: str, *, core: Any | None = None) -> Dict[str, Any]:
    target = multimodal_extraction_path(submission_id, core=core)
    payload = json.loads(target.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}



def load_multimodal_submission_view(submission_id: str, *, core: Any | None = None) -> Dict[str, Any]:
    extraction = read_optional_multimodal_extraction(submission_id, core=core)
    if extraction is not None:
        return extraction
    return load_multimodal_submission(submission_id, core=core)



def read_optional_multimodal_extraction(submission_id: str, *, core: Any | None = None) -> Optional[Dict[str, Any]]:
    target = multimodal_extraction_path(submission_id, core=core)
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else None



def ensure_multimodal_media_dir(submission_id: str, *, core: Any | None = None) -> Path:
    target = multimodal_submission_media_dir(submission_id, core=core)
    target.mkdir(parents=True, exist_ok=True)
    return target
