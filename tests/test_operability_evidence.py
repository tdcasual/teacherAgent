import json
from pathlib import Path


def test_slo_document_exists_with_required_sections() -> None:
    path = Path("docs/operations/slo-and-observability.md")
    assert path.exists(), "Missing SLO/observability baseline document."
    text = path.read_text(encoding="utf-8")
    assert "SLO-API-Availability" in text
    assert "SLO-API-Latency-P95" in text
    assert "/ops/metrics" in text
    assert "/ops/slo" in text
    assert "backend-slo-overview.json" in text


def test_dashboard_artifact_is_valid_and_complete() -> None:
    path = Path("ops/dashboards/backend-slo-overview.json")
    assert path.exists(), "Missing backend SLO dashboard artifact."
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("title") == "Backend SLO Overview"
    panels = payload.get("panels")
    assert isinstance(panels, list) and len(panels) >= 4
    titles = {str(p.get("title") or "") for p in panels if isinstance(p, dict)}
    assert "HTTP Requests Total" in titles
    assert "HTTP Error Rate" in titles
    assert "HTTP Latency P95 (sec)" in titles
    assert "SLO Status" in titles
