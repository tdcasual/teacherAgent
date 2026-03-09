from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Literal

from ..survey_bundle_merge_service import merge_survey_evidence_bundles
from ..survey_normalize_structured_service import normalize_structured_survey_payload
from ..survey_report_parse_service import SurveyReportParseDeps, parse_survey_report_payload
from ..survey_report_service import (
    build_survey_report_deps,
)
from ..survey_report_service import (
    get_survey_report as _get_survey_report_impl,
)
from ..survey_report_service import (
    list_survey_reports as _list_survey_reports_impl,
)
from ..survey_report_service import (
    list_survey_review_queue as _list_survey_review_queue_impl,
)
from ..survey_report_service import (
    rerun_survey_report as _rerun_survey_report_impl,
)
from ..upload_text_service import (
    UploadTextDeps,
    clean_ocr_text,
    extract_text_from_file,
    extract_text_from_html,
)


@dataclass(frozen=True)
class SurveyApplicationDeps:
    webhook_ingest: Callable[..., Dict[str, Any]]
    list_reports: Callable[..., Dict[str, Any]]
    get_report: Callable[..., Dict[str, Any]]
    rerun_report: Callable[..., Dict[str, Any]]
    list_review_queue: Callable[..., Dict[str, Any]]
    normalize_structured_payload: Callable[..., Any]
    parse_report_payload: Callable[..., Any]
    merge_evidence_bundles: Callable[..., Any]


class _NoopLimit:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        return False



def _default_upload_text_deps() -> UploadTextDeps:
    return UploadTextDeps(
        diag_log=lambda *_args, **_kwargs: None,
        limit=lambda _sem: _NoopLimit(),
        ocr_semaphore=object(),
    )



def _default_extract_text_from_file(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return extract_text_from_file(
        Path(path),
        deps=_default_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )



def build_survey_application_deps(core: Any) -> SurveyApplicationDeps:
    def _not_implemented(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        return {"ok": False, "error": "survey_not_implemented"}

    core_extract_text_from_file = getattr(core, "extract_text_from_file", None)

    def _extract_file(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
        if callable(core_extract_text_from_file):
            return core_extract_text_from_file(Path(path), language=language, ocr_mode=ocr_mode, prompt=prompt)
        return _default_extract_text_from_file(Path(path), language=language, ocr_mode=ocr_mode, prompt=prompt)

    parse_deps = SurveyReportParseDeps(
        extract_text_from_file=_extract_file,
        extract_text_from_html=extract_text_from_html,
        clean_text=clean_ocr_text,
    )
    report_deps = build_survey_report_deps(core)

    return SurveyApplicationDeps(
        webhook_ingest=getattr(core, "survey_webhook_ingest", _not_implemented),
        list_reports=lambda teacher_id, status=None: _list_survey_reports_impl(
            teacher_id=teacher_id,
            status=status,
            deps=report_deps,
        ),
        get_report=lambda report_id, teacher_id: _get_survey_report_impl(
            report_id=report_id,
            teacher_id=teacher_id,
            deps=report_deps,
        ),
        rerun_report=lambda report_id, teacher_id, reason=None: _rerun_survey_report_impl(
            report_id=report_id,
            teacher_id=teacher_id,
            reason=reason,
            deps=report_deps,
        ),
        list_review_queue=lambda teacher_id: _list_survey_review_queue_impl(
            teacher_id=teacher_id,
            deps=report_deps,
        ),
        normalize_structured_payload=lambda provider, payload: normalize_structured_survey_payload(provider=provider, payload=payload),
        parse_report_payload=lambda provider, payload: parse_survey_report_payload(provider=provider, payload=payload, deps=parse_deps),
        merge_evidence_bundles=lambda structured_bundle, parsed_bundle: merge_survey_evidence_bundles(
            structured_bundle=structured_bundle,
            parsed_bundle=parsed_bundle,
        ),
    )
