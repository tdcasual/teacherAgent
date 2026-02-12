from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class TeacherMemoryInsightsDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    recent_proposals: Callable[[str, int], List[Dict[str, Any]]]
    is_expired_record: Callable[[Dict[str, Any], datetime], bool]
    priority_score: Callable[..., int]
    rank_score: Callable[[Dict[str, Any]], float]
    age_days: Callable[[Dict[str, Any], datetime], int]
    load_events: Callable[[str, int], List[Dict[str, Any]]]
    parse_dt: Callable[[Any], Any]


def teacher_memory_insights(
    teacher_id: str,
    *,
    deps: TeacherMemoryInsightsDeps,
    days: int = 14,
) -> Dict[str, Any]:
    deps.ensure_teacher_workspace(teacher_id)
    window_days = max(1, min(int(days or 14), 90))
    now = datetime.now()
    window_start = now - timedelta(days=window_days)
    proposals = deps.recent_proposals(teacher_id, 1500)

    applied_total = 0
    rejected_total = 0
    active_total = 0
    expired_total = 0
    superseded_total = 0
    by_source: Dict[str, int] = {}
    by_target: Dict[str, int] = {}
    rejected_reasons: Dict[str, int] = {}
    active_priority_sum = 0.0
    active_priority_count = 0
    active_items: List[Dict[str, Any]] = []

    for rec in proposals:
        status = str(rec.get("status") or "").strip().lower()
        source = str(rec.get("source") or "manual").strip().lower() or "manual"
        target = str(rec.get("target") or "MEMORY").strip().upper() or "MEMORY"
        by_source[source] = by_source.get(source, 0) + 1
        by_target[target] = by_target.get(target, 0) + 1

        if status == "applied":
            applied_total += 1
            if rec.get("superseded_by"):
                superseded_total += 1
                continue
            if deps.is_expired_record(rec, now):
                expired_total += 1
                continue
            active_total += 1
            p = _coerce_float(rec.get("priority_score"))
            if p is None:
                p = float(
                    deps.priority_score(
                        target=target,
                        title=str(rec.get("title") or ""),
                        content=str(rec.get("content") or ""),
                        source=source,
                        meta=rec.get("meta") if isinstance(rec.get("meta"), dict) else None,
                    )
                )
            active_priority_sum += p
            active_priority_count += 1
            active_items.append(
                {
                    "proposal_id": str(rec.get("proposal_id") or ""),
                    "target": target,
                    "source": source,
                    "title": str(rec.get("title") or "")[:60],
                    "content": str(rec.get("content") or "")[:180],
                    "priority_score": int(round(p)),
                    "rank_score": round(deps.rank_score(rec), 2),
                    "age_days": deps.age_days(rec, now),
                    "expires_at": str(rec.get("expires_at") or ""),
                }
            )
        elif status == "rejected":
            rejected_total += 1
            reason = str(rec.get("reject_reason") or "unknown").strip() or "unknown"
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    active_items.sort(key=lambda x: (float(x.get("rank_score") or 0), int(x.get("priority_score") or 0)), reverse=True)

    events = deps.load_events(teacher_id, 5000)
    search_calls = 0
    search_hit_calls = 0
    context_injected = 0
    search_mode_breakdown: Dict[str, int] = {}
    query_stats: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        ts = deps.parse_dt(ev.get("ts"))
        if ts is None:
            continue
        if ts.tzinfo:
            now_tz = datetime.now(ts.tzinfo)
            if ts < now_tz - timedelta(days=window_days):
                continue
        else:
            if ts < window_start:
                continue
        et = str(ev.get("event") or "").strip()
        if et == "context_injected":
            context_injected += 1
            continue
        if et != "search":
            continue
        search_calls += 1
        mode = str(ev.get("mode") or "unknown").strip().lower() or "unknown"
        search_mode_breakdown[mode] = search_mode_breakdown.get(mode, 0) + 1
        try:
            hits = int(ev.get("hits") or 0)
        except Exception:
            hits = 0
        if hits > 0:
            search_hit_calls += 1
        query = str(ev.get("query") or "").strip()
        if not query:
            continue
        query_key = query[:120]
        st = query_stats.get(query_key) or {"query": query_key, "calls": 0, "hit_calls": 0}
        st["calls"] = int(st.get("calls") or 0) + 1
        if hits > 0:
            st["hit_calls"] = int(st.get("hit_calls") or 0) + 1
        query_stats[query_key] = st

    top_queries: List[Dict[str, Any]] = []
    for query_entry in query_stats.values():
        calls = max(1, int(query_entry.get("calls") or 1))
        hit_calls = int(query_entry.get("hit_calls") or 0)
        top_queries.append(
            {
                "query": str(query_entry.get("query") or ""),
                "calls": calls,
                "hit_calls": hit_calls,
                "hit_rate": round(hit_calls / calls, 4),
            }
        )
    top_queries.sort(key=lambda x: (int(x.get("hit_calls") or 0), int(x.get("calls") or 0)), reverse=True)

    return {
        "ok": True,
        "teacher_id": teacher_id,
        "window_days": window_days,
        "summary": {
            "applied_total": applied_total,
            "rejected_total": rejected_total,
            "active_total": active_total,
            "expired_total": expired_total,
            "superseded_total": superseded_total,
            "avg_priority_active": round(active_priority_sum / active_priority_count, 2) if active_priority_count else 0.0,
            "by_source": by_source,
            "by_target": by_target,
            "rejected_reasons": rejected_reasons,
        },
        "retrieval": {
            "search_calls": search_calls,
            "search_hit_calls": search_hit_calls,
            "search_hit_rate": round(search_hit_calls / search_calls, 4) if search_calls else 0.0,
            "search_mode_breakdown": search_mode_breakdown,
            "context_injected": context_injected,
        },
        "top_queries": top_queries[:10],
        "top_active": active_items[:8],
    }
