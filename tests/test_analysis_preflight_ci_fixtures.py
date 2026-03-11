from __future__ import annotations

from pathlib import Path


def test_analysis_preflight_ci_fixture_bundle_exists() -> None:
    root = Path('tests/fixtures/analysis_preflight')
    assert (root / 'metrics.json').exists()
    assert (root / 'review_feedback.jsonl').exists()
    assert (root / 'baseline' / 'report_1.json').exists()
    assert (root / 'candidate' / 'report_1.json').exists()



def test_analysis_preflight_ci_fixture_directories_are_not_empty() -> None:
    root = Path('tests/fixtures/analysis_preflight')
    assert any((root / 'baseline').iterdir())
    assert any((root / 'candidate').iterdir())
