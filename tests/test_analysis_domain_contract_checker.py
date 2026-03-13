from __future__ import annotations

import json
import subprocess
import sys

import scripts.check_analysis_domain_contract as checker


def test_analysis_domain_contract_checker_reports_docs_bindings_and_replay_support() -> None:
    payload = checker.check_analysis_domain_contract()

    assert payload['ok'] is True
    assert payload['domain_count'] >= 3
    for summary in payload['domains'].values():
        assert summary['has_runtime_binding'] is True
        assert summary['has_report_binding'] is True
        assert summary['has_runtime_lookup'] is True
        assert summary['has_report_lookup'] is True
        assert summary['has_onboarding_docs'] is True
        assert summary['has_report_plane_contract'] is True
        assert summary['has_replay_compare_support'] is True



def test_analysis_domain_contract_checker_cli_json_output() -> None:
    proc = subprocess.run(
        [sys.executable, 'scripts/check_analysis_domain_contract.py', '--json'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['ok'] is True
    assert 'domains' in payload
