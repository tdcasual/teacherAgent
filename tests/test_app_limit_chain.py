import pytest

from services.api.chat_limits import acquire_limiters


class _RecorderSemaphore:
    def __init__(self, name: str, log: list[str]):
        self._name = name
        self._log = log

    def acquire(self):
        self._log.append(f"acquire:{self._name}")
        return True

    def release(self):
        self._log.append(f"release:{self._name}")
        return True


def test_limit_accepts_multiple_limiters_in_order():
    log: list[str] = []
    a = _RecorderSemaphore("a", log)
    b = _RecorderSemaphore("b", log)
    c = _RecorderSemaphore("c", log)

    try:
        with acquire_limiters((a, b, c)):
            log.append("inside")
    except Exception as exc:
        pytest.fail(f"acquire_limiters should accept multiple limiters (tuple/list): {exc}")

    assert log == [
        "acquire:a",
        "acquire:b",
        "acquire:c",
        "inside",
        "release:c",
        "release:b",
        "release:a",
    ]
