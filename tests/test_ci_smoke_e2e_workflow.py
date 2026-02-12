from pathlib import Path


def test_ci_has_smoke_e2e_gate() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "smoke-e2e" in text
    assert "Run smoke E2E" in text
    assert "npm run e2e:smoke" in text
