from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path('scripts/analysis_strategy_eval.py')
FIXTURES_DIR = Path('tests/fixtures')



def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location('analysis_strategy_eval', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def test_analysis_strategy_eval_fixture_tree_contains_expected_cross_domain_cases() -> None:
    paths = sorted(str(path.relative_to(FIXTURES_DIR)) for path in FIXTURES_DIR.rglob('*.json'))
    assert 'surveys/structured/basic_payload.json' in paths
    assert 'surveys/provider_attachment_noise.json' in paths
    assert 'analysis_reports/class_report/self_hosted_form_basic.json' in paths
    assert 'analysis_reports/class_report/web_export_complex.json' in paths
    assert 'analysis_reports/class_report/pdf_summary_low_confidence.json' in paths
    assert 'multimodal/video_homework/basic_submission.json' in paths
    assert 'multimodal/video_homework/long_duration_trimmed.json' in paths
    assert 'multimodal/video_homework/ocr_noise_case.json' in paths



def test_analysis_strategy_eval_produces_cross_domain_summary() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(FIXTURES_DIR)

    assert report['fixture_count'] == 10
    assert set(report['confidence_buckets']) == {'low', 'medium', 'high'}
    assert set(report['domain_summaries']) == {'survey', 'class_report', 'video_homework'}
    assert report['domain_summaries']['survey']['fixture_count'] == 4
    assert report['domain_summaries']['class_report']['fixture_count'] == 3
    assert report['domain_summaries']['video_homework']['fixture_count'] == 3
    assert report['domain_summaries']['survey']['meets_minimum_fixture_count'] is True
    assert report['domain_summaries']['class_report']['meets_minimum_fixture_count'] is True
    assert report['domain_summaries']['video_homework']['meets_minimum_fixture_count'] is True
    assert report['expectation_failures'] == 0
    assert report['expectation_failure_reasons'] == {}
    assert report['rollout_recommendations']['ready_for_expansion'] is True
    assert report['rollout_recommendations']['minimum_fixture_counts']['survey']['required'] == 3
    assert report['rollout_recommendations']['minimum_fixture_counts']['class_report']['actual'] == 3
    assert report['rollout_recommendations']['required_edge_cases']['provider_attachment_noise']['covered'] is True
    assert report['rollout_recommendations']['required_edge_cases']['long_duration_submission']['covered'] is True
    assert report['edge_case_coverage']['overall']['provider_attachment_noise'] == 1
    assert report['edge_case_coverage']['overall']['long_duration_submission'] == 1
    assert report['edge_case_coverage']['overall']['low_confidence_parse'] >= 1
    case_ids = {item['case_id'] for item in report['cases']}
    assert case_ids == {
        'structured_basic_payload',
        'unstructured_pdf_report_excerpt',
        'unstructured_screenshot_ocr_excerpt',
        'survey_provider_attachment_noise',
        'class_report_self_hosted_form_basic',
        'class_report_web_export_complex',
        'class_report_pdf_summary_low_confidence',
        'video_homework_basic_submission',
        'video_homework_long_duration_trimmed',
        'video_homework_ocr_noise_case',
    }



def test_analysis_strategy_eval_reports_edge_case_coverage_and_rollout_thresholds() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(FIXTURES_DIR)

    assert report['edge_case_coverage']['by_domain']['survey']['provider_attachment_noise'] == 1
    assert report['edge_case_coverage']['by_domain']['class_report']['web_export_complex'] == 1
    assert report['edge_case_coverage']['by_domain']['video_homework']['long_duration_submission'] == 1
    assert report['domain_summaries']['video_homework']['edge_case_counts']['ocr_noise'] >= 1
    assert report['domain_summaries']['class_report']['edge_case_counts']['low_confidence_parse'] >= 1



def test_analysis_strategy_eval_cli_json_output() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--fixtures', str(FIXTURES_DIR), '--json', '--summary-only'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['fixture_count'] == 10
    assert 'domain_summaries' in payload
    assert 'edge_case_coverage' in payload
    assert 'rollout_recommendations' in payload
    assert payload['expectation_failures'] == 0
    assert 'cases' not in payload



def test_analysis_strategy_eval_help() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--help'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert 'usage:' in proc.stdout.lower()


def test_analysis_strategy_eval_reads_review_feedback(tmp_path: Path) -> None:
    module = _load_module()
    feedback_path = tmp_path / 'review_feedback.json'
    feedback_path.write_text(
        json.dumps(
            {
                'total_items': 2,
                'by_action': {'reject': 1, 'retry': 1},
                'by_domain': {'survey': 2},
                'by_reason_code': {'low_confidence': 2},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    payload = module.load_review_feedback_summary(feedback_path)

    assert payload['total_items'] == 2
    assert payload['by_action']['reject'] == 1


def test_analysis_strategy_eval_includes_review_feedback_in_report() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(FIXTURES_DIR, review_feedback={'total_items': 3, 'by_action': {'resolve': 2}})

    assert report['review_feedback']['total_items'] == 3
    assert report['review_feedback']['by_action']['resolve'] == 2


def test_analysis_strategy_eval_summarizes_review_feedback_dataset_items() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(
        FIXTURES_DIR,
        review_feedback={
            'items': [
                {
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'retry',
                    'disposition': 'retry_requested',
                    'reason_code': 'low_confidence',
                },
                {
                    'item_id': 'rvw_2',
                    'domain': 'class_report',
                    'strategy_id': 'class_signal.teacher.report',
                    'operation': 'reject',
                    'disposition': 'rejected',
                    'reason_code': 'missing_fields',
                },
            ]
        },
    )

    assert report['review_feedback']['total_items'] == 2
    assert report['review_feedback']['by_strategy']['survey.teacher.report'] == 1
    assert report['review_feedback']['by_domain_reason_code']['survey']['low_confidence'] == 1
    assert report['review_feedback']['by_domain_reason_code']['class_report']['missing_fields'] == 1


def test_analysis_strategy_eval_includes_review_feedback_drift_summary() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(
        FIXTURES_DIR,
        review_feedback={
            'items': [
                {
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'reject',
                    'disposition': 'rejected',
                    'reason_code': 'invalid_output',
                },
                {
                    'item_id': 'rvw_2',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'retry',
                    'disposition': 'retry_requested',
                    'reason_code': 'low_confidence',
                },
            ]
        },
    )

    assert report['review_feedback']['drift_summary']['top_regression_domains'][0]['domain'] == 'survey'
    assert report['review_feedback']['drift_summary']['top_regression_strategies'][0]['strategy_id'] == 'survey.teacher.report'
