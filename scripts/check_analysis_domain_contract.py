#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.domains.manifest_registry as manifest_registry  # noqa: E402
from services.api.domains.binding_registry import (  # noqa: E402
    report_provider_factory_lookup,
    runtime_deps_factory_lookup,
    runtime_runner_lookup,
)



def _has_onboarding_docs() -> bool:
    index_path = REPO_ROOT / 'docs' / 'INDEX.md'
    runtime_contract_path = REPO_ROOT / 'docs' / 'reference' / 'analysis-runtime-contract.md'
    onboarding_path = REPO_ROOT / 'docs' / 'reference' / 'analysis-domain-onboarding-template.md'
    checklist_path = REPO_ROOT / 'docs' / 'reference' / 'analysis-domain-checklist.md'
    if not all(path.exists() for path in (index_path, runtime_contract_path, onboarding_path, checklist_path)):
        return False
    index_text = index_path.read_text(encoding='utf-8')
    runtime_contract_text = runtime_contract_path.read_text(encoding='utf-8')
    return (
        'analysis-domain-onboarding-template.md' in index_text
        and 'analysis-domain-checklist.md' in index_text
        and 'analysis-domain-onboarding-template.md' in runtime_contract_text
        and 'analysis-domain-checklist.md' in runtime_contract_text
    )



def _has_report_plane_contract() -> bool:
    runtime_contract_path = REPO_ROOT / 'docs' / 'reference' / 'analysis-runtime-contract.md'
    if not runtime_contract_path.exists():
        return False
    text = runtime_contract_path.read_text(encoding='utf-8')
    required = [
        'GET /teacher/analysis/reports',
        'GET /teacher/analysis/reports/{report_id}',
        'POST /teacher/analysis/reports/{report_id}/rerun',
        'GET /teacher/analysis/review-queue',
        'GET /teacher/analysis/metrics',
    ]
    return all(item in text for item in required)



def _has_replay_compare_support() -> bool:
    return all(
        path.exists()
        for path in (
            REPO_ROOT / 'scripts' / 'replay_analysis_run.py',
            REPO_ROOT / 'scripts' / 'compare_analysis_runs.py',
        )
    )



def _domain_summary(manifest) -> Dict[str, Any]:
    runtime_binding = manifest.runtime_binding
    report_binding = manifest.report_binding
    strategy_ids = sorted(str(spec.strategy_id) for spec in manifest.strategies)
    specialist_ids = sorted(str(spec.agent_id) for spec in manifest.specialists)
    strategy_agents = {str(spec.specialist_agent or '').strip() for spec in manifest.strategies if str(spec.specialist_agent or '').strip()}
    missing_specialists = sorted(agent_id for agent_id in strategy_agents if agent_id not in set(specialist_ids))
    runtime_lookup = runtime_deps_factory_lookup()
    runner_lookup = runtime_runner_lookup()
    report_lookup = report_provider_factory_lookup()
    runtime_factory_name = str(getattr(runtime_binding, 'specialist_deps_factory', '') or '').strip()
    report_factory_name = str(getattr(report_binding, 'provider_factory', '') or '').strip()
    has_runtime_binding = bool(
        runtime_binding
        and runtime_factory_name
        and str(runtime_binding.payload_constraint_key or '').strip()
    )
    has_report_binding = bool(report_binding and report_factory_name)
    has_runtime_lookup = bool(has_runtime_binding and runtime_factory_name in runtime_lookup)
    has_runner_lookup = all(agent_id in runner_lookup for agent_id in specialist_ids)
    has_report_lookup = bool(has_report_binding and report_factory_name in report_lookup)
    has_onboarding_docs = _has_onboarding_docs()
    has_report_plane_contract = _has_report_plane_contract()
    has_replay_compare_support = _has_replay_compare_support()
    ok = bool(
        str(manifest.domain_id or '').strip()
        and has_runtime_binding
        and has_report_binding
        and has_runtime_lookup
        and has_runner_lookup
        and has_report_lookup
        and has_onboarding_docs
        and has_report_plane_contract
        and has_replay_compare_support
        and len(strategy_ids) > 0
        and len(specialist_ids) > 0
        and not missing_specialists
    )
    return {
        'domain_id': manifest.domain_id,
        'rollout_stage': str(manifest.rollout_stage or '').strip() or None,
        'feature_flags': list(manifest.feature_flags or []),
        'strategy_ids': strategy_ids,
        'specialist_ids': specialist_ids,
        'artifact_adapter_ids': sorted(str(spec.adapter_id) for spec in manifest.artifact_adapters),
        'has_runtime_binding': has_runtime_binding,
        'has_report_binding': has_report_binding,
        'has_runtime_lookup': has_runtime_lookup,
        'has_runner_lookup': has_runner_lookup,
        'has_report_lookup': has_report_lookup,
        'has_onboarding_docs': has_onboarding_docs,
        'has_report_plane_contract': has_report_plane_contract,
        'has_replay_compare_support': has_replay_compare_support,
        'missing_specialists': missing_specialists,
        'ok': ok,
    }



def check_analysis_domain_contract() -> Dict[str, Any]:
    registry = manifest_registry.build_default_domain_manifest_registry()
    domains = {manifest.domain_id: _domain_summary(manifest) for manifest in registry.list()}
    failures: List[Dict[str, Any]] = []
    for domain_id, summary in domains.items():
        if bool(summary.get('ok')):
            continue
        failures.append(
            {
                'domain_id': domain_id,
                'missing_specialists': summary['missing_specialists'],
                'has_runtime_lookup': summary['has_runtime_lookup'],
                'has_runner_lookup': summary['has_runner_lookup'],
                'has_report_lookup': summary['has_report_lookup'],
                'has_onboarding_docs': summary['has_onboarding_docs'],
                'has_report_plane_contract': summary['has_report_plane_contract'],
                'has_replay_compare_support': summary['has_replay_compare_support'],
            }
        )
    return {
        'ok': len(failures) == 0,
        'domain_count': len(domains),
        'domains': domains,
        'failures': failures,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check analysis domains satisfy manifest, binding, docs, and replay/compare contract basics.')
    parser.add_argument('--json', action='store_true', help='print JSON output')
    args = parser.parse_args(argv)

    payload = check_analysis_domain_contract()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok={payload['ok']} domain_count={payload['domain_count']}")
        for domain_id, summary in payload['domains'].items():
            print(
                f"- {domain_id}: runtime={summary['has_runtime_binding']} runtime_lookup={summary['has_runtime_lookup']} "
                f"report={summary['has_report_binding']} report_lookup={summary['has_report_lookup']} "
                f"docs={summary['has_onboarding_docs']} replay_compare={summary['has_replay_compare_support']} "
                f"missing_specialists={summary['missing_specialists']}"
            )
    return 0 if payload['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
