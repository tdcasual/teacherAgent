from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_module():
    path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "quality"
        / "backend_multi_angle_scoring.py"
    )
    spec = importlib.util.spec_from_file_location("backend_multi_angle_scoring", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scoring_config_has_required_modules_and_weights() -> None:
    path = Path("config/backend_multi_angle_scoring.json")
    assert path.exists(), "missing backend multi-angle scoring config"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    modules = ((payload.get("module_weights") or {}).keys())
    assert {"routes", "services", "workers", "runtime", "wiring", "skills"}.issubset(set(modules))


def test_normalize_kpi_higher_and_lower_better() -> None:
    mod = _load_module()
    assert mod.normalize_kpi(actual=95, target=100, direction="higher_better") == pytest.approx(95.0)
    assert mod.normalize_kpi(actual=0.005, target=0.01, direction="lower_better") == pytest.approx(100.0)
    assert mod.normalize_kpi(actual=0.02, target=0.01, direction="lower_better") == pytest.approx(50.0)


def test_compute_trend_score_applies_formula_and_clamp() -> None:
    mod = _load_module()
    trend_cfg = {"base": 50, "improvement_factor": 30, "stability_factor": 15, "regression_factor": 10}

    strong = mod.compute_trend_score(
        trend={"improvement": 1.0, "stability": 0.0, "regression_events_norm": 0.0},
        trend_config=trend_cfg,
    )
    weak = mod.compute_trend_score(
        trend={"improvement": -1.0, "stability": 1.0, "regression_events_norm": 1.0},
        trend_config=trend_cfg,
    )
    assert strong == pytest.approx(80.0)
    assert weak == pytest.approx(0.0)


def test_compute_module_score_combines_state_and_trend_bonus_penalty() -> None:
    mod = _load_module()
    config = {
        "state_weight": 0.7,
        "trend_weight": 0.3,
        "trend": {"base": 50, "improvement_factor": 30, "stability_factor": 15, "regression_factor": 10},
        "module_weights": {
            "routes": {
                "correctness": 30,
                "reliability": 20,
                "maintainability": 0,
                "security": 0,
                "delivery": 0,
                "cost_performance": 0,
            }
        },
    }
    payload = {
        "kpis": [
            {
                "dimension": "correctness",
                "actual": 90,
                "target": 100,
                "direction": "higher_better",
            },
            {
                "dimension": "reliability",
                "actual": 1,
                "target": 2,
                "direction": "higher_better",
            },
        ],
        "trend": {"improvement": 0.5, "stability": 0.2, "regression_events_norm": 0.0},
        "bonus": 2,
        "penalty": 1,
    }

    out = mod.compute_module_score(module_name="routes", module_payload=payload, config=config)
    assert out["state_score"] == pytest.approx(74.0)
    assert out["trend_score"] == pytest.approx(62.0)
    assert out["module_score"] == pytest.approx(71.4)


def test_compute_module_score_marks_insufficient_data_without_forcing_zero() -> None:
    mod = _load_module()
    config = {
        "state_weight": 0.7,
        "trend_weight": 0.3,
        "trend": {"base": 50, "improvement_factor": 30, "stability_factor": 15, "regression_factor": 10},
        "module_weights": {
            "routes": {
                "correctness": 30,
                "reliability": 0,
                "maintainability": 0,
                "security": 70,
                "delivery": 0,
                "cost_performance": 0,
            }
        },
    }
    payload = {
        "kpis": [
            {
                "dimension": "correctness",
                "actual": 100,
                "target": 100,
                "direction": "higher_better",
            }
        ],
        "trend": {"improvement": 0.0, "stability": 0.0, "regression_events_norm": 0.0},
    }

    out = mod.compute_module_score(module_name="routes", module_payload=payload, config=config)
    assert out["state_score"] == pytest.approx(100.0)
    assert out["insufficient_dimensions"] == ["security"]
    assert out["data_completeness"] == pytest.approx(0.3)


def test_build_report_outputs_global_and_module_scores() -> None:
    mod = _load_module()
    config = {
        "state_weight": 0.7,
        "trend_weight": 0.3,
        "trend": {"base": 50, "improvement_factor": 30, "stability_factor": 15, "regression_factor": 10},
        "module_weights": {
            "routes": {
                "correctness": 100,
                "reliability": 0,
                "maintainability": 0,
                "security": 0,
                "delivery": 0,
                "cost_performance": 0,
            },
            "services": {
                "correctness": 100,
                "reliability": 0,
                "maintainability": 0,
                "security": 0,
                "delivery": 0,
                "cost_performance": 0,
            },
        },
        "module_risk_weights": {"routes": 0.4, "services": 0.6},
    }
    payload = {
        "modules": {
            "routes": {
                "kpis": [{"dimension": "correctness", "actual": 100, "target": 100, "direction": "higher_better"}],
                "trend": {"improvement": 1.0, "stability": 0.0, "regression_events_norm": 0.0},
            },
            "services": {
                "kpis": [{"dimension": "correctness", "actual": 50, "target": 100, "direction": "higher_better"}],
                "trend": {"improvement": 0.0, "stability": 0.0, "regression_events_norm": 0.0},
            },
        }
    }

    report = mod.build_report(config=config, payload=payload)
    modules = {item["module"]: item for item in report["module_scores"]}
    assert modules["routes"]["module_score"] == pytest.approx(94.0)
    assert modules["services"]["module_score"] == pytest.approx(50.0)
    assert report["global_score"] == pytest.approx(67.6)
    assert report["top_risks"][0] == "services"
    assert report["top_improvements"][0] == "routes"


def test_cli_writes_report_json(tmp_path: Path) -> None:
    mod = _load_module()
    script_path = Path(mod.__file__).resolve()

    config_path = tmp_path / "config.json"
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "report.json"

    config_path.write_text(
        json.dumps(
            {
                "state_weight": 0.7,
                "trend_weight": 0.3,
                "trend": {
                    "base": 50,
                    "improvement_factor": 30,
                    "stability_factor": 15,
                    "regression_factor": 10,
                },
                "module_weights": {
                    "routes": {
                        "correctness": 100,
                        "reliability": 0,
                        "maintainability": 0,
                        "security": 0,
                        "delivery": 0,
                        "cost_performance": 0,
                    }
                },
                "module_risk_weights": {"routes": 1.0},
            }
        ),
        encoding="utf-8",
    )
    input_path.write_text(
        json.dumps(
            {
                "modules": {
                    "routes": {
                        "kpis": [
                            {
                                "dimension": "correctness",
                                "actual": 90,
                                "target": 100,
                                "direction": "higher_better",
                            }
                        ],
                        "trend": {"improvement": 0.2, "stability": 0.1, "regression_events_norm": 0.0},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(input_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert output_path.exists()

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["global_score"] == pytest.approx(79.35)
