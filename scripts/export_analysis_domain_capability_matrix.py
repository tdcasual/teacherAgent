#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_analysis_domain_contract import check_analysis_domain_contract



def build_analysis_domain_capability_matrix_markdown() -> str:
    payload = check_analysis_domain_contract()
    domains = payload.get('domains') or {}
    lines: List[str] = [
        '# Analysis Domain Capability Matrix',
        '',
        '由 manifest / binding / contract checker 生成，用于快速查看当前 analysis domains 的平台能力面。',
        '',
        '| domain_id | rollout_stage | strategy_ids | specialist_ids | runtime_binding | report_binding | replay_compare |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for domain_id in sorted(domains):
        summary = domains[domain_id] or {}
        strategy_ids = '<br>'.join(summary.get('strategy_ids') or []) or '-'
        specialist_ids = '<br>'.join(summary.get('specialist_ids') or []) or '-'
        lines.append(
            '| {domain_id} | {rollout_stage} | {strategy_ids} | {specialist_ids} | {runtime_binding} | {report_binding} | {replay_compare} |'.format(
                domain_id=domain_id,
                rollout_stage=summary.get('rollout_stage') or '-',
                strategy_ids=strategy_ids,
                specialist_ids=specialist_ids,
                runtime_binding='yes' if summary.get('has_runtime_binding') else 'no',
                report_binding='yes' if summary.get('has_report_binding') else 'no',
                replay_compare='yes' if summary.get('has_replay_compare_support') else 'no',
            )
        )
    lines.extend(
        [
            '',
            '## Source',
            '',
            '- `scripts/check_analysis_domain_contract.py --json`',
            '- `services/api/domains/manifest_registry.py`',
            '- `services/api/domains/binding_registry.py`',
        ]
    )
    return '\n'.join(lines) + '\n'



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export a markdown capability matrix for current analysis domains.')
    parser.add_argument('--output', required=True, help='output markdown path')
    args = parser.parse_args(argv)
    Path(args.output).write_text(build_analysis_domain_capability_matrix_markdown(), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
