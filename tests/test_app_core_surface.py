import services.api.app as app_mod


def test_app_core_does_not_export_worker_wrappers():
    assert not hasattr(app_mod, "start_chat_worker")
    assert not hasattr(app_mod, "start_upload_worker")
    assert not hasattr(app_mod, "start_exam_upload_worker")
