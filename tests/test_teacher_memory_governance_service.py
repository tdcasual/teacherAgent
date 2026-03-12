from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_governance_service import (
    TeacherMemoryGovernanceDeps,
    teacher_memory_auto_quota_reached,
    teacher_memory_find_conflicting_applied,
    teacher_memory_find_duplicate,
    teacher_memory_mark_superseded,
)


class TeacherMemoryGovernanceServiceTest(unittest.TestCase):
    def _deps(self, root: Path) -> TeacherMemoryGovernanceDeps:
        def proposal_path(teacher_id: str, proposal_id: str) -> Path:
            return root / teacher_id / 'proposals' / f'{proposal_id}.json'

        def recent_proposals(teacher_id: str, limit: int):
            proposal_dir = root / teacher_id / 'proposals'
            if not proposal_dir.exists():
                return []
            out = []
            for path in sorted(proposal_dir.glob('*.json')):
                out.append(json.loads(path.read_text(encoding='utf-8')))
                if len(out) >= limit:
                    break
            return out

        return TeacherMemoryGovernanceDeps(
            recent_proposals=recent_proposals,
            norm_text=lambda text: re.sub(r'\s+', '', str(text or '')).lower(),
            conflicts=lambda new_text, old_text: '三段式' in str(new_text) and '两段式' in str(old_text),
            now_iso=lambda: '2026-03-12T10:00:00',
            proposal_path=proposal_path,
            atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8'),
            auto_max_proposals_per_day=2,
        )

    def test_find_conflicting_applied_memory_only(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            proposal_dir = root / 'teacher_1' / 'proposals'
            proposal_dir.mkdir(parents=True, exist_ok=True)
            (proposal_dir / 'old.json').write_text(
                json.dumps({'proposal_id': 'old', 'status': 'applied', 'target': 'MEMORY', 'content': '以后输出两段式'}, ensure_ascii=False),
                encoding='utf-8',
            )
            (proposal_dir / 'daily.json').write_text(
                json.dumps({'proposal_id': 'daily', 'status': 'applied', 'target': 'DAILY', 'content': '今天提醒我'}, ensure_ascii=False),
                encoding='utf-8',
            )
            deps = self._deps(root)

            conflicts = teacher_memory_find_conflicting_applied(
                'teacher_1',
                proposal_id='new',
                target='MEMORY',
                content='以后输出三段式',
                deps=deps,
            )
            self.assertEqual(conflicts, ['old'])

    def test_mark_superseded_updates_records(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            proposal_dir = root / 'teacher_1' / 'proposals'
            proposal_dir.mkdir(parents=True, exist_ok=True)
            path = proposal_dir / 'old.json'
            path.write_text(json.dumps({'proposal_id': 'old', 'status': 'applied'}, ensure_ascii=False), encoding='utf-8')
            deps = self._deps(root)

            teacher_memory_mark_superseded('teacher_1', ['old'], 'new', deps=deps)

            record = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(record['superseded_by'], 'new')
            self.assertEqual(record['superseded_at'], '2026-03-12T10:00:00')

    def test_auto_quota_reached_counts_today_auto_records(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            proposal_dir = root / 'teacher_2' / 'proposals'
            proposal_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(2):
                (proposal_dir / f'p{idx}.json').write_text(
                    json.dumps(
                        {
                            'proposal_id': f'p{idx}',
                            'status': 'applied',
                            'source': 'auto_intent',
                            'created_at': f'2026-03-12T09:0{idx}:00',
                        },
                        ensure_ascii=False,
                    ),
                    encoding='utf-8',
                )
            deps = self._deps(root)
            self.assertTrue(teacher_memory_auto_quota_reached('teacher_2', deps=deps))

    def test_find_duplicate_by_key_or_normalized_content(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            proposal_dir = root / 'teacher_3' / 'proposals'
            proposal_dir.mkdir(parents=True, exist_ok=True)
            (proposal_dir / 'p1.json').write_text(
                json.dumps(
                    {
                        'proposal_id': 'p1',
                        'status': 'proposed',
                        'target': 'MEMORY',
                        'content': '以后 输出 三段式',
                        'dedupe_key': 'stable-1',
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )
            deps = self._deps(root)

            by_key = teacher_memory_find_duplicate(
                'teacher_3',
                target='MEMORY',
                content='其他内容',
                dedupe_key='stable-1',
                deps=deps,
            )
            self.assertEqual(by_key['proposal_id'], 'p1')

            by_content = teacher_memory_find_duplicate(
                'teacher_3',
                target='MEMORY',
                content='以后输出三段式',
                dedupe_key='stable-2',
                deps=deps,
            )
            self.assertEqual(by_content['proposal_id'], 'p1')


if __name__ == '__main__':
    unittest.main()
