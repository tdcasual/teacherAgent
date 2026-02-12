from pathlib import Path


def test_report_contains_target_metrics() -> None:
  text = Path('docs/plans/2026-02-12-maintainability-architecture-refactor-report.md').read_text(encoding='utf-8')
  assert 'app_core lines' in text
  assert 'student chunk size' in text
