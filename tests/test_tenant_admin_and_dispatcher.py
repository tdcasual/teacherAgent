import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def _load_app(tmp_dir: Path, *, admin_key: str):
    os.environ["TENANT_ADMIN_KEY"] = admin_key
    os.environ["TENANT_DB_PATH"] = str(tmp_dir / "tenants.sqlite3")
    os.environ["DIAG_LOG"] = "0"

    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def test_admin_requires_key():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        res = client.put(
            "/admin/tenants/t1",
            json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")},
        )
        assert res.status_code == 401


def test_create_tenant_and_dispatch_health():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        res = client.put(
            "/admin/tenants/t1",
            headers={"X-Admin-Key": "k"},
            json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")},
        )
        assert res.status_code == 200

        res2 = client.get("/t/t1/health")
        assert res2.status_code == 200
        assert res2.json().get("status") == "ok"

        # Tenant app should expose the same core API surface as the legacy app.
        res3 = client.get("/t/t1/skills")
        assert res3.status_code == 200
        payload = res3.json()
        assert isinstance(payload, dict)
        assert isinstance(payload.get("skills"), list)


def test_tenant_data_dir_isolated_for_exams_list():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        t1_data = tmp / "t1_data"
        t2_data = tmp / "t2_data"
        (t1_data / "exams" / "EX_T1").mkdir(parents=True)
        (t2_data / "exams" / "EX_T2").mkdir(parents=True)
        (t1_data / "exams" / "EX_T1" / "manifest.json").write_text('{"exam_id":"EX_T1"}', encoding="utf-8")
        (t2_data / "exams" / "EX_T2" / "manifest.json").write_text('{"exam_id":"EX_T2"}', encoding="utf-8")

        client.put(
            "/admin/tenants/t1",
            headers={"X-Admin-Key": "k"},
            json={"data_dir": str(t1_data), "uploads_dir": str(tmp / "t1_up")},
        )
        client.put(
            "/admin/tenants/t2",
            headers={"X-Admin-Key": "k"},
            json={"data_dir": str(t2_data), "uploads_dir": str(tmp / "t2_up")},
        )

        r1 = client.get("/t/t1/exams")
        r2 = client.get("/t/t2/exams")
        assert r1.status_code == 200
        assert r2.status_code == 200

        assert any(x.get("exam_id") == "EX_T1" for x in (r1.json().get("exams") or []))
        assert not any(x.get("exam_id") == "EX_T2" for x in (r1.json().get("exams") or []))
        assert any(x.get("exam_id") == "EX_T2" for x in (r2.json().get("exams") or []))


def test_tenant_unload_stops_chat_workers():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        os.environ["CHAT_WORKER_POOL_SIZE"] = "1"
        app_mod = _load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        res = client.put(
            "/admin/tenants/t1",
            headers={"X-Admin-Key": "k"},
            json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")},
        )
        assert res.status_code == 200

        handle = getattr(app_mod, "_TENANT_REGISTRY").get_loaded("t1")
        assert handle is not None
        module = handle.instance.module
        threads = list(getattr(module, "CHAT_WORKER_THREADS", []) or [])
        assert threads, "expected chat worker threads to be started for tenant"
        assert any(t.is_alive() for t in threads)

        res2 = client.delete("/admin/tenants/t1", headers={"X-Admin-Key": "k"})
        assert res2.status_code == 200

        # Stop should be best-effort quick; allow a short grace.
        for _ in range(80):
            if all(not t.is_alive() for t in threads):
                break
            import time

            time.sleep(0.025)
        assert all(not t.is_alive() for t in threads)
