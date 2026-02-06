import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class SkillsEndpointTest(unittest.TestCase):
    def test_skills_endpoint_returns_agent_config(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            client = TestClient(app_mod.app)

            res = client.get("/skills")
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertIn("skills", payload)
            skills = payload["skills"]
            self.assertIsInstance(skills, list)
            self.assertGreaterEqual(len(skills), 1)

            by_id = {s.get("id"): s for s in skills}
            self.assertIn("physics-core-examples", by_id)
            core = by_id["physics-core-examples"]
            self.assertEqual(core.get("schema_version"), 2)
            self.assertIn("agent", core)
            self.assertIn("prompt_modules", core["agent"])
            self.assertIn("tools", core["agent"])
            self.assertIn("budgets", core["agent"])


if __name__ == "__main__":
    unittest.main()

