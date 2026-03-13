from __future__ import annotations

from pathlib import Path

from services.api.analysis_metadata_repository import FileBackedAnalysisMetadataRepository
from services.api.review_feedback_store import read_review_feedback_rows
from services.api.review_queue_service import (
    ReviewQueueDeps,
    claim_review_item,
    enqueue_review_item,
    list_review_items,
    reject_review_item,
    resolve_review_item,
)


def _deps(tmp_path: Path) -> ReviewQueueDeps:
    return ReviewQueueDeps(
        metadata_repo=FileBackedAnalysisMetadataRepository(base_dir=tmp_path),
        queue_log='review/events.jsonl',
        review_feedback_log=tmp_path / 'analysis' / 'review_feedback.jsonl',
        now_iso=lambda: '2026-03-07T10:00:00',
    )



def test_review_queue_tracks_status_transitions_and_filters(tmp_path: Path) -> None:
    deps = _deps(tmp_path)

    queued = enqueue_review_item(
        domain='survey',
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
        target_type='report',
        target_id='report_1',
        deps=deps,
    )
    claim_review_item(item_id=queued['item_id'], reviewer_id='reviewer_1', deps=deps)
    resolve_review_item(item_id=queued['item_id'], reviewer_id='reviewer_1', resolution_note='verified', deps=deps)

    other = enqueue_review_item(
        domain='class_report',
        report_id='report_9',
        teacher_id='teacher_1',
        reason='needs_review',
        confidence=0.66,
        target_type='class',
        target_id='class_1',
        deps=deps,
    )
    reject_review_item(item_id=other['item_id'], reviewer_id='reviewer_2', resolution_note='invalid artifact', deps=deps)

    resolved = list_review_items(teacher_id='teacher_1', domain='survey', status='resolved', deps=deps)
    rejected = list_review_items(teacher_id='teacher_1', domain='class_report', status='rejected', deps=deps)

    assert resolved['items'][0]['item_id'] == queued['item_id']
    assert resolved['items'][0]['status'] == 'resolved'
    assert resolved['items'][0]['reviewer_id'] == 'reviewer_1'
    assert rejected['items'][0]['item_id'] == other['item_id']
    assert rejected['items'][0]['status'] == 'rejected'
    assert rejected['items'][0]['resolution_note'] == 'invalid artifact'



def test_reject_review_item_appends_feedback_row(tmp_path: Path) -> None:
    deps = _deps(tmp_path)

    queued = enqueue_review_item(
        domain='survey',
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
        target_type='report',
        target_id='report_1',
        strategy_id='survey.teacher.report',
        deps=deps,
    )
    reject_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_1',
        resolution_note='invalid executive summary',
        deps=deps,
    )

    rows = read_review_feedback_rows(tmp_path / 'analysis' / 'review_feedback.jsonl')
    assert rows[-1]['report_id'] == 'report_1'
    assert rows[-1]['domain'] == 'survey'
    assert rows[-1]['strategy_id'] == 'survey.teacher.report'
    assert rows[-1]['disposition'] == 'rejected'
    assert rows[-1]['reason_code'] == 'low_confidence'


def test_claim_review_item_does_not_append_feedback_row(tmp_path: Path) -> None:
    deps = _deps(tmp_path)

    queued = enqueue_review_item(
        domain='survey',
        report_id='report_2',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.55,
        target_type='report',
        target_id='report_2',
        deps=deps,
    )
    claim_review_item(item_id=queued['item_id'], reviewer_id='reviewer_1', deps=deps)

    rows = read_review_feedback_rows(tmp_path / 'analysis' / 'review_feedback.jsonl')
    assert rows == []
