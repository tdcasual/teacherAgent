from services.api.observability import ObservabilityStore


def test_observability_store_snapshot_fields() -> None:
    store = ObservabilityStore()
    store.inc_inflight()
    store.record(method="GET", route="/health", status_code=200, latency_sec=0.08)
    store.record(method="POST", route="/chat/start", status_code=503, latency_sec=1.2)
    store.dec_inflight()

    snap = store.snapshot()
    assert snap["http_requests_total"] == 2
    assert snap["http_5xx_total"] == 1
    assert 0.0 <= snap["http_error_rate"] <= 1.0
    assert snap["http_latency_sec"]["sample_count"] == 2
    assert "GET /health" in snap["requests_by_route"]
    assert "POST /chat/start" in snap["errors_by_route"]
    assert "latency_p95_ok" in snap["slo"]
    assert "error_rate_ok" in snap["slo"]
