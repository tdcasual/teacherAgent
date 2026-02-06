import importlib
import json
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["TEACHER_MEMORY_AUTO_APPLY_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_DECAY_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_TTL_DAYS_MEMORY"] = "2"
    os.environ["TEACHER_MEMORY_SEARCH_FILTER_EXPIRED"] = "1"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class TeacherMemoryInsightsTest(unittest.TestCase):
    def test_search_filters_expired_mem0_matches_and_reports_insights(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = app_mod.resolve_teacher_id("teacher")

            expired = app_mod.teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="旧偏好",
                content="输出要非常详细并包含长篇推导。",
            )
            active = app_mod.teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="新偏好",
                content="输出先结论再行动项。",
            )
            expired_id = str(expired.get("proposal_id") or "")
            active_id = str(active.get("proposal_id") or "")

            path = app_mod._teacher_proposal_path(teacher_id, expired_id)
            rec = json.loads(path.read_text(encoding="utf-8"))
            old_ts = (datetime.now() - timedelta(days=6)).isoformat(timespec="seconds")
            rec["created_at"] = old_ts
            rec["applied_at"] = old_ts
            rec["expires_at"] = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
            app_mod._atomic_write_json(path, rec)

            with patch(
                "services.api.mem0_adapter.teacher_mem0_search",
                return_value={
                    "ok": True,
                    "matches": [
                        {"source": "mem0", "proposal_id": expired_id, "snippet": "old"},
                        {"source": "mem0", "proposal_id": active_id, "snippet": "new"},
                    ],
                },
            ):
                res = app_mod.teacher_memory_search(teacher_id, "输出", limit=5)
            self.assertEqual(res.get("mode"), "mem0")
            matches = res.get("matches") or []
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].get("proposal_id"), active_id)

            insights = app_mod.teacher_memory_insights(teacher_id, days=14)
            self.assertTrue(insights.get("ok"))
            summary = insights.get("summary") or {}
            retrieval = insights.get("retrieval") or {}
            self.assertGreaterEqual(int(summary.get("expired_total") or 0), 1)
            self.assertGreaterEqual(int(retrieval.get("search_calls") or 0), 1)
            self.assertGreaterEqual(int(retrieval.get("search_hit_calls") or 0), 1)

    def test_insights_endpoint_available(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/memory/insights")
                self.assertEqual(res.status_code, 200)
                body = res.json()
                self.assertTrue(body.get("ok"))
                self.assertIn("summary", body)
                self.assertIn("retrieval", body)


if __name__ == "__main__":
    unittest.main()
