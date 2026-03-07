#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.survey_bundle_models import SurveyEvidenceBundle
from services.api.survey_normalize_structured_service import normalize_structured_survey_payload
from services.api.survey_report_parse_service import SurveyReportParseDeps, parse_survey_report_payload
from services.api.upload_text_service import extract_text_from_html


REQUIRED_FIELDS = ('title', 'teacher_id', 'class_name', 'sample_size', 'question_summaries')


def _parse_deps() -> SurveyReportParseDeps:
    return SurveyReportParseDeps(
        extract_text_from_file=lambda _path, **_kwargs: '',
        extract_text_from_html=extract_text_from_html,
    )


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'fixture must be a JSON object: {path}')
    return payload


def _present_required_fields(bundle: SurveyEvidenceBundle) -> List[str]:
    present: List[str] = []
    if bundle.survey_meta.title:
        present.append('title')
    if bundle.audience_scope.teacher_id:
        present.append('teacher_id')
    if bundle.audience_scope.class_name:
        present.append('class_name')
    if bundle.audience_scope.sample_size is not None:
        present.append('sample_size')
    if bundle.question_summaries:
        present.append('question_summaries')
    return present


def _artifact_completeness(bundle: SurveyEvidenceBundle) -> float:
    attachments = list(bundle.attachments or [])
    if not attachments:
        return 1.0
    parsed = 0
    for item in attachments:
        if str(item.get('parse_status') or '') == 'parsed' and int(item.get('text_length') or 0) > 0:
            parsed += 1
    return round(parsed / len(attachments), 4)


def _confidence_bucket(confidence: float) -> str:
    if confidence < 0.4:
        return 'low'
    if confidence < 0.7:
        return 'medium'
    return 'high'


def evaluate_fixture(path: Path) -> Dict[str, Any]:
    fixture = _load_json(path)
    mode = str(fixture.get('mode') or '').strip()
    provider = str(fixture.get('provider') or 'provider').strip() or 'provider'
    payload = dict(fixture.get('payload') or {})

    if mode == 'structured':
        bundle = normalize_structured_survey_payload(provider=provider, payload=payload)
    elif mode == 'unstructured':
        bundle = parse_survey_report_payload(provider=provider, payload=payload, deps=_parse_deps())
    else:
        raise ValueError(f'unsupported fixture mode {mode!r} for {path}')

    present_fields = _present_required_fields(bundle)
    missing_required = [field for field in REQUIRED_FIELDS if field not in present_fields]
    required_field_coverage = round(len(present_fields) / len(REQUIRED_FIELDS), 4)
    missing_field_rate = round(len(missing_required) / len(REQUIRED_FIELDS), 4)
    artifact_completeness = _artifact_completeness(bundle)
    confidence = float(bundle.parse_confidence)
    bucket = _confidence_bucket(confidence)

    expected = dict(fixture.get('expected') or {})
    expectation_failures: List[str] = []
    min_confidence = expected.get('min_confidence')
    if min_confidence is not None and confidence < float(min_confidence):
        expectation_failures.append(f'min_confidence<{min_confidence}')
    for field in expected.get('required_fields_present') or []:
        if str(field) not in present_fields:
            expectation_failures.append(f'missing_required:{field}')

    return {
        'case_id': str(fixture.get('case_id') or path.stem),
        'path': str(path),
        'mode': mode,
        'provider': provider,
        'parse_confidence': confidence,
        'confidence_bucket': bucket,
        'required_fields_present': present_fields,
        'missing_fields': list(bundle.missing_fields or []),
        'required_field_coverage': required_field_coverage,
        'missing_field_rate': missing_field_rate,
        'artifact_completeness': artifact_completeness,
        'attachment_count': len(bundle.attachments or []),
        'question_count': len(bundle.question_summaries or []),
        'expectation_failures': expectation_failures,
    }


def evaluate_fixture_tree(fixtures_dir: Path) -> Dict[str, Any]:
    paths = sorted(path for path in fixtures_dir.rglob('*.json') if path.is_file())
    if not paths:
        raise SystemExit(f'No survey fixtures found under {fixtures_dir}')

    cases = [evaluate_fixture(path) for path in paths]
    buckets = {'low': 0, 'medium': 0, 'high': 0}
    for item in cases:
        buckets[str(item['confidence_bucket'])] += 1

    fixture_count = len(cases)
    summary = {
        'fixture_count': fixture_count,
        'average_required_field_coverage': round(sum(float(item['required_field_coverage']) for item in cases) / fixture_count, 4),
        'average_missing_field_rate': round(sum(float(item['missing_field_rate']) for item in cases) / fixture_count, 4),
        'average_artifact_completeness': round(sum(float(item['artifact_completeness']) for item in cases) / fixture_count, 4),
        'confidence_buckets': buckets,
        'expectation_failures': sum(len(item['expectation_failures']) for item in cases),
        'cases': cases,
    }
    return summary


def _format_human(report: Dict[str, Any], *, summary_only: bool) -> str:
    lines = [
        'Survey bundle eval summary',
        f"fixtures: {report['fixture_count']}",
        f"avg coverage: {report['average_required_field_coverage']}",
        f"avg missing rate: {report['average_missing_field_rate']}",
        f"avg artifact completeness: {report['average_artifact_completeness']}",
        'confidence buckets:',
        f"  low={report['confidence_buckets']['low']} medium={report['confidence_buckets']['medium']} high={report['confidence_buckets']['high']}",
        f"expectation failures: {report['expectation_failures']}",
    ]
    if not summary_only:
        lines.append('cases:')
        for item in report['cases']:
            lines.append(
                f"  - {item['case_id']}: confidence={item['parse_confidence']} coverage={item['required_field_coverage']} missing={','.join(item['missing_fields']) or 'none'}"
            )
    return '\n'.join(lines) + '\n'


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Evaluate survey bundle fixtures and summarize coverage/confidence.')
    parser.add_argument('--fixtures', default='tests/fixtures/surveys', help='fixture directory to scan')
    parser.add_argument('--json', action='store_true', help='print JSON summary')
    parser.add_argument('--summary-only', action='store_true', help='omit per-case output')
    args = parser.parse_args(argv)

    report = evaluate_fixture_tree(Path(args.fixtures))
    payload: Dict[str, Any] = dict(report)
    if args.summary_only:
        payload.pop('cases', None)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_human(payload if args.summary_only else report, summary_only=args.summary_only), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
