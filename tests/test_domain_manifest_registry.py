from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_analysis_domain_contract import check_analysis_domain_contract
from services.api.artifacts.registry import ArtifactAdapterSpec, build_platform_artifact_registry
from services.api.domains.manifest_models import DomainManifest
from services.api.domains.manifest_registry import (
    DomainManifestRegistry,
    build_default_domain_manifest_registry,
)
from services.api.specialist_agents.registry import SpecialistAgentSpec
from services.api.strategies.contracts import StrategySpec
from services.api.strategies.selector import build_default_strategy_selector
from services.api.domains.runtime_builder import build_domain_specialist_registry


def test_default_domain_manifest_registry_exposes_supported_domains_and_rollout_flags() -> None:
    registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)

    manifests = registry.list()
    assert [item.domain_id for item in manifests] == ['video_homework']

    video_homework = registry.get('video_homework')
    assert video_homework.feature_flags == [
        'MULTIMODAL_ENABLED',
        'MULTIMODAL_MAX_UPLOAD_BYTES',
        'MULTIMODAL_MAX_DURATION_SEC',
        'MULTIMODAL_EXTRACT_TIMEOUT_SEC',
    ]



def test_platform_artifact_registry_matches_manifest_declarations() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)
    runtime_registry = build_platform_artifact_registry(manifest_registry=manifest_registry)

    declared_adapter_ids = {
        spec.adapter_id
        for manifest in manifest_registry.list()
        for spec in manifest.artifact_adapters
    }

    assert declared_adapter_ids == set()
    assert runtime_registry.find(output_artifact_type='class_signal_bundle') == []



def test_default_strategy_selector_uses_manifest_declared_specs() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.66)
    selector = build_default_strategy_selector(
        review_confidence_floor=0.66,
        manifest_registry=manifest_registry,
    )

    manifest_strategy_ids = {
        spec.strategy_id
        for manifest in manifest_registry.list()
        for spec in manifest.strategies
    }
    selector_strategy_ids = {spec.strategy_id for spec in selector._specs}

    assert selector_strategy_ids == manifest_strategy_ids
    assert next(spec for spec in selector._specs if spec.strategy_id == 'video_homework.teacher.report').specialist_agent == 'video_homework_analyst'



def test_specialist_registries_reuse_manifest_specs() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)

    video_homework_manifest = manifest_registry.get('video_homework')
    registry = build_domain_specialist_registry(domain_id='video_homework', manifests=manifest_registry, core=object())
    assert registry.get('video_homework_analyst') == video_homework_manifest.specialists[0]



def test_default_manifest_registry_declares_report_binding_metadata() -> None:
    registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)

    video_homework = registry.get('video_homework')
    assert video_homework.report_binding is None


SCRIPT_PATH = Path('scripts/check_analysis_domain_contract.py')


def test_analysis_domain_contract_checker_reports_default_registry_ready() -> None:
    payload = check_analysis_domain_contract()

    assert payload['ok'] is True
    assert payload['domains']['video_homework']['has_runtime_binding'] is True
    assert payload['domains']['video_homework']['specialist_ids'] == [
        'reviewer_analyst',
        'video_homework_analyst',
    ]


def test_analysis_domain_contract_checker_cli_json_output() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--json'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['ok'] is True
    assert 'video_homework' in payload['domains']
    assert 'survey' not in payload['domains']
    assert 'class_report' not in payload['domains']



def test_strategy_selector_rejects_manifest_strategy_with_missing_specialist_binding() -> None:
    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='broken',
            display_name='Broken Strategy Metadata',
            artifact_adapters=[
                ArtifactAdapterSpec(
                    adapter_id='broken.adapter',
                    accepted_inputs=['broken_input'],
                    output_artifact_type='broken_artifact',
                    task_kinds=['broken.analysis'],
                    validation_rules=[],
                )
            ],
            strategies=[
                StrategySpec(
                    strategy_id='broken.teacher.report',
                    accepted_artifacts=['broken_artifact'],
                    task_kinds=['broken.analysis'],
                    specialist_agent='missing_analyst',
                    roles=['teacher'],
                    target_scopes=['class'],
                )
            ],
            specialists=[
                SpecialistAgentSpec(
                    agent_id='other_analyst',
                    display_name='Other Analyst',
                    roles=['teacher'],
                    accepted_artifacts=['broken_artifact'],
                    task_kinds=['broken.analysis'],
                    budgets={'default': {'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 1}},
                    output_schema={'type': 'analysis_artifact'},
                )
            ],
        )
    )

    with pytest.raises(ValueError, match='strategy manifest'):
        build_default_strategy_selector(manifest_registry=registry)
