from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Mapping, Tuple

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


def _prom_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _prom_number(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    rendered = format(float(value), ".6f").rstrip("0").rstrip(".")
    return rendered if rendered else "0"


def _prom_line(name: str, value: Any, labels: Mapping[str, str] | None = None) -> str:
    if labels:
        inner = ",".join(f'{key}="{_prom_escape(val)}"' for key, val in labels.items())
        return f"{name}{{{inner}}} {_prom_number(value)}"
    return f"{name} {_prom_number(value)}"


def _prom_family(help_text: str, type_name: str, name: str, samples: Iterable[str]) -> List[str]:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} {type_name}"]
    lines.extend(samples)
    return lines


def _prom_labeled_counts(name: str, values: Mapping[str, int], label: str) -> List[str]:
    return [
        _prom_line(name, int(count), {label: key})
        for key, count in sorted(values.items())
    ]


def _prom_histogram_buckets(latency_buckets: Mapping[str, int]) -> Tuple[List[str], int]:
    lines: List[str] = []
    cumulative = 0
    for bucket in _LATENCY_BUCKETS:
        cumulative += int(latency_buckets.get(f"le_{bucket:.2f}s", 0) or 0)
        lines.append(_prom_line("http_request_duration_seconds_bucket", cumulative, {"le": str(bucket)}))
    cumulative += int(latency_buckets.get("gt_5.00s", 0) or 0)
    lines.append(_prom_line("http_request_duration_seconds_bucket", cumulative, {"le": "+Inf"}))
    return lines, cumulative


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

    def prometheus_text(self) -> str:
        snap = self.snapshot()
        latency = snap.get("http_latency_sec") or {}
        slo = snap.get("slo") or {}
        histogram = latency.get("histogram") or {}
        bucket_lines, bucket_count = _prom_histogram_buckets(histogram)
        lines: List[str] = []
        lines.extend(
            _prom_family(
                "Total HTTP requests observed by this process (not aggregated across workers).",
                "counter",
                "http_requests_total",
                [_prom_line("http_requests_total", snap.get("http_requests_total", 0))],
            )
        )
        lines.extend(
            _prom_family(
                "Total HTTP 5xx responses observed by this process.",
                "counter",
                "http_5xx_total",
                [_prom_line("http_5xx_total", snap.get("http_5xx_total", 0))],
            )
        )
        lines.extend(
            _prom_family(
                "5xx / requests since this process started.",
                "gauge",
                "http_error_rate",
                [_prom_line("http_error_rate", snap.get("http_error_rate", 0.0))],
            )
        )
        lines.extend(
            _prom_family(
                "In-flight HTTP requests in this process.",
                "gauge",
                "http_inflight_requests",
                [_prom_line("http_inflight_requests", snap.get("inflight_requests", 0))],
            )
        )
        lines.extend(
            _prom_family(
                "Seconds since this process started recording HTTP samples.",
                "gauge",
                "process_uptime_seconds",
                [_prom_line("process_uptime_seconds", snap.get("uptime_sec", 0.0))],
            )
        )
        lines.extend(
            _prom_family(
                f"Request latency quantiles over the in-process recent window (max {_MAX_RECENT_SAMPLES} samples).",
                "summary",
                "http_latency_seconds",
                [
                    _prom_line("http_latency_seconds", latency.get("p50", 0.0), {"quantile": "0.5"}),
                    _prom_line("http_latency_seconds", latency.get("p95", 0.0), {"quantile": "0.95"}),
                    _prom_line("http_latency_seconds", latency.get("p99", 0.0), {"quantile": "0.99"}),
                    _prom_line("http_latency_seconds_count", latency.get("sample_count", 0)),
                ],
            )
        )
        lines.extend(
            _prom_family(
                "HTTP request duration buckets for this process (cumulative).",
                "histogram",
                "http_request_duration_seconds",
                bucket_lines + [_prom_line("http_request_duration_seconds_count", bucket_count)],
            )
        )
        lines.extend(
            _prom_family(
                "HTTP requests by method+route in this process.",
                "counter",
                "http_requests_by_route_total",
                _prom_labeled_counts(
                    "http_requests_by_route_total",
                    snap.get("requests_by_route") or {},
                    "route",
                ),
            )
        )
        lines.extend(
            _prom_family(
                "HTTP 5xx responses by method+route in this process.",
                "counter",
                "http_5xx_by_route_total",
                _prom_labeled_counts(
                    "http_5xx_by_route_total",
                    snap.get("errors_by_route") or {},
                    "route",
                ),
            )
        )
        lines.extend(
            _prom_family(
                f"1 if in-window p95 latency is <= {slo.get('latency_p95_target_sec', 1.0)}s.",
                "gauge",
                "slo_latency_p95_ok",
                [_prom_line("slo_latency_p95_ok", 1 if slo.get("latency_p95_ok") else 0)],
            )
        )
        lines.extend(
            _prom_family(
                f"1 if process-lifetime 5xx rate is <= {slo.get('error_rate_target', 0.01)}.",
                "gauge",
                "slo_error_rate_ok",
                [_prom_line("slo_error_rate_ok", 1 if slo.get("error_rate_ok") else 0)],
            )
        )
        return "\n".join(lines) + "\n"


OBSERVABILITY = ObservabilityStore()
