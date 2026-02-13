import re
from pathlib import Path


WORKFLOWS = [
    ".github/workflows/ci.yml",
    ".github/workflows/docker.yml",
    ".github/workflows/teacher-e2e.yml",
    ".github/workflows/mobile-session-menu-e2e.yml",
]


def test_workflows_pin_actions_to_commit_sha() -> None:
    pattern = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)")
    unpinned: list[str] = []
    for path in WORKFLOWS:
        text = Path(path).read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            action, ref = match.group(1), match.group(2)
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                unpinned.append(f"{path}:{action}@{ref}")
    assert not unpinned, f"unpinned actions: {unpinned}"
