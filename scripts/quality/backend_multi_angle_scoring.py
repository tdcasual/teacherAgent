#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "backend_multi_angle_scoring.json"


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_kpi(actual: Any, target: Any, direction: str) -> float:
    actual_f = _as_float(actual, 0.0)
    target_f = _as_float(target, 0.0)
    if target_f <= 0:
        return 0.0
    if direction == "lower_better":
        return clamp(100.0 * target_f / max(actual_f, 1e-12), 0.0, 100.0)
    return clamp(100.0 * actual_f / target_f, 0.0, 100.0)


def _weighted_average(items: Iterable[tuple[float, float]]) -> float | None:
    total_weight = 0.0
    weighted_sum = 0.0
    for score, weight in items:
        if weight <= 0:
            continue
        total_weight += weight
        weighted_sum += score * weight
    if total_weight <= 0:
        return None
    return weighted_sum / total_weight


def compute_trend_score(trend: Dict[str, Any], trend_config: Dict[str, Any]) -> float:
    improvement = clamp(_as_float(trend.get("improvement"), 0.0), -1.0, 1.0)
    stability = clamp(_as_float(trend.get("stability"), 0.0), 0.0, 1.0)
    regressions = clamp(_as_float(trend.get("regression_events_norm"), 0.0), 0.0, 1.0)

    base = _as_float(trend_config.get("base"), 50.0)
    improvement_factor = _as_float(trend_config.get("improvement_factor"), 30.0)
    stability_factor = _as_float(trend_config.get("stability_factor"), 15.0)
    regression_factor = _as_float(trend_config.get("regression_factor"), 10.0)

    raw = base + improvement_factor * improvement - stability_factor * stability - regression_factor * regressions
    return clamp(raw, 0.0, 100.0)


def compute_state_score(
    module_weights: Dict[str, Any],
    kpis: list[Dict[str, Any]],
) -> tuple[float, Dict[str, float], list[str], float]:
    dimension_scores: Dict[str, float] = {}
    insufficient_dimensions: list[str] = []

    total_dimension_weight = 0.0
    available_dimension_weight = 0.0

    for dimension, configured_weight_raw in module_weights.items():
        configured_weight = _as_float(configured_weight_raw, 0.0)
        if configured_weight <= 0:
            continue
        total_dimension_weight += configured_weight

        dimension_kpis = [kpi for kpi in kpis if str(kpi.get("dimension") or "") == dimension]
        if not dimension_kpis:
            insufficient_dimensions.append(dimension)
            continue

        normalized: list[tuple[float, float]] = []
        for kpi in dimension_kpis:
            score = normalize_kpi(
                actual=kpi.get("actual"),
                target=kpi.get("target"),
                direction=str(kpi.get("direction") or "higher_better"),
            )
            normalized.append((score, _as_float(kpi.get("weight"), 1.0)))

        avg_score = _weighted_average(normalized)
        if avg_score is None:
            insufficient_dimensions.append(dimension)
            continue

        dimension_scores[dimension] = avg_score
        available_dimension_weight += configured_weight

    if available_dimension_weight <= 0:
        return 0.0, dimension_scores, insufficient_dimensions, 0.0

    weighted = _weighted_average(
        (dimension_scores[dimension], _as_float(module_weights.get(dimension), 0.0))
        for dimension in dimension_scores
    )
    if weighted is None:
        return 0.0, dimension_scores, insufficient_dimensions, 0.0

    completeness = available_dimension_weight / max(total_dimension_weight, 1e-12)
    return weighted, dimension_scores, insufficient_dimensions, completeness


def compute_module_score(module_name: str, module_payload: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    module_weights = (config.get("module_weights") or {}).get(module_name) or {}
    state_score, dimension_scores, insufficient_dimensions, data_completeness = compute_state_score(
        module_weights=module_weights,
        kpis=list(module_payload.get("kpis") or []),
    )

    trend_score = compute_trend_score(
        trend=dict(module_payload.get("trend") or {}),
        trend_config=dict(config.get("trend") or {}),
    )

    state_weight = _as_float(config.get("state_weight"), 0.7)
    trend_weight = _as_float(config.get("trend_weight"), 0.3)
    bonus = _as_float(module_payload.get("bonus"), 0.0)
    penalty = _as_float(module_payload.get("penalty"), 0.0)

    module_score = clamp(state_weight * state_score + trend_weight * trend_score + bonus - penalty, 0.0, 100.0)

    return {
        "module": module_name,
        "state_score": round(state_score, 4),
        "trend_score": round(trend_score, 4),
        "module_score": round(module_score, 4),
        "bonus": round(bonus, 4),
        "penalty": round(penalty, 4),
        "dimension_scores": {k: round(v, 4) for k, v in sorted(dimension_scores.items())},
        "insufficient_dimensions": sorted(insufficient_dimensions),
        "data_completeness": round(data_completeness, 4),
        "risk_weight": _as_float(module_payload.get("risk_weight"), _as_float((config.get("module_risk_weights") or {}).get(module_name), 0.0)),
    }


def compute_global_score(module_reports: list[Dict[str, Any]]) -> float:
    weighted_scores: list[tuple[float, float]] = []
    for report in module_reports:
        weight = _as_float(report.get("risk_weight"), 0.0)
        score = _as_float(report.get("module_score"), 0.0)
        if weight <= 0:
            continue
        weighted_scores.append((score, weight))
    weighted = _weighted_average(weighted_scores)
    if weighted is None:
        return 0.0
    return round(weighted, 4)


def build_report(config: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    module_payloads = dict(payload.get("modules") or {})
    known_modules = list((config.get("module_weights") or {}).keys())
    module_reports: list[Dict[str, Any]] = []

    for module_name in known_modules:
        module_reports.append(compute_module_score(module_name, dict(module_payloads.get(module_name) or {}), config))

    global_score = compute_global_score(module_reports)
    top_risks = [r["module"] for r in sorted(module_reports, key=lambda x: _as_float(x.get("module_score"), 0.0))[:3]]

    top_improvement_scores: list[tuple[str, float]] = []
    for module_name in known_modules:
        trend = dict((module_payloads.get(module_name) or {}).get("trend") or {})
        top_improvement_scores.append((module_name, _as_float(trend.get("improvement"), 0.0)))
    top_improvements = [name for name, _ in sorted(top_improvement_scores, key=lambda x: x[1], reverse=True)[:3]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "global_score": global_score,
        "module_scores": module_reports,
        "top_risks": top_risks,
        "top_improvements": top_improvements,
    }


def load_json(path: Path) -> Dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute backend multi-angle scoring report.")
    parser.add_argument("--input", required=True, help="Path to input JSON payload")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to scoring config JSON")
    parser.add_argument("--output", default="", help="Optional output report JSON path")
    args = parser.parse_args(argv)

    config = load_json(Path(args.config))
    payload = load_json(Path(args.input))
    report = build_report(config=config, payload=payload)

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
