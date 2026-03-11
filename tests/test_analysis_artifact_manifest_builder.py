from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/build_analysis_artifact_manifest.py')


def test_build_analysis_artifact_manifest_catalogs_known_artifacts(tmp_path: Path) -> None:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()
    for name, content in {
        'analysis-policy.json': '{}\n',
        'analysis-preflight.json': '{}\n',
        'analysis-rollout-decision.json': '{}\n',
        'analysis-rollout-brief.md': '# brief\n',
        'analysis-go-live-summary.md': '# summary\n',
        'analysis-release-notes.md': '# notes\n',
    }.items():
        (artifact_dir / name).write_text(content, encoding='utf-8')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload['artifact_count'] >= 6
    names = {item['name'] for item in payload['artifacts']}
    assert 'analysis-policy.json' in names
    assert 'analysis-release-notes.md' in names
    policy_entry = next(item for item in payload['artifacts'] if item['name'] == 'analysis-policy.json')
    assert policy_entry['exists'] is True
    assert policy_entry['format'] == 'json'
    assert policy_entry['artifact_type'] == 'policy'



def test_build_analysis_artifact_manifest_includes_dependency_metadata(tmp_path: Path) -> None:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()
    for name, content in {
        'analysis-policy.json': '{}\n',
        'analysis-preflight.json': '{}\n',
        'analysis-rollout-decision.json': '{}\n',
        'analysis-rollout-brief.md': '# brief\n',
        'analysis-go-live-summary.md': '# summary\n',
        'analysis-release-notes.md': '# notes\n',
        'analysis-artifact-manifest.json': '{}\n',
    }.items():
        (artifact_dir / name).write_text(content, encoding='utf-8')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload['build_sequence'][0] == 'analysis-policy.json'
    release_notes_entry = next(item for item in payload['artifacts'] if item['name'] == 'analysis-release-notes.md')
    assert release_notes_entry['build_order'] > 0
    assert 'analysis-go-live-summary.md' in release_notes_entry['depends_on']
    assert release_notes_entry['generated_by'] == 'scripts/quality/build_analysis_release_notes.py'
    manifest_entry = next(item for item in payload['artifacts'] if item['name'] == 'analysis-artifact-manifest.json')
    assert 'analysis-release-notes.md' in manifest_entry['depends_on']
