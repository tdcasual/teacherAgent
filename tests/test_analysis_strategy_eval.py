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
    assert 'analysis_reports/class_report/self_hosted_form_basic.json' in paths
    assert 'multimodal/video_homework/basic_submission.json' in paths



def test_analysis_strategy_eval_produces_cross_domain_summary() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(FIXTURES_DIR)

    assert report['fixture_count'] == 5
    assert set(report['confidence_buckets']) == {'low', 'medium', 'high'}
    assert set(report['domain_summaries']) == {'survey', 'class_report', 'video_homework'}
    assert report['domain_summaries']['survey']['fixture_count'] == 3
    assert report['domain_summaries']['class_report']['fixture_count'] == 1
    assert report['domain_summaries']['video_homework']['fixture_count'] == 1
    assert report['expectation_failures'] == 0
    case_ids = {item['case_id'] for item in report['cases']}
    assert case_ids == {
        'structured_basic_payload',
        'unstructured_pdf_report_excerpt',
        'unstructured_screenshot_ocr_excerpt',
        'class_report_self_hosted_form_basic',
        'video_homework_basic_submission',
    }



def test_analysis_strategy_eval_cli_json_output() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--fixtures', str(FIXTURES_DIR), '--json', '--summary-only'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['fixture_count'] == 5
    assert 'domain_summaries' in payload
    assert payload['expectation_failures'] == 0



def test_analysis_strategy_eval_help() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--help'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert 'usage:' in proc.stdout.lower()
