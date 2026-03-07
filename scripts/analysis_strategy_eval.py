#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.class_signal_bundle_models import ClassSignalBundle
from services.api.multimodal_submission_models import MultimodalSubmissionBundle
from services.api.report_adapters import adapt_pdf_report_summary, adapt_self_hosted_form_json, adapt_web_export_html
from services.api.strategies.selector import build_default_strategy_selector
from services.api.survey_bundle_models import SurveyEvidenceBundle
from services.api.survey_normalize_structured_service import normalize_structured_survey_payload
from services.api.survey_report_parse_service import SurveyReportParseDeps, parse_survey_report_payload
from services.api.upload_text_service import extract_text_from_html

SURVEY_REQUIRED_FIELDS = ('title', 'teacher_id', 'class_name', 'sample_size', 'question_summaries')
CLASS_REPORT_REQUIRED_FIELDS = ('title', 'teacher_id', 'class_name', 'question_like_signals', 'theme_like_signals')
VIDEO_HOMEWORK_REQUIRED_FIELDS = ('submission_id', 'teacher_id', 'student_id', 'media_files', 'evidence_channels')



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



def _iter_fixture_paths(fixtures_dir: Path) -> Iterable[Path]:
    allowed_roots = {'surveys', 'analysis_reports', 'multimodal'}
    for path in sorted(fixtures_dir.rglob('*.json')):
        if not path.is_file():
            continue
        rel = path.relative_to(fixtures_dir)
        if rel.parts and rel.parts[0] in allowed_roots:
            yield path



def _infer_domain(path: Path, fixture: Dict[str, Any]) -> str:
    domain = str(fixture.get('domain') or '').strip()
    if domain:
        return domain
    rel_parts = path.parts
    if 'surveys' in rel_parts:
        return 'survey'
    if 'analysis_reports' in rel_parts:
        return 'class_report'
    if 'multimodal' in rel_parts:
        return 'video_homework'
    raise ValueError(f'cannot infer domain for fixture: {path}')



def _build_artifact(path: Path, fixture: Dict[str, Any]):
    domain = _infer_domain(path, fixture)
    payload = dict(fixture.get('payload') or {})
    mode = str(fixture.get('mode') or '').strip()

    if domain == 'survey':
        provider = str(fixture.get('provider') or 'provider').strip() or 'provider'
        if mode == 'structured':
            bundle = normalize_structured_survey_payload(provider=provider, payload=payload)
        elif mode == 'unstructured':
            bundle = parse_survey_report_payload(provider=provider, payload=payload, deps=_parse_deps())
        else:
            raise ValueError(f'unsupported survey fixture mode {mode!r} for {path}')
        return domain, bundle, bundle.to_artifact_envelope(), 'survey.analysis', 'class'

    if domain == 'class_report':
        if mode == 'self_hosted_form_json':
            artifact = adapt_self_hosted_form_json(payload, {})
        elif mode == 'web_export_html':
            artifact = adapt_web_export_html(payload, {})
        elif mode == 'pdf_report_summary':
            artifact = adapt_pdf_report_summary(payload, {})
        elif mode == 'artifact':
            artifact = ClassSignalBundle.model_validate(payload).to_artifact_envelope()
        else:
            raise ValueError(f'unsupported class_report fixture mode {mode!r} for {path}')
        bundle = ClassSignalBundle.model_validate(artifact.payload)
        return domain, bundle, artifact, 'class_report.analysis', 'class'

    if domain == 'video_homework':
        if mode != 'artifact':
            raise ValueError(f'unsupported video_homework fixture mode {mode!r} for {path}')
        bundle = MultimodalSubmissionBundle.model_validate(payload)
        return domain, bundle, bundle.to_artifact_envelope(), 'video_homework.analysis', 'student'

    raise ValueError(f'unsupported domain {domain!r} for {path}')



def _present_required_fields(domain: str, bundle: Any) -> List[str]:
    if domain == 'survey':
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

    if domain == 'class_report':
        present = []
        if bundle.source_meta.title:
            present.append('title')
        if bundle.class_scope.teacher_id:
            present.append('teacher_id')
        if bundle.class_scope.class_name:
            present.append('class_name')
        if bundle.question_like_signals:
            present.append('question_like_signals')
        if bundle.theme_like_signals:
            present.append('theme_like_signals')
        return present

    if domain == 'video_homework':
        present = []
        if bundle.source_meta.submission_id:
            present.append('submission_id')
        if bundle.scope.teacher_id:
            present.append('teacher_id')
        if bundle.scope.student_id:
            present.append('student_id')
        if bundle.media_files:
            present.append('media_files')
        if bundle.transcript_segments or bundle.subtitle_segments or bundle.keyframe_evidence:
            present.append('evidence_channels')
        return present

    raise ValueError(f'unsupported domain {domain!r}')



def _required_fields(domain: str) -> Tuple[str, ...]:
    if domain == 'survey':
        return SURVEY_REQUIRED_FIELDS
    if domain == 'class_report':
        return CLASS_REPORT_REQUIRED_FIELDS
    if domain == 'video_homework':
        return VIDEO_HOMEWORK_REQUIRED_FIELDS
    raise ValueError(f'unsupported domain {domain!r}')



def _artifact_completeness(domain: str, bundle: Any) -> float:
    if domain == 'survey':
        attachments = list(bundle.attachments or [])
        if not attachments:
            return 1.0
        parsed = 0
        for item in attachments:
            if str(item.get('parse_status') or '') == 'parsed' and int(item.get('text_length') or 0) > 0:
                parsed += 1
        return round(parsed / len(attachments), 4)

    if domain == 'class_report':
        channels = [
            bool(bundle.question_like_signals),
            bool(bundle.theme_like_signals),
            bool(bundle.risk_like_signals),
            bool(bundle.narrative_blocks),
        ]
        return round(sum(1 for item in channels if item) / len(channels), 4)

    if domain == 'video_homework':
        channels = [
            bool(bundle.media_files),
            bool(bundle.transcript_segments or bundle.subtitle_segments),
            bool(bundle.keyframe_evidence),
        ]
        return round(sum(1 for item in channels if item) / len(channels), 4)

    raise ValueError(f'unsupported domain {domain!r}')



def _confidence_bucket(confidence: float) -> str:
    if confidence < 0.4:
        return 'low'
    if confidence < 0.7:
        return 'medium'
    return 'high'



def evaluate_fixture(path: Path) -> Dict[str, Any]:
    fixture = _load_json(path)
    domain, bundle, artifact, task_kind, target_scope = _build_artifact(path, fixture)
    required_fields = _required_fields(domain)
    present_fields = _present_required_fields(domain, bundle)
    missing_required = [field for field in required_fields if field not in present_fields]
    required_field_coverage = round(len(present_fields) / len(required_fields), 4)
    missing_field_rate = round(len(missing_required) / len(required_fields), 4)
    artifact_completeness = _artifact_completeness(domain, bundle)
    confidence = float(artifact.confidence or 0.0)
    bucket = _confidence_bucket(confidence)
    selector = build_default_strategy_selector()
    decision = selector.select(role='teacher', artifact=artifact, task_kind=task_kind, target_scope=target_scope)

    expected = dict(fixture.get('expected') or {})
    expectation_failures: List[str] = []
    min_confidence = expected.get('min_confidence')
    if min_confidence is not None and confidence < float(min_confidence):
        expectation_failures.append(f'confidence<{min_confidence}')

    expected_fields = [str(item).strip() for item in (expected.get('required_fields_present') or []) if str(item).strip()]
    for field in expected_fields:
        if field not in present_fields:
            expectation_failures.append(f'missing_required:{field}')

    expected_strategy_id = str(expected.get('strategy_id') or '').strip()
    if expected_strategy_id and decision.strategy_id != expected_strategy_id:
        expectation_failures.append(f'strategy_mismatch:{decision.strategy_id}')

    return {
        'case_id': str(fixture.get('case_id') or path.stem),
        'path': str(path),
        'domain': domain,
        'mode': str(fixture.get('mode') or '').strip(),
        'artifact_type': artifact.artifact_type,
        'parse_confidence': confidence,
        'confidence_bucket': bucket,
        'required_fields_present': present_fields,
        'missing_fields': list(artifact.missing_fields or []),
        'required_field_coverage': required_field_coverage,
        'missing_field_rate': missing_field_rate,
        'artifact_completeness': artifact_completeness,
        'selected_strategy_id': decision.strategy_id,
        'selected_delivery_mode': decision.delivery_mode,
        'review_required': bool(decision.review_required),
        'expectation_failures': expectation_failures,
    }



def _aggregate_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    fixture_count = len(cases)
    buckets = {'low': 0, 'medium': 0, 'high': 0}
    for item in cases:
        buckets[str(item['confidence_bucket'])] += 1

    domain_summaries: Dict[str, Any] = {}
    for domain in sorted({str(item['domain']) for item in cases}):
        items = [item for item in cases if item['domain'] == domain]
        item_count = len(items)
        domain_buckets = {'low': 0, 'medium': 0, 'high': 0}
        for item in items:
            domain_buckets[str(item['confidence_bucket'])] += 1
        domain_summaries[domain] = {
            'fixture_count': item_count,
            'average_required_field_coverage': round(sum(float(item['required_field_coverage']) for item in items) / item_count, 4),
            'average_missing_field_rate': round(sum(float(item['missing_field_rate']) for item in items) / item_count, 4),
            'average_artifact_completeness': round(sum(float(item['artifact_completeness']) for item in items) / item_count, 4),
            'confidence_buckets': domain_buckets,
            'expectation_failures': sum(len(item['expectation_failures']) for item in items),
        }

    return {
        'fixture_count': fixture_count,
        'average_required_field_coverage': round(sum(float(item['required_field_coverage']) for item in cases) / fixture_count, 4),
        'average_missing_field_rate': round(sum(float(item['missing_field_rate']) for item in cases) / fixture_count, 4),
        'average_artifact_completeness': round(sum(float(item['artifact_completeness']) for item in cases) / fixture_count, 4),
        'confidence_buckets': buckets,
        'expectation_failures': sum(len(item['expectation_failures']) for item in cases),
        'domain_summaries': domain_summaries,
        'cases': cases,
    }



def evaluate_fixture_tree(fixtures_dir: Path) -> Dict[str, Any]:
    paths = list(_iter_fixture_paths(fixtures_dir))
    if not paths:
        raise SystemExit(f'No analysis fixtures found under {fixtures_dir}')
    cases = [evaluate_fixture(path) for path in paths]
    return _aggregate_cases(cases)



def _format_human(report: Dict[str, Any], *, summary_only: bool) -> str:
    lines = [
        'Analysis strategy eval summary',
        f"fixtures: {report['fixture_count']}",
        f"avg coverage: {report['average_required_field_coverage']}",
        f"avg missing rate: {report['average_missing_field_rate']}",
        f"avg artifact completeness: {report['average_artifact_completeness']}",
        'confidence buckets:',
        f"  low={report['confidence_buckets']['low']} medium={report['confidence_buckets']['medium']} high={report['confidence_buckets']['high']}",
        f"expectation failures: {report['expectation_failures']}",
        'domains:',
    ]
    for domain, summary in report['domain_summaries'].items():
        lines.append(
            f"  - {domain}: fixtures={summary['fixture_count']} coverage={summary['average_required_field_coverage']} missing={summary['average_missing_field_rate']} failures={summary['expectation_failures']}"
        )
    if not summary_only:
        lines.append('cases:')
        for item in report['cases']:
            lines.append(
                f"  - {item['case_id']}: domain={item['domain']} confidence={item['parse_confidence']} coverage={item['required_field_coverage']} strategy={item['selected_strategy_id']} failures={len(item['expectation_failures'])}"
            )
    return '\n'.join(lines) + '\n'



def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Evaluate analysis artifacts across survey, class-report, and video-homework fixtures.')
    parser.add_argument('--fixtures', default='tests/fixtures', help='fixture directory to scan')
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
