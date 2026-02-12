from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List

_LATENCY_BUCKETS = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
_MAX_RECENT_SAMPLES = 5000


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * max(0.0, min(1.0, p))
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(ordered[lo])
    frac = idx - lo
    return float(ordered[lo]) * (1.0 - frac) + float(ordered[hi]) * frac


def _bucket_key(value: float) -> str:
    for bucket in _LATENCY_BUCKETS:
        if value <= bucket:
            return f"le_{bucket:.2f}s"
    return "gt_5.00s"


@dataclass(frozen=True)
class RequestSample:
    ts: float
    latency_sec: float
    status_code: int
    method: str
    route: str


class ObservabilityStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._inflight = 0
        self._requests_total = 0
        self._errors_total = 0
        self._requests_by_route: Dict[str, int] = defaultdict(int)
        self._errors_by_route: Dict[str, int] = defaultdict(int)
        self._latency_buckets: Dict[str, int] = defaultdict(int)
        self._recent: Deque[RequestSample] = deque(maxlen=_MAX_RECENT_SAMPLES)

    def inc_inflight(self) -> None:
        with self._lock:
            self._inflight += 1

    def dec_inflight(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    def record(self, *, method: str, route: str, status_code: int, latency_sec: float) -> None:
        status = int(status_code)
        latency = max(0.0, float(latency_sec))
        route_key = f"{method.upper()} {route}"
        with self._lock:
            self._requests_total += 1
            self._requests_by_route[route_key] += 1
            if status >= 500:
                self._errors_total += 1
                self._errors_by_route[route_key] += 1
            self._latency_buckets[_bucket_key(latency)] += 1
            self._recent.append(
                RequestSample(
                    ts=time.time(),
                    latency_sec=latency,
                    status_code=status,
                    method=method.upper(),
                    route=route,
                )
            )

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            recent = list(self._recent)
            inflight = self._inflight
            requests_total = self._requests_total
            errors_total = self._errors_total
            requests_by_route = dict(self._requests_by_route)
            errors_by_route = dict(self._errors_by_route)
            latency_buckets = dict(self._latency_buckets)
            started_at = self._started_at

        latencies = [x.latency_sec for x in recent]
        uptime_sec = max(0.0, time.time() - started_at)
        error_rate = (errors_total / requests_total) if requests_total else 0.0
        slo_latency_target_sec = 1.0
        slo_error_rate_target = 0.01
        p95 = _percentile(latencies, 0.95) if latencies else 0.0

        return {
            "uptime_sec": round(uptime_sec, 3),
            "inflight_requests": inflight,
            "http_requests_total": requests_total,
            "http_5xx_total": errors_total,
            "http_error_rate": round(error_rate, 6),
            "http_latency_sec": {
                "p50": round(_percentile(latencies, 0.50), 4) if latencies else 0.0,
                "p95": round(p95, 4),
                "p99": round(_percentile(latencies, 0.99), 4) if latencies else 0.0,
                "sample_count": len(latencies),
                "histogram": latency_buckets,
            },
            "requests_by_route": requests_by_route,
            "errors_by_route": errors_by_route,
            "slo": {
                "latency_p95_target_sec": slo_latency_target_sec,
                "error_rate_target": slo_error_rate_target,
                "latency_p95_ok": p95 <= slo_latency_target_sec,
                "error_rate_ok": error_rate <= slo_error_rate_target,
            },
        }


OBSERVABILITY = ObservabilityStore()
