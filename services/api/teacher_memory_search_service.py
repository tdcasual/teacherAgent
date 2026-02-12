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


def teacher_memory_search(
    teacher_id: str,
    query: str,
    *,
    deps: TeacherMemorySearchDeps,
    limit: int = 5,
) -> Dict[str, Any]:
    deps.ensure_teacher_workspace(teacher_id)
    q = (query or "").strip()
    if not q:
        return {"matches": []}
    topk = max(1, int(limit or 5))

    try:
        mem0_res = deps.mem0_search(teacher_id, q, topk)
        if mem0_res.get("ok") and mem0_res.get("matches"):
            raw_matches = list(mem0_res.get("matches") or [])
            matches: List[Dict[str, Any]] = []
            dropped_expired = 0
            for item in raw_matches:
                if not isinstance(item, dict):
                    continue
                if deps.search_filter_expired:
                    pid = str(item.get("proposal_id") or "").strip()
                    if pid:
                        rec = deps.load_record(teacher_id, pid)
                        if isinstance(rec, dict) and deps.is_expired_record(rec):
                            dropped_expired += 1
                            continue
                matches.append(item)
                if len(matches) >= topk:
                    break
            deps.diag_log(
                "teacher.mem0.search.hit",
                {"teacher_id": teacher_id, "query_len": len(q), "matches": len(matches), "dropped_expired": dropped_expired},
            )
            deps.log_event(
                teacher_id,
                "search",
                {
                    "mode": "mem0",
                    "query": q[:120],
                    "hits": len(matches),
                    "raw_hits": len(raw_matches),
                    "dropped_expired": dropped_expired,
                },
            )
            if matches:
                return {"matches": matches, "mode": "mem0"}
        if mem0_res.get("error"):
            deps.diag_log(
                "teacher.mem0.search.error",
                {"teacher_id": teacher_id, "query_len": len(q), "error": str(mem0_res.get("error"))[:200]},
            )
        else:
            deps.diag_log("teacher.mem0.search.miss", {"teacher_id": teacher_id, "query_len": len(q)})
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("teacher.mem0.search.crash", {"teacher_id": teacher_id, "error": str(exc)[:200]})

    files: List[Path] = [
        deps.teacher_workspace_file(teacher_id, "MEMORY.md"),
        deps.teacher_workspace_file(teacher_id, "USER.md"),
        deps.teacher_workspace_file(teacher_id, "AGENTS.md"),
        deps.teacher_workspace_file(teacher_id, "SOUL.md"),
    ]
    daily_dir = deps.teacher_daily_memory_dir(teacher_id)
    if daily_dir.exists():
        daily_files = sorted(daily_dir.glob("*.md"), key=lambda p: p.name, reverse=True)[:14]
        files.extend(daily_files)

    keyword_matches: List[Dict[str, Any]] = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            _log.debug("skipping unreadable memory file %s", path)
            continue
        for idx, line in enumerate(lines, start=1):
            if q not in line:
                continue
            start = max(0, idx - 2)
            end = min(len(lines), idx + 1)
            snippet = "\n".join(lines[start:end]).strip()
            keyword_matches.append(
                {
                    "source": "keyword",
                    "file": str(path),
                    "line": idx,
                    "snippet": snippet[:400],
                }
            )
            if len(keyword_matches) >= topk:
                deps.log_event(
                    teacher_id,
                    "search",
                    {
                        "mode": "keyword",
                        "query": q[:120],
                        "hits": len(keyword_matches),
                        "raw_hits": len(keyword_matches),
                    },
                )
                return {"matches": keyword_matches, "mode": "keyword"}
    deps.log_event(
        teacher_id,
        "search",
        {
            "mode": "keyword",
            "query": q[:120],
            "hits": len(keyword_matches),
            "raw_hits": len(keyword_matches),
        },
    )
    return {"matches": keyword_matches, "mode": "keyword"}
