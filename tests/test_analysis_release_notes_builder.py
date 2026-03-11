from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/build_analysis_release_notes.py')


def test_build_analysis_release_notes_renders_summary_and_next_actions(tmp_path: Path) -> None:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()
    (artifact_dir / 'analysis-rollout-decision.json').write_text(
        json.dumps(
            {
                'decision': 'blocked',
                'decision_label': 'BLOCKED',
                'ready_for_rollout': False,
                'summary': 'Analysis rollout is blocked until blocking issues are resolved.',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-rollout-brief.md').write_text(
        '# Analysis Rollout Brief\n\n## Recommended Actions\n- Runtime: Stabilize specialist output schema handling.\n',
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-go-live-summary.md').write_text(
        '# Analysis Go-Live Summary\n\n## Verification Snapshot\n- Policy valid: True\n- Blocking issues: 1\n',
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir), '--date', '2026-03-11', '--release-ref', 'main@abc123'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    output = proc.stdout
    assert '# Analysis Release Notes' in output
    assert 'Date: 2026-03-11' in output
    assert 'Release: main@abc123' in output
    assert 'Summary' in output
    assert 'Analysis rollout is blocked until blocking issues are resolved.' in output
    assert 'Release Decision' in output
    assert 'BLOCKED' in output
    assert 'Verification Snapshot' in output
    assert '- Policy valid: True' in output
    assert '- Blocking issues: 1' in output
    assert 'Recommended Next Actions' in output
    assert '- Runtime: Stabilize specialist output schema handling.' in output
