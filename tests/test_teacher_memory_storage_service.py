from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.paths import safe_fs_id
from services.api.teacher_memory_storage_service import (
    TeacherMemoryStorageDeps,
    teacher_memory_delete_proposal,
    teacher_memory_list_proposals,
)


class TeacherMemoryStorageServiceTest(unittest.TestCase):
    def _deps(self, root: Path) -> TeacherMemoryStorageDeps:
        return TeacherMemoryStorageDeps(
            ensure_teacher_workspace=lambda teacher_id: (root / teacher_id).mkdir(parents=True, exist_ok=True),
            teacher_workspace_dir=lambda teacher_id: root / teacher_id,
            safe_fs_id=safe_fs_id,
            atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8'),
            now_iso=lambda: '2026-03-12T11:00:00',
            teacher_daily_memory_path=lambda teacher_id: root / teacher_id / 'daily.md',
            teacher_workspace_file=lambda teacher_id, name: root / teacher_id / name,
            log_event=lambda teacher_id, event, payload: None,
        )

    def test_list_proposals_filters_status_and_infers_provenance(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            teacher_dir = root / 'teacher_1' / 'proposals'
            teacher_dir.mkdir(parents=True, exist_ok=True)
            (teacher_dir / 'p1.json').write_text(
                json.dumps({'proposal_id': 'p1', 'status': 'applied', 'source': 'auto_intent'}, ensure_ascii=False),
                encoding='utf-8',
            )
            (teacher_dir / 'p2.json').write_text(
                json.dumps({'proposal_id': 'p2', 'status': 'deleted', 'source': 'manual'}, ensure_ascii=False),
                encoding='utf-8',
            )

            result = teacher_memory_list_proposals('teacher_1', deps=self._deps(root), status='applied', limit=10)

            self.assertTrue(result['ok'])
            self.assertEqual([item['proposal_id'] for item in result['proposals']], ['p1'])
            self.assertEqual(result['proposals'][0]['provenance']['origin'], 'session_context')

    def test_delete_applied_proposal_marks_deleted_and_removes_entry(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            teacher_id = 'teacher_2'
            memory_path = root / teacher_id / 'MEMORY.md'
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text(
                '## 偏好\n- ts: 2026-03-12T10:00:00\n- entry_id: p1\n- source: manual\n\n以后输出三段式\n',
                encoding='utf-8',
            )
            proposal_dir = root / teacher_id / 'proposals'
            proposal_dir.mkdir(parents=True, exist_ok=True)
            proposal_path = proposal_dir / f"{safe_fs_id('p1', prefix='proposal')}.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        'proposal_id': 'p1',
                        'status': 'applied',
                        'target': 'MEMORY',
                        'source': 'manual',
                        'applied_to': str(memory_path),
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )

            result = teacher_memory_delete_proposal(teacher_id, 'p1', deps=deps)

            self.assertTrue(result['ok'])
            self.assertEqual(result['status'], 'deleted')
            self.assertNotIn('entry_id: p1', memory_path.read_text(encoding='utf-8'))
            record = json.loads(proposal_path.read_text(encoding='utf-8'))
            self.assertEqual(record['deleted_from_status'], 'applied')
            self.assertEqual(record['status'], 'deleted')


if __name__ == '__main__':
    unittest.main()
