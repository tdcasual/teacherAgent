from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

_SUBJECT_DISPLAY = {
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "math": "数学",
    "chinese": "语文",
    "english": "英语",
    "history": "历史",
    "geography": "地理",
    "politics": "政治",
}

_SUBJECT_SYNONYMS = {
    "physics": ("物理", "physics", "phy"),
    "chemistry": ("化学", "chemistry", "chem"),
    "biology": ("生物", "biology", "bio"),
    "math": ("数学", "math", "mathematics"),
    "chinese": ("语文", "chinese"),
    "english": ("英语", "english"),
    "history": ("历史", "history"),
    "geography": ("地理", "geography"),
    "politics": ("政治", "politics"),
}

_SCORE_HINTS = ("成绩", "得分", "分数", "score")
_SUBJECT_GENERIC_HINTS = ("单科", "学科", "科目", "subject")


def subject_display(subject_key: Optional[str]) -> str:
    key = str(subject_key or "").strip().lower()
    return _SUBJECT_DISPLAY.get(key, "单科")


def _contains_token(text: str, lowered: str, token: str) -> bool:
    token_norm = str(token or "").strip().lower()
    if not token_norm:
        return False
    if any(ord(ch) > 127 for ch in token_norm):
        return token_norm in lowered
    searchable = re.sub(r"[_\-/]+", " ", lowered)
    return re.search(rf"\b{re.escape(token_norm)}\b", searchable) is not None


def _detect_subject_keys(text: str) -> Set[str]:
    raw = str(text or "")
    lowered = raw.lower()
    hits: Set[str] = set()
    for subject_key, synonyms in _SUBJECT_SYNONYMS.items():
        if any(_contains_token(raw, lowered, token) for token in synonyms):
            hits.add(subject_key)
    return hits


def looks_like_subject_score_request(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    has_score = any(hint in normalized for hint in _SCORE_HINTS[:-1]) or (_SCORE_HINTS[-1] in lowered)
    has_subject = bool(_detect_subject_keys(normalized)) or any(
        hint in normalized for hint in _SUBJECT_GENERIC_HINTS[:-1]
    ) or (_SUBJECT_GENERIC_HINTS[-1] in lowered)
    return has_score and has_subject


def extract_requested_subject(text: str) -> Optional[str]:
    hits = _detect_subject_keys(str(text or ""))
    if len(hits) != 1:
        return None
    return next(iter(hits))


def _iter_overview_subject_texts(overview: Dict[str, Any]) -> Iterable[str]:
    if not isinstance(overview, dict):
        return []

    texts = []
    meta = overview.get("meta") if isinstance(overview.get("meta"), dict) else {}
    for key in ("subject", "subject_name", "subject_hint", "title", "name"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value)

    for key in ("exam_id", "notes"):
        value = overview.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value)

    for key in ("warnings", "paper_files", "answer_files", "score_files"):
        value = overview.get(key)
        if isinstance(value, list):
            for item in value[:20]:
                if isinstance(item, str) and item.strip():
                    texts.append(item)

    files = overview.get("files") if isinstance(overview.get("files"), dict) else {}
    manifest_path_raw = str(files.get("manifest") or "").strip()
    if manifest_path_raw:
        try:
            manifest_path = Path(manifest_path_raw)
            exam_dir = manifest_path.parent
            texts.append(exam_dir.name)
            for folder_name in ("paper", "answers", "scores"):
                folder = exam_dir / folder_name
                if not folder.exists() or not folder.is_dir():
                    continue
                for item in list(folder.iterdir())[:20]:
                    if item.is_file():
                        texts.append(item.name)
        except Exception:
            pass

    return texts


def infer_exam_subject_from_overview(overview: Dict[str, Any]) -> Optional[str]:
    hits: Set[str] = set()
    for text in _iter_overview_subject_texts(overview):
        hits.update(_detect_subject_keys(text))
    if len(hits) != 1:
        return None
    return next(iter(hits))


def should_guard_total_mode_subject_request(
    last_user_text: str,
    overview: Dict[str, Any],
) -> Tuple[bool, Optional[str], Optional[str]]:
    score_mode = str((overview or {}).get("score_mode") or "").strip().lower()
    if score_mode != "total":
        return False, extract_requested_subject(last_user_text), infer_exam_subject_from_overview(overview)

    requested_subject = extract_requested_subject(last_user_text)
    inferred_subject = infer_exam_subject_from_overview(overview)
    return True, requested_subject, inferred_subject
