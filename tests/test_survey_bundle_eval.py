from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


SCRIPT_PATH = Path('scripts/survey_bundle_eval.py')
FIXTURES_DIR = Path('tests/fixtures/surveys')


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location('survey_bundle_eval', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_survey_bundle_eval_fixture_tree_contains_expected_cases() -> None:
    paths = sorted(str(path.relative_to(FIXTURES_DIR)) for path in FIXTURES_DIR.rglob('*.json'))
    assert 'structured/basic_payload.json' in paths
    assert 'unstructured/pdf_report_excerpt.json' in paths
    assert 'unstructured/screenshot_ocr_excerpt.json' in paths


def test_survey_bundle_eval_produces_summary_for_fixture_tree() -> None:
    module = _load_module()
    report = module.evaluate_fixture_tree(FIXTURES_DIR)

    assert report['fixture_count'] == 3
    assert set(report['confidence_buckets']) == {'low', 'medium', 'high'}
    assert 0.0 <= report['average_required_field_coverage'] <= 1.0
    assert 0.0 <= report['average_missing_field_rate'] <= 1.0
    assert 0.0 <= report['average_artifact_completeness'] <= 1.0
    case_ids = {item['case_id'] for item in report['cases']}
    assert case_ids == {'structured_basic_payload', 'unstructured_pdf_report_excerpt', 'unstructured_screenshot_ocr_excerpt'}



def test_survey_bundle_eval_cli_json_output() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--fixtures', str(FIXTURES_DIR), '--json', '--summary-only'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['fixture_count'] == 3
    assert 'average_required_field_coverage' in payload



def test_survey_bundle_eval_help() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--help'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert 'usage:' in proc.stdout.lower()
