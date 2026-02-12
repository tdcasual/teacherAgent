from pathlib import Path


def test_ci_contains_quality_jobs() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "backend-quality" in text
    assert "frontend-quality" in text
