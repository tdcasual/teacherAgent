from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        _log.debug("env var %s=%r is not a valid int, using default %d", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except Exception:
        _log.debug("env var %s=%r is not a valid float, using default %s", name, raw, default)
        return default


def teacher_mem0_enabled() -> bool:
    return _env_bool("TEACHER_MEM0_ENABLED", False)


def teacher_mem0_write_enabled() -> bool:
    if not teacher_mem0_enabled():
        return False
    return _env_bool("TEACHER_MEM0_WRITE_ENABLED", True)


def teacher_mem0_index_daily_enabled() -> bool:
    # Daily logs can get noisy/costly; keep opt-in.
    return _env_bool("TEACHER_MEM0_INDEX_DAILY", False)


def teacher_mem0_topk_default() -> int:
    return max(1, _env_int("TEACHER_MEM0_TOPK", 5))


def teacher_mem0_threshold_default() -> float:
    # Qdrant scores are typically [0, 1]; keep default permissive.
    return max(0.0, _env_float("TEACHER_MEM0_THRESHOLD", 0.0))


def teacher_mem0_chunk_chars() -> int:
    return max(200, _env_int("TEACHER_MEM0_CHUNK_CHARS", 900))


def teacher_mem0_chunk_overlap_chars() -> int:
    return max(0, _env_int("TEACHER_MEM0_CHUNK_OVERLAP_CHARS", 100))


def _teacher_user_id(teacher_id: str) -> str:
    return f"teacher:{teacher_id}"


_MEM0_LOCK = threading.Lock()
_MEM0_INSTANCE: Any = None
_MEM0_INIT_ERROR: Optional[str] = None


def get_mem0() -> Optional[Any]:
    """
    Lazy-initialize mem0.Memory using repo-local mem0_config.get_config().
    Never throws: returns None on init failure.
    """
    global _MEM0_INSTANCE, _MEM0_INIT_ERROR
    if _MEM0_INSTANCE is not None:
        return _MEM0_INSTANCE
    if _MEM0_INIT_ERROR is not None:
        return None
    with _MEM0_LOCK:
        if _MEM0_INSTANCE is not None:
            return _MEM0_INSTANCE
        if _MEM0_INIT_ERROR is not None:
            return None
        try:
            from mem0 import Memory  # type: ignore
            from mem0_config import get_config  # type: ignore

            _MEM0_INSTANCE = Memory.from_config(get_config())
            return _MEM0_INSTANCE
        except Exception as exc:
            _log.warning("mem0 initialization failed", exc_info=True)
            _MEM0_INIT_ERROR = str(exc)
            return None


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """
    Simple char-based chunker (tokenizer-free), good enough for sem-search.
    """
    s = (text or "").strip()
    if not s:
        return []
    if len(s) <= max_chars:
        return [s]

    chunks: List[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(s):
        end = min(len(s), start + max_chars)
        chunk = s[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(s):
            break
        start += step
    return chunks


def teacher_mem0_should_index_target(target: str) -> bool:
    t = str(target or "").upper()
    if t == "DAILY":
        return teacher_mem0_index_daily_enabled()
    return t in {"MEMORY", "USER", "AGENTS", "SOUL", "HEARTBEAT"}


def teacher_mem0_search(
    teacher_id: str,
    query: str,
    *,
    limit: Optional[int] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    if not teacher_mem0_enabled():
        return {"ok": False, "disabled": True, "matches": []}

    memory = get_mem0()
    if memory is None:
        return {"ok": False, "error": _MEM0_INIT_ERROR or "mem0_unavailable", "matches": []}

    topk = max(1, int(limit or teacher_mem0_topk_default()))
    th = teacher_mem0_threshold_default() if threshold is None else float(threshold)
    user_id = _teacher_user_id(teacher_id)
    try:
        res = memory.search(query, user_id=user_id, limit=topk, threshold=th, rerank=False)
    except Exception as exc:
        _log.warning("mem0 search failed for teacher_id=%s", teacher_id, exc_info=True)
        return {"ok": False, "error": str(exc), "matches": []}

    items = []
    if isinstance(res, dict) and isinstance(res.get("results"), list):
        items = res.get("results") or []
    elif isinstance(res, list):
        items = res

    matches: List[Dict[str, Any]] = []
    for item in items[:topk]:
        if not isinstance(item, dict):
            continue
        md = item.get("metadata") or {}
        if not isinstance(md, dict):
            md = {}
        matches.append(
            {
                "source": "mem0",
                "id": item.get("id"),
                "score": item.get("score"),
                "snippet": str(item.get("memory") or "")[:400],
                "created_at": item.get("created_at"),
                "file": md.get("file"),
                "title": md.get("title"),
                "proposal_id": md.get("proposal_id"),
                "target": md.get("target"),
            }
        )
    return {"ok": True, "matches": matches}


def teacher_mem0_index_entry(
    teacher_id: str,
    text: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not teacher_mem0_write_enabled():
        return {"ok": False, "disabled": True}

    memory = get_mem0()
    if memory is None:
        return {"ok": False, "error": _MEM0_INIT_ERROR or "mem0_unavailable"}

    base_md: Dict[str, Any] = {}
    if isinstance(metadata, dict):
        base_md.update(metadata)

    max_chars = teacher_mem0_chunk_chars()
    overlap = teacher_mem0_chunk_overlap_chars()
    chunks = _chunk_text(text, max_chars=max_chars, overlap_chars=overlap)
    if not chunks:
        return {"ok": False, "error": "empty_text"}

    user_id = _teacher_user_id(teacher_id)
    results: List[Any] = []
    for i, chunk in enumerate(chunks):
        md = dict(base_md)
        md["chunk_index"] = i
        md["chunk_total"] = len(chunks)
        try:
            results.append(memory.add(chunk, user_id=user_id, infer=False, metadata=md))
        except Exception as exc:
            _log.warning("mem0 index chunk %d/%d failed for teacher_id=%s", i, len(chunks), teacher_id, exc_info=True)
            return {"ok": False, "error": str(exc), "indexed": i, "total": len(chunks)}

    return {"ok": True, "chunks": len(chunks), "results_count": len(results)}

