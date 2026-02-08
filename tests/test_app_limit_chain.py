import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


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
    with TemporaryDirectory() as td:
        app_mod = _load_app(Path(td))
        log: list[str] = []
        a = _RecorderSemaphore("a", log)
        b = _RecorderSemaphore("b", log)
        c = _RecorderSemaphore("c", log)

        try:
            with app_mod._limit((a, b, c)):
                log.append("inside")
        except Exception as exc:
            pytest.fail(f"_limit should accept multiple limiters (tuple/list): {exc}")

        assert log == [
            "acquire:a",
            "acquire:b",
            "acquire:c",
            "inside",
            "release:c",
            "release:b",
            "release:a",
        ]

