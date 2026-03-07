from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict


class SurveyWebhookError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


@dataclass(frozen=True)
class SurveyWebhookDeps:
    webhook_secret: Callable[[], str]
    load_survey_job: Callable[[str], Dict[str, Any]]
    write_survey_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    write_survey_raw_payload: Callable[[str, str, Dict[str, Any]], Any]
    enqueue_survey_job: Callable[[str], Dict[str, Any]]
    now_iso: Callable[[], str]
    diag_log: Callable[[str, Dict[str, Any]], None]



def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")



def compute_survey_signature(payload: Dict[str, Any], secret: str) -> str:
    digest = hmac.new(
        str(secret or "").encode("utf-8"),
        _canonical_payload_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"



def _verify_signature(payload: Dict[str, Any], signature: str, secret: str) -> None:
    expected = compute_survey_signature(payload, secret)
    if not hmac.compare_digest(str(signature or ""), expected):
        raise SurveyWebhookError(401, "invalid_signature")



def _payload_teacher_id(payload: Dict[str, Any]) -> str:
    teacher_id = str(payload.get("teacher_id") or "").strip()
    if not teacher_id and isinstance(payload.get("teacher"), dict):
        teacher_id = str((payload.get("teacher") or {}).get("id") or "").strip()
    return teacher_id



def _payload_class_name(payload: Dict[str, Any]) -> str:
    class_name = str(payload.get("class_name") or "").strip()
    if not class_name and isinstance(payload.get("class"), dict):
        class_name = str((payload.get("class") or {}).get("name") or "").strip()
    return class_name



def _payload_external_id(payload: Dict[str, Any]) -> str:
    for key in ("submission_id", "report_id", "id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    digest = hashlib.sha1(_canonical_payload_bytes(payload)).hexdigest()[:12]
    return digest



def _safe_id(value: str, prefix: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "_", str(value or "")).strip("_")
    if cleaned:
        return cleaned
    return f"{prefix}_{hashlib.sha1(str(value or '').encode('utf-8')).hexdigest()[:10]}"



def ingest_survey_webhook(
    *,
    provider: str,
    payload: Dict[str, Any],
    signature: str,
    deps: SurveyWebhookDeps,
) -> Dict[str, Any]:
    secret = str(deps.webhook_secret() or "").strip()
    if secret:
        _verify_signature(payload, signature, secret)

    teacher_id = _payload_teacher_id(payload)
    class_name = _payload_class_name(payload)
    if not teacher_id or not class_name:
        raise SurveyWebhookError(400, "teacher_scope_missing")

    external_id = _payload_external_id(payload)
    job_id = f"survey_{_safe_id(provider, 'provider')}_{_safe_id(external_id, 'submission')}"

    try:
        existing = deps.load_survey_job(job_id)
    except FileNotFoundError:
        existing = {}

    if existing:
        return {
            "ok": True,
            "job_id": job_id,
            "status": str(existing.get("queue_status") or "queued"),
            "duplicate": True,
        }

    deps.write_survey_raw_payload(job_id, f"{_safe_id(provider, 'provider')}.json", payload)
    deps.write_survey_job(
        job_id,
        {
            "job_id": job_id,
            "provider": provider,
            "external_id": external_id,
            "teacher_id": teacher_id,
            "class_name": class_name,
            "status": "webhook_received",
            "created_at": deps.now_iso(),
        },
    )
    enqueue_result = deps.enqueue_survey_job(job_id)
    deps.write_survey_job(
        job_id,
        {
            "queue_status": "queued",
            "enqueue_result": enqueue_result,
        },
    )
    deps.diag_log(
        "survey.webhook.accepted",
        {
            "job_id": job_id,
            "provider": provider,
            "teacher_id": teacher_id,
            "class_name": class_name,
        },
    )
    return {"ok": True, "job_id": job_id, "status": "queued", "duplicate": False}
