from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.compare_analysis_runs import build_compare_command
from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.analysis_metrics_store import AnalysisMetricsStore
from services.api.analysis_ops_service import AnalysisOpsService



def export_analysis_ops_snapshot(*, data_dir: Path, window_sec: int) -> dict:
    metrics_store = AnalysisMetricsStore(data_dir / 'analysis' / 'metrics_snapshot.json')
    service = AnalysisOpsService(
        metrics_service=AnalysisMetricsService(store=metrics_store),
        review_feedback_path=data_dir / 'analysis' / 'review_feedback.jsonl',
        data_dir=data_dir,
    )
    payload = service.snapshot(window_sec=window_sec)
    for pair in list((payload.get('replay_compare') or {}).get('candidate_pairs') or []):
        report_path = Path(pair['report_path']) if pair.get('report_path') else None
        base_report_path = Path(pair['base_report_path']) if pair.get('base_report_path') else None
        if report_path is None or base_report_path is None:
            continue
        pair['compare_command'] = build_compare_command(
            baseline_report_path=base_report_path,
            candidate_report_path=report_path,
        )
    return payload



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export a lightweight analysis ops snapshot for offline inspection.')
    parser.add_argument('--data-dir', default='./data', help='root data directory')
    parser.add_argument('--window-sec', type=int, default=86400, help='metrics aggregation window in seconds')
    args = parser.parse_args(argv)

    payload = export_analysis_ops_snapshot(data_dir=Path(args.data_dir), window_sec=int(args.window_sec or 86400))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
