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


def test_load_settings_and_build_paths_are_isolated(tmp_path):
    from services.api.config import build_paths
    from services.api.runtime_settings import load_settings

    app_root = tmp_path / "root"
    app_root.mkdir(parents=True)

    settings_a = load_settings(
        {
            "DATA_DIR": str(tmp_path / "data_a"),
            "UPLOADS_DIR": str(tmp_path / "uploads_a"),
        }
    )
    settings_b = load_settings(
        {
            "DATA_DIR": str(tmp_path / "data_b"),
            "UPLOADS_DIR": str(tmp_path / "uploads_b"),
        }
    )

    paths_a = build_paths(settings_a, app_root=app_root)
    paths_b = build_paths(settings_b, app_root=app_root)

    assert paths_a.DATA_DIR == tmp_path / "data_a"
    assert paths_b.DATA_DIR == tmp_path / "data_b"
    assert paths_a.UPLOADS_DIR == tmp_path / "uploads_a"
    assert paths_b.UPLOADS_DIR == tmp_path / "uploads_b"
    assert paths_a.DATA_DIR != paths_b.DATA_DIR
    assert paths_a.UPLOADS_DIR != paths_b.UPLOADS_DIR
