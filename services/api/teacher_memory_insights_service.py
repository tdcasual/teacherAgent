from __future__ import annotations

from dataclasses import dataclass, field
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


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                return int(stripped)
            except ValueError:
                return 0
    return 0


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


@dataclass
class _ProposalMetrics:
    applied_total: int = 0
    rejected_total: int = 0
    active_total: int = 0
    expired_total: int = 0
    superseded_total: int = 0
    active_priority_sum: float = 0.0
    active_priority_count: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_target: Dict[str, int] = field(default_factory=dict)
    rejected_reasons: Dict[str, int] = field(default_factory=dict)
    active_items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class _EventMetrics:
    search_calls: int = 0
    search_hit_calls: int = 0
    context_injected: int = 0
    search_mode_breakdown: Dict[str, int] = field(default_factory=dict)
    query_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _proposal_priority_score(
    rec: Dict[str, Any],
    *,
    target: str,
    source: str,
    deps: TeacherMemoryInsightsDeps,
) -> float:
    priority_score = _coerce_float(rec.get("priority_score"))
    if priority_score is not None:
        return priority_score
    return float(
        deps.priority_score(
            target=target,
            title=str(rec.get("title") or ""),
            content=str(rec.get("content") or ""),
            source=source,
            meta=rec.get("meta") if isinstance(rec.get("meta"), dict) else None,
        )
    )


def _build_active_item(
    rec: Dict[str, Any],
    *,
    target: str,
    source: str,
    priority_score: float,
    now: datetime,
    deps: TeacherMemoryInsightsDeps,
) -> Dict[str, Any]:
    return {
        "proposal_id": str(rec.get("proposal_id") or ""),
        "target": target,
        "source": source,
        "title": str(rec.get("title") or "")[:60],
        "content": str(rec.get("content") or "")[:180],
        "priority_score": int(round(priority_score)),
        "rank_score": round(deps.rank_score(rec), 2),
        "age_days": deps.age_days(rec, now),
        "expires_at": str(rec.get("expires_at") or ""),
    }


def _summarize_proposals(
    proposals: List[Dict[str, Any]],
    *,
    now: datetime,
    deps: TeacherMemoryInsightsDeps,
) -> _ProposalMetrics:
    metrics = _ProposalMetrics()
    for rec in proposals:
        status = str(rec.get("status") or "").strip().lower()
        source = str(rec.get("source") or "manual").strip().lower() or "manual"
        target = str(rec.get("target") or "MEMORY").strip().upper() or "MEMORY"
        metrics.by_source[source] = metrics.by_source.get(source, 0) + 1
        metrics.by_target[target] = metrics.by_target.get(target, 0) + 1
        if status == "applied":
            metrics.applied_total += 1
            if rec.get("superseded_by"):
                metrics.superseded_total += 1
                continue
            if deps.is_expired_record(rec, now):
                metrics.expired_total += 1
                continue
            priority_score = _proposal_priority_score(rec, target=target, source=source, deps=deps)
            metrics.active_total += 1
            metrics.active_priority_sum += priority_score
            metrics.active_priority_count += 1
            metrics.active_items.append(
                _build_active_item(
                    rec,
                    target=target,
                    source=source,
                    priority_score=priority_score,
                    now=now,
                    deps=deps,
                )
            )
            continue
        if status == "rejected":
            metrics.rejected_total += 1
            reason = str(rec.get("reject_reason") or "unknown").strip() or "unknown"
            metrics.rejected_reasons[reason] = metrics.rejected_reasons.get(reason, 0) + 1
    metrics.active_items.sort(
        key=lambda item: (float(item.get("rank_score") or 0), int(item.get("priority_score") or 0)),
        reverse=True,
    )
    return metrics


def _event_in_window(ts: Any, *, window_days: int, window_start: datetime) -> bool:
    if ts is None:
        return False
    if getattr(ts, "tzinfo", None):
        now_tz = datetime.now(ts.tzinfo)
        return bool(ts >= now_tz - timedelta(days=window_days))
    return bool(ts >= window_start)


def _record_query_stat(
    query_stats: Dict[str, Dict[str, Any]],
    *,
    query: str,
    hits: int,
) -> None:
    query_key = query[:120]
    stat = query_stats.get(query_key) or {"query": query_key, "calls": 0, "hit_calls": 0}
    stat["calls"] = int(stat.get("calls") or 0) + 1
    if hits > 0:
        stat["hit_calls"] = int(stat.get("hit_calls") or 0) + 1
    query_stats[query_key] = stat


def _summarize_events(
    events: List[Dict[str, Any]],
    *,
    window_days: int,
    window_start: datetime,
    deps: TeacherMemoryInsightsDeps,
) -> _EventMetrics:
    metrics = _EventMetrics()
    for event in events:
        ts = deps.parse_dt(event.get("ts"))
        if not _event_in_window(ts, window_days=window_days, window_start=window_start):
            continue
        event_type = str(event.get("event") or "").strip()
        if event_type == "context_injected":
            metrics.context_injected += 1
            continue
        if event_type != "search":
            continue
        metrics.search_calls += 1
        mode = str(event.get("mode") or "unknown").strip().lower() or "unknown"
        metrics.search_mode_breakdown[mode] = metrics.search_mode_breakdown.get(mode, 0) + 1
        hits = _coerce_int(event.get("hits"))
        if hits > 0:
            metrics.search_hit_calls += 1
        query = str(event.get("query") or "").strip()
        if query:
            _record_query_stat(metrics.query_stats, query=query, hits=hits)
    return metrics


def _build_top_queries(query_stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    top_queries.sort(
        key=lambda item: (int(item.get("hit_calls") or 0), int(item.get("calls") or 0)),
        reverse=True,
    )
    return top_queries


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

    proposal_metrics = _summarize_proposals(deps.recent_proposals(teacher_id, 1500), now=now, deps=deps)
    event_metrics = _summarize_events(
        deps.load_events(teacher_id, 5000),
        window_days=window_days,
        window_start=window_start,
        deps=deps,
    )
    top_queries = _build_top_queries(event_metrics.query_stats)

    return {
        "ok": True,
        "teacher_id": teacher_id,
        "window_days": window_days,
        "summary": {
            "applied_total": proposal_metrics.applied_total,
            "rejected_total": proposal_metrics.rejected_total,
            "active_total": proposal_metrics.active_total,
            "expired_total": proposal_metrics.expired_total,
            "superseded_total": proposal_metrics.superseded_total,
            "avg_priority_active": round(
                proposal_metrics.active_priority_sum / proposal_metrics.active_priority_count,
                2,
            )
            if proposal_metrics.active_priority_count
            else 0.0,
            "by_source": proposal_metrics.by_source,
            "by_target": proposal_metrics.by_target,
            "rejected_reasons": proposal_metrics.rejected_reasons,
        },
        "retrieval": {
            "search_calls": event_metrics.search_calls,
            "search_hit_calls": event_metrics.search_hit_calls,
            "search_hit_rate": round(event_metrics.search_hit_calls / event_metrics.search_calls, 4)
            if event_metrics.search_calls
            else 0.0,
            "search_mode_breakdown": event_metrics.search_mode_breakdown,
            "context_injected": event_metrics.context_injected,
        },
        "top_queries": top_queries[:10],
        "top_active": proposal_metrics.active_items[:8],
    }
