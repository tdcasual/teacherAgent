#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.analysis_policy_service import (  # noqa: E402
    DEFAULT_ANALYSIS_POLICY_PATH,
    build_analysis_policy_summary,
    load_analysis_policy_from_path,
)



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate analysis policy config and print a compact summary.')
    parser.add_argument('--config', default=str(DEFAULT_ANALYSIS_POLICY_PATH), help='analysis policy JSON path')
    parser.add_argument('--output', default='', help='optional output JSON path')
    parser.add_argument('--print-only', action='store_true', help='print summary even if invalid without failing')
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    try:
        policy = load_analysis_policy_from_path(config_path)
        payload = {
            'config_path': str(config_path),
            'valid': True,
            'summary': build_analysis_policy_summary(policy),
        }
        rendered = json.dumps(payload, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
        if args.print_only:
            return 0
        print('[OK] Analysis policy is valid.')
        return 0
    except Exception as exc:
        payload = {
            'config_path': str(config_path),
            'valid': False,
            'error': str(exc),
        }
        rendered = json.dumps(payload, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
        if args.print_only:
            return 0
        print(f'[FAIL] {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
