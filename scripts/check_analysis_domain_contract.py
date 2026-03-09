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


def _domain_summary(manifest) -> Dict[str, Any]:
    runtime_binding = manifest.runtime_binding
    report_binding = manifest.report_binding
    strategy_ids = sorted(str(spec.strategy_id) for spec in manifest.strategies)
    specialist_ids = sorted(str(spec.agent_id) for spec in manifest.specialists)
    strategy_agents = {str(spec.specialist_agent or '').strip() for spec in manifest.strategies if str(spec.specialist_agent or '').strip()}
    missing_specialists = sorted(agent_id for agent_id in strategy_agents if agent_id not in set(specialist_ids))
    has_runtime_binding = bool(
        runtime_binding
        and str(runtime_binding.specialist_deps_factory or '').strip()
        and str(runtime_binding.payload_constraint_key or '').strip()
    )
    has_report_binding = bool(report_binding and str(report_binding.provider_factory or '').strip())
    return {
        'domain_id': manifest.domain_id,
        'rollout_stage': str(manifest.rollout_stage or '').strip() or None,
        'feature_flags': list(manifest.feature_flags or []),
        'strategy_ids': strategy_ids,
        'specialist_ids': specialist_ids,
        'artifact_adapter_ids': sorted(str(spec.adapter_id) for spec in manifest.artifact_adapters),
        'has_runtime_binding': has_runtime_binding,
        'has_report_binding': has_report_binding,
        'missing_specialists': missing_specialists,
        'ok': bool(
            str(manifest.domain_id or '').strip()
            and has_runtime_binding
            and has_report_binding
            and len(strategy_ids) > 0
            and len(specialist_ids) > 0
            and not missing_specialists
        ),
    }



def check_analysis_domain_contract() -> Dict[str, Any]:
    registry = manifest_registry.build_default_domain_manifest_registry()
    domains = {manifest.domain_id: _domain_summary(manifest) for manifest in registry.list()}
    failures: List[Dict[str, Any]] = [
        {'domain_id': domain_id, 'missing_specialists': summary['missing_specialists']}
        for domain_id, summary in domains.items()
        if not bool(summary.get('ok'))
    ]
    return {
        'ok': len(failures) == 0,
        'domain_count': len(domains),
        'domains': domains,
        'failures': failures,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check default analysis domain manifests satisfy onboarding contract basics.')
    parser.add_argument('--json', action='store_true', help='print JSON output')
    args = parser.parse_args(argv)

    payload = check_analysis_domain_contract()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok={payload['ok']} domain_count={payload['domain_count']}")
        for domain_id, summary in payload['domains'].items():
            print(
                f"- {domain_id}: runtime={summary['has_runtime_binding']} report={summary['has_report_binding']} "
                f"strategies={len(summary['strategy_ids'])} specialists={len(summary['specialist_ids'])} missing_specialists={summary['missing_specialists']}"
            )
    return 0 if payload['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
