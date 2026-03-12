from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict

from .analysis_metrics_service import AnalysisMetricsService
from .review_feedback_service import build_review_feedback_dataset
from .review_feedback_store import read_review_feedback_rows


class AnalysisOpsService:
    def __init__(
        self,
        *,
        metrics_service: Any | None = None,
        review_feedback_path: str | Path | None = None,
        data_dir: str | Path | None = None,
        now_iso: Callable[[], str] | None = None,
    ) -> None:
        self._metrics_service = metrics_service
        self._review_feedback_path = Path(review_feedback_path) if review_feedback_path else None
        self._data_dir = Path(data_dir) if data_dir else None
        self._now_iso = now_iso or (lambda: datetime.now().isoformat(timespec='seconds'))

    def snapshot(self, *, window_sec: int = 86400) -> Dict[str, Any]:
        metrics = self._runtime_metrics(window_sec=window_sec)
        feedback_items = self._feedback_items()
        review_feedback = dict(build_review_feedback_dataset(items=feedback_items) or {})
        review_feedback['recommendations'] = list(review_feedback.get('tuning_recommendations') or [])
        feedback_summary = dict(review_feedback.get('summary') or {})
        replay_compare = _build_replay_compare_summary(self._report_rows())
        return {
            'generated_at': self._now_iso(),
            'window_sec': int(window_sec or 86400),
            'workflow_routing': dict(metrics.get('workflow_routing') or {}),
            'runtime_metrics': metrics,
            'review_feedback': review_feedback,
            'replay_compare': replay_compare,
            'ops_summary': {
                'top_failure_reason': _top_bucket(metrics.get('by_reason') or {}),
                'top_review_reason': _top_bucket(feedback_summary.get('by_reason_code') or {}),
                'needs_attention': _needs_attention(metrics=metrics, feedback_summary=feedback_summary, review_feedback=review_feedback),
            },
        }

    def _runtime_metrics(self, *, window_sec: int) -> Dict[str, Any]:
        metrics_snapshot = getattr(self._metrics_service, 'snapshot', None)
        if callable(metrics_snapshot):
            return dict(metrics_snapshot(window_sec=window_sec) or {})
        return AnalysisMetricsService().snapshot(window_sec=window_sec)

    def _feedback_items(self) -> list[Dict[str, Any]]:
        if self._review_feedback_path is None:
            return []
        return read_review_feedback_rows(self._review_feedback_path)

    def _report_rows(self) -> list[Dict[str, Any]]:
        if self._data_dir is None:
            return []
        rows: list[Dict[str, Any]] = []
        for domain, directory, pattern in _report_locations(self._data_dir):
            if not directory.exists():
                continue
            for path in sorted(directory.glob(pattern)):
                try:
                    payload = json.loads(path.read_text(encoding='utf-8'))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                row = dict(payload)
                row.setdefault('report_id', path.stem)
                row.setdefault('domain', domain)
                row['report_path'] = str(path)
                rows.append(row)
        rows.sort(key=_report_sort_key, reverse=True)
        return rows



def _report_locations(data_dir: Path) -> list[tuple[str, Path, str]]:
    return [
        ('survey', data_dir / 'survey_reports', '*.json'),
        ('class_report', data_dir / 'class_reports' / 'reports', '*.json'),
        ('video_homework', data_dir / 'video_homework_reports' / 'reports', '*.json'),
    ]



def _report_sort_key(report: Dict[str, Any]) -> str:
    return str(report.get('updated_at') or report.get('created_at') or '')



def _build_replay_compare_summary(reports: list[Dict[str, Any]]) -> Dict[str, Any]:
    pairs: list[Dict[str, Any]] = []
    for report in reports:
        artifact_meta = dict(report.get('artifact_meta') or {})
        lineage = artifact_meta.get('rerun_base_lineage') or report.get('rerun_base_lineage') or {}
        if not isinstance(lineage, dict) or not lineage:
            continue
        report_id = str(report.get('report_id') or '').strip()
        base_report_id = str(lineage.get('report_id') or lineage.get('target_id') or '').strip() or None
        report_path = str(report.get('report_path') or '').strip() or None
        base_report_path = _resolve_base_report_path(report_path=report_path, base_report_id=base_report_id)
        pairs.append(
            {
                'report_id': report_id,
                'domain': str(report.get('domain') or report.get('analysis_type') or '').strip() or None,
                'base_report_id': base_report_id,
                'has_rerun_base_lineage': True,
                'report_path': report_path,
                'base_report_path': base_report_path,
                'updated_at': str(report.get('updated_at') or report.get('created_at') or '').strip() or None,
            }
        )
    return {
        'candidate_pairs': pairs[:20],
        'total_candidates': len(pairs),
    }



def _resolve_base_report_path(*, report_path: str | None, base_report_id: str | None) -> str | None:
    if not report_path or not base_report_id:
        return None
    candidate = Path(report_path).with_name(f'{base_report_id}.json')
    return str(candidate) if candidate.exists() else None



def _top_bucket(values: Dict[str, Any]) -> str | None:
    rows = [(str(name or '').strip(), int(count or 0)) for name, count in dict(values or {}).items()]
    rows = [(name, count) for name, count in rows if name and count > 0]
    if not rows:
        return None
    rows.sort(key=lambda item: (-item[1], item[0]))
    return rows[0][0]



def _needs_attention(*, metrics: Dict[str, Any], feedback_summary: Dict[str, Any], review_feedback: Dict[str, Any]) -> bool:
    counters = dict(metrics.get('counters') or {})
    feedback_total = int(feedback_summary.get('total_items') or 0)
    recommendation_count = len(list(review_feedback.get('recommendations') or []))
    return any(
        [
            int(counters.get('fail_count') or 0) > 0,
            int(counters.get('review_downgrade_count') or 0) > 0,
            int(counters.get('reviewer_reject_count') or 0) > 0,
            feedback_total > 0,
            recommendation_count > 0,
        ]
    )
