from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes import survey_routes



def test_survey_webhook_route_calls_application_layer(monkeypatch) -> None:
    class _Core:
        pass

    called = {}

    async def _fake_ingest(*, provider, payload, signature, deps):
        called["provider"] = provider
        called["payload"] = payload
        called["signature"] = signature
        called["deps"] = deps
        return {"ok": True, "job_id": "survey_job_1", "status": "queued"}

    monkeypatch.setattr(survey_routes.survey_application, "survey_webhook_ingest", _fake_ingest)
    monkeypatch.setattr(survey_routes.survey_deps, "build_survey_application_deps", lambda _core: object())

    app = FastAPI()
    app.include_router(survey_routes.build_router(_Core()))
    with TestClient(app) as client:
        res = client.post(
            "/webhooks/surveys/provider",
            json={"teacher_id": "teacher_1", "class_name": "高二2403班"},
            headers={"X-Survey-Signature": "sha256=test"},
        )

    assert res.status_code == 200
    assert called["provider"] == "provider"
    assert called["payload"]["teacher_id"] == "teacher_1"
    assert called["signature"] == "sha256=test"



def test_survey_report_list_route_calls_application_layer(monkeypatch) -> None:
    class _Core:
        pass

    called = {}

    async def _fake_list(*, teacher_id, status, deps):
        called["teacher_id"] = teacher_id
        called["status"] = status
        return {"ok": True, "reports": []}

    monkeypatch.setattr(survey_routes.survey_application, "list_survey_reports", _fake_list)
    monkeypatch.setattr(survey_routes.survey_deps, "build_survey_application_deps", lambda _core: object())

    app = FastAPI()
    app.include_router(survey_routes.build_router(_Core()))
    with TestClient(app) as client:
        res = client.get("/teacher/surveys/reports", params={"teacher_id": "teacher_1", "status": "analysis_ready"})

    assert res.status_code == 200
    assert called["teacher_id"] == "teacher_1"
    assert called["status"] == "analysis_ready"
