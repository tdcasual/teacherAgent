from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict



def replay_analysis_run(*, report_path: Path) -> Dict[str, Any]:
    payload = json.loads(Path(report_path).read_text(encoding='utf-8'))
    report = dict(payload.get('report') or payload)
    artifact_meta = dict(payload.get('artifact_meta') or payload.get('bundle_meta') or {})
    lineage = {
        'report_id': str(report.get('report_id') or '').strip(),
        'strategy_id': str(report.get('strategy_id') or '').strip(),
        'strategy_version': str(report.get('strategy_version') or 'v1').strip() or 'v1',
        'prompt_version': str(report.get('prompt_version') or 'v1').strip() or 'v1',
        'adapter_version': str(report.get('adapter_version') or 'v1').strip() or 'v1',
        'runtime_version': str(report.get('runtime_version') or 'v1').strip() or 'v1',
    }
    return {
        'lineage': lineage,
        'artifact_meta': artifact_meta,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Rebuild minimal analysis lineage context from a stored report payload.')
    parser.add_argument('report_path', help='path to stored report JSON')
    args = parser.parse_args(argv)

    payload = replay_analysis_run(report_path=Path(args.report_path))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
