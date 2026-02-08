def test_settings_defaults_and_truthy(monkeypatch):
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api import settings

    assert settings.job_queue_backend() == ""
    assert settings.truthy("1") is True
