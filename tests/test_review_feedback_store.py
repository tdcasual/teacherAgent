from __future__ import annotations

from pathlib import Path

from services.api.review_feedback_store import append_review_feedback_row, read_review_feedback_rows


def test_review_feedback_store_round_trips_rows(tmp_path: Path) -> None:
    path = tmp_path / 'analysis' / 'review_feedback.jsonl'
    append_review_feedback_row(path, {'report_id': 'report_1', 'disposition': 'rejected'})
    append_review_feedback_row(path, {'report_id': 'report_2', 'disposition': 'resolved'})

    rows = read_review_feedback_rows(path)
    assert rows == [
        {'report_id': 'report_1', 'disposition': 'rejected'},
        {'report_id': 'report_2', 'disposition': 'resolved'},
    ]
