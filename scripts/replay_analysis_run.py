from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from services.api.strategies.planner import build_replay_request


def replay_analysis_run(*, report_path: Path) -> Dict[str, Any]:
    payload = json.loads(Path(report_path).read_text(encoding='utf-8'))
    report = dict(payload.get('report') or payload)
    analysis_artifact = dict(payload.get('analysis_artifact') or {})
    artifact_meta = dict(payload.get('artifact_meta') or payload.get('bundle_meta') or {})
    replay_context = dict(payload.get('replay_context') or {})
    artifact_payload = dict(replay_context.get('artifact_payload') or payload.get('artifact_payload') or {})
    if not artifact_payload:
        raise ValueError('artifact payload required for replay')
    replay_request = build_replay_request(
        domain=str(report.get('analysis_type') or replay_context.get('domain') or '').strip(),
        report=report,
        artifact_payload=artifact_payload,
        artifact_meta=artifact_meta,
        analysis_artifact=analysis_artifact,
    )
    return {
        'lineage': dict(replay_request.get('lineage') or {}),
        'artifact_meta': artifact_meta,
        'replay_request': replay_request,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Rebuild a replayable analysis request from a stored report payload.')
    parser.add_argument('report_path', help='path to stored report JSON')
    args = parser.parse_args(argv)

    payload = replay_analysis_run(report_path=Path(args.report_path))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
