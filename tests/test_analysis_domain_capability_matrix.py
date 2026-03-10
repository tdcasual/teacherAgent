from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.export_analysis_domain_capability_matrix import build_analysis_domain_capability_matrix_markdown


SCRIPT_PATH = Path('scripts/export_analysis_domain_capability_matrix.py')



def test_build_analysis_domain_capability_matrix_markdown_contains_core_columns() -> None:
    markdown = build_analysis_domain_capability_matrix_markdown()

    assert '# Analysis Domain Capability Matrix' in markdown
    assert '| domain_id | rollout_stage | strategy_ids | specialist_ids | runtime_binding | report_binding | replay_compare |' in markdown
    assert 'survey' in markdown
    assert 'class_report' in markdown
    assert 'video_homework' in markdown



def test_export_analysis_domain_capability_matrix_cli_writes_file(tmp_path: Path) -> None:
    output_path = tmp_path / 'analysis-domain-capability-matrix.md'
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--output', str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    text = output_path.read_text(encoding='utf-8')
    assert 'Analysis Domain Capability Matrix' in text
    assert 'survey.teacher.report' in text
