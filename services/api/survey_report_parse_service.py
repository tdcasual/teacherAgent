from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)
from .upload_text_service import clean_ocr_text

_log = logging.getLogger(__name__)

_CORE_MISSING_FIELDS = ("title", "teacher_id", "class_name")
_SAMPLE_SIZE_FIELDS = ("sample_size",)
_TITLE_RE = re.compile(r"(?:问\s*卷\s*标\s*题|报告标题|问卷名称|标题)\s*[:：=]?\s*([^\n|]+)", re.IGNORECASE)
_CLASS_RE = re.compile(r"(?:班\s*级|class_name)\s*[:：=]?\s*([^\n|]+)", re.IGNORECASE)
_SAMPLE_SIZE_RE = re.compile(r"(?:样\s*本\s*量|样\s*本\s*数|回收样本|有效样本|sample[_ ]?size)\s*[:：=]?\s*(\d+)", re.IGNORECASE)
_QUESTION_RE = re.compile(r"(?:^|\b)(Q\s*\d+)\s*[:：]?\s*(.*)$", re.IGNORECASE)
_GROUP_RE = re.compile(r"(?:分\s*组|群\s*体|group)\s*[:：=]?\s*([^|,，]+)(.*)$", re.IGNORECASE)
_THEME_RE = re.compile(r"(?:高频主题|文本主题|反馈主题|主题)\s*[:：=]?\s*([^|,，]+)(.*)$", re.IGNORECASE)
_STAT_RE = re.compile(r"([A-Za-z0-9_:+\-一-龥]{1,32})\s*[:：=]\s*(\d+)")
_COUNT_RE = re.compile(r"(?:count|次数|数量|evidence_count)\s*[:：=]\s*(\d+)", re.IGNORECASE)
_EXCERPTS_RE = re.compile(r"(?:excerpts?|摘录|示例)\s*[:：=]\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class SurveyReportParseDeps:
    extract_text_from_file: Callable[..., str]
    extract_text_from_html: Callable[[str], str]
    clean_text: Callable[[str], str] = clean_ocr_text



def _clean_value(value: Any) -> Optional[str]:
    text = str(value or "").strip().strip("#?：:|，,;；")
    return text or None



def _dedupe_strings(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result



def _teacher_id_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    teacher_id = _clean_value(payload.get("teacher_id"))
    if teacher_id:
        return teacher_id
    teacher = payload.get("teacher")
    if isinstance(teacher, dict):
        return _clean_value(teacher.get("id"))
    return None



def _class_name_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    class_name = _clean_value(payload.get("class_name"))
    if class_name:
        return class_name
    klass = payload.get("class")
    if isinstance(klass, dict):
        return _clean_value(klass.get("name"))
    return None



def _sample_size_from_payload(payload: Dict[str, Any]) -> Optional[int]:
    raw = payload.get("sample_size")
    try:
        return int(raw) if raw is not None else None
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None



def _survey_title_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    return _clean_value(payload.get("title"))



def _submission_id_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("submission_id", "report_id", "id"):
        value = _clean_value(payload.get(key))
        if value:
            return value
    return None



def _normalized_lines(text: str, clean_text: Callable[[str], str]) -> List[str]:
    normalized = clean_text(text)
    lines: List[str] = []
    for raw_line in normalized.splitlines():
        line = re.sub(r"\s+", " ", raw_line or "").strip()
        if line:
            lines.append(line)
    return lines



def _search_text_value(pattern: re.Pattern[str], texts: List[str]) -> Optional[str]:
    for text in texts:
        match = pattern.search(text)
        if not match:
            continue
        value = _clean_value(match.group(1))
        if value:
            return value
    return None



def _search_text_int(pattern: re.Pattern[str], texts: List[str]) -> Optional[int]:
    for text in texts:
        for raw_line in str(text or "").splitlines():
            line = str(raw_line or "").lstrip(" #?*:-|，,;；")
            match = pattern.match(line)
            if not match:
                continue
            try:
                return int(match.group(1))
            except Exception:
                _log.debug("numeric conversion failed", exc_info=True)
    return None



def _infer_attachment_kind(attachment: Dict[str, Any]) -> str:
    explicit = _clean_value(attachment.get("kind") or attachment.get("type") or attachment.get("source_kind"))
    if explicit:
        return explicit.lower()
    name = str(attachment.get("name") or attachment.get("path") or "").lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
        return "image"
    if name.endswith((".html", ".htm")):
        return "web"
    return "attachment"



def _attachment_name(attachment: Dict[str, Any], index: int) -> str:
    name = _clean_value(attachment.get("name"))
    if name:
        return name
    path = _clean_value(attachment.get("path"))
    if path:
        return Path(path).name
    url = _clean_value(attachment.get("url"))
    if url:
        return url
    return f"attachment-{index + 1}"



def _extract_attachment_text(attachment: Dict[str, Any], *, deps: SurveyReportParseDeps) -> str:
    inline_text = _clean_value(attachment.get("text") or attachment.get("content") or attachment.get("ocr_text"))
    if inline_text:
        return deps.clean_text(inline_text)
    html = attachment.get("html")
    if html is not None:
        return deps.extract_text_from_html(str(html))
    path = _clean_value(attachment.get("path"))
    if path:
        return deps.extract_text_from_file(Path(path))
    return ""



def _question_entry(questions: Dict[str, Dict[str, Any]], question_id: str) -> Dict[str, Any]:
    return questions.setdefault(
        question_id,
        {
            "question_id": question_id,
            "prompt": None,
            "response_type": None,
            "stats": {},
        },
    )


def _apply_question_stats(entry: Dict[str, Any], stat_text: str, *, skip_labels: set[str]) -> None:
    stats_found = False
    for label, count in _STAT_RE.findall(stat_text):
        if label.lower() in skip_labels or label.upper().startswith("Q"):
            continue
        entry.setdefault("stats", {})[str(label)] = int(count)
        stats_found = True
    if stats_found:
        entry["response_type"] = entry.get("response_type") or "single_choice"


def _parse_question_header(questions: Dict[str, Dict[str, Any]], question_match: re.Match[str]) -> str:
    question_id = re.sub(r"\s+", "", question_match.group(1).upper())
    rest = str(question_match.group(2) or "").strip()
    prompt = _clean_value(rest.split("|")[0])
    entry = _question_entry(questions, question_id)
    if prompt:
        entry["prompt"] = entry.get("prompt") or prompt
    _apply_question_stats(entry, rest, skip_labels=set())
    return question_id


def _parse_question_continuation(
    questions: Dict[str, Dict[str, Any]],
    current_question_id: Optional[str],
    line: str,
) -> None:
    if not current_question_id:
        return
    entry = _question_entry(questions, current_question_id)
    _apply_question_stats(entry, line, skip_labels={"sample_size", "count", "evidence_count"})


def _parse_question_summaries(texts: List[str], clean_text: Callable[[str], str]) -> List[SurveyQuestionSummary]:
    questions: Dict[str, Dict[str, Any]] = {}
    current_question_id: Optional[str] = None

    for text in texts:
        for line in _normalized_lines(text, clean_text):
            group_match = _GROUP_RE.search(line)
            theme_match = _THEME_RE.search(line)
            question_match = _QUESTION_RE.search(line)

            if group_match or theme_match:
                current_question_id = None

            if question_match:
                current_question_id = _parse_question_header(questions, question_match)
                continue

            _parse_question_continuation(questions, current_question_id, line)

    return [SurveyQuestionSummary(**item) for _, item in sorted(questions.items())]



def _parse_group_breakdowns(texts: List[str], clean_text: Callable[[str], str]) -> List[SurveyGroupBreakdown]:
    groups: Dict[str, Dict[str, Any]] = {}
    for text in texts:
        for line in _normalized_lines(text, clean_text):
            match = _GROUP_RE.search(line)
            if not match:
                continue
            group_name = _clean_value(match.group(1)) or "group"
            rest = str(match.group(2) or "")
            entry = groups.setdefault(group_name, {"group_name": group_name, "sample_size": None, "stats": {}})
            sample_match = _SAMPLE_SIZE_RE.search(rest)
            if sample_match:
                entry["sample_size"] = int(sample_match.group(1))
            for label, count in _STAT_RE.findall(rest):
                if label.lower() == "sample_size":
                    continue
                entry.setdefault("stats", {})[str(label)] = int(count)
    return [SurveyGroupBreakdown(**item) for _, item in sorted(groups.items())]



def _split_excerpts(raw: str) -> List[str]:
    parts = re.split(r"[；;|]", raw or "")
    return [item for item in (_clean_value(part) for part in parts) if item]



def _parse_free_text_signals(texts: List[str], clean_text: Callable[[str], str]) -> List[SurveyFreeTextSignal]:
    signals: Dict[str, Dict[str, Any]] = {}
    for text in texts:
        for line in _normalized_lines(text, clean_text):
            match = _THEME_RE.search(line)
            if not match:
                continue
            theme = _clean_value(match.group(1)) or "未分类反馈"
            rest = str(match.group(2) or "")
            entry = signals.setdefault(theme, {"theme": theme, "evidence_count": 0, "excerpts": []})
            count_match = _COUNT_RE.search(rest)
            if count_match:
                entry["evidence_count"] = max(int(entry.get("evidence_count") or 0), int(count_match.group(1)))
            excerpts_match = _EXCERPTS_RE.search(rest)
            if excerpts_match:
                entry["excerpts"] = _dedupe_strings(list(entry.get("excerpts") or []) + _split_excerpts(excerpts_match.group(1)))
            elif entry.get("evidence_count") and not entry.get("excerpts"):
                entry["excerpts"] = []
    return [SurveyFreeTextSignal(**item) for _, item in sorted(signals.items())]



def _build_missing_fields(
    *,
    title: Optional[str],
    teacher_id: Optional[str],
    class_name: Optional[str],
    sample_size: Optional[int],
    question_summaries: List[SurveyQuestionSummary],
    attachment_missing_fields: List[str],
) -> List[str]:
    missing_fields: List[str] = []
    if not title:
        missing_fields.append("title")
    if not teacher_id:
        missing_fields.append("teacher_id")
    if not class_name:
        missing_fields.append("class_name")
    if sample_size is None:
        missing_fields.append("sample_size")
    if not question_summaries:
        missing_fields.append("question_summaries")
    missing_fields.extend(attachment_missing_fields)
    return _dedupe_strings(missing_fields)



def _compute_parse_confidence(
    *,
    missing_fields: List[str],
    has_question_summaries: bool,
    has_empty_attachment_text: bool,
    has_image_attachment: bool,
) -> float:
    score = 0.85
    core_missing_count = sum(1 for field in _CORE_MISSING_FIELDS if field in missing_fields)
    score -= 0.15 * core_missing_count
    if any(field in missing_fields for field in _SAMPLE_SIZE_FIELDS):
        score -= 0.10
    if not has_question_summaries:
        score -= 0.15
    if has_empty_attachment_text:
        score -= 0.10
    if has_image_attachment:
        score -= 0.05
    return max(0.2, round(score, 4))



def parse_survey_report_payload(
    *,
    provider: str,
    payload: Dict[str, Any],
    deps: SurveyReportParseDeps,
) -> SurveyEvidenceBundle:
    attachments = payload.get("attachments") or []
    source_texts: List[str] = []
    attachment_records: List[Dict[str, Any]] = []
    attachment_missing_fields: List[str] = []
    has_image_attachment = False
    has_empty_attachment_text = False

    direct_text = _clean_value(payload.get("report_text") or payload.get("text"))
    if direct_text:
        source_texts.append(deps.clean_text(direct_text))
    html_text = payload.get("html")
    if html_text is not None:
        extracted_html = deps.extract_text_from_html(str(html_text))
        if extracted_html:
            source_texts.append(extracted_html)

    for index, raw_attachment in enumerate(attachments):
        if not isinstance(raw_attachment, dict):
            continue
        attachment = dict(raw_attachment)
        name = _attachment_name(attachment, index)
        kind = _infer_attachment_kind(attachment)
        has_image_attachment = has_image_attachment or kind == "image"
        text = ""
        parse_status = "parsed"
        try:
            text = _extract_attachment_text(attachment, deps=deps)
        except Exception:
            _log.debug("survey attachment parse failed", exc_info=True)
            parse_status = "error"
        if not text:
            parse_status = "missing_text"
            has_empty_attachment_text = True
            attachment_missing_fields.append(f"attachment_text:{name}")
        else:
            source_texts.append(text)
        attachment_records.append(
            {
                "name": name,
                "kind": kind,
                "path": _clean_value(attachment.get("path")),
                "url": _clean_value(attachment.get("url")),
                "text_length": len(text),
                "parse_status": parse_status,
            }
        )

    title = _survey_title_from_payload(payload) or _search_text_value(_TITLE_RE, source_texts)
    teacher_id = _teacher_id_from_payload(payload)
    class_name = _class_name_from_payload(payload) or _search_text_value(_CLASS_RE, source_texts)
    sample_size = _sample_size_from_payload(payload)
    if sample_size is None:
        sample_size = _search_text_int(_SAMPLE_SIZE_RE, source_texts)

    question_summaries = _parse_question_summaries(source_texts, deps.clean_text)
    group_breakdowns = _parse_group_breakdowns(source_texts, deps.clean_text)
    free_text_signals = _parse_free_text_signals(source_texts, deps.clean_text)
    missing_fields = _build_missing_fields(
        title=title,
        teacher_id=teacher_id,
        class_name=class_name,
        sample_size=sample_size,
        question_summaries=question_summaries,
        attachment_missing_fields=attachment_missing_fields,
    )

    return SurveyEvidenceBundle(
        survey_meta=SurveyMeta(
            title=title,
            provider=str(provider or "unstructured").strip() or "unstructured",
            submission_id=_submission_id_from_payload(payload),
        ),
        audience_scope=SurveyAudienceScope(
            teacher_id=teacher_id,
            class_name=class_name,
            sample_size=sample_size,
        ),
        question_summaries=question_summaries,
        group_breakdowns=group_breakdowns,
        free_text_signals=free_text_signals,
        attachments=attachment_records,
        parse_confidence=_compute_parse_confidence(
            missing_fields=missing_fields,
            has_question_summaries=bool(question_summaries),
            has_empty_attachment_text=has_empty_attachment_text,
            has_image_attachment=has_image_attachment,
        ),
        missing_fields=missing_fields,
        provenance={
            "source": "unstructured",
            "provider": provider,
            "attachment_count": len(attachment_records),
            "source_kinds": sorted({str(item.get("kind") or "attachment") for item in attachment_records}),
        },
    )
