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
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class TeacherProviderRegistryEndpointsTest(unittest.TestCase):
    def test_provider_registry_crud_flow(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)

            created = client.post(
                "/teacher/provider-registry/providers",
                json={
                    "teacher_id": "teacher_alpha",
                    "provider_id": "tprv_alpha_proxy",
                    "display_name": "Alpha Proxy",
                    "base_url": "https://proxy.alpha.example/v1",
                    "api_key": "sk-alpha-12345678",
                    "default_model": "gpt-4.1-mini",
                    "enabled": True,
                },
            )
            self.assertEqual(created.status_code, 200)
            self.assertTrue((created.json().get("provider") or {}).get("api_key_masked"))

            overview = client.get("/teacher/provider-registry", params={"teacher_id": "teacher_alpha"})
            self.assertEqual(overview.status_code, 200)
            providers = overview.json().get("providers") or []
            self.assertEqual(len(providers), 1)
            self.assertEqual((providers[0] or {}).get("provider"), "tprv_alpha_proxy")

            updated = client.patch(
                "/teacher/provider-registry/providers/tprv_alpha_proxy",
                json={"teacher_id": "teacher_alpha", "default_model": "gpt-4.1-nano"},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual((updated.json().get("provider") or {}).get("default_model"), "gpt-4.1-nano")

            deleted = client.request(
                "DELETE",
                "/teacher/provider-registry/providers/tprv_alpha_proxy",
                json={"teacher_id": "teacher_alpha"},
            )
            self.assertEqual(deleted.status_code, 200)

            overview_after = client.get("/teacher/provider-registry", params={"teacher_id": "teacher_alpha"})
            self.assertEqual(overview_after.status_code, 200)
            providers_after = overview_after.json().get("providers") or []
            self.assertEqual(len(providers_after), 1)
            self.assertFalse((providers_after[0] or {}).get("enabled"))


if __name__ == "__main__":
    unittest.main()
