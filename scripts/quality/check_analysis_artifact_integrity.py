#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

Issue = Dict[str, Any]
ArtifactEntry = Dict[str, Any]


def _issue(*, code: str, message: str, artifact: str = '', dependency: str = '') -> Issue:
    payload: Issue = {'code': code, 'message': message}
    if artifact:
        payload['artifact'] = artifact
    if dependency:
        payload['dependency'] = dependency
    return payload



def _load_manifest(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('manifest must be a JSON object')
    return payload



def _normalize_artifacts(raw_artifacts: Any) -> Tuple[List[ArtifactEntry], List[Issue]]:
    issues: List[Issue] = []
    if not isinstance(raw_artifacts, list):
        return [], [_issue(code='invalid_manifest', message='manifest field "artifacts" must be a list')]

    artifacts: List[ArtifactEntry] = []
    for index, raw_item in enumerate(raw_artifacts):
        if not isinstance(raw_item, dict):
            issues.append(
                _issue(
                    code='invalid_artifact_entry',
                    message=f'artifact entry at index {index} must be an object',
                )
            )
            continue
        artifacts.append(dict(raw_item))
    return artifacts, issues



def check_analysis_artifact_integrity(*, manifest_path: Path) -> Dict[str, Any]:
    issues: List[Issue] = []
    manifest = _load_manifest(manifest_path)

    artifact_dir_raw = manifest.get('artifact_dir') or str(manifest_path.parent)
    artifact_dir = Path(str(artifact_dir_raw))

    artifacts, artifact_issues = _normalize_artifacts(manifest.get('artifacts'))
    issues.extend(artifact_issues)

    raw_sequence = manifest.get('build_sequence')
    build_sequence = list(raw_sequence) if isinstance(raw_sequence, list) else []
    if not isinstance(raw_sequence, list):
        issues.append(_issue(code='invalid_manifest', message='manifest field "build_sequence" must be a list'))

    seen_names: set[str] = set()
    artifact_by_name: Dict[str, ArtifactEntry] = {}
    build_order_by_name: Dict[str, int] = {}

    normalized_entries: List[ArtifactEntry] = []
    for index, artifact in enumerate(artifacts):
        name = str(artifact.get('name') or '')
        if not name:
            issues.append(_issue(code='missing_artifact_name', message=f'artifact entry at index {index} is missing a name'))
            continue

        if name in seen_names:
            issues.append(
                _issue(
                    code='duplicate_artifact_name',
                    artifact=name,
                    message=f'artifact {name} is declared more than once in the manifest',
                )
            )
        else:
            seen_names.add(name)
            artifact_by_name[name] = artifact

        try:
            build_order = int(artifact.get('build_order'))
        except (TypeError, ValueError):
            build_order = 0
            issues.append(
                _issue(
                    code='invalid_build_order',
                    artifact=name,
                    message=f'artifact {name} must declare an integer build_order',
                )
            )

        artifact_path = Path(str(artifact.get('path') or artifact_dir / name))
        manifest_exists = bool(artifact.get('exists'))
        disk_exists = artifact_path.exists()
        artifact['name'] = name
        artifact['build_order'] = build_order
        artifact['path'] = str(artifact_path)
        artifact['exists'] = manifest_exists
        artifact['_disk_exists'] = disk_exists
        normalized_entries.append(artifact)
        build_order_by_name.setdefault(name, build_order)

        if manifest_exists != disk_exists:
            issues.append(
                _issue(
                    code='exists_flag_mismatch',
                    artifact=name,
                    message=(
                        f'artifact {name} exists={manifest_exists} in manifest but file presence on disk is {disk_exists}'
                    ),
                )
            )

        if not disk_exists:
            issues.append(
                _issue(
                    code='missing_artifact_file',
                    artifact=name,
                    message=f'artifact file is missing on disk: {artifact_path}',
                )
            )

    expected_sequence = [
        item['name'] for item in sorted(normalized_entries, key=lambda item: (int(item['build_order']), str(item['name'])))
    ]
    if build_sequence != expected_sequence:
        issues.append(
            {
                'code': 'build_sequence_mismatch',
                'message': 'manifest build_sequence does not match artifact build_order ordering',
                'expected_sequence': expected_sequence,
                'actual_sequence': build_sequence,
            }
        )

    for artifact in normalized_entries:
        name = str(artifact['name'])
        depends_on = artifact.get('depends_on') or []
        if not isinstance(depends_on, list):
            issues.append(
                _issue(
                    code='invalid_dependencies',
                    artifact=name,
                    message=f'artifact {name} must declare depends_on as a list',
                )
            )
            continue

        for dependency_name_raw in depends_on:
            dependency_name = str(dependency_name_raw)
            dependency = artifact_by_name.get(dependency_name)
            if dependency is None:
                issues.append(
                    _issue(
                        code='unknown_dependency',
                        artifact=name,
                        dependency=dependency_name,
                        message=f'artifact {name} depends on unknown artifact {dependency_name}',
                    )
                )
                continue

            if int(build_order_by_name.get(dependency_name, 0)) >= int(artifact['build_order']):
                issues.append(
                    _issue(
                        code='dependency_order_violation',
                        artifact=name,
                        dependency=dependency_name,
                        message=f'artifact {name} depends on {dependency_name} but build_order is not earlier',
                    )
                )

            if bool(artifact['_disk_exists']) and not bool(dependency.get('_disk_exists')):
                issues.append(
                    _issue(
                        code='missing_dependency_artifact',
                        artifact=name,
                        dependency=dependency_name,
                        message=f'artifact {name} exists but dependency file {dependency_name} is missing',
                    )
                )

    return {
        'ok': len(issues) == 0,
        'manifest_path': str(manifest_path),
        'artifact_dir': str(artifact_dir),
        'validated_artifacts': len(normalized_entries),
        'issue_count': len(issues),
        'issues': issues,
    }



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate analysis artifact manifest integrity.')
    parser.add_argument(
        '--manifest',
        default='analysis-artifacts/analysis-artifact-manifest.json',
        help='path to analysis artifact manifest JSON',
    )
    parser.add_argument('--output', default='', help='optional output JSON path')
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    try:
        payload = check_analysis_artifact_integrity(manifest_path=manifest_path)
    except Exception as exc:
        payload = {
            'ok': False,
            'manifest_path': str(manifest_path),
            'artifact_dir': str(manifest_path.parent),
            'validated_artifacts': 0,
            'issue_count': 1,
            'issues': [_issue(code='invalid_manifest', message=str(exc))],
        }

    rendered = json.dumps(payload, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    if payload['ok']:
        return 0
    print('[FAIL] Analysis artifact integrity validation failed.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
