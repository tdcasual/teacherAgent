def test_settings_defaults_and_truthy(monkeypatch):
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api import settings

    assert settings.job_queue_backend() == ""
    assert settings.truthy("1") is True


def test_settings_defaults_and_conversions(monkeypatch):
    monkeypatch.delenv("CHAT_WORKER_POOL_SIZE", raising=False)
    monkeypatch.delenv("TEACHER_MEMORY_AUTO_ENABLED", raising=False)
    monkeypatch.delenv("GRADE_COUNT_CONF_THRESHOLD", raising=False)
    monkeypatch.delenv("DEFAULT_TEACHER_ID", raising=False)
    from services.api import settings

    assert settings.chat_worker_pool_size() == 4
    assert settings.teacher_memory_auto_enabled() is True
    assert settings.grade_count_conf_threshold() == 0.6
    assert settings.default_teacher_id() == "teacher"
