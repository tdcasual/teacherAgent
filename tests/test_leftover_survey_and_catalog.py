from __future__ import annotations

from pathlib import Path


def test_upload_llm_drops_exam_score_parser() -> None:
    text = Path("services/api/upload_llm_service.py").read_text(encoding="utf-8")
    assert "def llm_parse_exam_scores" not in text
    assert "upload.exam_scores_parse" not in text


def test_paths_module_has_no_survey_helpers() -> None:
    text = Path("services/api/paths.py").read_text(encoding="utf-8")
    assert "def survey_job_path" not in text
    assert "def survey_report_path" not in text
    assert "survey_review_queue_path" not in text


def test_config_and_runtime_drop_survey_job_state() -> None:
    config = Path("services/api/config.py").read_text(encoding="utf-8")
    runtime = Path("services/api/runtime/runtime_state.py").read_text(encoding="utf-8")
    assert "SURVEY_JOB_DIR" not in config
    assert "SURVEY_JOB_QUEUE" not in runtime


def test_env_examples_drop_survey_webhook_secret() -> None:
    example = Path(".env.example").read_text(encoding="utf-8")
    prod = Path(".env.production.min.example").read_text(encoding="utf-8")
    assert "SURVEY_WEBHOOK_SECRET" not in example
    assert "SURVEY_WEBHOOK_SECRET" not in prod
    assert "SURVEY_WEBHOOK_ALLOW_INSECURE" not in example


def test_compose_defaults_publish_to_loopback() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert '${PUBLISH_HOST:-127.0.0.1}:8000:8000' in text
    assert '${PUBLISH_HOST:-127.0.0.1}:3001:80' in text
    assert '${PUBLISH_HOST:-127.0.0.1}:3002:80' in text
    assert '"8000:8000"' not in text
    assert '"3001:80"' not in text
    assert '"3002:80"' not in text


def test_skills_and_lessons_routes_require_principal() -> None:
    text = Path("services/api/routes/misc_general_routes.py").read_text(encoding="utf-8")
    skills_block = text.split("def skills")[1].split("def ")[0]
    lessons_block = text.split("def lessons")[1].split("def ")[0]
    assert "require_principal()" in skills_block
    assert "extra_skill_ids_for_principal" in skills_block
    assert "require_principal()" in lessons_block


def test_teacher_fetch_skills_sends_bearer() -> None:
    text = Path("frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts").read_text(encoding="utf-8")
    assert "Authorization: `Bearer ${authToken}`" in text
    assert "${apiBase}/skills" in text


def test_teacher_fallback_catalog_is_assignment_core() -> None:
    text = Path("frontend/apps/teacher/src/features/chat/catalog.ts").read_text(encoding="utf-8")
    assert "teacher-assignment-ops" in text
    assert "homework-generator" in text
    assert "student-coach" in text
    assert "physics-lesson-capture" not in text
    assert "physics-student-focus" not in text
    assert "physics-core-examples" not in text


def test_create_app_does_not_boot_analysis_ops() -> None:
    text = Path("services/api/app.py").read_text(encoding="utf-8")
    assert "AnalysisOpsService" not in text
    assert "analysis_ops_service" not in text
    assert "from .analysis_" not in text
    assert "from services.api.analysis_" not in text
    assert "analysis_runtime" not in text


def test_student_app_lazy_loads_page_chunks() -> None:
    text = Path("frontend/apps/student/src/App.tsx").read_text(encoding="utf-8")
    assert "lazy(() => import('./features/home/StudentTodayHome'))" in text
    assert "lazy(() => import('./features/submit/StudentSubmitPanel'))" in text
    assert "lazy(() => import('./features/history/StudentAssignmentHistoryPage'))" in text
    assert "lazy(() => import('./features/chat/ChatPanel'))" in text
    assert "from './features/home/StudentTodayHome'" not in text
