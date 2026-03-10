#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compare_analysis_runs import compare_analysis_runs  # noqa: E402



def _report_meta(path: Path) -> Dict[str, str]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    report = payload.get('report') if isinstance(payload.get('report'), dict) else payload
    raw = dict(report or {}) if isinstance(report, dict) else {}
    return {
        'report_id': str(raw.get('report_id') or path.stem).strip() or path.stem,
        'domain': str(raw.get('analysis_type') or '').strip() or 'unknown',
    }



def build_analysis_shadow_compare_report(*, baseline_dir: Path, candidate_dir: Path) -> Dict[str, Any]:
    baseline_files = sorted(path.name for path in Path(baseline_dir).glob('*.json'))
    candidate_files = sorted(path.name for path in Path(candidate_dir).glob('*.json'))
    if baseline_files != candidate_files:
        raise ValueError('matching report files required between baseline_dir and candidate_dir')

    pairs: List[Dict[str, Any]] = []
    by_domain: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))

    for file_name in baseline_files:
        baseline_path = Path(baseline_dir) / file_name
        candidate_path = Path(candidate_dir) / file_name
        meta = _report_meta(baseline_path)
        diff = compare_analysis_runs(
            baseline_report_path=baseline_path,
            candidate_report_path=candidate_path,
        )
        pair = {
            'file_name': file_name,
            'report_id': meta['report_id'],
            'domain': meta['domain'],
            'changed': bool(diff.get('changed')),
            'summary_changed': bool(diff.get('summary_changed')),
            'recommendations_changed': bool(diff.get('recommendations_changed')),
            'reason_code_changed': bool(diff.get('reason_code_changed')),
            'diff': diff.get('diff') or {},
        }
        pairs.append(pair)
        by_domain[meta['domain']]['total_pairs'] += 1
        if pair['changed']:
            by_domain[meta['domain']]['changed_pairs'] += 1

    total_pairs = len(pairs)
    changed_pairs = sum(1 for item in pairs if item['changed'])
    top_changed_reports = [
        {
            'report_id': item['report_id'],
            'domain': item['domain'],
            'file_name': item['file_name'],
            'change_flags': [
                flag
                for flag, changed in (
                    ('summary', item['summary_changed']),
                    ('recommendations', item['recommendations_changed']),
                    ('reason_code', item['reason_code_changed']),
                )
                if changed
            ],
        }
        for item in pairs
        if item['changed']
    ]

    return {
        'total_pairs': total_pairs,
        'changed_pairs': changed_pairs,
        'changed_ratio': round(changed_pairs / total_pairs, 4) if total_pairs else 0.0,
        'by_domain': {
            key: {
                'total_pairs': int(value.get('total_pairs', 0)),
                'changed_pairs': int(value.get('changed_pairs', 0)),
            }
            for key, value in by_domain.items()
        },
        'pairs': pairs,
        'top_changed_reports': top_changed_reports,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a batch shadow compare report from baseline and candidate analysis report directories.')
    parser.add_argument('--baseline-dir', required=True, help='directory containing baseline report JSON files')
    parser.add_argument('--candidate-dir', required=True, help='directory containing candidate report JSON files')
    parser.add_argument('--output', default='', help='optional output file path, defaults to stdout')
    args = parser.parse_args(argv)

    payload = build_analysis_shadow_compare_report(
        baseline_dir=Path(args.baseline_dir),
        candidate_dir=Path(args.candidate_dir),
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
