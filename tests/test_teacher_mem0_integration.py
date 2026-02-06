import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    # Default: keep mem0 disabled unless a test enables it explicitly.
    os.environ.pop("TEACHER_MEM0_ENABLED", None)
    os.environ.pop("TEACHER_MEM0_WRITE_ENABLED", None)
    os.environ.pop("TEACHER_MEM0_INDEX_DAILY", None)
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class TeacherMem0IntegrationTest(unittest.TestCase):
    def test_teacher_memory_search_keyword_fallback(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = "teacher"

            # Seed a keyword into curated memory.
            mem_path = app_mod.teacher_workspace_file(teacher_id, "MEMORY.md")
            mem_path.parent.mkdir(parents=True, exist_ok=True)
            mem_path.write_text("# Long-Term Memory\n\n偏好：输出要简洁\n", encoding="utf-8")

            res = app_mod.teacher_memory_search(teacher_id, "简洁", limit=5)
            self.assertEqual(res.get("mode"), "keyword")
            self.assertTrue(res.get("matches"))
            self.assertEqual(res["matches"][0].get("source"), "keyword")

    def test_teacher_memory_search_prefers_mem0_when_available(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = "teacher"

            with patch(
                "services.api.mem0_adapter.teacher_mem0_search",
                return_value={"ok": True, "matches": [{"source": "mem0", "snippet": "hello", "score": 0.9}]},
            ):
                res = app_mod.teacher_memory_search(teacher_id, "anything", limit=5)
            self.assertEqual(res.get("mode"), "mem0")
            self.assertEqual(res.get("matches")[0].get("source"), "mem0")

    def test_teacher_memory_apply_indexes_to_mem0_best_effort(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = "teacher"

            prop = app_mod.teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="T",
                content="以后输出都要简洁。",
            )
            proposal_id = prop["proposal_id"]

            with patch(
                "services.api.mem0_adapter.teacher_mem0_index_entry",
                return_value={"ok": True, "chunks": 1},
            ) as mock_index:
                res = app_mod.teacher_memory_apply(teacher_id, proposal_id, approve=True)

            self.assertEqual(res.get("status"), "applied")
            self.assertIn("mem0", res)
            self.assertTrue(mock_index.called)
            args, kwargs = mock_index.call_args
            self.assertEqual(args[0], teacher_id)
            self.assertIn("以后输出都要简洁", args[1])
            md = kwargs.get("metadata") or {}
            self.assertEqual(md.get("proposal_id"), proposal_id)
            self.assertEqual(md.get("target"), "MEMORY")


if __name__ == "__main__":
    unittest.main()

