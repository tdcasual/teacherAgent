from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .job_repository import _atomic_write_json
from .paths import (
    survey_bundle_path,
    survey_raw_payload_dir,
    survey_report_path,
    survey_review_queue_path,
)



def _safe_payload_name(name: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", str(name or "payload.json")).strip("._")
    return cleaned or "payload.json"



def write_survey_raw_payload(job_id: str, filename: str, payload: Dict[str, Any], *, core: Any | None = None) -> Path:
    raw_dir = survey_raw_payload_dir(job_id, core=core)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / _safe_payload_name(filename)
    _atomic_write_json(target, payload)
    return target



def load_survey_raw_payload(job_id: str, filename: str, *, core: Any | None = None) -> Dict[str, Any]:
    target = survey_raw_payload_dir(job_id, core=core) / _safe_payload_name(filename)
    return json.loads(target.read_text(encoding="utf-8"))



def list_survey_raw_payloads(job_id: str, *, core: Any | None = None) -> List[Dict[str, Any]]:
    raw_dir = survey_raw_payload_dir(job_id, core=core)
    if not raw_dir.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows.append(payload)
    return rows



def write_survey_bundle(job_id: str, payload: Dict[str, Any], *, core: Any | None = None) -> Path:
    target = survey_bundle_path(job_id, core=core)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target, payload)
    return target



def load_survey_bundle(job_id: str, *, core: Any | None = None) -> Dict[str, Any]:
    target = survey_bundle_path(job_id, core=core)
    return json.loads(target.read_text(encoding="utf-8"))



def write_survey_report(report_id: str, payload: Dict[str, Any], *, core: Any | None = None) -> Path:
    target = survey_report_path(report_id, core=core)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target, payload)
    return target



def load_survey_report(report_id: str, *, core: Any | None = None) -> Dict[str, Any]:
    target = survey_report_path(report_id, core=core)
    return json.loads(target.read_text(encoding="utf-8"))



def append_survey_review_queue_item(item: Dict[str, Any], *, core: Any | None = None) -> Path:
    target = survey_review_queue_path(core=core)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return target



def read_survey_review_queue(*, core: Any | None = None) -> List[Dict[str, Any]]:
    target = survey_review_queue_path(core=core)
    if not target.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        item = json.loads(raw)
        if isinstance(item, dict):
            rows.append(item)
    return rows
