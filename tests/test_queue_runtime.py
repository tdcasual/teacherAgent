class StubBackend:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def test_start_runtime_calls_require_redis_when_not_pytest():
    from services.api import queue_runtime

    backend = StubBackend()
    called = {"redis": 0}

    def require_redis():
        called["redis"] += 1

    queue_runtime.start_runtime(backend=backend, require_redis=require_redis, is_pytest=False)

    assert backend.started == 1
    assert called["redis"] == 1


def test_start_runtime_skips_require_redis_in_pytest():
    from services.api import queue_runtime

    backend = StubBackend()
    called = {"redis": 0}

    def require_redis():
        called["redis"] += 1

    queue_runtime.start_runtime(backend=backend, require_redis=require_redis, is_pytest=True)

    assert backend.started == 1
    assert called["redis"] == 0


def test_stop_runtime_calls_backend_stop():
    from services.api import queue_runtime

    backend = StubBackend()
    queue_runtime.stop_runtime(backend=backend)

    assert backend.stopped == 1
