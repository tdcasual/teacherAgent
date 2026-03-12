from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.replay_analysis_run import replay_analysis_run


def _recommendations(artifact: Dict[str, Any]) -> List[str]:
    values = artifact.get('teaching_recommendations') or artifact.get('recommendations') or []
    return [str(item).strip() for item in values if str(item).strip()]



def _confidence(artifact: Dict[str, Any], artifact_meta: Dict[str, Any]) -> float | None:
    value = (artifact.get('confidence_and_gaps') or {}).get('confidence')
    if value is None:
        value = artifact_meta.get('parse_confidence')
    try:
        return float(value) if value is not None else None
    except Exception:
        return None



def build_compare_command(*, baseline_report_path: Path, candidate_report_path: Path) -> list[str]:
    return [
        'python',
        'scripts/compare_analysis_runs.py',
        str(baseline_report_path),
        str(candidate_report_path),
    ]


def compare_analysis_runs(*, baseline_report_path: Path, candidate_report_path: Path) -> Dict[str, Any]:
    baseline = replay_analysis_run(report_path=baseline_report_path)
    candidate = replay_analysis_run(report_path=candidate_report_path)

    baseline_request = dict(baseline.get('replay_request') or {})
    candidate_request = dict(candidate.get('replay_request') or {})
    baseline_artifact = dict(baseline_request.get('analysis_artifact') or {})
    candidate_artifact = dict(candidate_request.get('analysis_artifact') or {})
    baseline_meta = dict(baseline_request.get('artifact_meta') or {})
    candidate_meta = dict(candidate_request.get('artifact_meta') or {})

    baseline_summary = str(baseline_artifact.get('executive_summary') or '').strip()
    candidate_summary = str(candidate_artifact.get('executive_summary') or '').strip()
    baseline_confidence = _confidence(baseline_artifact, baseline_meta)
    candidate_confidence = _confidence(candidate_artifact, candidate_meta)
    baseline_recommendations = _recommendations(baseline_artifact)
    candidate_recommendations = _recommendations(candidate_artifact)
    baseline_reason_code = str(baseline_meta.get('review_reason') or baseline_meta.get('reason_code') or '').strip() or None
    candidate_reason_code = str(candidate_meta.get('review_reason') or candidate_meta.get('reason_code') or '').strip() or None

    confidence_delta = None
    if baseline_confidence is not None and candidate_confidence is not None:
        confidence_delta = round(candidate_confidence - baseline_confidence, 4)

    return {
        'baseline_report_id': baseline_request.get('report_id'),
        'candidate_report_id': candidate_request.get('report_id'),
        'changed': any(
            [
                baseline_summary != candidate_summary,
                baseline_recommendations != candidate_recommendations,
                baseline_reason_code != candidate_reason_code,
                confidence_delta not in (None, 0.0),
            ]
        ),
        'summary_changed': baseline_summary != candidate_summary,
        'recommendations_changed': baseline_recommendations != candidate_recommendations,
        'reason_code_changed': baseline_reason_code != candidate_reason_code,
        'diff': {
            'summary': {'before': baseline_summary, 'after': candidate_summary},
            'confidence': {'before': baseline_confidence, 'after': candidate_confidence, 'delta': confidence_delta},
            'recommendations': {
                'before': baseline_recommendations,
                'after': candidate_recommendations,
                'before_count': len(baseline_recommendations),
                'after_count': len(candidate_recommendations),
                'delta': len(candidate_recommendations) - len(baseline_recommendations),
            },
            'reason_code': {'before': baseline_reason_code, 'after': candidate_reason_code},
        },
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compare two stored analysis reports with a compact diff summary.')
    parser.add_argument('baseline_report_path', help='path to baseline report JSON')
    parser.add_argument('candidate_report_path', help='path to candidate report JSON')
    args = parser.parse_args(argv)

    payload = compare_analysis_runs(
        baseline_report_path=Path(args.baseline_report_path),
        candidate_report_path=Path(args.candidate_report_path),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
