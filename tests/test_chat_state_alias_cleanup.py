import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ChatStateAliasCleanupTest(unittest.TestCase):
    def test_request_index_aliases_removed_from_module_scope(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            self.assertTrue(hasattr(app_mod, "CHAT_IDEMPOTENCY_STATE"))
            self.assertFalse(hasattr(app_mod, "CHAT_REQUEST_MAP_DIR"))
            self.assertFalse(hasattr(app_mod, "CHAT_REQUEST_INDEX_PATH"))
            self.assertFalse(hasattr(app_mod, "CHAT_REQUEST_INDEX_LOCK"))


if __name__ == "__main__":
    unittest.main()
