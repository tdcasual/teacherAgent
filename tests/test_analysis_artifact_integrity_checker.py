import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/check_analysis_artifact_integrity.py')


_BASE_ARTIFACTS = (
    {
        'name': 'analysis-policy.json',
        'format': 'json',
        'artifact_type': 'policy',
        'build_order': 10,
        'depends_on': [],
        'generated_by': 'scripts/quality/check_analysis_policy.py',
    },
    {
        'name': 'analysis-preflight.json',
        'format': 'json',
        'artifact_type': 'preflight',
        'build_order': 20,
        'depends_on': [],
        'generated_by': 'scripts/quality/check_analysis_preflight.py',
    },
    {
        'name': 'analysis-rollout-decision.json',
        'format': 'json',
        'artifact_type': 'decision',
        'build_order': 30,
        'depends_on': ['analysis-policy.json', 'analysis-preflight.json'],
        'generated_by': 'scripts/quality/build_analysis_rollout_decision.py',
    },
    {
        'name': 'analysis-rollout-brief.md',
        'format': 'markdown',
        'artifact_type': 'brief',
        'build_order': 40,
        'depends_on': ['analysis-policy.json', 'analysis-preflight.json', 'analysis-rollout-decision.json'],
        'generated_by': 'scripts/quality/build_analysis_rollout_brief.py',
    },
    {
        'name': 'analysis-go-live-summary.md',
        'format': 'markdown',
        'artifact_type': 'go_live_summary',
        'build_order': 50,
        'depends_on': ['analysis-rollout-decision.json', 'analysis-rollout-brief.md'],
        'generated_by': 'scripts/quality/build_analysis_go_live_summary.py',
    },
    {
        'name': 'analysis-release-notes.md',
        'format': 'markdown',
        'artifact_type': 'release_notes',
        'build_order': 60,
        'depends_on': ['analysis-rollout-decision.json', 'analysis-rollout-brief.md', 'analysis-go-live-summary.md'],
        'generated_by': 'scripts/quality/build_analysis_release_notes.py',
    },
    {
        'name': 'analysis-artifact-manifest.json',
        'format': 'json',
        'artifact_type': 'artifact_manifest',
        'build_order': 70,
        'depends_on': [
            'analysis-policy.json',
            'analysis-preflight.json',
            'analysis-rollout-decision.json',
            'analysis-rollout-brief.md',
            'analysis-go-live-summary.md',
            'analysis-release-notes.md',
        ],
        'generated_by': 'scripts/quality/build_analysis_artifact_manifest.py',
    },
)


_DEF_CONTENT = {
    'analysis-policy.json': '{}\n',
    'analysis-preflight.json': '{}\n',
    'analysis-rollout-decision.json': '{}\n',
    'analysis-rollout-brief.md': '# brief\n',
    'analysis-go-live-summary.md': '# summary\n',
    'analysis-release-notes.md': '# notes\n',
}


def _write_manifest(tmp_path: Path, *, mutate=None, build_sequence=None, missing_files=()) -> Path:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()

    for name, content in _DEF_CONTENT.items():
        if name not in missing_files:
            (artifact_dir / name).write_text(content, encoding='utf-8')

    entries = []
    for item in _BASE_ARTIFACTS:
        entry = dict(item)
        entry['path'] = str(artifact_dir / entry['name'])
        entry['exists'] = entry['name'] not in missing_files
        entries.append(entry)

    if mutate is not None:
        entries = mutate(entries)

    manifest_payload = {
        'artifact_dir': str(artifact_dir),
        'artifact_count': len(entries),
        'build_sequence': build_sequence or [item['name'] for item in entries],
        'artifacts': entries,
    }
    manifest_path = artifact_dir / 'analysis-artifact-manifest.json'
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False) + '\n', encoding='utf-8')
    return manifest_path



def test_check_analysis_artifact_integrity_passes_for_complete_chain(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--manifest', str(manifest_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload['ok'] is True
    assert payload['issue_count'] == 0
    assert payload['validated_artifacts'] == 7



def test_check_analysis_artifact_integrity_fails_on_unknown_dependency(tmp_path: Path) -> None:
    def mutate(entries: list[dict[str, object]]) -> list[dict[str, object]]:
        updated = []
        for entry in entries:
            changed = dict(entry)
            if changed['name'] == 'analysis-release-notes.md':
                changed['depends_on'] = list(changed['depends_on']) + ['ghost-artifact.md']
            updated.append(changed)
        return updated

    manifest_path = _write_manifest(tmp_path, mutate=mutate)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--manifest', str(manifest_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload['ok'] is False
    assert any(issue['code'] == 'unknown_dependency' for issue in payload['issues'])



def test_check_analysis_artifact_integrity_fails_on_build_sequence_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        build_sequence=[
            'analysis-preflight.json',
            'analysis-policy.json',
            'analysis-rollout-decision.json',
            'analysis-rollout-brief.md',
            'analysis-go-live-summary.md',
            'analysis-release-notes.md',
            'analysis-artifact-manifest.json',
        ],
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--manifest', str(manifest_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload['ok'] is False
    assert any(issue['code'] == 'build_sequence_mismatch' for issue in payload['issues'])



def test_check_analysis_artifact_integrity_fails_on_duplicate_names_and_missing_dependency_file(tmp_path: Path) -> None:
    def mutate(entries: list[dict[str, object]]) -> list[dict[str, object]]:
        duplicated = [dict(item) for item in entries]
        duplicated.append(dict(duplicated[0]))
        return duplicated

    manifest_path = _write_manifest(tmp_path, mutate=mutate, missing_files=('analysis-go-live-summary.md',))

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--manifest', str(manifest_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload['ok'] is False
    issue_codes = {issue['code'] for issue in payload['issues']}
    assert 'duplicate_artifact_name' in issue_codes
    assert 'missing_dependency_artifact' in issue_codes
