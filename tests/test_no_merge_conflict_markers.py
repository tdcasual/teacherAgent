from __future__ import annotations

import re
from pathlib import Path

_SCAN_ROOTS = [
    Path("services"),
    Path("frontend"),
    Path("tests"),
    Path("docs"),
    Path(".github"),
]
_CONFLICT_LINE = re.compile(r"^(<<<<<<< .+|=======|>>>>>>> .+)$")
_SKIP_PARTS = {
    'node_modules',
    'dist',
    'dist-student',
    'dist-teacher',
    'playwright-report',
    'test-results',
}


def test_repository_has_no_merge_conflict_markers() -> None:
    offenders: list[str] = []
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith('.') and part not in {'.github'} for part in path.parts):
                continue
            if any(part in _SKIP_PARTS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(_CONFLICT_LINE.fullmatch(line) for line in text.splitlines()):
                offenders.append(path.as_posix())
    assert not offenders, f"merge conflict markers found in: {offenders}"
