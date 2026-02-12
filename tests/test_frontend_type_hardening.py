from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (_ROOT / rel_path).read_text(encoding="utf-8")


def test_eslint_enables_explicit_any_rule() -> None:
    source = _read("frontend/eslint.config.js")
    assert "@typescript-eslint/no-explicit-any" in source


def test_teacher_state_hooks_do_not_use_any_updater_casts() -> None:
    paths = (
        "frontend/apps/teacher/src/features/state/useTeacherWorkbenchState.ts",
        "frontend/apps/teacher/src/features/state/useTeacherSessionState.ts",
    )
    for rel_path in paths:
        source = _read(rel_path)
        assert "(value as any)" not in source, f"remove any-cast updater in {rel_path}"


def test_teacher_chat_api_avoids_any_in_error_and_session_merging() -> None:
    source = _read("frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts")
    assert "catch (err: any)" not in source
    assert "(err as any)?.message" not in source
    assert "setHistorySessions: (value: any[] | ((prev: any[]) => any[])) => void" not in source
    assert "prev.map((item: any)" not in source
    assert "seeded.map((item: any)" not in source
    assert "(data as any).lane_queue_position" not in source


def test_teacher_workbench_view_model_is_strongly_typed() -> None:
    view_model_source = _read(
        "frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts",
    )
    teacher_workbench_source = _read(
        "frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx",
    )
    assert "Record<string, any>" not in view_model_source
    assert "workbench: Record<string, any>" not in view_model_source
    assert "viewModel as any" not in teacher_workbench_source


def test_assignment_workflow_hook_avoids_any_hotspots() -> None:
    source = _read(
        "frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts",
    )
    assert "Promise<any>" not in source
    assert "Record<string, any>" not in source
    assert "value: any" not in source
    assert "catch (err: any)" not in source


def test_skills_tab_and_assignment_progress_section_avoid_any_hotspots() -> None:
    skills_source = _read(
        "frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx",
    )
    progress_source = _read(
        "frontend/apps/teacher/src/features/workbench/workflow/AssignmentProgressSection.tsx",
    )

    assert "useState<any>" not in skills_source
    assert "catch (e: any)" not in skills_source
    assert "(skill: any)" not in skills_source
    assert "const body: any" not in skills_source
    assert "(prompt: any)" not in skills_source
    assert "(ex: any)" not in skills_source

    assert "setProgressPanelCollapsed: any" not in progress_source
    assert "formatProgressSummary: any" not in progress_source
    assert "progressData: any" not in progress_source
    assert "fetchAssignmentProgress: any" not in progress_source
    assert "(s: any)" not in progress_source
    assert "as any" not in progress_source


def test_draft_mutations_and_exam_workflow_hooks_avoid_any_hotspots() -> None:
    draft_mutations_source = _read(
        "frontend/apps/teacher/src/features/workbench/hooks/useDraftMutations.ts",
    )
    exam_workflow_source = _read(
        "frontend/apps/teacher/src/features/workbench/hooks/useExamWorkflow.ts",
    )

    assert "Record<string, any>" not in draft_mutations_source
    assert "value: any" not in draft_mutations_source
    assert "(candidate: any)" not in draft_mutations_source

    assert "(candidate: any)" not in exam_workflow_source
    assert "catch (err: any)" not in exam_workflow_source


def test_assignment_and_exam_status_polling_hooks_avoid_any_hotspots() -> None:
    assignment_polling_source = _read(
        "frontend/apps/teacher/src/features/workbench/useAssignmentUploadStatusPolling.ts",
    )
    exam_polling_source = _read(
        "frontend/apps/teacher/src/features/workbench/useExamUploadStatusPolling.ts",
    )

    assert "data as any" not in assignment_polling_source
    assert "catch (err: any)" not in assignment_polling_source

    assert "data as any" not in exam_polling_source
    assert "catch (err: any)" not in exam_polling_source


def test_workbench_utils_and_routing_api_avoid_any_hotspots() -> None:
    workbench_utils_source = _read(
        "frontend/apps/teacher/src/features/workbench/workbenchUtils.ts",
    )
    routing_api_source = _read(
        "frontend/apps/teacher/src/features/routing/routingApi.ts",
    )

    assert "normalizeDifficulty = (value: any)" not in workbench_utils_source
    assert "difficultyLabel = (value: any)" not in workbench_utils_source
    assert "(data as any)?.detail" not in routing_api_source


def test_exam_candidate_analysis_avoids_any_hotspots() -> None:
    source = _read(
        "frontend/apps/teacher/src/features/workbench/workflow/examCandidateAnalysis.ts",
    )
    assert "candidate: any" not in source
    assert "examCandidateSummaries: any[]" not in source
    assert ".map((item: any)" not in source
    assert "map((x: any)" not in source
    assert ".filter((item: any)" not in source
    assert "examCandidateColumns: any[]" not in source
    assert "(candidate: any)" not in source


def test_teacher_app_avoids_any_hotspots() -> None:
    source = _read("frontend/apps/teacher/src/App.tsx")
    assert "JSON.parse(raw) as any" not in source
    assert "'--teacher-topbar-height' as any" not in source


def test_teacher_helpers_avoid_any_hotspots() -> None:
    formatters_source = _read(
        "frontend/apps/teacher/src/features/workbench/workbenchFormatters.ts",
    )
    composer_source = _read(
        "frontend/apps/teacher/src/features/chat/useTeacherComposerInteractions.ts",
    )
    catalog_source = _read("frontend/apps/teacher/src/features/chat/catalog.ts")
    view_state_source = _read(
        "frontend/apps/teacher/src/features/chat/viewState.ts",
    )

    assert "job as any" not in formatters_source
    assert "nativeEvent as any" not in composer_source
    assert "routing?: any" not in catalog_source
    assert "normalizeSessionViewStatePayload = (raw: any)" not in view_state_source


def test_student_runtime_files_avoid_any_hotspots() -> None:
    student_app_source = _read("frontend/apps/student/src/App.tsx")
    send_lock_source = _read("frontend/apps/student/src/features/chat/sendLock.ts")
    send_flow_source = _read(
        "frontend/apps/student/src/features/chat/useStudentSendFlow.ts",
    )
    student_view_state_source = _read(
        "frontend/apps/student/src/features/chat/viewState.ts",
    )

    assert "catch (err: any)" not in student_app_source
    assert "(err as any)?.message" not in student_app_source
    assert "nativeEvent as any" not in student_app_source

    assert "navigator as any" not in send_lock_source
    assert "async (lock: any)" not in send_lock_source

    assert "catch (err: any)" not in send_flow_source
    assert "normalizeSessionViewStatePayload = (raw: any)" not in student_view_state_source


def test_shared_markdown_and_app_types_avoid_any_hotspots() -> None:
    shared_markdown_source = _read("frontend/apps/shared/markdown.ts")
    teacher_types_source = _read("frontend/apps/teacher/src/appTypes.ts")
    student_types_source = _read("frontend/apps/student/src/appTypes.ts")

    assert "tree: any" not in shared_markdown_source
    assert "node: any" not in shared_markdown_source
    assert "parent: any" not in shared_markdown_source
    assert "nodes: any[]" not in shared_markdown_source

    assert "Record<string, any>" not in teacher_types_source
    assert "best?: any" not in teacher_types_source
    assert "[k: string]: any" not in student_types_source
