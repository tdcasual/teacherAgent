from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_catalog_service import (
    effective_assignment_kind,
    effective_content_source,
)


def test_effective_content_source_defaults() -> None:
    assert effective_content_source({}) == "upload"
    assert effective_content_source({"content_source": "bank"}) == "bank"
    assert effective_content_source({"content_source": "ai"}) == "ai"
    assert effective_content_source({"source_files": ["a.pdf"]}) == "upload"
    assert effective_content_source({"mode": "kp"}) == "ai"
    assert effective_content_source({"mode": "hybrid"}) == "ai"
    assert effective_content_source({"mode": "upload"}) == "upload"
    with TemporaryDirectory() as td:
        folder = Path(td)
        (folder / "generated_stems").mkdir()
        assert effective_content_source({}, folder=folder) == "ai"
    assert effective_assignment_kind({}) == "problem_set"
    assert effective_assignment_kind({"assignment_kind": "scenario"}) == "scenario"
    assert effective_assignment_kind({"assignment_kind": "exam"}) == "problem_set"
