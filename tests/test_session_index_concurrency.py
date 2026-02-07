import importlib
import os
import random
import threading
import time
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


class SessionIndexConcurrencyTest(unittest.TestCase):
    def test_teacher_session_index_does_not_drop_updates_under_concurrency(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = "teacher_demo"
            rng = random.Random(7)

            for i in range(80):
                sid_a = f"session_{i}_a"
                sid_b = f"session_{i}_b"
                errors = []

                def writer(session_id: str, delay: float):
                    try:
                        time.sleep(delay)
                        app_mod.update_teacher_session_index(
                            teacher_id,
                            session_id,
                            preview=session_id,
                            message_increment=1,
                        )
                    except Exception as exc:  # pragma: no cover - asserted below
                        errors.append(exc)

                t1 = threading.Thread(target=writer, args=(sid_a, rng.random() * 0.002))
                t2 = threading.Thread(target=writer, args=(sid_b, rng.random() * 0.002))
                t1.start()
                t2.start()
                t1.join()
                t2.join()

                self.assertEqual(errors, [])
                items = app_mod.load_teacher_sessions_index(teacher_id)
                ids = {str(item.get("session_id") or "") for item in items}
                self.assertIn(sid_a, ids)
                self.assertIn(sid_b, ids)


if __name__ == "__main__":
    unittest.main()
