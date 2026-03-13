from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemorySearchDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    mem0_search: Callable[[str, str, int], Dict[str, Any]]
    search_filter_expired: bool
    load_record: Callable[[str, str], Dict[str, Any]]
    is_expired_record: Callable[[Dict[str, Any]], bool]
    diag_log: Callable[[str, Dict[str, Any]], None]
    log_event: Callable[[str, str, Dict[str, Any]], None]
    teacher_workspace_file: Callable[[str, str], Path]
    teacher_daily_memory_dir: Callable[[str], Path]


@dataclass(frozen=True)
class _Mem0FilterStats:
    dropped_expired: int = 0
    dropped_inactive: int = 0
    dropped_missing: int = 0


def _filter_mem0_matches(
    teacher_id: str,
    raw_matches: List[Any],
    *,
    topk: int,
    deps: TeacherMemorySearchDeps,
) -> tuple[List[Dict[str, Any]], _Mem0FilterStats]:
    matches: List[Dict[str, Any]] = []
    dropped_expired = 0
    dropped_inactive = 0
    dropped_missing = 0
    for item in raw_matches:
        if not isinstance(item, dict):
            continue
        if deps.search_filter_expired:
            proposal_id = str(item.get("proposal_id") or "").strip()
            if proposal_id:
                record = deps.load_record(teacher_id, proposal_id)
                if not isinstance(record, dict):
                    dropped_missing += 1
                    continue
                status = str(record.get("status") or "").strip().lower()
                if status != "applied" or record.get("superseded_by"):
                    dropped_inactive += 1
                    continue
                if deps.is_expired_record(record):
                    dropped_expired += 1
                    continue
        matches.append(item)
        if len(matches) >= topk:
            break
    return matches, _Mem0FilterStats(
        dropped_expired=dropped_expired,
        dropped_inactive=dropped_inactive,
        dropped_missing=dropped_missing,
    )


def _search_mem0(
    teacher_id: str,
    query: str,
    *,
    topk: int,
    deps: TeacherMemorySearchDeps,
) -> Dict[str, Any] | None:
    try:
        mem0_result = deps.mem0_search(teacher_id, query, topk)
        if mem0_result.get("ok") and mem0_result.get("matches"):
            raw_matches = list(mem0_result.get("matches") or [])
            matches, stats = _filter_mem0_matches(teacher_id, raw_matches, topk=topk, deps=deps)
            deps.diag_log(
                "teacher.mem0.search.hit",
                {
                    "teacher_id": teacher_id,
                    "query_len": len(query),
                    "matches": len(matches),
                    "dropped_expired": stats.dropped_expired,
                    "dropped_inactive": stats.dropped_inactive,
                    "dropped_missing": stats.dropped_missing,
                },
            )
            deps.log_event(
                teacher_id,
                "search",
                {
                    "mode": "mem0",
                    "query": query[:120],
                    "hits": len(matches),
                    "raw_hits": len(raw_matches),
                    "dropped_expired": stats.dropped_expired,
                    "dropped_inactive": stats.dropped_inactive,
                    "dropped_missing": stats.dropped_missing,
                },
            )
            if matches:
                return {"matches": matches, "mode": "mem0"}
        if mem0_result.get("error"):
            deps.diag_log(
                "teacher.mem0.search.error",
                {"teacher_id": teacher_id, "query_len": len(query), "error": str(mem0_result.get("error"))[:200]},
            )
        else:
            deps.diag_log("teacher.mem0.search.miss", {"teacher_id": teacher_id, "query_len": len(query)})
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("teacher.mem0.search.crash", {"teacher_id": teacher_id, "error": str(exc)[:200]})
    return None


def _memory_search_files(teacher_id: str, deps: TeacherMemorySearchDeps) -> List[Path]:
    files = [
        deps.teacher_workspace_file(teacher_id, "MEMORY.md"),
        deps.teacher_workspace_file(teacher_id, "USER.md"),
        deps.teacher_workspace_file(teacher_id, "AGENTS.md"),
        deps.teacher_workspace_file(teacher_id, "SOUL.md"),
    ]
    daily_dir = deps.teacher_daily_memory_dir(teacher_id)
    if daily_dir.exists():
        files.extend(sorted(daily_dir.glob("*.md"), key=lambda path: path.name, reverse=True)[:14])
    return files


def _scan_keyword_matches(files: List[Path], query: str, *, topk: int) -> List[Dict[str, Any]]:
    keyword_matches: List[Dict[str, Any]] = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            _log.debug("skipping unreadable memory file %s", path)
            continue
        for index, line in enumerate(lines, start=1):
            if query not in line:
                continue
            start = max(0, index - 2)
            end = min(len(lines), index + 1)
            snippet = "\n".join(lines[start:end]).strip()
            keyword_matches.append(
                {
                    "source": "keyword",
                    "file": str(path),
                    "line": index,
                    "snippet": snippet[:400],
                }
            )
            if len(keyword_matches) >= topk:
                return keyword_matches
    return keyword_matches


def teacher_memory_search(
    teacher_id: str,
    query: str,
    *,
    deps: TeacherMemorySearchDeps,
    limit: int = 5,
) -> Dict[str, Any]:
    deps.ensure_teacher_workspace(teacher_id)
    normalized_query = (query or "").strip()
    if not normalized_query:
        return {"matches": []}
    topk = max(1, int(limit or 5))

    mem0_response = _search_mem0(teacher_id, normalized_query, topk=topk, deps=deps)
    if mem0_response is not None:
        return mem0_response

    keyword_matches = _scan_keyword_matches(_memory_search_files(teacher_id, deps), normalized_query, topk=topk)
    deps.log_event(
        teacher_id,
        "search",
        {
            "mode": "keyword",
            "query": normalized_query[:120],
            "hits": len(keyword_matches),
            "raw_hits": len(keyword_matches),
        },
    )
    return {"matches": keyword_matches, "mode": "keyword"}
