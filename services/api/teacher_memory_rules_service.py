from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Sequence, Tuple


def teacher_memory_is_sensitive(content: str, *, patterns: Sequence[Any]) -> bool:
    text = str(content or "")
    if not text.strip():
        return False
    return any(p.search(text) for p in patterns)


def teacher_memory_parse_dt(raw: Any) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def teacher_memory_record_ttl_days(
    rec: Dict[str, Any],
    *,
    ttl_days_daily: int,
    ttl_days_memory: int,
) -> int:
    try:
        if rec.get("ttl_days") is not None:
            return max(0, int(rec.get("ttl_days") or 0))
    except Exception:
        pass
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
    if isinstance(meta, dict):
        try:
            if meta.get("ttl_days") is not None:
                return max(0, int(meta.get("ttl_days") or 0))
        except Exception:
            pass
    target = str(rec.get("target") or "").strip().upper()
    source = str(rec.get("source") or "").strip().lower()
    if target == "DAILY" or source == "auto_flush":
        return ttl_days_daily
    return ttl_days_memory


def teacher_memory_record_expire_at(
    rec: Dict[str, Any],
    *,
    parse_dt: Callable[[Any], Optional[datetime]],
    record_ttl_days: Callable[[Dict[str, Any]], int],
) -> Optional[datetime]:
    expire_from_field = parse_dt(rec.get("expires_at"))
    if expire_from_field is not None:
        return expire_from_field
    ttl_days = record_ttl_days(rec)
    if ttl_days <= 0:
        return None
    base_ts = parse_dt(rec.get("applied_at")) or parse_dt(rec.get("created_at"))
    if base_ts is None:
        return None
    return base_ts + timedelta(days=int(ttl_days))


def teacher_memory_is_expired_record(
    rec: Dict[str, Any],
    *,
    decay_enabled: bool,
    record_expire_at: Callable[[Dict[str, Any]], Optional[datetime]],
    now: Optional[datetime] = None,
) -> bool:
    if not decay_enabled:
        return False
    expire_at = record_expire_at(rec)
    if expire_at is None:
        return False
    if now is not None:
        now_dt = now
    elif expire_at.tzinfo:
        now_dt = datetime.now(expire_at.tzinfo)
    else:
        now_dt = datetime.now()
    return now_dt >= expire_at


def teacher_memory_age_days(
    rec: Dict[str, Any],
    *,
    parse_dt: Callable[[Any], Optional[datetime]],
    now: Optional[datetime] = None,
) -> int:
    base_ts = parse_dt(rec.get("applied_at")) or parse_dt(rec.get("created_at"))
    if base_ts is None:
        return 0
    if base_ts.tzinfo:
        now_dt = now or datetime.now(base_ts.tzinfo)
    else:
        now_dt = now or datetime.now()
    return max(0, int((now_dt - base_ts).total_seconds() // 86400))


def teacher_memory_norm_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    compact = re.sub(r"[，。！？、,.!?;；:：`'\"“”‘’（）()\\[\\]{}<>]", "", compact)
    return compact


def teacher_memory_stable_hash(*parts: str) -> str:
    joined = "||".join(str(p or "").strip() for p in parts)
    return hashlib.sha1(joined.encode("utf-8", errors="ignore")).hexdigest()[:20]


def teacher_memory_priority_score(
    *,
    target: str,
    title: str,
    content: str,
    source: str,
    meta: Optional[Dict[str, Any]] = None,
    durable_intent_patterns: Sequence[Any],
    auto_infer_stable_patterns: Sequence[Any],
    temporary_hint_patterns: Sequence[Any],
    is_sensitive: Callable[[str], bool],
    norm_text: Callable[[str], str],
) -> int:
    text = f"{title or ''}\n{content or ''}".strip()
    source_norm = str(source or "manual").strip().lower()
    target_norm = str(target or "MEMORY").strip().upper()
    score = 0.0

    if source_norm == "manual":
        score += 70
    elif source_norm == "auto_intent":
        score += 62
    elif source_norm == "auto_infer":
        score += 54
    elif source_norm == "auto_flush":
        score += 36
    else:
        score += 44

    if target_norm == "MEMORY":
        score += 12
    elif target_norm == "DAILY":
        score += 4

    if any(p.search(text) for p in durable_intent_patterns):
        score += 15
    if any(p.search(text) for p in auto_infer_stable_patterns):
        score += 10
    if any(p.search(text) for p in temporary_hint_patterns):
        score -= 18
    if is_sensitive(text):
        score = 0
    if len(norm_text(text)) < 12:
        score -= 8
    if "先" in text and "后" in text:
        score += 6
    if "模板" in text or "格式" in text or "结构" in text:
        score += 6

    if isinstance(meta, dict):
        try:
            similar_hits = int(meta.get("similar_hits") or 0)
        except Exception:
            similar_hits = 0
        if similar_hits > 0:
            score += min(16, similar_hits * 4)

    return max(0, min(100, int(round(score))))


def teacher_memory_rank_score(
    rec: Dict[str, Any],
    *,
    decay_enabled: bool,
    priority_score: Callable[..., int],
    age_days: Callable[[Dict[str, Any]], int],
    record_ttl_days: Callable[[Dict[str, Any]], int],
) -> float:
    priority = rec.get("priority_score")
    parsed_priority: Optional[float] = None
    if isinstance(priority, (int, float)):
        parsed_priority = float(priority)
    elif isinstance(priority, str):
        raw_priority = priority.strip()
        if raw_priority:
            try:
                parsed_priority = float(raw_priority)
            except ValueError:
                parsed_priority = None
    if parsed_priority is None:
        p = float(
            priority_score(
                target=str(rec.get("target") or "MEMORY"),
                title=str(rec.get("title") or ""),
                content=str(rec.get("content") or ""),
                source=str(rec.get("source") or "manual"),
                meta=rec.get("meta") if isinstance(rec.get("meta"), dict) else None,
            )
        )
    else:
        p = parsed_priority
    age = age_days(rec)
    ttl_days = record_ttl_days(rec)
    if not decay_enabled or ttl_days <= 0:
        return p
    decay = max(0.2, 1.0 - (age / max(1, ttl_days)))
    return p * decay


def teacher_memory_shingles(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return set()
    if len(compact) == 1:
        return {compact}
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def teacher_memory_loose_match(
    a: str,
    b: str,
    *,
    norm_text: Callable[[str], str],
) -> bool:
    na = norm_text(a)
    nb = norm_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) <= len(nb):
        short, long = na, nb
    else:
        short, long = nb, na
    if len(short) >= 12 and short in long:
        return True
    sa = teacher_memory_shingles(na)
    sb = teacher_memory_shingles(nb)
    if not sa or not sb:
        return False
    union = sa | sb
    if not union:
        return False
    jac = len(sa & sb) / len(union)
    return jac >= 0.72


def teacher_memory_has_term(text: str, terms: Tuple[str, ...]) -> bool:
    t = str(text or "")
    return any(term in t for term in terms)


def teacher_memory_conflicts(
    new_text: str,
    old_text: str,
    *,
    norm_text: Callable[[str], str],
    conflict_groups: Sequence[Tuple[Tuple[str, ...], Tuple[str, ...]]],
) -> bool:
    n = norm_text(new_text)
    o = norm_text(old_text)
    if not n or not o or n == o:
        return False
    for a_terms, b_terms in conflict_groups:
        if teacher_memory_has_term(n, a_terms) and teacher_memory_has_term(o, b_terms):
            return True
        if teacher_memory_has_term(n, b_terms) and teacher_memory_has_term(o, a_terms):
            return True
    return False
