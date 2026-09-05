from __future__ import annotations

from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = (
    "services.api.analysis_metrics_service",
    "services.api.analysis_metrics_store",
    "services.api.analysis_target_resolution_service",
    "services.api.analysis_target_models",
    "services.api.analysis_ops_service",
    "services.api.analysis_policy_service",
    "services.api.analysis_lineage_service",
    "services.api.analysis_metadata_repository",
    "services.api.analysis_gate_ownership_service",
    "services.api.analysis_specialist_failure_service",
    "services.api.multimodal_orchestrator_service",
    "services.api.review_queue_service",
    "services.api.review_feedback_service",
)

_RUNTIME_SOURCES = (
    Path("services/api/app.py"),
    Path("services/api/chat_start_service.py"),
    Path("services/api/app_routes.py"),
    Path("services/api/wiring/chat_wiring.py"),
)


def _forbidden_import_needles(root: str) -> tuple[str, ...]:
    leaf = root.rsplit(".", 1)[-1]
    return (
        root,
        f"from .{leaf} import",
        f"from services.api.{leaf} import",
        f"from services.api import {leaf}",
        f"import {leaf}",
    )


def test_runtime_files_do_not_import_forbidden_analysis_modules() -> None:
    hits: list[str] = []
    for path in _RUNTIME_SOURCES:
        text = path.read_text(encoding="utf-8")
        for root in FORBIDDEN_IMPORT_ROOTS:
            for needle in _forbidden_import_needles(root):
                if needle in text:
                    hits.append(f"{path.as_posix()}: {needle}")
                    break
    assert hits == [], f"forbidden analysis/multimodal imports still present: {hits}"


def test_app_source_forbids_analysis_imports_and_runtime_metrics() -> None:
    text = Path("services/api/app.py").read_text(encoding="utf-8")
    assert "from .analysis_" not in text
    assert "from services.api.analysis_" not in text
    assert "analysis_runtime" not in text
    assert "AnalysisMetricsService" not in text
    assert "AnalysisMetricsStore" not in text


def test_chat_start_source_forbids_analysis_target_resolution() -> None:
    text = Path("services/api/chat_start_service.py").read_text(encoding="utf-8")
    assert "extract_report_id_from_text" not in text
    assert "analysis_target_resolution_service" not in text


def test_app_routes_source_forbids_multimodal_router() -> None:
    text = Path("services/api/app_routes.py").read_text(encoding="utf-8")
    assert "multimodal_enabled" not in text
    assert "multimodal_routes" not in text
    assert "build_multimodal_router" not in text
    assert "include_router(build_multimodal_router" not in text


def test_exam_and_survey_application_modules_are_absent() -> None:
    assert not Path("services/api/exam/application.py").exists()
    assert not Path("services/api/survey/application.py").exists()


def test_paths_has_no_resolve_analysis_dir() -> None:
    text = Path("services/api/paths.py").read_text(encoding="utf-8")
    assert "def resolve_analysis_dir" not in text
