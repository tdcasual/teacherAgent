from __future__ import annotations

from pathlib import Path

from services.api.analysis_metadata_repository import FileBackedAnalysisMetadataRepository



def test_file_backed_metadata_repository_roundtrip_json_and_jsonl(tmp_path: Path) -> None:
    repo = FileBackedAnalysisMetadataRepository(base_dir=tmp_path)

    repo.write_json('reports/report_1.json', {'report_id': 'report_1', 'status': 'analysis_ready'})
    repo.append_jsonl('review/events.jsonl', {'event': 'enqueue', 'item_id': 'rvw_1'})
    repo.append_jsonl('review/events.jsonl', {'event': 'claim', 'item_id': 'rvw_1'})

    assert repo.read_json('reports/report_1.json')['status'] == 'analysis_ready'
    assert [item['event'] for item in repo.read_jsonl('review/events.jsonl')] == ['enqueue', 'claim']
